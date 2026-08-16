---
type: paper
name: Ambulance
full_title: "Ambulance: saving BFT through racing"
authors: [Neil Giridharan, Shubham Mishra, Lorenzo Alvisi, Natacha Crooks, Benjamin Marsh, Hein Meling, Kartik Nayak, Grzegorz Prusak]
venue: OSDI
year: 2026
tags: [bft, consensus, state-machine-replication, tail-latency, blockchain]
source_pdf: "[[osdi26-giridharan.pdf]]"
source_md: "[[osdi26-giridharan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Ambulance：用协议竞速应对 BFT 节点减速（OSDI 2026）

> **原题**：Ambulance: saving BFT through racing

> **一句话总结**：传统 BFT 用 timeout 判断 leader 是否变慢，时间设短了会误切换，设长了又会一直等；Ambulance 让 leader 走两轮通信的 “sports car” lane、所有 replica 同时走三轮通信的 “truck” lane，用协议进度而不是墙上时钟决定是否进入恢复，在无减速时保持 Autobahn 的 214k tx/s 和约 205 ms latency，在 10 秒单节点暂停实验中把峰值 latency 最多降低 10.8×。

## 问题与动机

生产中的 replica 往往不是彻底 crash，而是因为 I/O contention、[[Garbage-Collection|GC]]、data synchronization 或短暂网络问题慢几秒。论文列出的 Sei、etcd 和 Neo4j 事件都属于这种 slowdown。Leader-based BFT 通常依靠 timeout 处理它：

- timeout 太激进，会把仍能工作的 leader 当成故障，触发有破坏性的 view change；
- timeout 太保守，其他 replica 就会等待慢 leader，期间没有提交进展；
- 实际部署为了少误报，timeout 常设为 RTT 的 10 倍以上，有的达到 30 秒，因此短暂 slowdown 会直接进入尾延迟。

Hedging 让 backup 在固定延迟后也开始提案，但延迟期间仍没有做可用于最终提交的工作。完全异步的 cooperative protocol 不依赖 timeout，却通常增加正常路径的通信轮数，并降低吞吐。Ambulance 想同时得到两点：正常时和 PBFT/Autobahn 一样快，leader 变慢时又接近异步协议的恢复速度。

论文把关键要求叫作 **productive waiting**：backup 在判断 leader 是否慢的同时，就先做恢复一定会需要的 non-equivocation 工作；若 leader 输掉竞速，这些工作可以接着使用，而不是从头开始。

## 系统模型与正确性边界

Ambulance 使用 `n = 3f + 1` 个 replica，最多 `f` 个 Byzantine replica。它假设有 PKI、数字签名，以及 threshold signature 的 trusted setup；攻击者很强但静态，能协调全部故障参与者，却不能破解标准密码学。Replica 之间是可靠、认证的点到点 channel，消息最终会送达；论文不限制故障 client 的数量（§3）。

一个容易误读的点是：**论文采用 asynchronous network model，不是 partial synchrony。安全性和活性都不要求已知或最终稳定的网络延迟上界。** 活性依赖最终消息送达和不可预测的 common coin；每个 recovery view 以大于 `2/3` 的概率选中已经持久化的 lane，因此以概率 1 最终终止（附录 B.2）。这是正确性结论，不是固定时间内完成的性能保证：异步 adversary 仍可让某一轮很慢。

## 关键观察 / 隐含假设

- **观察 1：可以用通信阶段数制造 leader 优势。** Leader 的 non-equivocation certificate 走两轮 all-to-all；普通 replica 的 certificate 走三轮 linear path。正常 leader 因而天然领先一个 message delay，不需要先猜一个毫秒级 timeout（§4–§5.1）。
  - **依赖假设**：一个 message-delay 的相对优势足以覆盖正常 scheduling 和网络抖动。
  - **反例**：附录 C 明确说 LAN 中差距可能太小，需要增加 dummy phase，甚至重新加入 time-based delay；所以“完全无需时间参数”取决于部署环境。
- **观察 2：竞速工作本身就是共识的第一阶段。** 所有 backup 从一开始就为自己的 lane 生成 non-equivocation certificate；leader 变慢后，恢复不必丢掉这些工作（§4）。
  - **依赖假设**：并行维护 `n` 个 replica lane 的小消息、签名和状态不会挤压 payload data path。
  - **可能失效场景**：replica 数很大、batch 很小、签名验证昂贵或控制面已经占满 CPU/network。
- **观察 3：不同 replica 不必看到同一个竞速结果。** 有的 replica 可以先看到 sports-car certificate，有的先到 cutoff；只要 certificate 规则保证相交，后者仍可接收其他 replica 的 leader commit certificate（§5.1.3）。
  - **设计含义**：协议不把“本地看到 leader 输了”当作全局事实，而是在 recovery 中带证据重新选择值。
- **观察 4：先选 recovery leader 会暴露攻击目标。** Ambulance 先让至少 `n−f` 个 lane 完成 non-equivocation 和 persistence，最后才随机选 lane；adversary 得知赢家时，提交所需工作已经完成（§5.2）。
- **假设 1：common coin 的输出不可提前预测。** 实现用 view number 的 threshold-signature shares 合成唯一签名，再以其 hash 对 `n` 取模选 lane。
  - **证据强度**：强。附录给出 safety/liveness proof；实际系统仍依赖 trusted setup、密钥管理和正确实现。
- **假设 2：Autobahn 式 data dissemination 和 pipelining 可以复用。** 论文的高 throughput 很大程度来自 Autobahn data layer，而不只是 racing agreement（§5.4–§5.5、§6.1）。

## 核心方法

### 1. Leader 的 sports-car lane

每个 view 有一个指定 leader，但 leader 同时也保留普通 replica lane。Leader 先广播 `SC-PREPARE`；每个 replica 收到后，把 `SC-PREP-VOTE` 广播给所有 replica。任何 replica 收到 `n−f = 2f+1` 个相同 vote，就形成 sports-car certificate。因为 vote 是 all-to-all，所有 replica 可以在两次 message delay 后各自形成证书（§5.1.1、图 1）。

这个 certificate 只完成 non-equivocation，还不是 commit。若某 replica 在本地 cutoff 前拿到它，就广播 `SC-COMMIT`；收齐 `n−f` 个 commit 后形成 leader commit certificate，提交 leader value，并把证书转发给其他 replica。整个正常路径是三次 message delay，与 latency-optimal PBFT 相同（§4、§5.1.3）。

### 2. 每个 replica 的 truck lane

每个 proposer `P` 同时广播自己的 `TRUCK-PREPARE`。其他 replica 只把 vote 回给 `P`；`P` 收齐 `n−f` 个 vote 后形成 truck certificate，再广播 `TRUCK-CONFIRM`。这是一条三次 message delay 的 linear path，比 sports-car certificate 慢一轮，但产生的也是可用于 recovery 的 non-equivocation proof（§5.1.2、图 2）。

每个 replica 收到 `n−f` 个不同 lane 的 truck certificate 后，本地达到 **race cutoff**。这是可以等待的最大安全数量：故障 replica 可能不响应，不能等多于 `n−f`；设得更小又会过早判断 leader 慢（§5.1.3）。

若 sports-car certificate 先到，本地支持 leader 并发送 `SC-COMMIT`；若 cutoff 先到，本地停止为 leader 发送新的 `SC-PREP-VOTE` 和 `SC-COMMIT`，进入 recovery。但它仍处理已经收到的 `SC-COMMIT`：即使自己认为 leader 输了，只要别人形成 leader commit certificate，仍会提交同一个 leader value。

### 3. Recovery 第一步：决定每个 lane 恢复什么值

每个 replica 广播 `STATUS`，带上自己是否见过 leader prepare 和 sports-car certificate。Proposer 收齐 `n−f` 个 status 后有三种情况（§5.2.1）：

1. 任一 status 带 sports-car certificate，就恢复 leader value；
2. 没有 certificate，但见过 leader prepare，则恢复自己的 truck value，并把 `n−f` 个“没有 sports-car certificate”的签名组成 no-commit certificate；之后仍需做 race exclusion；
3. 连 leader prepare 都没有，则 `n−f` 个否定签名组成 no-lock certificate，证明 sports-car certificate 不可能存在；自己的 truck certificate 可直接升级，跳过 race exclusion。

第二种情况不能直接用 truck value：一个 Byzantine proposer 可能既取得 leader value 的证书，又为自己的 lane 取得另一个证书。可选的 race-exclusion phase 用 `REC-PREPARE/REC-PREP-VOTE` 把该 lane 锁定在一个恢复值上；第三种情况已有 no-lock proof，所以省掉这轮（§5.2.2）。

### 4. Recovery 第二、三步：先持久化，再开奖

完成 non-equivocation 后，proposer 广播 `REC-CONFIRM`。Replica 验证后返回 `REC-CONFIRM-VOTE`；proposer 收齐 `n−f` 个 vote，形成 recovery-confirm certificate 并广播 `FINISH`。Replica 收到 `n−f` 个不同 lane 的 `FINISH`，才进入 election（§5.2.2）。

每个 replica 对 view number 广播 threshold-signature share；收齐 `2f+1` 份后合成唯一签名 `σ`，计算 `hash(σ) mod n`。如果选中的 lane 已在收集到的 `n−f` 个 lane 中完成 persistence，就提交；否则进入下一 view。由于开奖前至少 `n−f` 个 lane 已准备好，每轮成功概率为 `(n−f)/n > 2/3`（§5.2.3、附录 B.2）。

后续 view 不再重跑正常竞速，而是执行 retry protocol：先收集上一 view 是否可能已提交的证据，再运行 race exclusion、persistence 和随机 election（§5.3、附录 A）。论文概览给出的 expected latency 是：正常情况 3 次 message delay；leader 在 race 中没有提案时 recovery 为 9.5 次，已经提案时为 10.5 次。§6 的 1 秒实验把“从进入 recovery 到第一 view 完成”的路径另记为 7 次 message delay，两种数字的起点不同，不应直接混用。

### 5. Multi-shot、motorization 与实现

单 slot 协议在生产中会 pipeline 多个 slot，并限制同时进行的 slot 数 `k`，避免 slow slot 无限积压。Motorization 直接采用 Autobahn data layer：proposal payload 在独立 data lane 中提前传播，agreement 主要处理引用和小 certificate（§5.4–§5.5）。

Prototype 用 Rust 写在 Autobahn 开源代码库上，网络是 Tokio TCP，payload 用 [[RocksDB|RocksDB]] 落盘，认证签名是 ed25519-dalek。它实现 §5.6 的工程优化，但**没有实现普通协议 vote 的 signature aggregation**。Threshold signature 只用于 lane election；把其他 vote 也聚合、将通信量降低约 `n` 倍，是作者提出的大规模优化，不是本次评测已经验证的能力（§5.6、§6）。

## 设计取舍

- **备用工作换快速恢复。** 所有 replica 从一开始运行自己的 lane，不再空等 timeout；代价是正常情况也要发送 truck 消息、验证签名并保存更多 certificate。
- **协议进度换墙上时间。** 对 WAN slowdown 不需调毫秒阈值，但“领先一个 message delay”在 LAN 可能不足；dummy phase 或 time delay 会重新带来参数。
- **二次消息量换短 leader path。** Sports-car lane 用 all-to-all vote，让每个 replica 两轮内拿到 certificate；replica lane 用多一轮换 linear communication。
- **先做 `n−f` 条 lane 再随机选一条。** 这样 adversary 不能提前瞄准赢家，但本轮可能选中尚未完成的 lane，需要重试；延迟有概率尾部，不是固定上界。
- **继承 data layer 换可比性。** Ambulance 和 Autobahn 的 common-case 比较很干净；与使用 Batched HotStuff data layer、sequential/chained consensus 的 ParBFT2、SMVBA 比，结果混入了 data dissemination 和 pipelining 差异。
- **多类 certificate 换异步 safety。** No-lock、no-commit、recovery non-equivocation、recovery confirm、election 等状态让证明成立，也增加实现、审计和运维诊断难度。

## 实验设计

§6.1–§6.2 的 AWS testbed 是 4 个 replica，分布在 `us-west-1`、`us-west-2`、`us-east-1`、`us-east-2`，区域间 RTT 为 20–72 ms。每台是 **m6a.4xlarge**（16 vCPU、64 GB RAM、30 GB gp3 SSD、12.5 GB/s network），不是 production 使用的 m6i.12xlarge。Client 与 replica 同 region，发送 512-byte no-op transaction；统一 batch 500 KB/1,000 transactions，leader round-robin。每个 common-case load 点运行 60 秒。

Baseline 是 Autobahn、ParBFT2 和 SMVBA。Ambulance/Autobahn 使用相同 Autobahn data layer 和 PBFT-style multi-shot pipelining；ParBFT2/SMVBA 使用 Batched HotStuff data layer，前者采用 chained progress，后者和 ParBFT2 pessimistic path 都顺序运行 consensus instance。因而不同 baseline 的峰值 throughput 不能解释为 agreement protocol 的纯差异。

Slowdown 实验在 `t=3 s` 把一个 replica 的全部处理暂停 1/2/5/7/10 秒。每个点是 5 次 run、500 ms 窗口内 latency 的 median。为减少排队，Ambulance/Autobahn load 为 100k tx/s，ParBFT2/SMVBA 为 10k tx/s；Autobahn 每种时长分别测试低于和高于 slowdown 的 timeout。

ParBFT2 的 optimistic→pessimistic 切换实现有 bug，所以论文**只运行它的 pessimistic path，而且没有注入 slowdown**，hedging delay 设为 75 ms。这个结果反映 pessimistic slowdown latency，不反映真实切换或 common case；不能把其 1.58 s 曲线当成完整 ParBFT2 在同一故障下的端到端结果（§6.2）。

## 实验与结果

- **正常路径与 Autobahn 基本相同。** `n=4` 时，Ambulance 和 Autobahn 峰值 throughput 都是 214k tx/s，latency 为 205 ms 和 203 ms。ParBFT2 是 167k tx/s/382 ms，SMVBA 是 50.6k tx/s/462 ms（§6.1、图 5）。作者把前两者的瓶颈定位为 data-layer serialization/deserialization；因此该实验说明 racing metadata 在这个配置下没有可见吞吐税，不代表 lane overhead 在更大 `n` 下也可忽略。
- **1–2 秒暂停时，峰值延迟为 510.4/633.4 ms。** 1 秒时，相对 Autobahn 的 500 ms/2 s timeout 分别低 1.6×/1.7×，相对 SMVBA/ParBFT2 低 1.4×/3.1×；2 秒时，相对 Autobahn 的 1 s/5 s timeout 低 2.2×/3.0×，相对 SMVBA/ParBFT2 低 1.2×/2.5×（§6.2、图 7–8）。这些倍数高度依赖 Autobahn timeout 的选择。
- **5–10 秒暂停时，Ambulance 不按暂停时长线性变慢。** 5/7/10 秒 slowdown 的峰值 latency 为 787.7/810/932 ms，相对 Autobahn 分别改善 3.1×–6.3×、6.9×–8.6×、7.9×–10.8×。更长暂停会增加 recovery 需要多个 view 的概率，但不会让系统一直等满 slowdown（§6.2、图 9–11）。SMVBA 在长 slowdown 下与 Ambulance 接近；ParBFT2 维持约 1.58 s，但受上述实验限制。
- **Production tail 改善而 median 持平。** Sei 部署有 40 个 replica，分布于 20 个 AWS region，每台为 m6i.12xlarge（48 vCPU、192 GB RAM、18.75 GB/s network）。24 小时同 workload、180k tx/s load、220k tx/s peak capacity 下，slowdown 约每 1,000 slot 一次；Ambulance 与 2 秒 timeout 的 Autobahn median 为 244/242 ms，P99 为 662 ms/1.27 s，尾延迟改善 1.92×（§6.3、图 6）。
- **Proof 覆盖异步 safety 和概率 1 liveness。** 附录 B 证明同一 slot 不会提交冲突值；若某正确 replica 终止，会转发可验证 termination certificate；每个 view 至少以 `(n−f)/n > 2/3` 概率选中已持久化 lane，所以未终止概率按几何尾下降到 0。证明依赖可靠认证 channel、quorum/签名正确、static adversary 和 common coin，不覆盖实现 crash、磁盘损坏或错误配置。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| Racing 不牺牲 Autobahn 级 common-case 性能 | §6.1、图 5：214k tx/s、205 vs 203 ms | `n=4`、WAN、500 KB batch；共用 Autobahn data layer | 强 |
| 不等 timeout 可显著降低 slowdown 峰值延迟 | §6.2、图 7–11：1–10 s pause 下改善最高 10.8× | 单 replica sleep；收益随 baseline timeout 变化 | 强 |
| 在 production workload 中降低 P99 | §6.3、图 6：662 ms vs 1.27 s，median 持平 | 单个 Sei 部署、24 小时、Autobahn 2 s timeout | 强 |
| 异步模型下保持 safety 并以概率 1 终止 | §3、附录 B 的 Theorem 1/2 | `n=3f+1`、static adversary、可靠认证 channel、trusted setup/common coin | 强 |
| 普通 lane 的额外开销可忽略 | §6.1：`n=4` 时 bottleneck 在 data layer | 未扫描 replica 数、batch、签名成本；aggregation 未实现 | 中到弱 |

## 批判性分析

### 论证链条

论文最强的地方不是简单“去掉 timeout”，而是把 slowdown detection 和共识必做的 non-equivocation 合并：leader 正常就走三轮短路径；leader 慢时，backup 已经拿到 truck certificate。Recovery 又把传统的“先选 leader”反过来，先准备多条 lane、最后随机开奖。这两步分别回答了“等待时做什么”和“异步 adversary 会盯住谁”，设计与 proof 对得上。

性能证据也呈现了正确边界。Ambulance 与 Autobahn 共用代码库和 data layer，因此 common-case 214k tx/s 的对照可信。Slowdown sweep 同时展示了低 timeout 和高 timeout，说明 Autobahn 的两难，而不是只挑一个坏参数。不过论文摘要式的最大 10.8× 主要来自长 slowdown 与保守 timeout；SMVBA 在长 slowdown 已接近 Ambulance，说明创新的重点是同时保住 common-case throughput，而不是 recovery latency 全面胜过异步协议。

### 假设压力测试

实验只让一个 replica 执行 `sleep`，没有模拟 Byzantine replica 对不同 peer 选择性延迟、多个共同故障域、packet loss/reordering、磁盘 stall 或网络非对称。协议 proof 覆盖 Byzantine message behavior，但性能曲线没有覆盖 adversarial scheduling；攻击者可迫使多次 election 失败，安全性仍在，尾延迟却可能比当前图更长。

One-message-delay head start 也不是普适常数。WAN RTT 20–72 ms 时足够清楚，LAN 或 colocated validator 中，各 replica 启动 slot 的微小偏差可能让正常 leader 落后。附录建议 dummy phase 或 time-based delay，证明部署仍要选择 bias 强度；只是 dummy phase 同时产生 recovery certificate，比纯 sleep 更有用。

### 实验可信度

四个 AWS region、1–10 秒 sweep、两档 Autobahn timeout、相同 data layer，以及 40-replica/20-region production run，覆盖比单一 microbenchmark 强。论文也主动披露 ParBFT2 switching bug，这是重要透明度。

但 baseline 可比性并不对称。ParBFT2 没有真正经历 slowdown 和 path switch，SMVBA/ParBFT2 还使用不同 data layer 与 sequential/chained execution；它们的 throughput/latency 差距不能完全归因于 timeout、hedging 或 async。Production 只有 24 小时同一 workload，没给 slowdown 类型、严重度分布、P99.9 或多日重复；“约每千 slot 一次”也不能说明真实事件是否与 `sleep` 相似。

### 系统性缺陷

Ambulance 为每个 slot/view 保存多 lane、多阶段 certificate，再与 pipeline 上限 `k`、RocksDB durability 和 data layer 交互。论文没有系统测量正常路径的控制消息字节数、signature verify CPU、certificate memory/disk、recovery state cleanup 或更大 `n/f` 的扩展性；普通 vote aggregation 又没有实现。`n=40` production 结果很好，但没有拆分这些开销。

工程恢复也不是协议终止证明。Process crash 后如何重建 lane 状态、certificate 何时 durable、client retry 是否重复执行、state transfer、membership/key rotation 和 rolling upgrade 如何兼容新的消息类型，正文没有展开。错误实现 no-lock/no-commit 或跨 view 清理状态会直接威胁 safety，值得 model checking 和 fault campaign。

## 局限与后续工作

- **局限 1**：Performance fault injection 仅为 `n=4` 中一个 replica sleep，没有 correlated、Byzantine-selective、loss/reorder 或磁盘 slowdown。
- **局限 2**：最大 10.8× 强依赖 Autobahn timeout；ParBFT2 因 bug 未测试真实 optimistic→pessimistic switch。
- **局限 3**：Common-case baseline 使用不同 data layer/pipelining；只有 Ambulance 与 Autobahn 接近纯 agreement A/B。
- **局限 4**：没有扫描 `n/f`、小 batch、签名 CPU 和 control-message bandwidth；protocol-vote aggregation 未实现。
- **局限 5**：LAN 可能需要 dummy phase 或 time delay，timer-free 的部署结论并非无条件成立。
- **局限 6**：Production 只有单 deployment 的 24 小时结果，缺少事件分类、P99.9、跨天重复和恢复操作证据。
- **后续工作 1**：在 `n=4..100` 下扫描 batch/RTT，逐项报告 truck lane bytes、signature verification、certificate memory、goodput 和 tail latency。
- **后续工作 2**：注入多 replica GC/disk stall、方向性 loss、partition、Byzantine selective delay 和连续 view failure，报告 recovery view 分布而非只报 peak。
- **后续工作 3**：修复并端到端运行 ParBFT2 switch，用相同 data layer/pipelining 构建 timeout、hedging、async agreement 的 controlled comparison。
- **后续工作 4**：对 dummy-phase 数量和 time bias 做在线校准，测 false-slow rate、正常 latency 与 slowdown recovery 的 Pareto curve。
- **后续工作 5**：做 crash/restart、RocksDB corruption、state transfer、membership/key rotation 和 rolling-upgrade fault campaign，并用 model checker 覆盖跨 view certificate 状态。

## 相关

- **相关概念**：Byzantine fault tolerance、state-machine replication、asynchronous consensus、common coin、hedging、protocol racing、[[Garbage-Collection]]
- **相关系统**：Autobahn、ParBFT2、SMVBA、PBFT、HotStuff
- **同会议**：[[OSDI-2026]]
