# Disentangling the Dual Role of NIC Receive Rings

**作者**：Boris Pismenny (EPFL & NVIDIA), Adam Morrison (Tel Aviv University), Dan Tsafrir (Technion – Israel Institute of Technology)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/pismenny
**源文件**：[osdi25-pismenny.pdf](../../papers/osdi-2025/osdi25-pismenny.pdf)

---

## 一、背景

随着以太网速率增长到数百 Gbps，高性能网络应用依赖 Direct Data I/O (DDIO) 技术让 NIC 直接在 LLC（Last-Level Cache）中进行 DMA 读写，避免访问主内存，从而实现高吞吐和低延迟的数据包处理。

DDIO 的有效性取决于 I/O working set（NIC 与 CPU 交换数据包所涉及的内存区域）的大小。当前 NIC-CPU 接口使用 per-core 的 Rx ring（接收环），每个 ring 默认有 ≥1Ki 个条目，每个条目指向一个 1500B 的缓冲区。在多核并行处理场景下，所有 Rx ring 的缓冲区总量（N × R × 1500B）很容易超过 LLC 容量，导致 DDIO 失效、内存带宽成为瓶颈，严重影响吞吐和延迟（"leaky DMA" 问题）。

---

## 二、要解决的问题

1. **I/O working set 过大**：per-core Rx ring 需要预填充大量空缓冲区以吸收突发流量，16 核 × 1Ki 条目 × 1500B = 24 MiB，远超典型 22 MiB LLC 容量，导致新到数据包驱逐未处理的数据包，CPU 被迫从主内存访问数据。

2. **缩小 ring 不可行**：减小单个 Rx ring 的大小会使其无法吸收数据包突发（burst），造成丢包和 TCP 等协议性能下降。

3. **shRing 的负载不均衡问题**：前作 shRing 通过多核共享一个大 Rx ring 来缩小 I/O working set，但共享 ring 需要锁和原子操作进行同步，增加了每包处理开销。更关键的是，当负载不均衡时（某些核过载），过载核会垄断共享 ring 的条目，阻塞其他核接收数据包，导致丢包。shRing 不得不在检测到不均衡时回退到 per-core ring，此时又回到 I/O working set 过大的问题。

4. **负载不均衡普遍存在**：论文分析 CAIDA 真实流量 trace 表明，RSS 分配到各核的数据包速率差异持续在 3.25×–4.33× 之间，负载不均衡在实际工作负载中非常常见。

---

## 三、洞察与设计

**关键洞察**：传统 Rx ring 不必要地将两个正交的 producer-consumer 结构耦合在一起——(1) 内存分配（CPU 生产空缓冲区，NIC 消费）和 (2) 数据包接收（NIC 生产已填充的数据包，CPU 消费）。正是这种耦合导致了"要吸收突发就必须分配大量缓冲区"的困境，也使得跨核共享缓冲区必须同时共享接收能力。

基于这一洞察，论文提出 **rxBisect**，将传统 Rx ring 拆分为两种独立的 ring：

- **Allocation ring (Ax)**：CPU 向其中填充空缓冲区供 NIC 消费，可以很小（如 128 条目），因为缓冲区可以跨核共享。
- **Bisected reception ring (Bx)**：NIC 向其中写入接收到的数据包通知，可以很大（如 1Ki 条目）以吸收突发，但 Bx 条目本身不持有缓冲区，因此不增加 I/O working set。

核心机制：每个 Bx ring 可以关联多个核的 Ax ring。当数据包到达时，NIC 通过 RSS 选择目标 Bx ring，然后从任意关联的、有可用缓冲区的 Ax ring 中消费一个缓冲区来存储数据包。这实现了**跨核缓冲区共享而无需软件同步**——共享由 NIC 硬件完成。当某核的 Ax ring 耗尽时，NIC 自动从其他核的 Ax ring 借用缓冲区，避免了 shRing 中过载核阻塞其他核的问题。

---

## 四、实现细节

**NIC 侧**：
- 数据包到达时，NIC 先用 RSS 确定目标 Bx ring，再选择一个有空缓冲区的 Ax ring（优先使用关联的本核 Ax ring，若为空则选随机非空 Ax ring）
- NIC 从 Ax ring 的 head 描述符 DMA 读取缓冲区地址，将数据包 DMA 写入该缓冲区，再向 Bx ring 的 head 描述符 DMA 写入通知（包含缓冲区指针、来源 Ax ring 及条目索引）
- 关键路径上的依赖 DMA 数量与 privRing、shRing 相同

**软件侧**：
- 各核独立处理自己的 Bx ring，使用 sense-reverse 机制无锁地检测新条目
- 处理 Bx 条目时：若包含数据包则取出处理；若缓冲区来自本核 Ax ring 则分配新空缓冲区补充，通过 doorbell 通知 NIC
- 跨核缓冲区归还依赖 DPDK/Linux 的两级内存分配器（per-core cache + shared pool），同步开销极小（<0.2% CPU cycles）

**原型实现**：
- 基于软件 NIC emulator 实现，emulator 运行在独立核上，通过虚拟 Rx ring 模拟 rxBisect 的 Ax/Bx ring 行为
- Emulator 忠实模拟 DDIO 效果：将 packet buffer 和 worker core 放在与物理 NIC 相同的 NUMA 节点上
- 仿真保守估计性能：吞吐下降最多 12%，延迟增加最多 94%

---

## 五、实验结果

**实验平台**：Dell PowerEdge R640 服务器 × 2，Xeon Silver 4216 (16 核, 22 MiB LLC)，128 GiB DDR4，2 × 100 Gbps NVIDIA ConnectX-5 NIC，DPDK。

**网络功能 (NAT/LB) 在均衡负载下**（16 核，200 Gbps，1500B 数据包）：

| 指标 | privRing | shRing | rxBisect |
|------|----------|--------|----------|
| 吞吐 (Gbps) | ~160 (NAT) / ~162 (LB) | ~195 | ~200 (line rate) |
| 延迟 (µs) | ~1200+ | ~67–69 | ~100–119 |

rxBisect 相比 privRing 吞吐提升最高 37%（MICA），延迟降低最高 11×。

**MICA Key-Value Store**（8 核，128B key + 1024B value，95% PUT）：

| 负载 | privRing | shRing | rxBisect |
|------|----------|--------|----------|
| Uniform | baseline | +29% | +34% |
| Skewed (Zipf 0.99) | baseline | +6% | +14% |

**不均衡负载场景**：
- 处理变异性实验：目标核增加内存访问次数，shRing 吞吐下降最高 60%，rxBisect 保持 line rate
- 流量变异性实验：目标核流量占比增大，shRing 吞吐下降最高 49%，rxBisect 保持稳定
- CAIDA 真实 trace + PageRank co-location：rxBisect 比 dynamic shRing 吞吐高 16%–20%

**Ring size 敏感性**：
- Ax ring 128 条目即可匹配 privRing 1Ki 条目的 no-drop 吞吐（4 核共享缓冲区）
- Bx ring 增大不影响 I/O working set，吞吐保持 line rate

---

## 六、批判性分析

1. **仿真而非真实硬件**：这是论文最大的局限。rxBisect 需要修改 NIC 硬件接口，但原型完全基于软件仿真。仿真额外占用一个 CPU 核，引入了不可忽视的开销（吞吐 -12%，延迟 +94%）。论文声称仿真"保守低估"了性能，但这一论证建立在"硬件实现不会引入新瓶颈"的假设之上。实际 NIC 硬件中跨 Ax ring 选择缓冲区的调度逻辑、多 ring 关联的元数据管理等可能引入未被仿真覆盖的开销。

2. **比较方法论的不对称性**：rxBisect 运行在仿真模式下，而 privRing 和 shRing 运行在真实硬件上。论文在 rxBisect 输时展示 emulated 对比线，在赢时只展示 non-emulated baseline，这种选择性展示可能放大了 rxBisect 的优势。

3. **工作负载覆盖有限**：主要评估 NAT、LB 两个简单 NF 和 MICA KV-store。这些都是 per-packet 处理相对简单的应用。对于更复杂的应用（如深度包检测、加密/解密），计算密集度更高时 I/O working set 问题可能不那么突出，rxBisect 的收益可能降低。

4. **仅覆盖 1500B 大包**：论文明确聚焦大包场景以 stress memory subsystem，但对 64B 小包场景（更考验 per-packet 处理效率）几乎没有深入评估。小包场景下 I/O working set 本身较小，rxBisect 的额外复杂性是否值得缺乏论证。

5. **NIC 厂商采纳前景不明**：rxBisect 要求改变 NIC 硬件接口标准（descriptor format、ring 语义等），这是一个生态级别的变更。论文引用了 Mellanox RMP 作为部分支持，但明确指出 RMP 不足以实现 rxBisect。缺乏对硬件实现复杂度和迁移路径的讨论。

---

## 七、AI Infra / MLSys 视角

1. **GPU 通信与 RDMA 场景的借鉴**：分布式训练和推理大量使用 RDMA/RoCE 进行 GPU 间通信，同样面临 NIC 缓冲区管理和 LLC 污染问题。rxBisect 的分配/接收解耦思路可以启发 RDMA shared receive queue (SRQ) 的改进设计，特别是在 AllReduce、Pipeline Parallelism 等通信模式中不同 GPU 流量不均衡的场景。

2. **KV Cache 传输优化**：LLM 推理中 KV cache 的跨节点传输（如 prefill-decode 分离架构中的 KV cache migration）涉及大量网络 I/O。如果 NIC 接收缓冲区管理更高效，可以减少 CPU 侧的 cache 污染，让更多 LLC 容量留给模型推理的热数据。

3. **可跟进的研究方向**：
   - 将 rxBisect 的解耦思路应用到 GPU Direct RDMA (GDR) 场景，研究 GPU memory 与 NIC ring 的交互优化
   - 在 SmartNIC/DPU 上实现 rxBisect 逻辑，无需修改商用 NIC 硬件
   - 研究 AI 训练集群中 ECMP 导致的流量不均衡对 NIC 缓冲区管理的影响

---

## 八、总结

rxBisect 提出了一种新的 NIC-CPU 接收接口设计，通过将传统 Rx ring 拆分为独立的 Allocation ring 和 Bisected reception ring，解耦了缓冲区分配与数据包接收两个正交功能。这使得系统可以用少量缓冲区（小 Ax ring）维持小 I/O working set，同时用大 Bx ring 吸收突发流量，并通过 NIC 硬件实现无锁的跨核缓冲区共享。在仿真评估中，rxBisect 相比 privRing 和 shRing 分别提升吞吐最高 37% 和 20%，特别在负载不均衡场景下优势显著。主要局限在于需要 NIC 硬件支持且目前仅有软件仿真验证，距离实际部署仍有距离。
