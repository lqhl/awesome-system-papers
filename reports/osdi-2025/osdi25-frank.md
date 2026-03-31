# Picsou: Enabling Replicated State Machines to Communicate Efficiently

**作者**：Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu, Natacha Crooks（UC Berkeley）; Suyash Gupta（University of Oregon）; Manos Kapritsos（University of Michigan）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, 2025，Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/frank
**源文件**：[osdi25-frank.pdf](../../papers/osdi-2025/osdi25-frank.pdf)

---

## 一、背景

大量现代基础设施依赖复制状态机（RSM）来提供高可用性和容错能力，典型例子包括键值存储（Etcd、TiDB）、集群管理器（Kubernetes）以及各类微服务。这些 RSM 在不同组织、不同数据中心之间频繁需要互相通信：Etcd 灾难恢复通过 Kafka 镜像到另一个数据中心、政府机构之间出于运营主权要求各自维护独立 RSM 后再显式同步数据、区块链生态则不断追求跨链互操作性。

然而，如何让两个 RSM 之间高效、可靠地通信，在学术上缺乏形式化框架，工程上缺乏通用高效的协议。现有系统在这一问题上普遍采用临时方案，难以保证强一致性或高性能。

---

## 二、要解决的问题

**现有方案的不足**：

1. **Apache Kafka**（业界事实标准）：在两个 RSM 之间插入第三个 RSM（Kafka 集群）来中转数据，引入额外延迟、带宽开销和单点信任问题。
2. **All-to-All broadcast（ATA）**：每个发送方副本向所有接收方副本广播，消息复杂度为 O(n_s × n_r)，在 WAN 场景下带宽开销巨大。
3. **Leader-to-Leader（LL）**：由主节点转发，主节点成为瓶颈，主节点故障时无法保证投递。
4. **GeoBFT 的 OTU**：类似 LL，仅将消息发送给 u+1 个接收副本，依然存在领导者瓶颈，且不支持任意异构 RSM。

这些方案均无法同时满足四个关键需求：①形式化的强保证，②故障下的鲁棒性（不降吞吐、不破坏正确性），③无故障情况下的低开销（单次发送、常数大小元数据），④对任意异构 RSM 的通用性（支持 CFT/BFT/PoS，支持不同网络和故障模型）。

---

## 三、核心设计

**C3B 原语（Cross-Cluster Consistent Broadcast）**

论文首先将 RSM 间通信问题形式化为 C3B 原语，定义两个正确性属性：
- **Eventual Delivery**：若 RSM_s 发送消息 m，则 RSM_r 最终投递 m。
- **Integrity**：RSM_r 投递 m 当且仅当 RSM_s 曾经发送过 m（仅需至少一个正确副本接收到即满足条件）。

**PICSOU 协议**

PICSOU 是 C3B 的实用实现，设计灵感来自 TCP，三大设计支柱为：Efficiency（无故障情况下每消息仅发一次，元数据 O(1) 大小）、Generality（支持 CFT/BFT/PoS RSM）、Robustness（故障不影响正确性，最小化重传）。

核心机制是 **QUACK（Quorum ACKnowledgments）**：
- 类比 TCP 的累积 ACK，但适配分布式副本场景
- ACK(k) 表示序号 1..k 的所有消息已被接收 RSM 中至少一个正确副本收到
- 累积形式确保元数据大小为常数（单个计数器）
- 重复收到 ACK(k) 则意味着序号 k+1 的消息丢失或延迟

**发送逻辑**：
- 发送方副本对消息按序号轮流分配（replica R_sl 负责发送 k' mod n_s ≡ l 的消息），实现 O(n) 并行
- 每轮轮转接收方副本（sender rotates receiver），保证故障副本不持续阻塞通信
- 发送方同时传输一个窗口的消息（类似 TCP 窗口）

**φ-list 机制**：
- 在 QUACK 中附加常数大小的 φ-list，记录最近已知丢失的消息序号
- 使接收方能并发恢复多个被 Byzantine 节点选择性丢弃的消息

**Stake 支持（Dynamic Sharewise Scheduler，DSS）**：
- 针对 Proof-of-Stake 系统（如 Algorand），各副本持有不同权重
- Weighted QUACK：ACK 权重等于副本 stake；QUACK 在总权重 ≥ u_i+1 时成立
- 采用 **Hamilton 分配法**（apportionment method）在每个量子时间内公平分配发送任务，避免整数取整带来的不公平性
- 两 RSM stake 差异极大时，以 LCM 方式缩放权重，分离"成功路径"与"故障路径"的粒度

---

## 四、实现细节

- 约 **4500 行 C++20** 代码
- 序列化：Google Protobuf v3.10.0
- 网络：NNG v1.5.2
- 设计为**即插即用库**，可与任意 RSM 集成
- RSM 将已提交的消息以 `(m, k, k')` 三元组形式传递给 PICSOU；k' 为可选序号（⊥ 表示不转发），用于过滤哪些消息需要跨 RSM 传输
- QUACK 通过 piggyback 附着在接收 RSM 向发送 RSM 发出的消息上（全双工利用），若无数据消息则发送 no-op
- 节点 ID 通过可验证随机数（VRF，如 Algorand 方案）分配，防止 Byzantine 节点占据连续编号
- 重传时若发现 duplicate QUACK 带有更低序号，发送方将已垃圾回收消息的最高 quack 序号附在 QUACK 中，接收方凭此推断中间消息已被某正确副本接收

---

## 五、实验结果

**实验环境**：最多 45 个 GCP c2-standard-8 节点（Intel Cascade Lake，8vCPU，32 GiB RAM，15 Gbits/s），每次实验运行 180s（含 30s 预热/冷却）。

**基线**：
| 方案 | 描述 |
|------|------|
| OST | 单发送方→单接收方，性能上界（不满足 C3B） |
| ATA | 全对全广播，O(n_s × n_r) |
| LL | 主节点到主节点 |
| Kafka 2.13-3.7.0 | 业界标准，内部使用 Raft |
| OTU（GeoBFT） | 主节点发 u+1 副本，then 内部广播 |

**微基准（File RSM，无共识瓶颈）**：
| 场景 | PICSOU vs ATA |
|------|--------------|
| n=4, 小消息 (0.1kB) | 3.2× |
| n=19, 小消息 | 6.6× |
| n=4, 大消息 (1MB) | 2.5× |
| n=19, 大消息 | 12.1× |
| 地理复制 n=4 (US-West→香港，133ms RTT) | 12× |
| 地理复制 n=19 | 44× |

**故障场景（1MB 消息，33% 副本故障）**：
- 崩溃故障：PICSOU 吞吐下降 22.8%–30.5%（符合预期），仍比 ATA/OTU/LL 高 2×–8.9×
- Byzantine ACK 攻击：影响轻微，正确副本等待 u_r+1 个匹配 ACK 即可抵御虚假 ACK

**真实应用**：
| 应用 | 结论 |
|------|------|
| Etcd 灾难恢复 (DR) | PICSOU 使 Etcd 吞吐达 70 MB/s（磁盘上限），ATA/LL/OTU 受限于 WAN 带宽（50 MB/s），Kafka 因高延迟下性能下降；PICSOU 约 2× 优于 Kafka |
| 数据协调（Data Reconciliation） | 与 DR 实验类似，Kafka 存在已知高延迟 consumer 问题 |
| 区块链桥（Algorand↔ResilientDB） | PICSOU 对 RSM 吞吐影响 <15%；Algorand base 吞吐 120 blocks/s，ResilientDB ≈6000 batches/s |

---

## 六、批判性分析

**1. 微基准的代表性存疑**

论文微基准使用 "File RSM"（内存中无限速生成消息），刻意让共识不成为瓶颈。这是衡量 C3B 协议本身性能的合理设计，但论文在展示 24× 优势时并未充分强调这只是理想上界。在真实部署中，共识本身（Raft、PBFT、Algorand）往往是瓶颈，PICSOU 的端到端收益会大幅缩水——这在 Etcd DR 实验中也得到印证（实际约 2×，而非 24×）。

**2. Kafka 的比较不够公平**

论文明确承认在 Data Reconciliation 实验中 Kafka 存在"已知的高延迟 consumer 问题"，"正在修复"。在结论尚未清楚的情况下，将这组数据纳入论文并与 PICSOU 进行比较，会误导读者对 PICSOU 优势的判断。

**3. φ-list 大小需手动调优**

φ-list 是控制 Byzantine 故障恢复能力的关键参数，论文通过扫描实验确定"最优"值（256 bits）。但这个最优值与网络规模、故障率、消息大小均相关，实际部署时需要再次调优，论文未提供系统性调优指导。

**4. 延迟代价被轻描淡写**

论文承认 PICSOU 的延迟随网络规模线性增长（因轮转策略），但仅在 Blockchain Bridge 实验的脚注中提及，正文未作深入分析。对于要求低延迟的区块链或金融场景，这是重大限制。

**5. Reconfiguration 假设过于乐观**

论文假设 reconfiguration 是罕见事件，且依赖外部 membership service。对于动态成员变更频繁的 PoS 区块链（每个 epoch 节点集可能大幅变动），PICSOU 的 reconfiguration 代价（需重传未确认消息）未经充分评估。

**6. 非对称 RSM 通信的真实端到端收益有限**

Etcd DR 场景中通信是单向的（没有反向数据流），无法利用 QUACK 的全双工 piggyback 优化。论文虽然通过发送 no-op 实现 ACK，但这本身引入了额外的开销，使 PICSOU 的设计优势打折扣。

---

## 七、总结

PICSOU 将 RSM 间通信问题形式化为 C3B 原语，并借鉴 TCP 的累积 ACK 与全双工思想，设计了基于 QUACK 的高效跨集群广播协议。协议支持 CFT/BFT/PoS 等多种共识模型，在无故障情况下每消息仅发送一次且元数据开销恒定，在有故障时通过 φ-list 和副本轮转实现鲁棒恢复。微基准下 PICSOU 在大规模网络中比 ATA 快 24×，在真实 Etcd 灾难恢复场景中比 Kafka 快约 2×。主要局限在于：性能优势在有共识瓶颈的真实场景中会显著缩小；延迟随规模线性增长对延迟敏感场景不友好；动态 PoS stake 环境下的调度开销和 reconfiguration 代价尚待深入评估。
