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
last_reviewed: 2026-07-30
---

# 用协议竞速抵御 BFT Slowdown（OSDI 2026）

> **原题**：Ambulance: saving BFT through racing

> **一句话总结**：timeout 过小会误触发破坏性 view change、过大则让 BFT 在 slow leader 上空等；Ambulance 让 leader 走较短“sportscar lane”、其他 replica 同时走可提交工作的“truck lane”，以 protocol step 而非 wall clock 决胜，达到 Autobahn 的 214k tx/s/约 205 ms common case，同时在 slowdown 下将峰值 latency 改善 1.6–3.0×。

## 问题与动机

production BFT/SMR 的 replica 常因 I/O contention、[[Garbage-Collection|GC]]、data sync 或 network blip 变慢数秒而非直接 crash。leader-based protocol 通常用 timeout 发现异常：aggressive timeout 在 leader 仍活着时触发 competing proposal/view change，conservative timeout 则让系统数秒不做有用工作。geo deployment 常把 timeout 配为 RTT 的十倍甚至 30 秒。

hedging 让多个 proposer staggered 参与，减少 destructive takeover，但后继 proposer 仍先等固定 delay；asynchronous/cooperative BFT 无需 timeout，却付出较高 common-case message delay 和较低 throughput。Ambulance 试图同时满足 cooperative（并发 proposal 不互相破坏）与 productive（等待期间做的工作可用于 commit）。

## 关键观察 / 隐含假设

- **观察 1**：slowdown detection 不应是 leader 与 clock 的比赛；wall-clock cutoff 既需要精确 tuning，又让 backup idle（§1–2）。
  - **依赖假设**：protocol message progress 比 elapsed time 更稳定地反映 leader 相对速度。
  - **可能失效场景**：network 对不同 lane 非对称、scheduler 优先级让 backup protocol progress 同样受阻，或 adversary 有意操纵 message order。
- **观察 2**：可通过让 leader proposal protocol step 更少，给它结构性 head start；正常时 leader 胜，慢时 backup 已完成的工作接管（§3–5）。
  - **依赖假设**：额外 backup work 的 bandwidth/CPU 不伤害 leader common case，且 quorum certificate 能消解不同 replica 对胜者的观察。
  - **可能失效场景**：CPU/network 已饱和、小 batch 或 validator 数增大后 background lane overhead 主导。
- **假设 1**：partial synchrony/BFT 标准边界 `n ≥ 3f+1` 成立，cryptographic vote/certificate 不被伪造，slow replica 数不超过容错边界。
  - **证据强度**：强。附录给出 safety/liveness proof；实现评测不等于任意网络模型。
- **假设 2**：Autobahn-style data dissemination 可与 agreement race 解耦并维持高 throughput。
  - **证据强度**：强。实现复用其 data layer 并在 AWS/production 对比。

## 核心方法

每个 view 同时有快的 leader “sportscar” lane 与较慢但不等待 timer 的 backup “truck” lane。leader 路径有更少 sequential protocol steps，正常网络下自然先到达 race cutoff；backup replica 从一开始就交换 proposal/vote，其 certificate 若 leader 变慢便成为可提交的恢复工作，而不是超时后才重新开始。

replica 可能对 leader 是否先过 cutoff 看法不同。Ambulance 用 signed prepare/confirm certificate 和 race-cutoff certificate 约束 lane election，使 conflicting value 的 quorum 必须相交于正确 replica；recovery 收集 status 并选择已获得最高级 certificate 的 value，避免某些 replica 已在 sportscar commit、另一些切到 truck 时破坏 safety。

multi-shot protocol 继承 Autobahn 的 data lane/motorization：batch 独立可靠传播，agreement 主要确认 digest，多个 lane pipeline 充分利用带宽。threshold signature 压缩 quorum metadata；retry/view change 仍用于真正无法完成的情况，但常见 slowdown 不再由 timeout 触发。

## 设计取舍

- **持续 backup work 换快速恢复**：消除 idle hedge delay，却增加 normal-case message/crypto/CPU 开销；高吞吐实验显示网络仍由 payload 主导。
- **协议 step 充当相对时钟**：免除 timeout tuning，但 latency 受最慢必要 message path 与 adversarial scheduling 影响。
- **复用 Autobahn data layer**：隔离 agreement innovation并获得成熟 throughput，限制结论到类似 lane-based dissemination。
- **certificate complexity**：保证 race 分歧时 safety，显著增加 protocol state、实现验证与 operator debugging 难度。

## 实验与结果

- AWS 多 region 部署使用 m6i.12xlarge、30 GB gp3、12.5 GB/s network，512-byte no-op transaction、500 KB baseline batch，与 Autobahn、ParBFT2、SMVBA 对比（§6）。
- common case 中 Ambulance 与 Autobahn 峰值均为 214k tx/s，latency 约 205 ms；ParBFT2 为 167k tx/s/382 ms，SMVBA 为 50.6k tx/s/462 ms（§6.1）。
- 注入 1/2/5/7/10 秒单 replica slowdown 时，Ambulance 峰值 latency 相对 Autobahn 改善 1.6–3.0×，相对 ParBFT2 改善 1.7–3.1×（§6.2）。
- 一组 case 中 Ambulance 峰值 796.1 ms，比 Autobahn 的 timeout-sensitive peak 改善约 1.7×；另一 case 为 633.4 ms，比 SMVBA 766 ms 好 1.2×、比 ParBFT2 好 2.5×（§6.2）。
- 24 小时 production run、约 180k tx/s load（系统 peak 220k）中，median 与 Autobahn 近似（244 vs 242 ms），P99 为 662 ms vs 1.27 s，改善 1.92×（§6.2、图 6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| protocol race 不牺牲 common-case BFT 性能 | §6.1：214k tx/s、205 ms，与 Autobahn 持平 | AWS geo、512 B tx、500 KB batch | 强 |
| slowdown 下优于 timeout/hedging/asynchronous baseline | §6.2：峰值 latency 低 1.6–3.1× | 单 replica sleep 1–10 s、设定 timeout | 强 |
| production tail latency 改善 | §6.2、图 6：P99 662 ms vs 1.27 s | 24 小时、180k tx/s、单一 production workload | 强 |
| lane disagreement 仍保证 safety/liveness | §5 与附录 lemmas | partial synchrony、quorum/crypto assumptions | 强 |

## 批判性分析

### 论证链条

论文准确指出 timeout/hedging 的无效等待，再让 backup work 同时满足 fault detection 与 recovery，设计新颖且 proof/implementation/evaluation 相互支撑。common-case 与 Autobahn 等同说明 productive race 没有明显 throughput tax；最大 slowdown 收益仍取决于 baseline timeout，故应优先看跨 1–10 秒 sweep 而非单个倍数。

### 假设压力测试

实验主要将一个 replica `sleep`，比真实 correlated GC、network asymmetry、packet reorder 与 Byzantine equivocation 简单。若 leader 与部分 backup 处于共同故障域，所有 lane 都慢；若攻击者故意让不同 quorum 观察不同 race order，会增加 recovery certificate 交换。较大 validator set 和昂贵 signature 也可能使 backup lane 从“几乎免费”变成 bottleneck。

### 实验可信度

强 baseline、geo AWS、production run、throughput/median/P99 和多 slowdown duration 使性能证据完整，附录 proof 提供 correctness。缺少不同 `n/f`、payload、bandwidth、loss/reordering 与 multi-fault 的大矩阵；production workload 由相关团队部署，缺少更长事件统计和 incident 分类。

### 系统性缺陷

协议 state/certificate/lane 数增加实现 attack surface，operator 需解释究竟哪个 race/certificate 阻塞。论文未充分量化 normal-case backup bandwidth、CPU、signature verification 与 storage durability；client retry、membership change、state transfer 和 rolling upgrade 与新 certificate format 的交互也不是重点。

## 局限与后续工作

- **局限 1**：主要 fault injection 为单 replica slowdown，correlated/Byzantine slowdown 覆盖有限。
- **局限 2**：validator 数、signature cost 与 race overhead 的 scaling 未充分展开。
- **局限 3**：依赖 Autobahn data layer，其他 BFT architecture 的移植成本未知。
- **后续工作 1**：扫描 `n=4..100`、多 slow/Byzantine replica、asymmetric loss/reorder，报告 safety check、P99 与 backup bandwidth。
- **后续工作 2**：与 adaptive timeout/hedging 做等资源对比，将 CPU、network 和 crypto cost 一并计入 goodput。
- **后续工作 3**：对 membership change、rolling upgrade、state transfer 和 crash recovery 做 Jepsen-style fault campaign，验证 multi-shot durability。

## 相关

- **相关概念**：[[Byzantine-Fault-Tolerance]]、[[State-Machine-Replication]]、[[Partial-Synchrony]]、[[Hedged-Requests]]
- **同类系统**：[[Autobahn]]、[[ParBFT]]、[[SMVBA]]
- **同会议**：[[OSDI-2026]]
