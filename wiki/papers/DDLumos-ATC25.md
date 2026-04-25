---
type: paper
name: DDLumos
full_title: "DDLumos: Understanding and Detecting Atomic DDL Bugs in DBMSs"
authors: [Zhiyong Wu, Jie Liang, Jingzhou Fu, Wenqian Deng, Yu Jiang]
venue: ATC
year: 2025
tags: [database, fuzzing, bug-detection, dbms, atomic-ddl]
source_pdf: "[[atc2025-wu-zhiyong.pdf]]"
source_md: "[[atc2025-wu-zhiyong]]"
---

# DDLumos: Understanding and Detecting Atomic DDL Bugs in DBMSs (ATC 2025)

> **一句话总结**：先分析 PostgreSQL/MySQL/MariaDB 中 207 个 Atomic DDL bug（94% 由 metadata conflict 触发），再用 metadata-conflict-guided DDL 合成 + 图一致性分析的 fuzzer DDLumos 在 6 个 DBMS 中发现 73 个新 bug、14 个已修复。

## 问题

Atomic DDL（保证 schema 修改 all-or-nothing）是现代 DBMS 核心，但实现错误普遍存在，会导致数据损坏、系统不可用。已有 DBMS fuzzer（SQLancer/SQLsmith/SQUIRREL/TXCHECK）专注 DQL/DML 的逻辑/事务/崩溃 bug，对 DDL 关注少，生成的 DDL 几乎不带 metadata conflict——而 ADB 的特性正是要靠多 DDL 间的 metadata 冲突触发，已有工具检测不到。

## 核心方法

**特征研究（207 个 bug）**：
- Manifestation：44% incorrect result、32% post-recovery data inconsistency、24% system unavailability。
- Root cause：32% incomplete rollback、22% improper metadata sync、18% concurrency control、22% error handling。
- Trigger condition：93% 含 metadata conflict point（多个 DDL 操作同一 metadata 元素，如表/列/索引/约束），94% 直接被 conflict 触发。

**DDLumos 工具**：
- **Metadata Conflict-Guided DDL Synthesis**：维护 metadata table 跟踪每个 schema 元素的 conflict point 计数；按 80% DDL / 20% DML+DQL 的比例合成；DDL 合成时用 conflict point 少的元素优先填充 skeleton（保证多次出现产生冲突）；测试用例长度 15 条 SQL（覆盖 98% 已知 bug）。
- **Graph-Based Consistency Analysis**：构造 metadata graph（表/列/索引/约束/触发器/行数/视图作为节点+依赖边），SQL 执行后对比 graph 和 DBMS 实际 metadata；同步检测 incorrect result + system unavailability，异步发 kill signal 触发崩溃恢复后检 post-recovery inconsistency。
- 多客户端并发分发触发并发控制相关 bug。

深度细节回 [[atc2025-wu-zhiyong]]。

## 关键结果

- 在 MySQL/MariaDB/Percona/PolarDB/GreatSQL/PostgreSQL 6 个 DBMS 上 2 周发现 73 个未公开的 ADB（14/15/14/11/15/4），全部确认，14 个已修复。
- 重新发现率：1 周内重现 94.7% 已研究的 bug。
- 48 小时对比：比 SQLancer 多 27 个 bug、比 SQLsmith 多 31、比 SQUIRREL 多 32、比 TXCHECK 多 26。

## 相关

- **相关概念**：[[Fuzzing]]、[[DBMS]]、[[Schema-Evolution]]
- **同类系统**：SQLancer、SQLsmith、SQUIRREL、TXCHECK
- **同会议**：[[ATC-2025]]
