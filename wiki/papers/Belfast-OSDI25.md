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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering (OSDI 2025)

> **一句话总结**：Belfast 实现 SpecLog 抽象，用 fix-ante ordering 让 shard 在全局协调前预测 record 位置；在 CloudLab 微基准中，相对 Scalog 的平均 delivery latency 降低 3.2–3.5×、平均 e2e latency 降低 1.6×。

## 问题与动机

Scalog 类 durability-first shared log 先写 shard 再批量向 sequencer 要 global cut，导致 **delivery latency**（ingest 到可消费）高，下游计算只能等待，**e2e latency** 被放大。金融反欺诈、高频交易、实时分析等需要毫秒级 e2e，同时仍要弹性加 shard、灵活放置、高吞吐——Corfu order-first 做不到前者，Scalog 做不到后者。

核心矛盾：shard 报告 record 数量的「自由意志」使预测全局位置几乎不可能。

## 关键观察 / 隐含假设

- **观察 1**：许多数据驱动应用的下游会对 record 做有状态计算；若能在 global order 确定前 **推测性交付**，计算可与 sequencing overlap。
  - **依赖假设**：应用能处理 speculative bit，并在 confirm 前不外化结果；失败时需 rollback/recompute。
  - **可能失效场景**：compute 极短时 benefit 有限；无状态转发类 pipeline。
- **观察 2**：**fix-ante ordering** 预定义 global cut 序列与 per-shard quota，shard 用 no-op/延迟满足 quota，则预测位置与 actual cut 一致（除罕见全 shard 失败）。
  - **依赖假设**：ingestion rate 可估计以设 rate-based quota；burst/drop 有 lag-fix 与 lease window 兜底。
  - **证据强度**：强——论文论证 failure-free 时 quota 可由 no-op 或延迟满足；并评估 burst、rate change、straggler。
- **假设 1**：append 仍须等 actual cut 才 ack，以保 linearizability（不能「先 ack B 再写 A」）。
  - **证据强度**：强——论文以两 shard execution 说明这一因果；意味着 append latency 不能靠 speculation 降低。

## 核心方法

**SpecLog 接口**：与 Scalog 类似 append/subscribe/trim，但 delivery 带 speculative 位，后续 confirm 或 fail。

**fix-ante ordering**：预定 cut 序列 P₁,P₂,…；quota qᵢⱼ = dᵢⱼ - d₍ᵢ₋₁₎ⱼ；shard 恰好报告 quota 条（多则延迟、少则 no-op）。位置预测由 lexicographic 规则与累计 quota 确定。

**Belfast 机制**：
- rate-based quota 匹配摄入速率；
- **lag-fix**：burst 时 sequencer 催促落后 shard 填 no-op 以推进 cut；
- **speculation lease window**：仅在 window 边界改 quota/增删 shard，防 misspeculation；
- straggler shard 可临时 quota=0。

## 设计取舍

- **取舍 1**：为准确 speculation 牺牲 append/confirm 在慢 shard 上的延迟（sequencer 等齐 quota）。
- **取舍 2**：misspeculation 时正确性靠应用 rollback，非 log 层隐藏。
- **边界条件**：整 shard 失败或 sequencer 不可达时 speculation fail，性能回落但正确。

## 实验与结果

- CloudLab、4 KB record、2/4 shard、下游平均 1.5 ms batch compute 的微基准中，平均 delivery latency 相对 Scalog 降 3.2–3.5×，平均 e2e latency 降 1.6×（§6.1，Fig. 7）。
- 4 shard 时，compute 为 0.5 ms/1.5 ms 的 e2e 收益为 1.17×/1.63×；compute 到 50 ms 时收益比趋近 1（§6.2，Fig. 8）。
- 所测 10-shard workload 中，fix-ante 的 append latency overhead 为 5.8%（§6.3，Fig. 9）。
- 2→4→2 shard 的一次在线弹性实验中，作者报告无 downtime、无吞吐下降，新 shard 的吞吐提升延后少于 100 ms，且 e2e 仍低于 Scalog（§6.7，Fig. 13）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Belfast 在主微基准中降低 delivery 与 e2e latency | 平均 delivery latency 3.2–3.5× 更低、平均 e2e latency 1.6× 更低；2/4 shard 的 p99 e2e 改善为 1.4×/1.17×（§6 Setup、§6.1，Fig. 7） | CloudLab、4 KB record、2/4 shard、1.5 ms 下游 compute | high |
| 收益依赖 compute 与 ordering 的 overlap | 4 shard 时 0.5 ms compute 为 1.17×、1.5 ms 为 1.63×；50 ms 时 benefit ratio 趋近 1（§6.2，Fig. 8） | 只改变 compute time 的 4-shard workload | high |
| fix-ante 的 append latency 代价为 5.8% | 所测 10-shard workload 的 append latency overhead 为 5.8%（§6.3，Fig. 9） | 少量 upstream client、2/4/10 shard；无可机器读取的绝对延迟 | high |
| 在线弹性实验未观察到 downtime 或吞吐下降 | 2→4→2 shard 时，新 shard 提升延后少于 100 ms，e2e 仍低于 Scalog（§6.7，Fig. 13） | 一次 add-two-then-remove 实验，非通用生产 SLA | medium-high |
| Belfast 的 e2e 优势在规模实验中仍存在 | 相对 Scalog，2/10 shard 的 e2e advantage 为 1.66×/1.4×（§6.8，Fig. 14） | 真实流量仅到 2/10 shard；40-shard 结论来自 shard emulation | high |

## Critical Analysis

### 论证链条

delivery 高 → overlap 计算可降低 e2e → 需准确预测 → fix-ante quota → Belfast 工程化（quota/lag-fix/lease）。逻辑闭合；append 路径未加速是明确边界。

### 假设压力测试

- 摄入速率剧烈不可预测时 no-op 与延迟增多，append/confirm 变差。
- 应用 rollback 成本高时（大状态索引），misspeculation 代价被低估。
- 与 LazyLog「读解耦」假设不同，本文面向 ingest-consume 同步场景。

### 实验可信度

微基准 + 三应用 + failure case；baseline Scalog 强。缺 Kafka/Redpanda 生产 trace 对比。

### 系统性缺陷

论文未讨论：下游 exactly-once 外化语义、speculation fail 的运维告警、multi-tenant quota 公平性。

## 局限与 Future Work

- **局限 1**：append ack 仍受 sequencing 批次与 quota 等待影响。
- **局限 2**：罕见全 shard 失败时 speculation 失效。
- **Future work 1**：order-first log 上的 SpecLog；自适应 window 与 quota 的 ML 预测。
- **Future work 2**：量化不同 compute/ordering 比例下的 e2e 收益下界。

## 相关

- **相关概念**：[[Speculative-Decoding]]（思想类比：推测+验证）
- **同类系统**：Scalog、Corfu、Boki、FlexLog、Kafka
- **同会议**：[[OSDI-2025]]
