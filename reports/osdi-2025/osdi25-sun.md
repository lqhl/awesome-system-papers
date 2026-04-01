# Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload

**作者**：Xun Sun, Mingxing Zhang, Yingdi Shan, Kang Chen, Jinlei Jiang (Tsinghua University); Yongwei Wu (Tsinghua University, Quan Cheng Laboratory)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/sun
**源文件**：[osdi25-sun.pdf](../../papers/osdi-2025/osdi25-sun.pdf)

---

## 一、背景

随着数据密集型应用的快速增长，高密度存储系统的需求日益增加。基于 DPU（Data Processing Unit）的 JBOF（Just a Bunch of Flash）架构通过将多块 NVMe SSD 与低功耗 DPU 组合在紧凑的 1U/2U 机箱中，提供了一种节能、低成本的存储方案。与传统 CPU 存储服务器相比，DPU 功耗仅 75-150W（Xeon CPU 为 300-500W），在能效上有显著优势。

SuperMicro（36-SSD JBOF）和 AIC（26-SSD JBOF）等厂商已推出高密度 JBOF 服务器产品，表明业界对高密度存储优化有迫切需求。理论上，每个 DPU 连接更多 SSD 可以显著提升吞吐量功耗比（throughput per watt），因为 DPU 控制平面的固定功耗 P 远大于单块 SSD 的功耗 p。

---

## 二、要解决的问题

1. **DPU CPU 成为扩展瓶颈**：现有 JBOF key-value store（如 LEED）严重依赖 DPU 的 ARM CPU 处理 SSD I/O 操作。实验表明，LEED 在连接 4 块 SSD 时吞吐量就已饱和，CPU 使用率达到上限（400%），无法随 SSD 数量线性扩展。

2. **网络 I/O 严重闲置**：LEED 的网络 I/O 利用率不到 1%（实际不超过 600K IOPS，而 ConnectX-6 HCA 可处理 200M IOPS），存在三个数量级的性能差距，这部分资源完全未被利用。

3. **写密集场景的额外瓶颈**：即使读操作可以通过 NVMe-oF target offload 卸载，CPU 仍被内存并发控制和随机 SSD 写操作消耗殆尽。

4. **一致性难题**：将操作卸载到客户端后，DPU DRAM 中的缓存状态与 SSD 状态之间缺乏硬件缓存一致性协议（不同于 CPU L1/L2 cache 有 MESI 等协议自动维护），需要软件层面保证 linearizability。

---

## 三、洞察与设计

**关键洞察**：在 IOPS-bound 的 JBOF 场景中，DPU 的网络 I/O 能力（RDMA read/write 可达 200M IOPS）与 SSD I/O 性能之间存在三个数量级的差距，导致网络资源严重闲置（< 1%利用率），而 CPU 是唯一的瓶颈。因此，可以将尽可能多的 SSD I/O 操作卸载到网络侧，用富余的网络 IOPS 替代紧缺的 CPU 周期。

基于这一洞察，Scalio 的核心设计包括三个方面：

### 1. Offloaded Read —— NVMe-oF Target Offload

利用 DPU HCA 的硬件能力，客户端可直接通过网络向 SSD 发送 NVMe 命令，经 PCIe P2P 通信完成数据读取，完全绕过 DPU CPU。读操作分两个阶段：
- **In-Memory Query Phase**：客户端通过 RDMA read 获取 hash block，在本地线性搜索目标 key。命中则直接返回；未命中则通过 RDMA CAS 锁定一个 victim slot。
- **SSD Access & Cache Update Phase**：客户端通过 NVMe-oF target offload 从 SSD 读取数据，再通过 RDMA write 回填缓存。

### 2. Two-Layer In-Memory Structure —— Inline Cache

设计紧凑的 RDMA-accessible hash table，每个 hash block 包含多个 slot，存储小 key-value pairs（key + value 内联存储）。block 大小可达 1KB，单次 RDMA read 即可获取整个 block（可容纳约 10 个 100 字节的 key-value pairs）。hash block 中还包含 SSD index 的 offset 指针，用于 cache miss 时的 SSD 访问。

### 3. Batched Write —— Group Commit

客户端通过 RDMA send 将写请求追加到 DPU 内存中的 ring buffer，DPU CPU 批量轮询并一次性刷入 SSD（只要 batch 大小 < SSD block 粒度如 4KB），将每次 key-value update 的 SSD 写次数从 2 次减少到约 1 次，之后更新 next_offset 字段并通知客户端。

---

## 四、实现细节

### 数据结构

- **Hash Table Slot**：包含 key、value、occupied（是否有效 key）、complete（value 是否完整写入）、last_ts（最近访问时间戳，用于 LRU 驱逐）五个字段。
- **Hash Block**：连续地址的多个 slot + 一个 next_offset 指向 SSD index 对应区域。
- **Ring Buffer**：存储客户端写请求及 client ID，支持 RDMA append。

### Cache 一致性协议

基于 occupied 和 complete 两个 flag 定义四种状态：
- **State A**（occupied=0, complete=1）：空 slot，可重用
- **State B**（occupied=1, complete=0）：正在填充中，其他客户端需等待重试
- **State C**（occupied=1, complete=1）：有效缓存项
- **State D**（occupied=0, complete=0）：填充过程中被 invalidate，视为 miss

**Read 流程中的 double-read 验证**：客户端锁定 victim slot 后，执行第二次 RDMA read 检查同一 hash block 是否已有其他客户端为相同 key 占据了另一个 slot，避免 key 冲突。

**Write 流程中的 cache invalidation**：写操作完成后，客户端通过 RDMA read + RDMA write 将对应 key 的 slot 的 occupied 置 0，触发状态转换到 State A 或 State D。

**Lease 机制**：每个 slot 维护 timeout_timestamp，客户端获取锁时写入当前时间 + lease duration。若 lease 过期，其他客户端可安全驱逐该 slot，处理客户端故障场景。

### Linearizability 证明

- Read 的 linearization point：cache hit 时为 RDMA read 到达缓存的时刻；cache miss 时为 victim slot 被锁定并通过 double-read 验证的时刻。
- Write 的 linearization point：update 应用到 SSD 之后，且不再存在同 key 的 State B 或 State C slot 的最早时刻。

### 实现环境

基于 Linux kernel 5.15.0，使用 MLNX_OFED driver（24.04-0.7.0），配置 NVMe target subsystem（nvmet）并启用 `attr_offload` 参数。复用 LEED 的 SPDK 栈和 SSD 存储数据结构。源码已开源：https://github.com/madsys-dev/scalio-osdi25-ae。

---

## 五、实验结果

### 实验平台

| 组件 | 配置 |
|------|------|
| 存储节点 | 1 节点，Intel Xeon Gold CPU（限制为 8 核 8GB 内存模拟 DPU） |
| SSD | 7× Samsung 970 PRO（每块 500K IOPS @4KB） |
| 网络 | ConnectX-6 HCA，RDMA |
| 客户端 | 5 节点，最多 160 客户端线程 |

### 基线

- LEED：JBOF key-value store
- LEED + Ditto：LEED 加上 Ditto 分布式内存缓存（1GB cache）

### 主要结果（YCSB A/B/C/D/F，1-7 SSDs）

| 指标 | Scalio vs LEED | Scalio vs LEED+Ditto |
|------|---------------|---------------------|
| 吞吐量提升 | 2.5× - 17× | 1.8× - 3.3× |
| 读密集工作负载（B/C/D） | 最高 3× speedup | 主要来自 NVMe-oF target offload |
| 写密集工作负载（A/F） | 最高 2× speedup | 主要来自 batched write |

### 优化拆解（7-SSD 配置）

| 优化项 | 贡献 |
|--------|------|
| Offloaded read | 1.5× - 3.2× speedup |
| Inline cache | 吸收 62.6% - 85.2% 读写操作（YCSB B/C/D），带来 2.7× - 6.7× speedup |
| Batched write | 最高 1.96× speedup（写密集场景），SSD 写次数从 2 降至约 1 |

### 延迟

- Scalio（无 batched write）vs LEED+Ditto：延迟降低 20%-30%，吞吐量提升 2×-3×
- Scalio（有 batched write）：YCSB A 场景下吞吐量达 800M IOPS（2.1× 提升），延迟为 614μs（1.97× 增加）

### 敏感性分析

- **Skewness**（Zipfian 0.5-1.01）：Scalio 在所有 skewness 下均优于基线 2×-3×
- **数据集大小**（20M-80M records）：吞吐量仅轻微下降，表现稳健
- **CPU 核数**（4/8/16）：Scalio 对 CPU 核数不敏感；核数从 16 减至 4，与基线差距从 1×-2× 扩大到 2×-5×
- **Hash block 容量**（4/8/16 slots）：对性能影响很小

---

## 六、批判性分析

1. **模拟 DPU 环境的代表性存疑**：实验使用 Intel Xeon Gold CPU 限制为 8 核 8GB 内存来模拟 DPU。然而，真实 DPU 使用 ARM 核心，其单核性能、缓存层次、内存控制器行为与 Xeon 差异显著。论文声称这是"保守估计"，但缺乏在真实 DPU 硬件上的验证数据。NVMe-oF target offload 的性能特征在不同 HCA firmware 版本和不同 DPU 平台上可能存在差异。

2. **SSD 数量有限**：实验最多测试 7 块 SSD，而论文多次引用的 SuperMicro 36-SSD JBOF 和 AIC 26-SSD JBOF 才是真正的目标场景。在 7 SSD 时 LEED 已经饱和，但 Scalio 的扩展趋势在更大规模下是否依然线性并未得到验证。

3. **Speedup 跨度大**：2.5× - 17×（vs LEED）和 1.8× - 3.3×（vs LEED+Ditto）的跨度说明性能提升高度依赖工作负载特征。最高的 17× 来自与不含缓存的裸 LEED 对比，实际更公平的比较应以 LEED+Ditto 为基线，此时提升为 1.8×-3.3×。

4. **写延迟 trade-off 被淡化**：batched write 带来的延迟增加（如 YCSB A 中 1.97× 延迟增长）在延迟敏感场景下可能不可接受。论文将此描述为"tolerable"，但未讨论 tail latency 分布（P99/P999），也未分析 batch size 对延迟的影响。

5. **Value 大小限制**：系统聚焦于小 key-value pairs（key ≤16B, value ≤64B），hash block 的 inline 设计在 value 较大时会失效。论文未讨论 value 大小增长时系统退化到何种程度，也未提供与 LEED 在更大 value size 下的对比。

6. **故障处理过于简化**：论文将服务器故障处理推给 RAID 或 dual-DPU 等正交方案，对 lease 过期导致的性能影响（如大规模客户端故障场景下的锁恢复开销）未做分析。

7. **Cache 一致性协议的 RDMA CAS 开销**：虽然论文声称减少了 RDMA CAS 的使用，但 double-read 验证和 lock 操作仍需 CAS。在高并发写场景下，CAS 竞争和重试的开销未被量化。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 存储的启发**：LLM 推理中的 KV cache 管理（如 vLLM 的 PagedAttention）面临类似的多层存储一致性问题——GPU HBM、CPU DRAM、SSD 三级存储间的数据调度。Scalio 的 RDMA-based cache consistency protocol 和 NVMe-oF target offload 思路可直接借鉴于 KV cache offloading 场景，实现 GPU 绕过 CPU 直接访问远端 SSD 上的 KV cache blocks。

2. **Checkpoint 和模型存储加速**：大模型训练中的 checkpoint 写入是典型的 bursty write 场景。Scalio 的 batched write + group commit 机制可以应用于分布式 checkpoint 系统，利用 DPU/SmartNIC 的网络能力卸载 checkpoint I/O，减少训练 GPU 的阻塞时间。

3. **Embedding Table 存储**：推荐系统中的大规模 embedding table 服务（如 Meta 的 DLRM）需要高 IOPS 的小 key-value 访问，与本文的目标场景高度吻合。NVMe-oF target offload + inline cache 的设计可以为 embedding lookup 提供低延迟、高吞吐的存储后端。

4. **值得跟进的方向**：
   - 将 NVMe-oF target offload 与 GPU Direct Storage（GDS）结合，实现 GPU → RDMA → SSD 的零 CPU 数据通路，用于 LLM prefill/decode 阶段的 KV cache swap
   - 在真实 DPU（如 BlueField-3）上验证 Scalio 的性能，探索 DPU 上的 ARM 核心在 AI workload（如 embedding lookup、feature store）中的实际表现
   - 扩展 cache consistency protocol 以支持 variable-length value（适配 KV cache 的 variable sequence length）

---

## 八、总结

Scalio 是首个利用 NVMe-oF Target Offload 技术解决 DPU-based JBOF key-value store 扩展性问题的系统。其核心贡献在于发现并利用了 JBOF 场景中网络 I/O 与 SSD I/O 之间三个数量级的性能差距，通过将 SSD 读操作卸载到 HCA 硬件、设计紧凑的 inline cache 吸收热点读、以及 batched write 减少 SSD 写次数，实现了相比 LEED+Ditto 1.8×-3.3× 的吞吐量提升。系统适用于小 key-value pairs 的高密度 JBOF 存储场景，主要局限在于仅在模拟 DPU 环境下验证、SSD 规模有限（最多 7 块）、且对大 value 和延迟敏感场景的适用性有待探索。
