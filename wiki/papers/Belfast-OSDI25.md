---
type: paper
name: Belfast
full_title: "Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering"
authors: [Shreesha G. Bhat, Tony Hong, Xuhao Luo, Jiyu Hu, Aishwarya Ganesan, Ramnatthan Alagappan]
venue: OSDI
year: 2025
tags: [shared-log, speculative-execution, distributed-systems, ordering, low-latency]
source_pdf: "[[osdi25-bhat.pdf]]"
source_md: "[[osdi25-bhat]]"
---

# Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering (OSDI 2025)

> **一句话总结**：Belfast 用「fix-ante ordering」让 shared log 的 shard 在全局协调前就能准确预测 record 位置，把下游计算与 shared log 协调 overlap，相比 Scalog 把 delivery 延迟降 3×、端到端延迟降 1.6×。

## 问题

现代数据驱动应用（高频交易、实时搜索、欺诈检测、IoT 分析）需要一个同时满足以下属性的 shared log：总序、弹性（动态加减 shard）、灵活数据放置、可扩展、**低端到端延迟**。Scalog 这类 durability-first 架构用「先写 shard、再批量同步到 sequencing layer 定序」解决前几个需求，但因此付出了高 delivery 延迟的代价：record 持久化后还要等 sequencer 收齐各 shard 报告、算全局 cut、做 Paxos 容错，才能交付下游处理——对 ms 级敏感的应用是致命的。

Corfu 这类 order-first 的设计 delivery 延迟同样高，还顺带失去了弹性和放置灵活性。

## 核心方法

作者观察到：如果能在全局协调**之前**就让 shard 把 record 用预测的位置交付给下游，下游计算就能与协调 overlap，协调完成时计算也差不多完成，相当于「白拿」全局协调时间。关键是预测要准，否则回滚代价抵消收益。

**SpecLog 抽象**保持 Scalog 一样的 API，但 delivery 时多带一个「是否 speculative」的 bit；之后 sequencer 算出 actual cut 时发一个 confirm 或 fail。

**Fix-ante ordering** 是让预测准确的关键机制。不让各 shard free-will 汇报自己 durable 的数量，而是**预定好**一串 global cut 序列 P1, P2, ...，每个 cut 给每个 shard 分配 quota（本轮必须汇报的 record 数）。shard 通过填 no-op 或 delay 来精确满足 quota，于是每个 shard 都能根据别人的 quota 精确算出自己 record 在全局序中的位置——无需等 sequencer。只有整个 shard 全死这种极少数情况会导致 misspeculation，此时 SpecLog 失败但保持正确性。

**Belfast 实现**要解决几个现实问题：

- **Rate-based quota**：按 shard 实际 ingestion rate 设 quota，避免 no-op 过多或 delay 过多。
- **Lag-fix 处理突发**：某 shard burst 时立即多次汇报，sequencer 发现滞后的 shard 后主动通知后者加频率汇报（必要时填 no-op），避免 actual cut 被卡住。
- **Speculation lease window**：长期 rate 变化时必须改 quota；为防止部分 shard 用旧 cut、部分用新 cut 导致 misspeculation，把 W 个 cut 打包成一个租期窗口，shard 统一在窗口边界切换。加减 shard 也只在窗口边界发生。
- Straggler 处理：sequencer 可动态把某 shard 从部分 cut 里剔除。

## 关键结果

- Delivery latency 比 Scalog 早 **~3×**。
- 端到端延迟降 **1.6×**（下游计算量不同时都有收益）。
- 10 shard 时 append 延迟开销仅 **5.8%**。
- 三个应用案例（入侵检测、欺诈监控、高频交易）端到端延迟降 **1.4×–1.6×**。
- 保持 Scalog 的弹性、灵活放置、可扩展；能无停机加减 shard。

## 相关

- **相关概念**：Shared-Log、Total-Order-Broadcast、Speculative-Execution、Paxos
- **同类系统**：Scalog、Corfu、Boki、FlexLog、Kafka
- **同会议**：[[OSDI-2025]]
