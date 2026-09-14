---
type: paper
name: Ambulance
full_title: Ambulance: saving BFT through racing
authors: [Neil Giridharan, Shubham Mishra, Lorenzo Alvisi, Natacha Crooks, Benjamin Marsh, Hein Meling, Kartik Nayak, Grzegorz Prusak]
venue: OSDI
year: 2026
tags: [bft, consensus, slowdown-tolerance, fault-detection, state-machine-replication]
source_pdf: "[[osdi26-giridharan.pdf]]"
source_md: "[[osdi26-giridharan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-24
---

# 让 BFT 在慢故障下继续前进（OSDI 2026）

> **原题**：Ambulance: saving BFT through racing

> **一句话总结**：传统 BFT 用超时让 leader 与时钟竞速，慢 leader 会让系统空等；Ambulance 让 leader 与其他副本执行不同长度的协议路径竞速，把检测慢故障期间的工作直接转化为提交准备，在正常情况下保持 3 个消息延迟，并在 1–10 秒单副本 slowdown 下将峰值延迟控制在 510.4–932 ms。

## 问题与动机

实用 BFT 状态机复制（SMR）通常依赖 leader 推进协议。leader 变慢时，超时机制面临两个冲突：超时过短会误触发 view change，超时过长则让所有副本空等。生产系统中的超时通常是秒级，论文列举了 Sei 的 2 秒、Microsoft CCF 的 5 秒、Neo4j 的 7 秒和 Diem 的 30 秒配置。

已有 hedging 方案让多个副本分阶段提议，但仍需等待人为设定的 hedging delay；异步 BFT 能较快绕过慢 leader，却在正常路径承担更高延迟和更低吞吐。论文的目标是同时保留 leader-based BFT 的正常性能和异步协议的慢故障韧性。

## 关键观察 / 隐含假设

- **观察 1：超时检测既具有破坏性，也不产生有用工作。** 超时可能在旧 leader 仍存活时触发竞争性提议；保守超时则让系统在检测期间停顿。论文 §2.2 将 timeout 与 hedging 都归为依赖时间等待的机制。
  - **依赖假设**：慢故障会造成单个副本持续落后，但多数正确副本仍能继续处理消息。
  - **可能失效场景**：若网络对不同副本造成长期、非对称的消息延迟，协议步骤进度未必能可靠区分节点变慢和路径变慢。
- **观察 2：非冲突（non-equivocation）和持久化本来就是提交所需的工作。** 因此，检测阶段可以执行这些步骤，而不必做无意义的等待。leader 的 sports-car certificate 需 2 个消息延迟，普通 replica lane 的 truck certificate 需 3 个消息延迟（§5.1）。
  - **依赖假设**：非慢 leader 的协议处理速度足以稳定地先于 `n-f` 个 truck certificates 完成。
  - **可能失效场景**：节点负载、网络抖动或副本数量变化导致两条路径的结构性差异不足时，可能增加误判或 recovery 频率。
- **假设 1：异步网络下，随机选出的 lane 能在选举时点之后避免被攻击。** 论文把 lane election 延后到至少 `n-f` 条 lane 完成持久化之后，并用 threshold signature 的哈希值选 lane（§5.2.3）。
  - **证据强度**：强；安全性和选举唯一性有形式化证明，但生产环境中的随机性、实现和攻击成本仍需独立审计。

## 核心方法

Ambulance 为每个 slot 设置多个 proposal lane。leader lane 使用较短的 all-to-all 交换生成 sports-car certificate；每个 replica lane 使用较慢的线性 truck certificate。leader 只需在 `n-f` 个 truck certificates 形成前完成自己的 certificate，就被视为赢得 race。这个 cutoff 让正常 leader 获得结构性优势，同时避免固定 hedging delay。

race 期间的 truck certificate 不是废弃工作。leader 输掉 race 后，副本直接把自己的 lane 证书带入 recovery。恢复过程先交换 STATUS，判断 leader 的值是否可能已经提交；若存在 sports-car certificate，所有 lane 必须恢复 leader 的值，否则优先恢复本 lane 的 truck certificate（§5.2.1）。

恢复随后执行可选的 race-exclusion 和 persistence。前者阻止 Byzantine replica 在 leader lane 与自己的 truck lane 之间制造跨 lane 冲突；若已证明 leader 不可能形成 sports-car certificate，则可跳过。persistence 阶段生成 recovery confirm certificate，确保候选值在提交后仍能存活。

当至少 `n-f` 条 lane 完成持久化后，副本才进行 lane election。每个副本广播 view number 的 threshold-signature share，收集 `2f+1` 份后得到唯一签名，并计算 `hash(σ) mod n` 作为赢家。赢家若已完成持久化即可提交，否则进入下一 view。该顺序避免网络对预先知晓的 winner 进行定向阻断。

多 slot 场景沿用 [[Autobahn]] 的 pipelining 和 motorization data layer，把数据传播与共识元数据分离。论文实现了 Rust 原型，使用 Tokio、RocksDB 和 ed25519-dalek。

## 设计取舍

- **正常路径的结构性偏置换取恢复复杂度。** leader 使用两步 all-to-all，普通 lane 使用三步线性交互，因此正常路径接近 PBFT；代价是 recovery 要处理 lane 间的 certificate、no-commit/no-lock 证明和随机选举。
- **随机延后选 leader 换取抗定向攻击能力。** recovery 先让多个 lane 完成提交准备，再选 winner；若随机选中尚未准备好的 lane，协议必须重试并进入下一 view。
- **线性投票减少通信开销但增加消息延迟。** §5.6 提供 all-to-all voting 选项以降低 recovery latency；大型 `n` 下还可用 threshold signature 压缩协议投票，但原型没有实现该优化。
- **依赖 Autobahn data layer 获得吞吐。** 这使 Ambulance 的吞吐结果与共识设计解耦；若部署无法采用该数据层，结论不能直接外推。

## 实验与结果

- 在 AWS EC2 的 4 节点、四个区域、512-byte no-op transaction 工作负载下，Ambulance 峰值吞吐为 214k tx/s，与 Autobahn 的 214k tx/s 相同；延迟为 205 ms，Autobahn 为 203 ms（图 5，§6.1）。
- 同一设置下，ParBFT2 峰值为 167k tx/s、延迟 382 ms；SMVBA 为 50.6k tx/s、462 ms。Ambulance 的正常路径为 3 个消息延迟，而 ParBFT2 和 SMVBA 分别为 5 和 6 个消息延迟（§6.1）。
- 单副本 slowdown 下，1 秒和 2 秒注入实验的峰值延迟分别为 510.4 ms 和 633.4 ms；相较采用生产配置超时的 Autobahn，分别低 1.7× 和 3.0×（图 7–8，§6.2）。
- 5、7、10 秒 slowdown 下，Ambulance 峰值延迟为 787.7、810、932 ms；相较 Autobahn 的改善最高达到 10.8×。但这些实验通过暂停一个副本模拟 slowdown，不能覆盖所有 I/O、网络和 GC 形态（图 9–11，§6.2）。
- Sei 的 40 节点、20 个 AWS 区域、24 小时生产部署中，Ambulance 与 Autobahn 的中位延迟分别为 244 ms 和 242 ms；P99 分别为 662 ms 和 1.27 s，降低 1.92×（图 6，§6.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Ambulance 在正常负载下保持 timeout-based BFT 的性能 | 214k tx/s、205 ms，对比 Autobahn 的 214k tx/s、203 ms（图 5，§6.1） | 4 节点、AWS 四区域、512-byte no-op、共享 data layer | 强 |
| protocol-rigged racing 能快速绕过慢 leader | 1–10 秒 slowdown 的峰值延迟为 510.4–932 ms，明显低于多数 Autobahn 配置（图 7–11，§6.2） | 单副本 sleep 注入；ParBFT2 主要以 pessimistic path 测试 | 中 |
| 生产 tail latency 得到改善且正常延迟不变 | 40 节点跨 20 区域部署中，P99 从 1.27 s 降至 662 ms，中位数近似相同（图 6，§6.3） | Sei workload，24 小时，约每千 slot 一次 slowdown | 中 |
| recovery 中的随机 lane election 同时提供一致性和不可预测性 | threshold signature 唯一性、选举规则及安全性证明（§5.2.3、附录 §B） | 依赖 PKI、threshold-signature trusted setup 与异步网络模型 | 强 |

## 批判性分析

### 论证链条

论文的逻辑链条较完整：生产 slowdown 使固定 timeout 失效；hedging 仍需等待；非冲突和持久化是提交必需步骤；把这些步骤放进 race 可让检测工作直接服务于 recovery。正常路径和 slowdown 路径的消息延迟分析与实验方向一致。

但“leader 一定在 cutoff 前获胜”的直觉依赖于两步与三步协议的实现成本差异。网络延迟、CPU 调度和签名处理可能让消息延迟差异被噪声覆盖。论文展示了 AWS 区域实验和生产 CDF，却没有系统测量误判率、race winner 随负载变化的分布，或 cutoff 参数的敏感性。

### 假设压力测试

实验只暂停单个 replica 的全部处理。真实 slowdown 可能只影响 RocksDB fsync、数据同步、NIC 或某条网络路径；这些故障可能使副本仍能完成部分协议步骤，导致 lane 进度与“节点整体变慢”不一致。论文的异步模型保证安全与最终活性，但没有证明在任意现实 slowdown 分布下延迟都不随故障持续时间增长。

生产实验使用 40 节点，但主要报告一条 24 小时 CDF，缺少不同 `n`、不同 fault fraction 和不同 batch/pipelining 参数的扩展曲线。论文也没有比较 recovery 期间的网络带宽峰值、CPU 签名开销和 RocksDB 写放大。

### 实验可信度

Autobahn 是较强且共享 data layer 的对照，适合检验共识设计的正常路径差异。SMVBA 与 ParBFT2 的 data layer 和 pipelining 不同，因此吞吐比较混合了共识与数据传播差异。尤其 ParBFT2 的 slowdown 实验因 optimistic–pessimistic switching bug 只运行 pessimistic path，作者已说明其不能代表完整 common-case 行为。这降低了与 hedging 方案的端到端比较强度。

### 系统性缺陷

Ambulance 引入多个并行 lane、certificate 类型和跨 lane 排除规则，代码和运维状态明显比单 leader 协议复杂。论文给出了安全性证明，但未报告故障恢复、证书存储、日志重放和线上可观测性成本。随机选举若命中未完成 lane 会触发新 view；在高丢包或多副本慢的场景下，重试次数和尾延迟需要单独测量。

## 局限与后续工作

- **局限 1：slowdown 模型较窄。** 当前主要使用暂停单副本模拟故障，尚未覆盖局部 I/O、逐步退化、网络方向性丢包和多个副本同时变慢。
- **局限 2：参数与规模边界未充分展开。** cutoff、pipelining 参数、lane 数量及 `n` 增大后的消息和证书开销缺少完整敏感性分析。
- **后续工作 1：测量 race 误判。** 在真实 RTT 抖动、CPU jitter 和局部网络故障下统计 leader 输掉 race 的比例、恢复 view 数和额外带宽。
- **后续工作 2：评估多故障组合。** 在最多 `f` 个副本以不同方式变慢时，分别测量 P50/P99、恢复成功率、lane election 重试次数和持久化开销。
- **后续工作 3：验证实现复杂度。** 对比 all-to-all 与线性 recovery、普通签名与 threshold signature，在 4、40 及更大副本规模下报告 CPU、内存、网络和故障注入后的恢复时间。

## 相关

- **相关概念**：[[Byzantine Fault Tolerance]]、[[State Machine Replication]]、[[Asynchronous BFT]]、[[Threshold Signature]]
- **同类系统**：[[Autobahn]]、[[ParBFT]]、[[SMVBA]]、[[HotStuff]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[Ambulance-vs-Autobahn]]
