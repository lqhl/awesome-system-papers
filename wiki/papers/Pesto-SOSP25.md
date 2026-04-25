---
type: paper
name: Pesto
full_title: "Pesto: Cooking up High Performance BFT Queries"
authors: [Florian Suri-Payer, Neil Giridharan, Liam Arzola, Shir Cohen, Lorenzo Alvisi, Natacha Crooks]
venue: SOSP
year: 2025
tags: [bft, database, sql, concurrency-control, byzantine, transactions]
source_pdf: "[[3731569.3764799.pdf]]"
source_md: "[[3731569.3764799]]"
---

# Pesto: Cooking up High Performance BFT Queries (SOSP 2025)

> **一句话总结**:Pesto 是首个支持**完整 SQL**的高性能 [[BFT]] 数据库，放弃 State Machine Replication、允许副本暂时不一致、只按查询需求做 predicate-level 同步，TPC-C 上吞吐匹配单机 Postgres/Peloton，比经典 SMR+DB 吞吐高 2.3×、延迟降 2.7-3.9×。

## 问题

去中心化应用（金融、医疗、土地登记、confidential computing）需要**BFT 数据库**让互不信任的参与方共享一致状态。现有方案两难：

- **分层设计**（BFT consensus + 单机 DB 引擎，如 HotStuff+Peloton）：全序所有操作丧失并行度；分片时 2PC 叠 consensus 开销爆炸；交互式事务多轮来回延迟极高，多数系统干脆只支持 stored procedure。
- **集成设计**：Basil 等把 concurrency control / replication / 2PC 融合，性能接近 CFT，但**只支持 KV 接口**。对 join、scan、aggregation 这种常见查询，客户端必须拉回原始行自己算——一个简单 join 可能要数百万次 GET。

挑战有两个：
1. 任意 SQL 查询的**可串行化正确性**如何保证？若走 consistent replication 又回到全序，吞吐垮掉。
2. 乐观并发控制（OCC）对 range query 天然糟糕——需要逻辑锁住 predicate 范围，abort 率飙升。

## 核心方法

Pesto 的关键 insight：**consistency 只需对查询的 predicate 有效，不必对整个数据库有效**。

- **Inconsistent replication + on-demand snapshot**: 副本可以不一致、平行处理，客户端对复杂查询只要求 f+1 个匹配结果。不匹配时启动「range read 协议」的 snapshot 路径：副本投票出当前查询涉及的 transaction id 集合 (SS-VOTE)，客户端聚合出 f+1 以上出现的 id 作为 snapshot proposal，发给副本同步所需 transaction，在统一快照上重新执行查询。
- **Semantic concurrency control (SemanticCC)**：受 precision locking 启发。副本把查询拆成 operator tree、对每个叶子记录 filter predicate 和 active read set (ARS, 满足 predicate 的行)。提交时只检查并发写**是否满足查询 predicate** ——不满足的并发写不冲突。大幅降低 range query 的 abort 率。
- **n=5f+1 副本**以保证 Byzantine independence（3f+1 模型下 malicious client + leader 可合谋 front-run）。
- **Prepared-visible writes**: OCC 验证通过即乐观可见，减少冲突窗口；用精心设计的 dependency tracking (DepSet) 保持 Byz-serializability。
- **两步提交 + 异步 writeback**: 常规无故障可 single round-trip commit，遇故障或网络乱序时多一轮保证 durability。

支持交互式事务（开发者最爱）、sharding，作为现有 SQL DB 的 drop-in replacement。

## 关键结果

- **TPC-C**：吞吐匹配非复制的 Peloton 和 Postgres；比 HotStuff/BFT-Smart + Peloton 经典分层吞吐高 **2.3×**
- 延迟降 **2.7-3.9×** 相比分层 BFT 方案
- AuctionMark、Seats workload 也有同等量级收益
- YCSB 微基准显示复杂分析查询上比 Basil 大幅改善（Basil 要拉全表到客户端）
- Leaderless 设计：副本故障对性能影响小，即使高度不一致副本也稳健

## 相关

- **相关概念**:[[BFT]]、[[SMR]]、[[OCC]]、[[Serializability]]、[[Two-Phase-Commit]]、[[Precision-Locking]]、[[MVTSO]]
- **同类系统**:[[Basil]]、[[HotStuff]]、[[BFT-Smart]]、[[PBFT]]、[[Postgres]]
- **同会议**:[[SOSP-2025]]
