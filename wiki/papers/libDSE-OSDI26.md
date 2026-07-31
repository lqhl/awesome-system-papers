---
type: paper
name: libDSE
full_title: "Distributed Speculative Execution for Resilient Cloud Applications"
authors: [Tianyu Li, Badrish Chandramouli, Philip A. Bernstein, Samuel Madden]
venue: OSDI
year: 2026
tags: [durable-execution, fault-tolerance, speculation, microservices, distributed-systems]
source_pdf: "[[osdi26-li-tianyu.pdf]]"
source_md: "[[osdi26-li-tianyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向韧性云应用的分布式推测执行

> **原题**：Distributed Speculative Execution for Resilient Cloud Applications

## 一句话总结

libDSE 让 message-passing service 跳过无故障路径上的同步持久化，通过显式 recovery dependency graph、atomic action、轻量 sthread 和一致 rollback 在故障后修复状态，使 persistence-bound durable workflow 的端到端延迟最多降低一个数量级。

## 问题与动机

Temporal、Azure Durable Functions 等 durable execution 系统通过记录 intent、task result 与 history，在崩溃后 replay 并维持 exactly-once illusion；但 DAG 每加深一级就多一次同步持久化，分布式拆分反而放大 latency。libDSE 区分“编程抽象要求 durability”与“每一步物理执行必须先落盘”：组件可先交换 speculative message，只有向用户、payment API 或 legacy DB 暴露 effect 前才等待依赖变为 durable。

这不是共享状态上的局部 speculation。shared-nothing service 两端都可能失败，rollback 会跨多参与者传播，并与应用异步代码竞争。系统必须同时保证 recoverability 与 failure transparency，且支持 non-deterministic operation。

## 关键观察 / 隐含假设

### 关键观察

- durability 的同步等待可跨 service chain 重叠；只要一次 speculative unit 更可能完成而非被故障中断，常见路径收益大于恢复代价。
- message consumption 本身建立 causal dependency，既涵盖数据依赖，也涵盖 workflow 根据回复决定下一调用的 control-flow dependency。
- recovery point 粒度的 dependency tracking 比逐 message 更粗，但显著降低无故障路径 bookkeeping 和故障时多轮协议。
- 外部 effect 可由 speculation barrier 隔离，允许 DSE-aware 组件与 legacy system 渐进共存。

### 隐含假设

- 组件满足 fail-restart、会在有界时间恢复，网络 channel 可靠；不考虑 Byzantine failure。
- 每个 StateObject 有单一、可线性化的 recoverable state，开发者能正确实现 Persist/Restore/ListVersions。
- 故障率较低，回滚丢弃的 speculative work 小于常态同步持久化节省。
- 服务之间可以携带 libDSE header；不可回滚外部 side effect 必须严格置于 barrier 之后。

## 核心方法

### StateObject 与 action

开发者把可恢复状态封装为 StateObject，并实现异步 `Persist`、`Restore` 与版本枚举。每次状态访问位于 action：action 可并发，但绝不与 Persist/Restore 交叠，所以其 effect 要么整体持久化，要么整体回滚。RPC message 携带 opaque dependency header；`StartAction` 会拒绝来自已回滚 sender 的 message，`EndAction` 生成返回 header。

### sthread 与 barrier

长 RPC 若一直占用 action 会阻止集群持久化。`sthread` 在 action 中 detach，携带创建时的 speculative dependency，随后可 sleep、retry 或 await；完成后通过 message-like merge 回到父 StateObject。若中途 rollback，merge 被拒绝，父对象恢复后重新派生任务。`Barrier()` 等到所有上游 dependency non-speculative，用于响应外部 client 或调用不可回滚系统。

## 推测协议

### 恢复依赖图

vertex 表示 `(StateObject id, global failure counter, local persistence counter)` 标识的 recoverable point，edge `u→v` 表示恢复 `u` 必须同时保留 `v`。sender 把 origin vertex 附在 message；receiver consumption 时加入 edge，随下一次 Persist 把 graph fragment 异步交给 coordinator。

### Boundary 与有界 rollback

recoverable boundary 是所有 vertex 已持久化且不存在指向 boundary 外 edge 的 closure，只有其中产生的 message 可向外暴露。为避免 domino effect，Commit Ordering Rule 规定 `A_y` 只能接收 persistence counter 不大于 `y` 的 message；否则先异步发起本地 Persist 再继续。这让任意 counter 前缀形成有限 closure，也把 rollback 限制在对应持久化进度之后。

### Failure partition 与 coordinator

故障时 coordinator 删除丢失 vertex，再迭代删除依赖它们的 vertex，持久化一个单调 global failure sequence 与 rollback decision。Recovery Partition Rule 禁止不同 failure counter 的 incarnation 互相消费消息：旧消息丢弃，来自“未来”的消息延迟。coordinator 的 boundary view 可陈旧但安全，因为 persistent graph prefix 不可变；正常路径无需持久化 boundary decision，重启后可由参与者持久状态重算，只有故障 decision 需要同步写入可靠 log。

## 实现

libDSE/coordinator 约 4,000 行 C#，集成 gRPC interceptor 与 ASP.NET managed service。action 使用 shared lock，Persist/Restore 使用 exclusive lock，并以 biased locking 优化常态。作者构建 speculative append-only log，再复用它实现 FASTER KV、DARQ workflow、event broker、WAL 与 strict-2PL/2PC transaction store。

## 实验与结果

- travel reservation service chain 相比 Temporal 与非 speculative baseline，长 workflow 延迟降低约一个数量级；随 chain 加深，baseline 累加 sync persist，而 libDSE 主要增加 RPC cost。
- 50K events/s、120 s 的 DARQ workload 中，libDSE 同时降低 end-to-end latency 与 storage bytes；group-commit window 越大，越多短命 intermediate state 在落盘前被消费并裁剪。
- 4 shard、100% distributed transaction 的 modified TPC-C 中，非推测提交集中在 10 ms group-commit 的倍数，libDSE 多数 transaction 少于 20 ms，并优于 in-memory Orleans。
- 故障恢复会短暂增加 transaction abort，但总体只比 baseline 高 0.3%，retry 后吞吐影响很小。
- gRPC interceptor 版本饱和吞吐约低 25%；把 header 处理放 user code 后，协议本身延迟增幅可忽略、吞吐下降少于 5%，说明主要成本来自 interceptor 实现。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| DSE 可消除 durable chain 的累积 persist latency | 图 8：长 workflow 相比 Temporal/非推测实现约 10 倍更低延迟 | persistence-bound 深链收益最大，compute-heavy workload 收益小 | 强 |
| speculation 可跨异构 service 正确恢复 | travel、event、2PC 三类实现及注入/真实故障实验 | 论文只有 correctness sketch，没有完整形式化证明 | 强 |
| rollback 的用户影响可控 | 图 12：transaction abort rate 仅额外增加 0.3% | 故障频率和 dependency fan-out 更高时可能扩大 | 强 |
| runtime protocol 本身开销较低 | 图 13：manual instrumentation 吞吐损失少于 5% | 自动 gRPC interceptor 最大吞吐损失约 25% | 强 |
| speculation 还可减少写放大 | 图 9：中间 event state 在 commit window 内被裁剪 | 依赖 intermediate state 生命周期短于持久化周期 | 强 |
## 批判性分析

### 论证链条

论文没有把 speculation 限定为一个 workflow engine，而是给出 StateObject、action、sthread、barrier 和 dependency protocol 的完整组合，可覆盖 KV、broker、workflow 与 transaction。把 control-flow causality 统一建模为 message-consumption edge 尤其简洁。stateless boundary computation 也把 coordinator 移出常态 critical path。

### 假设压力测试

- libDSE 不是 drop-in：legacy service 必须重构状态边界、实现 rollback，并严格使用 action/sthread；错误 Restore 会破坏全局安全。
- safety 仅给 informal sketch，concurrent failure、partition、coordinator failover 与 duplicated incarnation 的状态空间值得机器验证。
- recoverable-point false sharing 会保守回滚大量无关 work；高度扇出的 service graph 可能出现大 blast radius。
- eventually consistent/Dynamo-style store 缺乏单一恢复点，不适合 StateObject。
- centralized coordinator 虽不限制 internal throughput，却会在饱和时延迟 external visibility。
- 自动 interceptor 的 25% throughput penalty 并不“minimal”；实际易用性与性能仍有明显取舍。

### 实验可信度

workflow、event stream、distributed transaction 和故障注入覆盖较广，microbenchmark 还能分离协议与 interceptor 成本；但协议只有 correctness sketch，缺少 model checking 与更高故障率的 blast-radius 实验。

## 局限与后续工作

- **局限**：StateObject/rollback 不是 drop-in，false sharing 和中心 coordinator 会放大复杂拓扑下的恢复成本。
- **后续工作**：应形式化验证并自动检查状态边界，同时优化 dependency granularity 和 gRPC metadata path。

后续应形式化验证协议；提供 language/runtime 自动 state capture 与 action checking；用细粒度或分层 dependency 减少 false sharing；研究 replicated、eventually consistent state；为 speculation window 做 failure-rate-aware 自适应控制；并优化 gRPC metadata path，使自动集成接近手工少于 5% 的成本。

## 相关概念

- [[Durable-Execution]]
- [[Speculative-Execution]]
- [[Distributed-Rollback]]
- [[Fault-Tolerance]]
- [[Microservices]]
