# Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload

**作者**：Xun Sun, Mingxing Zhang, Yingdi Shan, Kang Chen, Jinlei Jiang（清华大学）；Yongwei Wu（清华大学，泉城实验室）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会）
**链接**：https://www.usenix.org/conference/osdi25/presentation/sun
**源文件**：[osdi25-sun.pdf](../../papers/osdi-2025/osdi25-sun.pdf)

---

## 一、背景

随着数据密集型应用的快速增长（社交网络、电商、云存储等），对高密度、低功耗存储系统的需求日益旺盛。基于 DPU（Data Processing Unit）的 JBOF（Just a Bunch of Flash）系统因此受到学术界和工业界的广泛关注。

JBOF 系统将多块 NVMe SSD 与一两颗 DPU 集成于 1U/2U 机箱中。DPU 是专用 ASIC，集成了网络、数据加速与存储处理功能，功耗仅为传统 Xeon CPU 的 1/4 左右（75–150W vs. 300–500W）。随着 SSD 数量增加，每瓦吞吐量理论上可线性提升，使 JBOF 成为极具吸引力的能效优化方向。

LEED 是该架构上最具代表性的 KV store，针对 SmartNIC JBOF 平台设计，采用日志结构 SSD 存储和小型哈希内存索引，在单 DPU 配 4 块 SSD 时可接近饱和 SSD I/O。然而，当 SSD 数量进一步增加时，LEED 的吞吐量不再扩展。

NVMe-oF（NVMe over Fabrics）Target Offload 是近年 DPU 引入的一项硬件优化：将 NVMe 命令直接由 HCA（Host Channel Adapter）硬件通过 PCIe P2P 通信处理，完全绕过 DPU 的 ARM 核，使 target 侧 CPU 使用率降为零。

---

## 二、要解决的问题

**核心问题：DPU CPU 是 JBOF KV store 扩展的瓶颈。**

LEED 的实验揭示：

- 每增加一块 SSD，需要分配一个专用 CPU 核处理 SSD I/O；4 块 SSD 时 CPU 使用率达 400%，吞吐量随即饱和
- 网络 I/O 极度欠利用：LEED 最多仅利用 ConnectX-6 HCA 最大 IOPS 的不到 1%（600K IOPS vs. 200M IOPS 上限）
- SSD I/O 与网络 I/O 之间存在三个数量级的性能差距，这一"剪刀差"是 offload 的根本机遇

即便将读路径全部 offload，写密集型负载仍会因内存并发控制和随机 SSD 写操作而拖垮 DPU CPU。

此外，在 disaggregated 架构下，将 I/O 操作 offload 到客户端后，DRAM 缓存与 SSD 数据的一致性无法通过硬件 cache coherence（如 MESI 协议）自动维护，需要显式的 cache invalidation 机制，而朴素的"写缓存优先"或"写 SSD 优先"协议均无法保证线性一致性（linearizability）。

---

## 三、核心设计

Scalio 的核心思路是：**将尽可能多的 I/O 操作从 DPU CPU offload 到网络侧（HCA 硬件或客户端 RDMA 操作），同时通过两层存储架构和显式一致性协议保证正确性**。

### 3.1 两层存储架构

- **上层**：DPU DRAM 中的 RDMA 可访问哈希表，充当热点数据的内联缓存（inline cache）
- **下层**：SSD 上的日志结构数据（沿用 LEED 设计）

哈希表以 block 为粒度组织，每个 block 包含多个 slot，内联存储 key-value 对（针对小 KV 优化）。客户端通过单侧 RDMA read 直接读取哈希 block，无需经过 DPU CPU。

### 3.2 读路径（完全 CPU 旁路）

1. 客户端 RDMA read 哈希 block → 线性搜索目标 key
2. **Cache hit**：直接返回 value
3. **Cache miss**：客户端通过 RDMA CAS 锁定 victim slot（基于 LRU last_ts）→ 执行 NVMe-oF Target Offload 从 SSD 直接读取数据 → RDMA write 填充缓存并释放锁

整个读路径（包括 SSD 访问）完全绕过 DPU CPU。

### 3.3 写路径（批量提交）

1. 客户端通过 RDMA send 将写请求追加到 DPU 环形缓冲区
2. DPU CPU 批量轮询环形缓冲区，合并写操作批量刷入 SSD（group commit），减少 SSD I/O 次数（2 次→约 1 次）
3. DPU 更新内存中的 next_offset，通知各客户端
4. 客户端收到通知后，通过 RDMA write 使缓存中过期项失效

写路径仍需 DPU CPU 参与批处理，但显著降低了 CPU 负载。

### 3.4 缓存一致性协议

Scalio 为每个 slot 引入两个标志位（occupied 和 complete），定义四种状态：

| 状态 | occupied | complete | 含义 |
|------|----------|----------|------|
| A | 0 | 1 | 空闲，可复用 |
| B | 1 | 0 | 正在填充中 |
| C | 1 | 1 | 有效完整 |
| D | 0 | 0 | 填充中被失效 |

- 读缓存失效时使用 RDMA CAS 保证原子性，并通过 **double-read** 检测 key 碰撞
- 写操作完成后，客户端扫描哈希 block，将同 key 的 slot 由 C/B 转为 A/D
- 支持 lease 机制处理客户端崩溃场景（timeout_timestamp 超时后可被他人强制释放）

论文给出了线性一致性的形式化证明，定义了读写操作的线性化点，并证明所有操作都在各自的 invoke/return 范围内被线性化。

---

## 四、实现细节

- **软件栈**：Linux 5.15.0（原生 NVMe-oF target 支持），MLNX_OFED 驱动，SPDK 用户态存储库；为公平对比，Scalio 使用与 LEED 相同的 SPDK 栈和 SSD 数据结构
- **NVMe-oF Target Offload**：通过 `nvmet` 内核模块配置，启用 `attr_offload` 参数
- **哈希 block 大小**：每 block 最多 1 KB，最多容纳 10 个 100 字节的 KV pair；敏感性分析表明 1 KB 以内不会造成网络饱和
- **LRU eviction**：客户端在后台通过 RDMA write 更新 last_ts，evict 最旧的 slot
- **测试平台**：1 个存储节点 + 5 个客户端节点（最多 160 客户端线程），RDMA 高速互联；存储节点配 7 块 Samsung 970 PRO SSD（每块 500K IOPS @4KB），ConnectX-6 HCA；模拟 DPU 环境：Intel Xeon Gold 限制到 8 核 + 8 GB 内存
- **源码**：https://github.com/madsys-dev/scalio-osdi25-ae

---

## 五、实验结果

### 主要吞吐量对比（7 SSD 配置，YCSB 系列）

| 工作负载 | 特征 | Scalio vs LEED | Scalio vs LEED+Ditto |
|----------|------|-----------------|----------------------|
| YCSB A | 50% 读 + 50% 写 | ~17× | ~1.8× |
| YCSB B | 95% 读 + 5% 写 | ~17× | ~3.3× |
| YCSB C | 100% 读 | ~17× | ~3.3× |
| YCSB D | 95% 读（最近热点） | ~10× | ~2.5× |
| YCSB F | 读-改-写 | ~10× | ~1.8× |

> 注：LEED 吞吐量在 4 SSD 时即饱和；Scalio 可持续扩展至 7 SSD。

### 各优化组件贡献分解（7 SSD 配置）

| 优化 | 效果 |
|------|------|
| Offloaded read（NVMe-oF target offload） | 1.5×–3.2× 提升；SSD I/O 利用率接近饱和 |
| Inline cache | YCSB B/C/D 分别吸收 85.2%/72.2%/62.6% 读请求；6.7× 峰值加速 |
| Batched write | 1.96× 峰值加速；SSD 写次数从 2 降至约 1 |

### 延迟对比（7 SSD，YCSB A 为例）

- 无 batched write 的 Scalio 比 LEED+Ditto 延迟降低 20%–30%，同时吞吐量提升 2–3×
- 启用 batched write 后，吞吐量进一步提升（800K IOPS，2.1×），延迟增加 1.97×（614 μs）

### 敏感性分析

- 工作负载倾斜度（Zipfian 常数 0.5–1.01）：Scalio 对所有倾斜度下均保持 2–3× 优势，高倾斜时 cache hit ratio 更高
- CPU 核数（4–16 核）：Scalio 对核数变化不敏感；LEED+Ditto 在 4 核时性能大幅下降，差距扩大至 2–5×
- Hash block 大小（4/8/16 slots）：性能差异极小

---

## 六、批判性分析

**1. 实验平台的根本性局限**

Scalio 的测试平台用受限的 Intel Xeon Gold（8 核 + 8 GB）模拟 DPU，而非真实 DPU 硬件（如 NVIDIA BlueField-3）。真实 DPU 的 ARM 核性能、PCIe P2P 拓扑、HCA 与内存的互联延迟特性与 Xeon 差异显著。作者辩称这是"保守估计"，但这一论断未经实测验证。论文实际上证明的是"CPU 受限后 offload 有效"，而非"在 DPU 上 Scalio 有效"——这是不小的概念差距。

**2. SSD 选型与基线不公平**

Scalio 使用 Samsung 970 PRO（消费级 M.2 SSD），而 LEED 原论文使用的是 Samsung 983 DCT（企业级数据中心 SSD）。不同 SSD 的 IOPS 特性、队列深度敏感性差异较大，导致跨系统的绝对数字对比存疑。

**3. 规模过小，难以推广**

实验最多测试 7 块 SSD，而论文动机中提到的商业 JBOF 产品已达 26–36 SSD。在 7 块 SSD 时表现良好，并不能保证在 36 SSD 时的系统行为，特别是缓存一致性协议的并发竞争和 RDMA CAS 的争用程度会显著不同。

**4. 写路径的延迟代价被低估**

Group commit 引入了约 2× 的 P99 延迟增加。论文将其定性为"可接受的代价"，但对于延迟敏感的 KV 服务（如电商实时推荐），614 μs 的均值延迟已不算低。更重要的是论文未提供 P99/P999 延迟分布，这对评估 batched write 的实际适用性至关重要。

**5. 一致性证明的适用范围**

线性一致性证明建立在"客户端失败由 lease 超时处理"的假设上，但 lease 期间 slot 处于 State B，其他读请求需 spin-wait 重试。在高并发、高冲突场景下，这可能导致严重的尾延迟。论文未讨论这一场景。

**6. 写操作仍需 DPU CPU**

NVMe-oF Target Offload 只解决了读路径的 CPU 问题；写路径仍需 DPU CPU 参与批处理和通知。论文因此在写密集型负载上仅获得 2× 提升，而非读密集型的 3× 以上。这说明 offload 策略存在根本性的非对称性，但论文对此分析不足。

---

## 七、AI Infra / MLSys 视角

**与 AI 系统的关联**

KV store 是 AI 基础设施的重要组件：大规模推荐系统使用 KV store 作为特征存储（feature store），分布式训练中的参数服务器本质上也是 KV store，LLM 推理中的 KV cache 持久化也可能用到高性能 KV store。Scalio 的技术思路对以下 AI Infra 场景有借鉴价值：

**可迁移的设计思路**

1. **CPU Offload 到硬件加速器**：Scalio 通过 NVMe-oF Target Offload 将 SSD I/O 完全卸载给 HCA 硬件，避免 CPU 成为 I/O 瓶颈。类似思路可用于 AI 推理系统中的存储访问路径（如大规模 embedding table 的 SSD offload），特别是在 DPU/SmartNIC 上运行 embedding lookup 的场景。

2. **Disaggregated 架构下的缓存一致性**：随着 AI 集群向存算分离演进（如 GCP 的 disaggregated serving），DRAM 缓存与远端存储的一致性问题将普遍化。Scalio 的四状态协议和 RDMA-based 失效机制提供了一种实用参考。

3. **RDMA one-sided 操作最大化**：Scalio 尽量将 RDMA CAS（慢 10×）替换为 RDMA read/write，这一权衡设计原则对构建高性能 AI 系统的 disaggregated 存储层有直接指导意义。

**值得跟进的方向**

- 在真实 DPU 硬件上验证 Scalio，特别是 LLM embedding table 场景（大 value，访问倾斜度极高）
- 探索将 NVMe-oF Target Offload 应用于 KV cache offload 场景（如 LLM 推理的 prefix caching、paged attention 的 SSD swap）
- 研究 disaggregated KV store 在 AI 特征服务中的 batch lookup 优化，将 Scalio 的 group commit 思路延伸到读路径的批量化

---

## 八、总结

Scalio 是第一个利用 NVMe-oF Target Offload 解决 DPU-based JBOF KV store 扩展瓶颈的系统，通过将 SSD 读操作完全卸载到 HCA 硬件、内联缓存吸收热点读、批量写降低 SSD I/O 次数，以及 RDMA-based 四状态一致性协议，在 7 SSD 配置下相比 SOTA 基线实现了 1.8×–3.3× 的吞吐量提升并保证线性一致性。主要局限在于：实验使用模拟 DPU 而非真实硬件、测试规模远低于商用 JBOF 产品上限、写路径仍受 DPU CPU 制约，且对延迟尾部特性的分析不足。
