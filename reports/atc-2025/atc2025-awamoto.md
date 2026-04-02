# Opening Up Kernel-Bypass TCP Stacks

**作者**：Shinichi Awamoto, Michio Honda (University of Edinburgh)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/awamoto
**源文件**：[[atc2025-awamoto.pdf]]

---

## 一、背景

TCP 是互联网和数据中心中最广泛使用的传输协议，Linux 内核协议栈长期以来针对大数据传输吞吐量进行了优化，并借助 TSO、GSO、BigTCP 等硬件/软件 offload 技术持续演进。然而，随着数据中心网络带宽迈向 100 Gb/s 及以上，内核协议栈面临三大瓶颈：(1) 大量并发连接时的 C10K/C10M 问题；(2) 多核扩展性受限于锁竞争和缓存失效；(3) 高软件开销导致小消息（RPC）的延迟过高。

为此，学术界和工业界涌现了大量 kernel-bypass TCP 协议栈（如 mTCP、F-Stack、IX、TAS、Demikernel），它们通过用户态 packet I/O（基于 DPDK、netmap 等）绕过内核，追求更高吞吐和更低延迟。各大云厂商（阿里巴巴 LUNA、腾讯 F-Stack）也在生产环境中部署了此类方案。

---

## 二、要解决的问题

1. **缺乏系统性对比**：现有 kernel-bypass 协议栈通常只与 Linux 内核栈及一到两个其他方案比较，且往往只在自己擅长的 workload 上展示结果。没有人在统一硬件和统一应用上全面对比过这些协议栈。

2. **workload 覆盖不足**：大多数 kernel-bypass 协议栈的评估只关注小消息 RPC 场景，忽略了大数据传输（bulk transfer）、高并发连接、多核扩展性等同样重要的维度。例如，没有一个被测协议栈曾对大数据传输性能做过完整评估。

3. **可复现性差**：由于不同协议栈的 API、编程模型、依赖库版本、配置参数差异巨大，第三方研究者很难在自己的环境中运行和公平比较这些协议栈。

4. **实际部署困难被低估**：应用移植工作量、配置调优复杂度、软件维护成本等实际工程挑战在现有文献中未被充分讨论。

---

## 三、洞察与设计

**关键洞察**：现有 kernel-bypass TCP 协议栈的架构设计决策（线程模型、资源分区方式、执行模型）在不同 workload 下存在根本性的 trade-off，没有任何一个协议栈能在大数据传输、小消息延迟、高并发连接、多核扩展性这四个基本维度上同时表现良好。

基于这一观察，作者构建了一套统一的测量框架来系统性揭示这些 trade-off：

- **统一应用 nophttpd**：为 6 个协议栈（Linux、mTCP、F-Stack、IX、TAS、Demikernel）分别实现了优化的最小 HTTP 服务器，避免了用不同应用比较不同协议栈带来的不公平。
- **统一客户端**：使用经过修改的 wrk 工具作为统一客户端，通过降低服务器 CPU 频率来避免客户端成为瓶颈。
- **四维 workload 覆盖**：bulk data transfer（128KB–2MB）、unloaded small message latency（64B–64KB）、concurrent connections（100–1600）、multi-core scalability（1–24 cores）。

六个协议栈的关键架构差异：

| 协议栈 | 线程模型 | API 风格 | TCP 实现 |
|--------|----------|----------|----------|
| mTCP | App-stack 线程对绑定同一核，shared-nothing | Socket-like | 自研 |
| F-Stack | App 在 stack 线程内回调执行，多进程 | Event callback | FreeBSD 移植 |
| IX | Run-to-completion，App 在 stack 线程内执行 | Packet-level TX/RX | lwIP |
| TAS | Stack 与 App 分离到不同线程/核 | Socket-like (LD_PRELOAD) | 自研 |
| Demikernel | Run-to-completion，单线程，Rust | Async packet-level I/O | 自研 |

---

## 四、实现细节

**nophttpd 服务器**：针对每个协议栈的原生 API 和执行模型分别实现，不使用统一 wrapper 层（避免引入对特定协议栈的偏向）。Linux 版本使用 epoll 事件循环，Demikernel 版本用 Rust 实现。

**协议栈修复与增强**（作者在评测中需要做的修改）：
- **mTCP**：需要模拟不同 RSS hash seed 的分布效果，修改源码以使用预计算的 seed；需要针对不同 workload 手动选择 busy-polling 或 interrupt 模式。
- **TAS**：发现缺少 Window Scaling 选项导致 bulk transfer 吞吐极低，作者自行实现了该选项；还需调整默认 buffer 大小和关闭带宽限制。
- **IX**：使用 Reflex 中的 IX 实现（移除了 Dune 依赖），避免额外保护域开销。
- **wrk 客户端**：修复了多线程 stat 聚合的可扩展性问题。

**硬件配置**：Intel Xeon Gold 5418N (Sapphire Rapids, 1.8GHz) + Intel XXV710-DA2 25GbE NIC，两台机器背靠背直连，Linux kernel 5.18。TSO 在所有协议栈上统一禁用以确保公平。

---

## 五、实验结果

### Bulk Data Transfer（单连接，128KB–2MB）

| 协议栈 | 峰值吞吐 (2MB) |
|--------|----------------|
| Linux | **14.69 Gb/s**（最高） |
| F-Stack | 13.66 Gb/s |
| mTCP | ~10–12 Gb/s |
| TAS | ~10–12 Gb/s |
| IX | 最低 |
| Demikernel | 最低 |

Linux 胜出因其长期优化；IX 和 Demikernel 因 packet-level API 需要应用手动分片，效率最差。

### Unloaded Small Message Latency（单连接，64B，P50 RTT）

| 协议栈 | P50 RTT |
|--------|---------|
| Demikernel | **13 µs**（最低） |
| Linux | 17 µs |
| IX | ~16 µs |
| TAS | ~20 µs |
| F-Stack | ~20 µs |
| mTCP | ~48 µs（受 batching 和上下文切换影响） |

Linux 内核栈在 busy-polling 模式下的延迟与 kernel-bypass 方案可比。

### Concurrent Connections 吞吐（单核，64B 消息，100–1600 连接）

| 协议栈 | 相对表现 |
|--------|----------|
| IX | **最高，领先 30–684%** |
| mTCP | 次高，优于 TAS 17–95% |
| TAS | 中等（多用一核） |
| F-Stack | ≈ Linux |
| Linux | 低吞吐、高延迟，随连接数增加恶化 |
| Demikernel | P50 延迟较高 |

IX 在 P50 延迟上比 Demikernel 低 73–85%。mTCP 尾延迟极高（可达 124 ms）。

### Multi-core Scalability（4800 连接，1–24 核）

| 协议栈 | 扩展性表现 |
|--------|-----------|
| IX | 1–16 核最佳（24 核因 bug 性能下降） |
| TAS | **最佳多核扩展性**，16→24 核吞吐增加 67% |
| mTCP | 24 核时扩展衰减（仅 +8.7%） |
| F-Stack | 扩展较好但始终低于 IX/TAS/mTCP |
| Demikernel | 无法测试（单线程设计） |

---

## 六、批判性分析

1. **硬件限制削弱结论普适性**：实验使用 25 GbE NIC，而论文动机强调的是 100 Gb/s+ 网络。在 25 Gb/s 下，bulk transfer 的瓶颈可能在网卡而非协议栈，Linux 的优势可能在更高带宽下被放大或缩小——这一点未被讨论。作者也承认未测试并行 bulk transfer。

2. **TSO 统一禁用的公平性存疑**：禁用 TSO 是为了"公平"（因 mTCP 和 Demikernel 不支持），但这恰恰掩盖了支持 TSO 的协议栈（Linux、F-Stack）在真实部署中的优势。真实场景中 TSO 是默认启用的，这使得 bulk transfer 的结论对实际部署参考价值有限。

3. **IX 使用的是 Reflex 中的旧版本**：作者因 IX 原版不稳定而使用 Reflex 版本，但 Reflex 移除了 Dune 保护域。IX 后续的 ZygOS、Shinjuku 都有改进，却未能获取到更新代码。这意味着 IX 的评测结果可能无法代表 IX 系列的最新水平。

4. **配置调优不透明**：TAS 需要手动搜索最优 stack/app 核分配比例，mTCP 需要手动选择 polling vs. interrupt——这些选择对结果影响巨大，但论文未给出完整的灵敏度分析。"brute-force search" 的描述缺乏可复现性。

5. **单一应用模式**：所有实验使用最小化 HTTP 服务器（nophttpd），虽然有利于公平比较，但与真实应用（memcached、Redis、存储系统）的行为差距较大。论文对此有所意识但未展开讨论。

6. **缺少 kernel 优化新技术的比较**：论文未测试 io_uring、MegaPipe、NetChannel 等内核增强方案。鉴于 Linux 内核栈在 unloaded latency 上已与 kernel-bypass 方案可比，io_uring 可能进一步缩小差距，但论文仅在 discussion 中简短提及。

---

## 七、AI Infra / MLSys 视角

1. **ML 训练/推理中的网络栈选型启示**：分布式训练中存在大量 all-reduce/all-gather 通信（bulk transfer）和参数服务器 RPC（small messages）。本文揭示没有一个 kernel-bypass 协议栈能同时处理好这两种模式，这对 ML 通信库（如 NCCL 的 TCP backend、Gloo）的协议栈选型有直接参考价值。MLTCP [66] 已尝试将应用行为融入 TCP 拥塞控制，是一个可延伸的方向。

2. **DPU/SmartNIC 场景下的 TAS 架构**：TAS 将 stack 和 application 分配到不同核的架构天然适合 DPU（如 NVIDIA BlueField）上的 TCP offload 场景。论文指出 FlexTOE 已基于 TAS 在 SmartNIC 上实现了细粒度并行，这是 AI Infra 中值得跟进的方向。

3. **推理服务的尾延迟问题**：在线推理服务（如 LLM serving）对尾延迟极为敏感。IX 系列（ZygOS、Shinjuku）通过 work stealing 和 preemptive scheduling 优化尾延迟的思路，可以借鉴到推理请求调度中。

4. **可操作的 future work**：基于本文发现，一个有价值的研究切入点是设计一个能感知 workload 类型（bulk vs. RPC）的自适应协议栈，在同一地址空间内根据连接特征动态切换处理策略（类似论文提到的 MultiStack 思路），这对 ML 集群中混合流量模式（训练流 + 推理 RPC + 存储 I/O）尤为重要。

---

## 八、总结

本文首次在统一硬件和统一应用上系统性对比了 6 个代表性 kernel-bypass TCP 协议栈，覆盖 bulk transfer、small message latency、concurrent connections 和 multi-core scalability 四个基本维度。核心发现是：没有任何一个协议栈能同时在所有维度表现良好——Linux 在 bulk transfer 上最优，IX 在 RPC 吞吐和并发连接上领先，TAS 多核扩展性最佳，Demikernel 延迟最低但仅限少量连接。论文还揭示了 kernel-bypass 协议栈在应用移植、配置调优、软件维护等方面的实际工程挑战，为未来构建通用高性能协议栈指明了方向。实验代码已开源于 https://github.com/uoenoplab/stackbench。
