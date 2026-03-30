# Disentangling the Dual Role of NIC Receive Rings

## 论文基本信息

- **标题**: Disentangling the Dual Role of NIC Receive Rings
- **作者**: Boris Pismenny (EPFL & NVIDIA), Adam Morrison (Tel Aviv University), Dan Tsafrir (Technion)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/pismenny

## 研究背景与动机

随着以太网速度向百Gbps级别增长，网络密集型应用的性能高度依赖于直接数据 I/O（DDIO）技术的有效性。DDIO 使得 NIC 能够直接 DMA 到 CPU 的最后级缓存（LLC），而非主内存，从而让软件更快地访问数据包数据，并节省主内存带宽。

DDIO 的有效性取决于 I/O 工作集的大小——即 NIC 为数据包交换 DMA 的内存区域。如果 I/O 工作集超过 LLC 容量，新到达的数据包会从 LLC 中驱逐尚未处理的数据包（"leaky DMA" 问题）。这导致 CPU 访问数据包数据时不得不从主内存读取，速度更慢甚至成为瓶颈。

**关键事实**：≥100 Gbps NIC 的默认 Rx ring 大小为 R=1024 entries，每个 buffer 1500B。因此每个 core 的 I/O 工作集至少为 R×1500B ≈ 1.5 MiB。由于 LLC 容量通常每 core 不到 1.5 MiB，多核网络处理很容易超过整体 LLC 容量。

## 要解决的核心问题

**核心问题**：现有 Rx ring 接口将两个正交的生产者-消费者结构耦合在一个 ring 中，导致无法在不损害其他能力的前提下缩小 I/O 工作集：

1. **内存分配**：CPU core 生产空 buffer，NIC 消费空 buffer 来存储到达的数据包
2. **数据包交付**：NIC 生产到达的数据包，CPU core 消费它们

由于这个耦合：
- 不能简单减少每 core 分配的 buffer 数量（否则影响 burst 吸收能力）
- 不能在 core 间共享分配好的 buffer（否则同时强制共享数据包接收能力）

**现有方案及其局限**：
- **Few Dispatchers**（Shinjuku、Shenango）： dispatcher core 成为 ≥100Gbps 下的瓶颈
- **Small Private Rings**：ring 太小无法吸收 burst，导致丢包
- **ShRing**：支持 ring 共享，但负载不均衡时（某些 core 持续过载而其他空闲）会导致数据包丢失

## 主要贡献

1. **深入揭示问题根因**：提出 Rx ring 接口将两个正交的生产者-消费者结构（内存分配 + 数据包交付）纠缠在一起，是 I/O 工作集问题和 ShRing 瓶颈的根本原因
2. **rxBisect 接口设计**：将传统的 Rx 数组拆分为独立的 Allocation ring (Ax) 和 Bisected reception ring (Bx)，允许内存分配与接收解耦
3. **跨 core 共享机制**：NIC 可从任意 Ax ring 获取 buffer 来存储到达的数据包，无论目标 Bx ring 是哪个；buffer replenish 通知也相应解耦
4. **软件仿真实现**：在自研软件 NIC 框架上实现 rxBisect，验证了设计可行性

## 研究方法与设计

### rxBisect 核心设计

将传统 Rx ring 拆分为两个独立的 ring：
- **Ax (Allocation ring)**：CPU core 向 NIC 提供空 buffer，NIC 消费它们
- **Bx (Bisected reception ring)**：NIC 向 CPU 交付到达的数据包

**关键特性**：
- Ax 和 Bx 可以有不同大小
- Ax 可以远小于 Bx（如各 1 Ki entries，但 Ax 用于空闲 buffer 管理，Bx 用于数据包接收）
- NIC 可从任意 core 的 Ax ring 获取 buffer 来存储到达的数据包（跨 core 共享 buffer）
- Buffer replenish 时，通知通过数据包所在的 Bx ring 进行，而非原来直接与 Ax 关联

### 跨 Core Buffer 共享

当数据包到达时：
1. NIC 通过 RSS 选择目标 Bx ring（与原设计相同）
2. NIC 从**任意**属于同一软件实体且在同一 NUMA 节点上的 Ax ring 获取空 buffer（而非只能从目标 core 的 Ax 获取）
3. 新数据包的 Bx descriptor 中包含 replenish 通知，指明从哪个 core 的 Ax 获取了 buffer

Replenish 处理：
- Core 处理 Bx 中的通知时，从对应的 Ax 放入新的空 buffer
- 无需跨 core 同步（同步由 NIC 在 hardware 层完成）

### Completion Ring（CR）设计

Modern NIC 使用 per-core in-memory CR 结构来通知软件数据包交付。rxBisect 保留 CR 机制，但：
- 每个 Bx ring 关联一个 CR（与原设计相同）
- 新数据包到达时，CR entry 包含 replenish 通知

### 跨 Core Buffer 共享的优势

相比 ShRing：
- **无锁设计**：ShRing 需要 software 同步来更新共享 Rx ring，而 rxBisect 将同步 offload 给 NIC hardware
- **负载均衡友好**：即使某些 core 过载，过载 core 的 Ax 中的 buffer 可以被其他 core 的数据包使用，不会阻塞空闲 core
- **I/O 工作集可控**：Ax 可以设得很小（仅需维持 pipeline 深度），Bx 可根据 burst 需求设置

### 与 ShRing 的关键区别

| 特性 | ShRing | rxBisect |
|---|---|---|
| 同步机制 | Software 锁/原子指令 | Hardware（NIC） |
| Buffer 来源 | 只能从目标 core 的 Rx ring | 可从任意 Ax ring |
| 过载处理 | 过载 core 独占共享 entries | 过载 core 的 Ax 可被其他 core 共享 |
| I/O 工作集 | 固定（默认 R×1500B） | 可独立配置（Ax < Bx） |

## 关键实现细节

### 软件仿真框架

论文使用自研软件 NIC 框架（software NIC framework）来仿真 rxBisect 和对比系统。该框架还仿真了：
- PrivRing（per-core private Rx ring baseline）
- ShRing（共享 Rx ring）
- rxBisect

**注意**：论文声称软件仿真"may be similar or worse than real performance"，但实际数据显示 emulation 可能导致吞吐量降低最多 12%，延迟增加最多 94%（Table in §5）。这意味着 rxBisect 的真实性能可能比仿真结果更好。

### 仿真框架的真实性验证

§5 的实验比较了仿真与非仿真版本（PrivRing）的性能，以验证仿真保真度。显示仿真性能相似或更差，使论文有信心用仿真结果比较 rxBisect 与非仿真 baseline 和 ShRing。

## 实验结果与分析

### 测试环境
- 16-core CPU（22 MiB LLC）
- 两个 100 Gbps NVIDIA ConnectX-5 NIC
- DPDK-based 状态负载均衡器（LB）网络功能

### I/O 工作集影响

Figure 2 展示了大 I/O 工作集的影响：
- **吞吐量**：线速（line rate）在 R≤128 时达到；R=1024 时降低 0.8×
- **延迟**：R=1024 时增加最多 37×
- **内存带宽**：R=1024 时增加最多 4.9×

关键发现：当 I/O 工作集 fits 在 DDIO 用的两个 LLC ways 时达到线速；超过 LLC 时显著降级。

### rxBisect vs. Baseline

**吞吐量**：
- rxBisect 相比 per-core Rx baseline 提升最高 **37%**
- rxBisect 相比理想化 ShRing（在负载均衡时）提升最高 **20%**

**延迟**：
- rxBisect 在维持线速时，延迟比 baseline 低最多 **11×**
- 显著延迟改善发生在 rxBisect 能维持线速而 baseline 无法维持时

### 负载不均衡评估

Figure 5 展示了不同过载比例下各系统的性能：
- rxBisect 在所有过载配置下均优于 ShRing 和 baseline
- 过载 core 比例越高，rxBisect 优势越明显
- ShRing 在严重不均衡时退化为接近 per-core baseline（因为其 fallback 机制）

### 丢包率

rxBisect 在高负载下维持接近零的丢包率，而 baseline 在 R=1 Ki 时丢包率显著增加。

## 潜在问题与局限性

1. **纯软件仿真**：虽然作者验证了仿真"相似或更差"，但 rxBisect 的核心创新（跨 core buffer 共享由 hardware NIC 完成）无法在纯软件仿真中验证。需要真实 NIC hardware 实现才能验证这一关键设计假设
2. **仅测试了负载均衡器 NF**：论文未在真实应用（如键值存储、RPC 服务）上测试 rxBisect 的效果，网络功能的 workload 特性可能不能代表所有场景
3. **不支持跨 NUMA**：论文的跨 core 共享要求"同一 NUMA 节点"，对于跨 NUMA 场景的优化（如现代服务器中 GPU 直接访问网络）未涉及
4. **Modern NIC 特性依赖**：rxBisect 依赖于 modern NIC 的 Completion Ring 特性和精细的 ring 管理能力，而这些特性在不同厂商/NIC 型号间的支持情况不明确
5. **与 ShRing 的"公平比较"存疑**：论文比较了 rxBisect 与"理想化 ShRing"（假设无同步开销），而实际 ShRing 的同步开销在真实环境中可能比 rxBisect 更低，因为 rxBisect 的跨 core 共享机制需要更复杂的 NIC 硬件逻辑
6. **扩展到多队列 NIC 的复杂性**：真实 100 Gbps NIC 通常有多个 hardware queue，rxBisect 的 Ax/Bx 拆分在这些场景下的可扩展性未评估

## 未来工作方向

1. 在真实 NIC hardware 上实现 rxBisect（论文提到这是 future work）
2. 探索 rxBisect 与 DPDK 之外的框架（如 AF_XDP、io_uring）的集成
3. 将 rxBisect 扩展到 Tx ring 管理的优化
4. 与 SmartNIC 或可编程 NIC 的集成

## 个人评注

### 优点

1. **问题根因分析出色**：将 Rx ring 的双重角色（内存分配 + 数据包交付）解耦是本文的核心洞察，这是一个在业界被忽视已久的问题
2. **设计简洁有力**：将单一 Rx ring 拆分为 Ax + Bx 的方案在概念上简单，但解决了根本性的设计问题
3. **实验扎实**：从 I/O 工作集的基础测量到跨 core 共享的消融实验，设计周密
4. **对 ShRing 的批评准确**：ShRing 被描述为"pathological"的负载不均衡场景实际上在真实数据中心广泛存在，论文有力地论证了这一点

### 不足与可疑之处

1. **最关键的不足：没有真实 hardware 实现**：rxBisect 的核心创新（hardware-level 跨 core buffer 共享）完全依赖软件仿真，而软件的模拟准确性无法验证真正的硬件行为。论文自己在 §5 承认 emulation 可能使性能降低 12%（吞吐量）和增加 94%（延迟），这一巨大差异意味着 rxBisect 的真实性能数据完全未知
2. **仿真框架的代表性存疑**：自研软件 NIC 框架是否能够真实模拟现代 100 Gbps NIC 的行为（特别是 DDIO cache 行为）？论文对此的论证不够充分
3. **ShRing 比较的公平性问题**：论文将自己的 rxBisect 与"idealized ShRing"比较，假设 ShRing 无同步开销。但即使有同步开销，ShRing 也是在真实 hardware 上实现的，而 rxBisect 只是仿真。这个比较在方法论上不够公平
4. **PCIe 和 DDIO 交互被简化**：真实的 DDIO 行为在不同 PCIe topology（direct/indirect NIC 连接）下差异显著，rxBisect 在 indirect 连接场景下的行为未被评估
5. **论文标题有夸大之嫌**："Disentangling the Dual Role of NIC Receive Rings"暗示解决了 NIC Rx ring 的核心问题，但实际上这是一个特定于现代 high-speed NIC + DDIO 场景的问题，对于 10 Gbps 以下 NIC 或不使用 DDIO 的系统影响有限
