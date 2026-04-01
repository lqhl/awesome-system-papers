# Picsou: Enabling Replicated State Machines to Communicate Efficiently

**作者**：Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu (UC Berkeley); Suyash Gupta (University of Oregon); Manos Kapritsos (University of Michigan)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/frank
**源文件**：[osdi25-frank.pdf](../../papers/osdi-2025/osdi25-frank.pdf)

---

## 一、背景

复制状态机（Replicated State Machine, RSM）是现代分布式系统的核心基础设施，被广泛用于键值存储（Etcd）、集群管理（Kubernetes）、微服务等场景。在实际部署中，多个 RSM 之间频繁需要进行高效、可靠的消息交换——例如 Etcd 跨集群灾备通过 Kafka 做镜像、政府机构间独立运行的 RSM 需要数据同步、区块链生态中不同链之间的互操作等。

然而，目前 RSM 之间的通信缺乏一个正式的抽象原语和高效的协议。现有方案要么是 ad-hoc 的、保证模糊的（如 Kafka 依赖第三方 RSM 中继）、要么依赖昂贵的 All-to-All 广播（O(n_s × n_r) 消息复杂度），在 WAN 环境下更是瓶颈。

---

## 二、要解决的问题

1. **缺乏正式抽象**：RSM 间通信没有像 Reliable Broadcast 那样的形式化原语，导致各系统自行设计，保证不一致。
2. **效率低下**：All-to-All 广播消息量为 O(n_s × n_r)，随网络规模二次增长；Leader-to-Leader 方案在 leader 故障时无法保证消息投递。
3. **鲁棒性不足**：Kafka 等方案引入额外的共识协议开销；现有方案无法同时支持 crash 和 Byzantine 故障模型。
4. **通用性差**：现有方案通常假设同构的 RSM，无法让 BFT 协议（如 PBFT）与 CFT 协议（如 Raft）或 Proof-of-Stake 系统（如 Algorand）之间通信。

---

## 三、洞察与设计

**关键洞察**：RSM 间通信问题与 TCP 的可靠传输问题在结构上高度相似——两者都需要在不可靠通道上实现可靠的流式消息传递，都可以利用全双工通信和累积确认来高效检测消息投递成功或丢失。但 RSM 通信需要处理多对多（而非点对点）以及 Byzantine 节点可能撒谎的额外挑战。

基于这一洞察，论文首先定义了 **Cross-Cluster Consistent Broadcast (C3B)** 原语：如果 RSM_s 传输消息 m 给 RSM_r，那么 RSM_r 中至少一个正确副本最终会收到 m（Eventual Delivery），且只有 RSM_s 确实发送过的消息才会被投递（Integrity）。

然后提出 **PICSOU** 协议，核心设计包括：

- **QUACKs（Quorum Acknowledgments）**：累积仲裁确认机制。每个接收副本维护一个有序列表，发送累积 ACK(p) 表示序号 ≤ p 的所有消息均已收到。当发送方收集到 u_r + 1 个副本的 ACK 时，形成 QUACK，证明至少一个正确副本已收到消息。重复 QUACK（duplicate QUACK）则表明后续消息丢失。
- **Round-Robin 轮转**：发送方副本均匀分配消息发送任务（replica R_sl 发送序号 k' mod n_s ≡ l 的消息），且每轮轮转接收方，确保每对副本最终都会通信，避免持续发送给故障节点。
- **全双工 Piggyback**：ACK 信息搭载在反向消息上，无需额外通信。
- **φ-list 并行重传**：故障时通过常量大小的元数据标记丢失消息范围，支持并行恢复多条丢失消息。

对于 Proof-of-Stake 系统中 stake 不等的场景，PICSOU 引入 **Dynamic Sharewise Scheduler (DSS)**，借鉴 Hamilton 分配法（apportionment）和 Linux CFS 调度器的思想，按权重公平分配发送/接收任务，并通过 LCM 缩放解决异构 RSM 间 stake 差异巨大的问题。

---

## 四、实现细节

- 约 4500 行 C++20 代码实现
- 使用 Google Protobuf v3.10.0 做序列化，NNG v1.5.2 做网络通信
- 设计为即插即用的库，可集成到现有 RSM 系统
- 采用 UpRight 故障模型统一处理 crash 和 Byzantine 故障：n = 2u + r + 1（u 为任意故障上限，r 为 Byzantine 故障上限）
- 消息格式：⟨m, k, k'⟩Q_s，其中 k 为共识序号，k' 为 PICSOU 传输序号，Q_s 为提交签名
- QUACK 形成条件：u_r + 1 个副本的累积 ACK；duplicate QUACK 需 r + 1 个重复 ACK（仅在 Byzantine 场景下，crash-only 场景下单个重复 ACK 即可触发重传）
- DSS 使用 Hamilton 方法进行分配：计算标准除数（SD = ΔΔΔ/q）、标准配额（SQ = δ/SD）、下配额（LQ = ⌊SQ⌋），剩余名额按罚比（penalty ratio）降序分配
- 支持 reconfiguration：利用外部配置服务感知成员变更，未确认的消息在重配置后重新发送

---

## 五、实验结果

**实验平台**：最多 45 个 GCP c2-standard-8 节点（Intel Cascade Lake, 8vCPU, 32 GiB RAM, 15 Gbits/s），每次实验运行 180 秒。

**对比基线**：One-Shot (OST, 性能上界), All-to-All (ATA), Leader-to-Leader (LL), OTU (GeoBFT), Kafka

**配合的 RSM**：File RSM（无限快，压测用）、Etcd Raft v3.0、ResilientDB (PBFT)、Algorand (PoS)

| 实验 | PICSOU 表现 |
|------|-------------|
| 小消息(0.1kB), 4 副本 | 比 ATA 快 2.5×, 比 LL 快 ~4× |
| 大消息(1MB), 4 副本 | 比 ATA 快 3.2× |
| 小消息(0.1kB), 19 副本 | 比 ATA 快 6.6× |
| 大消息(1MB), 19 副本 | 比 ATA 快 12.1×, 接近 OST 上界 |
| 跨地域(US-West ↔ HK), 19 副本, 1MB | 比 ATA 快 44× |
| Crash 故障(33% 副本崩溃) | 吞吐下降 22.8%–30.5%，仍比 ATA 快 2×–8.9× |
| Etcd 灾备应用 | 比 Kafka 快约 2× |
| 数据对账应用 | 与 ATA/LL/OTU 性能相当或更优 |
| 跨链桥(Algorand ↔ ResilientDB) | 对 RSM 吞吐影响 < 15% |

---

## 六、批判性分析

1. **微基准与端到端差距**：在 File RSM 微基准上 PICSOU 比 ATA 快高达 24×，但在真实应用（Etcd 灾备）中优势缩减为约 2×。这表明在实际场景中共识本身往往是瓶颈，C3B 协议的优化空间有限。论文标题和摘要突出的"24×"数字具有误导性。

2. **Kafka 基线的公平性**：作者承认 Kafka 在数据对账实验中存在"known issue with high latency consumers"导致性能异常低，但仍将其作为基线报告。这削弱了与 Kafka 比较的说服力。

3. **Byzantine 故障实验不足**：论文的核心卖点之一是支持 BFT，但实验中没有展示 Byzantine 故障下的性能（只测了 crash 故障）。仅通过 φ-list 的理论分析来论证 Byzantine 鲁棒性是不够的。

4. **延迟指标缺失**：论文几乎只报告吞吐量，但明确指出"latency will increase proportionally to network size"。对于灾备等场景，恢复延迟同样关键，但论文未给出具体数据。

5. **可扩展性上限**：所有实验的 RSM 规模上限为 19 副本。对于区块链场景（论文反复提及的应用场景之一），典型网络规模远大于此，PICSOU 在更大规模下的表现未知。

6. **DSS 调度器的实际验证薄弱**：Weighted RSM 实验仅在 File RSM 上测试，且当高 stake 节点成为瓶颈时吞吐量确实下降。论文未讨论实际 PoS 系统中 stake 分布的典型模式及对 DSS 的影响。

---

## 七、总结

PICSOU 提出了 C3B 这一形式化的 RSM 间通信原语，并通过借鉴 TCP 的累积确认机制设计了 QUACKs，在无故障场景下实现每条消息仅发送一次、仅附带常量大小元数据的高效通信。系统支持 crash 和 Byzantine 混合故障模型，可连接异构 RSM（Raft、PBFT、Algorand）。主要局限在于微基准优势难以完全转化为端到端收益，且缺乏大规模和 Byzantine 故障下的充分实验验证。
