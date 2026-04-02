# MTP: Transport for In-Network Computing

**作者**：Tao Ji (UT Austin), Rohan Vardekar (University of Illinois Chicago), Balajee Vamanan (University of Illinois Chicago), Brent E. Stephens (Google and University of Utah), Aditya Akella (UT Austin)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/ji
**源文件**：[nsdi2025-ji.pdf](../../papers/nsdi-2025/nsdi2025-ji.pdf)

---

## 一、背景

数据中心正面临日益增长的计算需求，In-Network Computing (INC) 作为一种有前景的方案，通过将应用级 (L7) 的处理逻辑卸载到可编程交换机和 SmartNIC 等网络设备上来加速应用。INC 的典型应用场景包括 key-value 缓存（NetCache）、L7 负载均衡、事务数据库加速、入侵检测，以及机器学习的 in-network aggregation（如 SwitchML、ATP）。

然而，INC 虽然在功能层面蓬勃发展，但一个根本性的问题尚未解决：现有的传输协议（TCP/RDMA/Homa）无法与 INC 的操作语义兼容。INC 中的 L7 offload 会对应用消息执行 mutation（修改消息内容和长度）、intercept（主动丢弃消息）、reordering（重排消息顺序）和 delaying（引入长且不可预测的延迟），这些操作会破坏传统传输协议的可靠性和拥塞控制机制。

---

## 二、要解决的问题

1. **可靠性被破坏**：TCP 和 RDMA 基于连续的字节/包序号空间来做可靠传输。当 offload 对消息执行 mutation（改变消息长度）或 intercept 时，接收端 ACK 的字节/包数与发送端不一致，导致发送端无法正确判断丢包与重传。Homa 在 mutation 场景下同样无法正确恢复丢失的字节范围。

2. **拥塞控制失效**：offload 引入的长且不可预测的延迟使得基于 ECN 和 RTT 的拥塞控制信号无法及时到达发送端。Homa 的 receiver-driven credit 机制依赖已知且恒定的 RTT 和带宽假设，在 INC 场景下也会失效。

3. **现有 workaround 不通用**：已有工作要么要求 offload "终止"传输协议（在硬件资源受限的设备上不可行），要么做出不切实际的简化假设（如消息不超过一个 MTU、每个 RPC 新建连接），要么只针对特定 offload 类型做 ad-hoc 适配，无法泛化。

---

## 三、洞察与设计

**关键洞察**：现有传输协议失败的根本原因在于它们将可靠性和拥塞控制绑定在包/字节序号空间上，而 INC 操作（mutation、intercept、reordering）会破坏这个序号空间的连续性。如果将传输协议的基本操作单元从 packet/byte 提升到 message 级别——与 L7 offload 的处理语义对齐——就可以将关键传输决策（丢包检测、重传、拥塞控制、路径选择）与底层序号解耦。

基于此洞察，MTP 的核心设计包括：

### 1. 消息级可靠性协议
- 发送端为每条消息设置重传超时（RTO），接收端在收到完整消息后发送 E2E ACK。
- 接收端是"被动"的：只在消息完整到达时回复 ACK，不检查消息编号的连续性或顺序。因此天然兼容 reordering 和 intercept。
- 消息被分为 segments，接收端用 bitmask 追踪已收到的 segments，通过消息长度判断何时收齐。

### 2. Pathlet 抽象
- 将路径上的每个 offload 实例建模为 pathlet，同类型的 offload 实例可被分组。
- Pathlet 不需要维护任何 MTP 特定状态，仅需在适当时机生成 ACK 包。

### 3. Dual-RTO 机制
- Pathlet 通过 PRX ACK（消息到达 pathlet）和 PTX ACK（消息离开 pathlet）通知发送端，使发送端区分"消息在网络中传输"（用短 fabric RTO）与"消息在 pathlet 中处理"（用长 pathlet RTO），避免虚假重传。

### 4. 多 pathlet 拥塞控制框架
- Pathlet 将自身的 buffer/queue 占用率映射为 8-bit 量化值，通过专用 feedback 包直接回传发送端（不需经过接收端反射）。
- 基于 Swift CCA 对 pathlet 反馈做 AIMD，每个 pathlet 独立维护 cwnd。
- Proactive Pathlet Switching (PPS)：当某 pathlet 持续拥塞时，主动将流切换到同类型的备选 pathlet。

### 5. Virtual Channels
- 为解决 exactly-once 语义问题，设计固定数量的 virtual channel，每个 channel 独立追踪最后完成的消息编号，避免 HoL blocking 且只用常量空间。

---

## 四、实现细节

- **MTP Stack**：基于 DPDK 实现的用户态协议栈，采用类 RDMA verbs 的 queue pair API。发送和接收端通过共享内存区域交换消息体，实现了无锁内存分配器支持乱序释放。
- **Middlebox Wrapper**：为使现有 L7 offload 兼容 MTP，实现了参考 wrapper，能够生成 PTX/PRX ACK 和 congestion feedback。Wrapper 支持 full buffering 模式，对部分到达的消息设置 100µs 超时后释放 buffer。
- **代码规模**：MTP stack + libmtp + message generator 约 6K 行 C/C++；参考 middlebox（wrapper + reference offload）约 600 行 C。
- **MTP Header**：仅 20 字节 + 可选 5 字节 pathlet congestion feedback。
- **连接建立**：三次握手，类似 TCP。
- **Pathlet 路由**：通过 IPv6 Segment Routing 实现源路由，pathlet 地址编码在包头中。
- **Pathlet 发现**：通过 Service Discovery Protocol 查询 pathlet 类型和实例地址，缓存在客户端。

---

## 五、实验结果

### 端到端应用：NetCache

| 指标 | MTP-based | UDP-based (baseline) |
|------|-----------|---------------------|
| 可持续吞吐 | >95% 系统最大吞吐 | 80% 时开始掉速 |
| p99 延迟 (高负载) | ≤4x unloaded latency | 高负载时急剧飙升 |
| 虚假重传 | 接近零 | 大量（导致服务器吞吐浪费） |
| 集成代价 (P4) | +69 行 P4（0.3% crossbar, 2.3% gateway） | - |

### Dual-RTO 效果

- Dual RTO 在 fabric RTO 400-1050µs 范围内均可达到 >90% goodput 且零虚假重传；单一 RTO 无此范围。

### 拥塞控制

- MTP CC（Swift-based + 8-bit pathlet feedback）可稳定收敛到公平份额；legacy CC（DCTCP + ECN）在多流共享 middlebox 时无法收敛。
- PPS 使总 goodput 达到两个 pathlet 平均吞吐的 ~98%，而 ECMP 只能达到 ~90%。

### 大规模仿真（ns-3, 128 节点 fat-tree）

| 指标 | MTP | TCP |
|------|-----|-----|
| p99 消息完成时间 | 降低 65%（3.6x 加速） | 基线 |
| 最大可持续负载 | >80% | ~60% 即饱和 |
| 重传率 | 接近零 | 10-15% |

### ACK 开销

- 最坏情况（4KB 消息, 2 pathlet, ACK + feedback）：链路带宽开销 6%，可忽略。
- 2 核 MTP stack 总 RX CPU 开销 ~55%，仍能饱和 25Gbps 链路。

---

## 六、批判性分析

1. **full buffering 假设的局限性**：MTP 的设计围绕 full buffering 展开，即假设 pathlet 会完整缓存消息再处理。虽然论文论证了这在大多数场景下成立，但 streaming 场景（如实时视频处理、大模型流式推理）被推到了 future work，而这恰恰是越来越重要的场景。论文建议的 workaround（将 stream 拆成单包消息）在语义和效率上都可能有问题。

2. **实验规模和应用多样性不足**：端到端实验仅用了 NetCache 一个应用，且是 read-only 场景。对于 mutation 改变消息长度、多级 pathlet chain、intercept 等复杂场景，只有仿真结果。缺少真实 SmartNIC 上的实验（middlebox 运行在通用 CPU 上模拟）。

3. **Pathlet 发现和故障处理**：论文假设了一个 pathlet registry 和 SDP，但对 pathlet 动态上下线、故障检测和恢复几乎没有讨论。在生产环境中，pathlet 的可用性管理是一个重要问题。

4. **安全性被完全搁置**：INC 本身需要检查和修改包载荷，与 TLS 的安全模型根本冲突。论文虽然提到了 mcTLS 作为可能的互补方案，但没有任何验证。这在实际部署中是一个 blocker。

5. **拥塞控制评估不够全面**：CC 评估使用的是 DCTCP/Swift 的简单适配，论文自己也承认这不是最优的 CCA，并将系统性的 CC for INC 研究留给了未来。在 pathlet 处理时间分布极端（如双峰分布中 5% 的请求延迟 20x）时，CC 的鲁棒性仍需验证。

6. **Virtual Channel 数量的工程权衡**：需要 ~122 个 virtual channel 才能在 4KB 消息 + 40µs RTT + 100Gbps 下饱和链路，这意味着每个连接需要维护大量状态。论文提到连接状态与 in-flight 消息和 pathlet 数量成正比，但在高带宽低延迟场景下这个开销可能并不小。

---

## 七、AI Infra / MLSys 视角

1. **对分布式训练 in-network aggregation 的直接价值**：MTP 天然适配 SwitchML、ATP、SHArP 等 in-network aggregation 场景。在这些场景中，交换机上的 aggregator 会 delay（等待 straggler）和 mutate（用聚合结果替换原始梯度）消息，正是现有传输协议最痛苦的地方。MTP 的 dual-RTO 和消息级可靠性可以避免因 straggler 导致的虚假重传，提高聚合效率。

2. **Pathlet 抽象对 AI 推理流水线的启发**：现代 AI 推理系统中，请求可能经过多级处理（prefill → decode → post-processing），每级可能部署在不同硬件上。Pathlet 的抽象和 per-pathlet congestion control 思路可以迁移到推理流水线的流量管理中，特别是在 disaggregated inference 场景下。

3. **PPS 对 Expert Parallelism / MoE 路由的借鉴**：MoE 模型中的 expert routing 面临类似的 load balancing 问题——某些 expert 可能成为热点。PPS 的思路（基于拥塞反馈主动切换目标）可以启发更好的 expert 负载均衡策略。

4. **可探索的 future work**：
   - 将 MTP 与 RDMA NIC 集成，利用硬件加速 MTP stack 来降低 CPU 开销，使其在大规模 AI 训练集群中可用。
   - 扩展 MTP 支持 streaming 语义，适配 LLM 推理中的 token-by-token 流式输出场景。
   - 研究 pathlet 级的优先级调度，支持 AI 推理中延迟敏感请求和批量训练流量的混合传输。

---

## 八、总结

MTP 是首个原生支持 In-Network Computing 的传输协议，通过将传输操作的基本单元从 packet/byte 提升到 message 级别，并引入 pathlet 抽象、dual-RTO、per-pathlet 拥塞控制等机制，解决了 INC 中 mutation、intercept、reordering 和 delaying 对传统传输协议的兼容性问题。实验表明 MTP 在 NetCache 场景中提升吞吐 15%+，在大规模仿真中降低尾延迟 65%。其主要局限在于 full buffering 假设限制了 streaming 场景的支持，且安全性、大规模生产部署等问题有待解决。
