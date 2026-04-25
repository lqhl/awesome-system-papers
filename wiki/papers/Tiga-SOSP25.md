---
type: paper
name: Tiga
full_title: "Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks"
authors: [Jinkun Geng, Shuai Mu, Anirudh Sivaraman, Balaji Prabhakar]
venue: SOSP
year: 2025
tags: [transactions, geo-distributed, consensus, concurrency-control, clock-sync]
source_pdf: "[[3731569.3764854.pdf]]"
source_md: "[[3731569.3764854]]"
---

# Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks (SOSP 2025)

> **一句话总结**:合并 consensus 与 concurrency control 为单层协议,用同步时钟(Huygens/chrony)给每个事务预先分配 future timestamp,让多数事务在 1 WRTT 内达成严格可串行化 commit——比 Tapir/Janus/Detock 吞吐高 1.3-7.2×、延迟低 1.4-4.6×。

## 问题

跨 region 的 OLTP 系统(Spanner 风格)需要 concurrency control(保证 strict serializability)+ consensus(linearizable replication)。两层堆叠导致多 WRTT commit,延迟高。已有"融合"协议(Tapir、Janus、Detock)乐观依赖事务到达顺序,但跨 region 下不同 server 看到的顺序不一致,冲突时 fast path 失败,退化到多轮。

## 核心方法

三大设计决策:

- **Consolidation**:单层协议同时完成 replica 间和 shard 间一致排序,避免 "overpay"。
- **Proactive ordering with synchronized clocks**:coordinator 发送事务时,基于测量的 OWD(one-way delay)给事务分配一个 future timestamp(发送时间 + headroom)。server 收到后 hold 到本地时钟超过 timestamp 再按 timestamp 序处理——headroom 掩盖了到不同 server 的异构延迟,达成一致排序。依赖 [[Clock-Synchronization]] 的 μs 级精度([[Huygens]]、公有云 chrony <5ms),但"依赖时钟只求性能、不求正确性"。
- **Leader per shard + timestamp agreement**:fast path(1 WRTT)失败时,shard leader 之间走 timestamp agreement slow path(1.5-2 WRTT);full replication 下 leader 可共置于一 region,LAN 开销可忽略。
- **避免 timestamp inversion**:细致设计避免 linearizability 是单 shard 局部属性 vs strict serializability 的全局属性不匹配,已形式化证明并提供 TLA+ spec。

## 关键结果

- MicroBench(低冲突):吞吐 1.3-7.2× 优于 2PL/OCC+Paxos、NCC、Calvin+、Detock、Tapir、Janus;中位延迟 1.4-4.6× 更低。
- TPC-C(含多-shot 交互事务):吞吐 1.6-3.5×,延迟 1.5-3.7× 优于最好 baseline。
- 使用 Google Cloud 默认 chrony(4.54 ms 误差)已足够。
- 开源于 GitHub。

## 相关

- **相关概念**:[[Clock-Synchronization]]、[[Huygens]]、Strict Serializability、[[TPC-C]]、Timestamp Inversion
- **同类系统**:[[Spanner]]、Tapir、Janus、Detock、Calvin+、NCC
- **同会议**:[[SOSP-2025]]
