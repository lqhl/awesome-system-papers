# Barre: Empowering Simplified and Versatile Programmable Congestion Control in High-Speed AI Clusters

**作者**：Yajuan Peng, Haoran Wei, Xiaolong Zhong, Junkai Huang, Haohan Xu, Zicheng Wang, Yang Bai, Zhuo Jiang, Jianxi Ye, Xiaoliang Wang, Xiaoming Fu (Fudan University), Huichen Dai (ByteDance)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/peng-yajuan
**源文件**：[[atc2025-peng-yajuan.pdf]]

---

## 一、背景

随着大规模 LLM 训练的兴起，数据中心网络已进入 400 Gbps 时代（NIC 端口带宽），网络基础设施需要互连数千乃至上万个 GPU。RoCEv2（RDMA over Converged Ethernet v2）是当前 AI 集群中节点间通信的主流传输协议，而 DCQCN 是 RoCEv2 网络中事实上的拥塞控制算法。然而 DCQCN 设计于 2014 年前后，其参数调优困难，在 400 Gbps 高带宽、动态流量模式下表现不佳——宽松配置会导致 PFC pause 增加 2-3 倍，激进调优则牺牲吞吐。

尽管学术界已提出多种先进 CC 算法（如 HPCC、Swift、PowerTCP），但它们在生产环境中的部署受限于：(1) 依赖特殊硬件功能（如 INT 需要交换机和 NIC 全面支持）；(2) 计算开销大（如 Swift 需要平方根计算）；(3) 与商用硬件不兼容。因此，现代 AI 数据中心仍普遍使用十年前的 DCQCN。

---

## 二、要解决的问题

1. **DCQCN 在高速网络中失效**：DCQCN 的拥塞响应迟缓（控制环路过长），依赖 PFC 做背压，在 400 Gbps 网络中参数调优极为困难，严格/宽松配置之间难以兼顾吞吐和延迟。

2. **先进 CC 算法无法落地**：HPCC 要求全链路 INT 支持（商用设备普遍不满足）；Swift 对 RTT baseline 敏感，多层拓扑中不同路径长度导致不公平带宽分配（如 Hop=1 vs Hop=5 的实验，Figure 1）；所有这些算法的计算复杂度超出商用 NIC 嵌入式 CPU 的处理能力。

3. **AI 训练流量模式的多样性**：LLM 训练中 AllReduce（小规模 incast、要求快速收敛）、AlltoAll（大规模全网状、要求保守速率调节）、SendRecv（严格延迟要求）等通信模式交替出现，单一参数配置无法适应所有场景。AlltoAll 在 Meta 的统计中占集合通信总流量的约 60%，其 N:N 全网状模式极易引发瞬态拥塞。

4. **Rate-based 控制的固有缺陷**：RNIC 仅支持 per-flow 粒度的速率控制，无法像 window-based 控制那样显式限制 inflight bytes，拥塞发生时发送端在收到拥塞信号前持续注入数据包。

---

## 三、洞察与设计

**关键洞察**：现代可编程 SmartNIC（如 BlueField-3）提供的硬件加速 CC 事件接口（TX Event、CNP Event、RTT Event）可以替代传统的 ACK Event 和 Timer Event，实现更低开销、更快响应的拥塞控制。尤其是 BF-3 的 CNP 响应间隔已达 1μs 级别，使得「小幅度、高频率」的 per-CNP 速率调整成为可能——这与 DCQCN 依赖固定时间间隔内累计 CNP 数量的方式截然不同。

基于此洞察，Barre 设计了一个 AIMD 框架下的 rate-based CC 方案，核心思路是：

- **自适应调整间隔**：不使用固定 Timer，而是基于实时 RTT 动态调整速率增加间隔（无拥塞时 RTT 短 → 增频快；拥塞时 RTT 长 → 增频慢）。每收到一个 CNP 就立即做小幅度的乘性下降（R = R × β，0.95 < β < 0.99），替代 DCQCN 的按间隔批量调整。

- **三个功能组件**（轻量、解耦、可独立使用）：
  1. **Fast Increase**：mice flow（连接数少、无拥塞）时用大步长 A 快速收敛到满带宽；一旦收到 CNP 即重置为小步长 α，避免 elephant flow 下的网络振荡。判断条件是连续 K 次 RTT 内增速均未收到 CNP。
  2. **Dual-lock**：将 DCQCN 中 ByteCounter "OR" Timer 的速率增加触发条件改为 "AND"——高速流的增速频率受 Timer（RTT）约束，低速流受 ByteCounter 约束，解决严重拥塞下延迟 CNP 反馈导致的过度注入和公平性问题。
  3. **Inflight Monitor**：利用 TX Event 提供的累计发送字节数，估算 inflight bytes 上限 γ = R × RTT，超过阈值则立即降速至 1/4，作为极端拥塞下的防御机制，弥补 rate-based 控制无法显式限制 inflight bytes 的缺陷。

---

## 四、实现细节

- **硬件平台**：基于 NVIDIA BlueField-3 SuperNIC 的 PCC（Programmable Congestion Control）功能实现。CC 算法编译为二进制文件，烧录至 NIC 固件，运行在 NIC 内嵌的 RISC-V 核上，全程绕过 PCIe 通道，无需 host CPU 参与。

- **事件驱动架构**：Barre 仅使用三种事件——TX Event（包含累计发送字节和时间戳）、CNP Event、RTT Event，相比 ACK Event 和 Timer Event 开销更低。BF-3 的 4 个 RISC-V 核可处理 1000 万事件/秒。

- **RTT Probe 改进**：
  - 在 RTT probe 包中增加 sequence header，避免不同批次 probe 包的 mismatch（128 GPU AlltoAll 测试中 RTT probe 丢包率高达 8.9%）。
  - 每个 RTT_Rsp 包同时携带 RTT_Req 的发送时间和 RTT_Rsp 的接收时间，发送端直接计算时间差得到实时 RTT。

- **Per-flow 增加因子**：αk = RTTk · α / C，其中 C 为常数（1-2μs），长路径流获得更大的增加因子，补偿因 RTT 长而导致的增速频率下降，改善公平性。

- **部署方式**：对应用层完全透明，不修改 RoCEv2 协议。算法参数：β 在 0.95-0.99 之间，Fast Increase 阈值 K，Dual-lock ByteCounter 阈值 8KB。

---

## 五、实验结果

**实验平台**：256 GPU 集群，每 GPU 配备 BF-3 400 Gbps NIC，三层 CLOS 拓扑，ToR 使用 AOC 将 800G 下行拆分为两个 400G 端口。

| 实验 | 指标 | Barre vs DCQCN | Barre vs IB |
|------|------|----------------|-------------|
| NCCL AlltoAll (256 GPU) | 延迟 | 平均降低 55.89% | 接近持平 |
| NCCL AlltoAll (256 GPU) | 带宽利用率 | 提高 15% | 接近持平 |
| NCCL AlltoAll (256 GPU) | PFC 触发 | 零 PFC | - |
| 端到端训练任务 | 吞吐 | 平均提高 9.6% | - |
| AlltoAll 通信延迟 | 延迟 | 最高降低 50% | - |

**组件逐步启用效果**：

| 组件 | 效果 |
|------|------|
| Fast Increase | mice flow (QP=4) 吞吐提升 8.5%；elephant flow (QP=1000) 队列长度降低 48% |
| + Dual-lock | 交换机平均队列长度降低 79.9%（最大 90.25%，QP=4000） |
| + Inflight Monitor | NCCL AlltoAll 吞吐平均提升 16.45%（最大 21.79%） |

**RTT-based Enhancement**（128 GPU）：延迟平均降低 5.71%，吞吐提升 7.13%。

**Barre 思想优化 DCQCN**：仅调整 DCQCN 的 5 个参数（CNP 间隔、减速因子、增速幅度等），在 1024 GPU AllReduce 测试中吞吐平均提升 19.54%，公平性显著改善。

**生产部署**：超过 10,000 GPU、400G BF-3 NIC，跨四层交换机（S3），运行超过一年，零 PFC 触发，持续稳定。

---

## 六、批判性分析

1. **基线选择不充分**：论文仅与 DCQCN 和 InfiniBand 做定量对比，对 HPCC、Swift、PowerTCP 等仅做「定性分析」（Appendix A.1），理由是它们无法在真实系统中部署。这虽有道理，但也回避了在模拟环境中的公平对比。对于声称「simple yet highly effective」的系统，应展示在相同模拟条件下与这些算法的性能差距。

2. **实验规模与生产规模的差距**：核心定量实验在 256 GPU 上完成，而声称已部署 10,000+ GPU。论文未提供万卡规模下的定量性能数据（仅有 Figure 11 的交换机流量日志截图），10K GPU 场景下的拥塞模式可能与 256 GPU 显著不同。

3. **训练吞吐提升的归因不清**：声称端到端训练任务吞吐平均提升 9.6%，但未详细说明工作负载类型、模型大小、并行策略等。不同训练配置下通信占比差异巨大，9.6% 的「平均」可能掩盖了很大的方差。

4. **Inflight Monitor 的粗粒度**：检测到 inflight 超限后直接降速至 1/4，这是一个相当激进的动作。论文未讨论这种急剧降速对尾延迟和吞吐抖动的影响，也未解释 1/4 这个比例的选择依据。

5. **RTT probe 丢包问题**：论文承认 128 GPU 测试中 RTT probe 丢包率高达 8.9%，虽然提出了 sequence header 的修复方案，但未报告修复后的丢包率是否降至零。如果仍有丢包，Barre 依赖 RTT 的核心机制就存在可靠性风险。

6. **对 MoE 工作负载缺乏针对性评估**：论文多次强调 MoE 架构的 AlltoAll 流量是关键挑战，但评估主要使用 NCCL AlltoAll benchmark 而非真实 MoE 训练。MoE 中的 AlltoAll 具有动态 token 路由导致的负载不均衡，与均匀 AlltoAll 差异显著。

---

## 七、AI Infra / MLSys 视角

1. **CC 算法与 AI 训练通信模式的协同设计**：Barre 针对 AI 训练中 mice flow（AllReduce/SendRecv）和 elephant flow（AlltoAll）交替出现的特点，用 Fast Increase 实现自适应切换。这个思路值得扩展——未来可以将 collective communication library（如 NCCL）的通信模式信息直接传递给 CC 层，实现 application-aware 的拥塞控制。

2. **可编程 NIC 上的 CC 算法空间**：Barre 展示了 BF-3 PCC 平台的潜力，但仅利用了 TX/CNP/RTT 三种事件。随着 NIC 可编程性的增强（如 BF-4），可以探索更丰富的状态信息（如 per-QP inflight bytes 的精确追踪）和更复杂的决策逻辑（如轻量级 RL agent）。

3. **Barre 优化 DCQCN 的实用价值**：Section 6.3 展示仅调参即可在 1024 GPU AllReduce 上提升 19.54% 吞吐——这对没有 BF-3 PCC 能力的集群也有直接参考价值。可作为现有 DCQCN 集群的 low-hanging fruit 优化。

4. **值得跟进的方向**：
   - **Inference 场景的 CC 优化**：论文提到推理任务通常百 GPU 规模、AlltoAll 消息更小（<1GB），但未专门评估。推理的延迟敏感性和 prefill/decode 交替模式值得专门研究。
   - **跨域拥塞控制**：论文聚焦单集群内部，但随着集群规模扩展到跨数据中心训练（如 DeepSeek-V3），跨域 CC 的挑战更大。
   - **与 NVLink/NVSwitch 的协同**：论文禁用 NVLink 测试 RDMA 路径，但实际训练中 NVLink 和 RDMA 流量共存，两者的交互对 CC 策略的影响值得研究。

---

## 八、总结

Barre 是一个面向 400 Gbps AI 集群的实用拥塞控制方案，通过充分利用 BlueField-3 SuperNIC 的可编程 CC 能力（TX/CNP/RTT 事件驱动），实现了基于 AIMD 的自适应速率控制。三个核心组件（Fast Increase、Dual-lock、Inflight Monitor）轻量解耦，分别解决快速收敛、公平性和极端拥塞下的 inflight 控制问题。在 ByteDance 生产环境中部署超过一年（10K+ GPU），性能接近 InfiniBand、显著优于 DCQCN，且设计思想可直接优化 DCQCN 参数。主要局限在于强依赖 BF-3 PCC 平台（可移植性待验证）、万卡规模缺乏定量数据、以及未充分评估真实 MoE 训练场景。
