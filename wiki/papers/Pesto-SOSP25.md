---
type: paper
name: Pesto
full_title: "Pesto: Cooking up High Performance BFT Queries"
authors: [Florian Suri-Payer, Neil Giridharan, Liam Arzola, Shir Cohen, Lorenzo Alvisi, Natacha Crooks]
venue: SOSP
year: 2025
tags: [bft, database, sql, distributed-systems, byzantine]
source_pdf: "[[3731569.3764799.pdf]]"
source_md: "[[3731569.3764799]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Pesto：编写高性能 BFT 查询（SOSP 2025）

> **原题**：Pesto: Cooking up High Performance BFT Queries

> **一句话总结**：BFT 数据库若用 [[State-Machine-Replication]] 全序事务则延迟高；Pesto 延续 Basil 的 ordering-free 设计并扩展到完整 SQL，用按需 snapshot 同步 + SemanticCC，在 TPC-C 上与 Peloton/Postgres 吞吐相当（~1784 tx/s），相对 Peloton-HotStuff **2.3×** 吞吐、**2.7–3.9×** 更低延迟。

## 问题与动机

去中心化应用需要 BFT 数据存储，但 layering consensus + DB（Peloton-HS 等）强制全序、扼杀并行；Basil 集成 CC+2PC 高性能但仅 KVS API，join/scan 需百万次 GET 重组查询。应用需要 **interactive SQL**、丰富查询、水平扩展——Pesto 要做「Basil 性能 + SQL 表达力」。

## 关键观察 / 隐含假设

- **观察 1**：查询一致性只需在**该查询 predicate 相关状态**上成立，不必全库强一致复制执行。
  - **依赖假设**：客户端能对 server-side 查询结果做 quorum 匹配验证；不一致时 snapshot 同步可收敛。
  - **可能失效场景**：宽范围 scan 高争用时 snapshot 同步频率上升，可能逼近 SMR 成本。
- **观察 2**：OCC 对 range query 通常需锁大范围；SemanticCC 仅当写**影响查询语义结果**时才冲突。
  - **依赖假设**：查询计划可提取语义 predicate；precision locks 思想可扩展到 SQL。
  - **可能失效场景**：复杂 UDF/聚合使「语义冲突」判定保守化。
- **假设 1**：`n=5f+1` 副本 + Byzantine independence 可兼顾安全与 leaderless 鲁棒性。
  - **证据强度**：强（继承 Basil 模型）；比 `3f+1` leader BFT 副本更多。

## 核心方法

**不一致复制**：副本无序并行执行；点读走 Basil GET（1 RTT）；range read 走 Range protocol，必要时 **snapshot synchronization** 对齐相关状态。

**SemanticCC**：prepare 阶段用查询语义判断写-读冲突；支持 optimistic prepared writes。

**2PC commit**：fast path 单 RTT（97% TPC-C）；跨 shard 扩展；`5f+1` quorum（range read 需 `3f+1` 匹配 + 与 commit quorum 相交）。

## 设计取舍

- **取舍 1**：放弃全序 → 极高并行，但 snapshot/CC 协议复杂度显著高于 SMR。
- **取舍 2**：range read quorum 更大 → 读扩展性弱于点读；TPC-C 点读重可 load-balance 反超 unreplicated。
- **边界条件**：AuctionMark/SEATS range read 多时仅 **1.1–1.2×** SMR 吞吐优势。

## 实验与结果

- TPC-C：Pesto **1784 tx/s** ≈ Peloton **1777** / Postgres **1781**；vs Peloton-HS **758**、Peloton-Smart **785**（**2.3×**）
- 延迟：vs Peloton-HS **3.9×** 更低，vs Peloton-Smart **2.7×**
- Fast path commit **97%**；点读 **99.9%** range read 单 RTT（TPC-C 语境）
- 分片：2 shard **1.64×**、3 shard **2.21×**；峰值接近 Basil KVS **1.23×** 差距
- YCSB 分析查询显著优于 Basil

## 批判性分析

### 论证链条

「predicate-local 一致性 + 语义 OCC」→ 避免全序同时支持 SQL，TPC-C 与 unreplicated 对齐，链条在 OLTP 基准上闭合。到「任意 SQL 工作负载」跳步：复杂 analytics、长事务、多表 DDL 覆盖有限；与 CRDB 比较 CRDB 允许多 shard 机器数不等，峰值 **2.91×** 低于 Pesto 需结合成本模型解读。

### 假设压力测试

- **拜占庭客户端**：无界恶意客户端可故意 abort 他人事务——模型标准假设，但 WAN 高延迟下 quorum RTT 放大。
- **副本故障**：leaderless 设计鲁棒，但 `5f+1` 存储/带宽开销 vs `3f+1` 生产经济性未讨论。
- **SQL 复杂度**：TPC-C 仍偏点读；真 analytic warehouse 可能 snapshot 风暴。

### 实验可信度

CloudLab m510、closed-loop 重试；对 Peloton-SMR 放松 determinism 已声明「对 baseline 慷慨」。缺与最新 commercial BFT DB（如部分 blockchain SQL 层）对比。

### 系统性缺陷

副本数、签名、quorum 带来运维复杂度；论文未讨论备份、跨地域延迟、可观测性（debug 不一致查询）。Snapshot 协议在 partial synchrony 外的 liveness 边界需细读补充材料。

## 局限与后续工作

- **局限 1**：range read 需更大 quorum 与 table version 单调性加固（§6）。
- **局限 2**：分片扩展仍 CPU bottleneck，与专用 KVS 有差距。
- **Future work 1**：TPC-H 类 analytic 负载测量 snapshot 同步触发率与 P99。
- **Future work 2**：WAN 部署下 `5f+1` 与 `3f+1` SMR 的$/tx 交叉点。

## 相关

- **相关概念**：[[Byzantine-Fault-Tolerance]]、[[State-Machine-Replication]]、[[Serializability]]、[[Two-Phase-Commit]]
- **同类系统**：Basil、Peloton、HotStuff、BFT-SMaRt
- **同会议**：[[SOSP-2025]]
