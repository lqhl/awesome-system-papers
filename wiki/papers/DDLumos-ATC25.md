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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# DDLumos: Understanding and Detecting Atomic DDL Bugs in DBMSs (ATC 2025)

> **一句话总结**：对 PostgreSQL/MySQL/MariaDB 中 207 个 Atomic DDL bug 的实证研究发现 93% 由 metadata conflict 触发，据此设计的 DDLumos 用 metadata-conflict-guided DDL 合成 + metadata graph 一致性 oracle，在 6 个 DBMS 上 2 周发现 73 个新 bug（14 已修复），48 小时内比 SQLancer/SQLsmith/SQUIRREL/TXCHECK 多检 27/31/32/26 个，1 周内复现 94.7% 已知 bug。

## 问题与动机

[[Atomic-DDL]] 是现代 [[DBMS]] 保证 schema 修改 all-or-nothing 的核心机制：DDL 要么完全成功，要么回滚到原状态，避免 partial update 导致 catalog 与物理存储不一致。MySQL 采用 statement-level atomic DDL，PostgreSQL 支持把多条 DDL 包进 atomic transaction。实现涉及 rollback log、metadata synchronization、concurrency control、error handling 等多子系统协同，工程复杂度极高。

作者把 **Atomic DDL Bug（ADB）** 定义为：执行 Atomic DDL 时出现 partial update、数据损坏或系统不一致。这类 bug 危害大——MariaDB 近期 119 个 ADB 中 48% 影响后续 DDL/DML；MySQL 相关 50 个 CVE 中 29 个 CVSS > 7.0，28% 导致 crash、33% 数据损坏。Figure 1 的 MySQL 8.0 例子很典型：`ALTER TABLE` 因外键约束失败，本应保留单列 c1，却错误留下 c1+c3。

现有 [[DBMS]] testing 工具（SQLancer、SQLsmith、[[SQUIRREL]]、TXCHECK）主要盯 DQL/DML 的逻辑 bug、事务 atomicity、crash/memory safety，对 DDL 关注极少。即使生成 DDL，也几乎不刻意制造 **metadata conflict**——多个 DDL 操作同一 table/column/index/constraint。而作者实证表明 93% 已知 ADB 都依赖这种冲突场景。更麻烦的是，ADB 有三种不同 manifestation（执行期 incorrect result、crash/hang、崩溃恢复后 inconsistency），现有工具普遍缺少 recovery oracle 和 metadata 一致性检查。

DDLumos 的目标不是替代通用 DBMS fuzzer，而是补齐 Atomic DDL 这一被忽视的测试面：先理解 ADB 如何出现，再针对性生成高 conflict DDL 序列并用 graph-based oracle 检测三种 bug 形态。

## 关键观察 / 隐含假设

- **观察 1**：绝大多数 ADB 由 DDL 间的 metadata conflict 触发。207 个 bug 中 193 个（93%）含 metadata conflict point，181/193（94%）直接被 conflict statement 触发；84% 的 case 含超过 4 个 conflict point。
  - **依赖假设**：schema 演化 workload 中，多条 DDL 会反复 touch 同一 metadata 元素（表、列、索引、约束、触发器）；冲突不是极端 corner case，而是 schema migration 和在线 DDL 的常见模式。
  - **可能失效场景**：只含单表 `CREATE`、彼此独立的 schema object、或 plugin/extension 专属 metadata 的 bug，可能不依赖 conflict point；论文 rediscovery 实验也漏掉 8 个依赖特殊 plugin/configuration 的 bug。
  - **证据强度**：强。基于 207 个手工复现 bug 的统计 + 新发现 73 bug 的 root cause 分布与 study 一致。

- **观察 2**：ADB 分三类 manifestation，需要不同 oracle 和触发场景。44% incorrect result（catalog 与预期不符但 server 仍存活）、32% post-recovery data inconsistency（kill 后重启 schema 错误/丢表）、24% system unavailability（crash/hang/assertion）。
  - **依赖假设**：metadata graph 能近似刻画「DDL 执行后应有的 schema 状态」；从 DBMS 查询 `information_schema` 等接口足以作为 ground truth；异步 kill + reboot 能代表真实 power failure/crash recovery。
  - **可能失效场景**：只影响 query result 但不反映在 catalog metadata 的 bug、需要特定 replication/topology 才显现的 inconsistency、或 kill timing 极窄的 race，graph oracle 可能漏检；论文承认 3 个 bug 需两周才 rediscover。
  - **证据强度**：中到强。三类 oracle 与 bug report 症状对齐，但 metadata-only oracle 对 DML correctness 盲区未评估。

- **观察 3**：已知 ADB 的 trigger sequence 很短——98% 不超过 15 条 SQL。因此固定 test case 长度 L=15 能在效率与触发深度间取得平衡。
  - **依赖假设**：复杂 Atomic DDL bug 不需要很长 SQL history；15 条足以覆盖 rollback log、online DDL、并发交错的主要状态机路径。
  - **可能失效场景**：需要长事务链、特定 migration script 或跨 session 状态积累的 bug；NoSQL/非关系型 schema 模型可能不适用该长度假设。
  - **证据强度**：中。来自历史 bug 统计，但对新 bug 的外推未单独验证。

- **假设 1**：metadata table 中 conflict point 计数 +「优先选低计数元素填充 DDL skeleton」能有效导向高冲突序列，优于随机 DDL 生成。
  - **证据强度**：强。DDLumos 平均每条 DDL 含 1.24 个 conflict point，显著高于 SQLancer（0.30）、SQLsmith（0.03）、SQUIRREL（0.18）、TXCHECK（0.45）；48 小时 bug 数 36 vs baseline 4–10。

- **假设 2**：2–5 个 client worker 按 sequence id 分发 SQL、偶尔 overlap 执行，足以覆盖 18% concurrency-related ADB，而不需要真实 production 级并发负载。
  - **依赖假设**：ADB 的并发缺陷主要由有限 DDL lock/interleaving 触发，而非海量 DML 竞争。
  - **可能失效场景**：高 QPS mixed workload、跨 region replication lag、或 storage engine 层与 SQL 层分离的复杂部署。
  - **证据强度**：中。发现了 IICC 类 bug，但并发模型比真实应用简单。

## 核心方法

DDLumos 分两模块：**Test Case Generator**（metadata conflict-guided synthesis）和 **Metadata Consistency Analyzer**（graph-based detection）。适配新 DBMS 只需约 10 行 SQL 查 metadata + 复用目标 DBMS 的 Yacc grammar（grammar adaptor 自动适配运算符）。

### Metadata Conflict-Guided DDL Synthesis

维护 **metadata table**，记录每个 schema 元素（表、列、索引、约束等）及其 **conflict point** 计数——被多少后续 DDL touch。每执行一条 DDL 就更新计数。

合成循环（Algorithm 1）：
1. 从 metadata table 取当前状态 `Me` 和 conflict 信息 `Cp`
2. 按 80% DDL / 20% DML+DQL 选 statement type；DDL 类型优先选历史使用频率低的（如 `ALTER TABLE`、`CREATE INDEX`）保证多样性
3. 若生成 DDL：按 conflict point 升序排序 metadata，用低计数元素填充 skeleton（每个 skeleton 至少 2 个 metadata object，如 `ALTER TABLE t1 ADD COLUMN c2, ADD INDEX i1`）
4. 若生成 DML/DQL：基于现有 metadata 保证语义合法
5. 更新 metadata table，追加到 test case，直到 L=15

多客户端并发：每条 SQL 带 sequence id，2–5 个 worker 按序分发；偶尔让后续语句在前一条完成前发出，刻意触发 concurrency control 路径。

### Graph-Based Consistency Analysis

对每条 statement 动态维护 **metadata graph**：节点为 table/column/index/constraint/trigger/view/row count 等，边为依赖或层级关系。执行 SQL 后从 DBMS 拉实际 metadata，与 graph 期望状态比对。

Algorithm 2 覆盖三种 detection scenario：
- **System unavailability**：connection check，server 断连或无响应即报 bug
- **Incorrect result**：逐步 `ConsistencyAnalysis(M, G)`，metadata 不匹配即报 bug
- **Post-recovery data inconsistency**：异步 `sendKillSignal` 中断 DDL，重启后 `RebootandGetMetadata()` 再比对 graph

这与 SQLancer 的 query equivalence oracle、TXCHECK 的事务图 oracle 不同——DDLumos 的 oracle 是 **schema/metadata 一致性**，且显式包含 crash recovery 路径。

## 设计取舍

- **metadata graph 换 expressiveness**：不 dump 全库数据，只跟踪 DDL 可影响的 catalog 结构。收益是 graph 维护成本可控；代价是可能漏掉「catalog 正确但数据行内容错误」类 ADB，论文未讨论 DML-level oracle。
- **conflict-guided 合成换通用性**：80% DDL 比例和 conflict-biased population 牺牲了对纯 DML/DQL bug 的覆盖，换更高 DDL module branch coverage（48h 在六系统合计覆盖 8852 branches，约为 SQLancer 的 1.9×）。
- **固定 L=15 换 fuzz 效率**：避免过长序列拖慢 graph 分析；代价是可能漏掉需长 migration history 的 bug。
- **kill signal 模拟 crash 换真实性**：实现简单、可自动化；代价是不覆盖 graceful shutdown、部分 fsync 失败、复制节点 staggered recovery 等更贴近生产的 failure mode。
- **grammar adaptor 换适配成本**：复用 DBMS 自带 Yacc 文件，新系统适配声称只需少量 SQL + grammar；但仍需人工写 metadata 查询和 anomaly 判定，且不支持 plugin 环境（8/207 历史 bug 因此漏复现）。

## 实验与结果

- **研究对象**：实证研究 PostgreSQL（38）、MySQL（50）、MariaDB（119）共 207 个 ADB；检测评估覆盖 MySQL、MariaDB、Percona、PolarDB、GreatSQL、PostgreSQL 六个开源 DBMS。
- **新 bug**：2 周发现 73 个此前未知 ADB（MySQL 14、MariaDB 15、Percona 14、PolarDB 11、GreatSQL 15、PostgreSQL 4），全部 vendor confirmed，14 已修复，9 个分配 CVE。
- **manifestation 分布（新 bug）**：31 incorrect result、22 system unavailability、20 post-recovery inconsistency。
- **root cause（新 bug）**：incomplete rollback 21、improper metadata sync 15、concurrency control 11、faulty error handling 19、other 7——与 207-bug study 比例一致。
- **48h baseline 对比**：DDLumos 平均发现 36 个 ADB；SQLancer 9、SQLsmith 5、SQUIRREL 4、TXCHECK 10。分别多 27/31/32/26 个。与 SQLancer/TXCHECK 仅有 2–3 个重叠，与 SQLsmith/SQUIRREL 正交。
- **DDL module coverage**：48h 内 DDLumos 在六系统覆盖 8852 branches，比 SQUIRREL/SQLancer/SQLsmith/TXCHECK 分别多 10732/14938/11976/14490（论文 Table 3 汇总口径）。
- **metadata conflict density**：平均每条 DDL 1.24 conflict points，比最强 baseline TXCHECK 高 0.76。
- **rediscovery**：对 207 个已知 bug 在对应历史版本上跑 1 周，复现 196 个（94.7%）；前两天即达 86.5%（179/207）。PostgreSQL 34/38、MySQL 48/50、MariaDB 114/119。
- **环境**：Ubuntu 20.04，AMD EPYC 7742 128-core，504 GiB RAM；每 DBMS Docker 容器 5 CPU + 50 GiB RAM。

## Critical Analysis

### 论证链条

论文链条清晰：动机案例（Figure 1）说明 rollback 失败后果严重 → 207-bug study 建立「metadata conflict 是主 trigger」→ 设计直接对准 conflict tracking + 三类 oracle → 新 bug 数、branch coverage、conflict density、rediscovery rate 四条证据同向支撑。

最强环节是 **study 与 tool 的闭环**：不是先造工具再找 justification，而是先用公开 issue tracker 建立 ADB taxonomy，再把统计结论写进 generator 和 analyzer。rediscovery 94.7% 尤其有力——说明 synthesis 策略确实复现了真实 bug trigger pattern，而非只挖 trivial crash。

薄弱跳步在于：「metadata conflict point 多」被等同于「更深层 Atomic DDL 逻辑覆盖」，再到「更多真实 ADB」。branch coverage 和 bug 数相关，但论文没有证明多出来的 branches 对应更高严重度或 production-relevant path；部分新 bug 可能只是简单 catalog 泄漏。

### 假设压力测试

DDLumos 对 **关系型 OLTP DBMS、schema 频繁变更、Atomic DDL 已实现但工程复杂** 的场景最自然。六个受测系统均属此类。

压力来自四类场景。第一，**PostgreSQL 仅 4 个新 bug**，远低于 MySQL 系 fork（14–15 个），可能说明 PG 的 atomic DDL transaction 模型更成熟，或 DDLumos 的 grammar/metadata 适配对 PG 不够激进——论文未深入解释该 skew。第二，**plugin/configuration 依赖**：8 个历史 bug 因未启用 plugin 而漏复现，暗示 production 中 extension-heavy 部署的 ADB 风险被低估。第三，**replication 与分布式 DDL**：实验全是单实例 Docker，未覆盖 primary-replica metadata lag、online DDL 在副本上的行为。第四，**kill timing sensitivity**：3 个 bug 需两周才出现，说明异步 crash 的采样策略对 rare race 仍不够系统。

论文把 ADB 与 transaction atomicity bug 区分清楚，但未证明 metadata graph oracle 不会把「预期内的 temporary inconsistency」（如 online DDL 中间状态）误报为 bug；依赖 DBMS 返回的 catalog 视图作为 ground truth，若 catalog API 本身在 bug 状态下不可信，oracle 会失效。

### 实验可信度

baseline 选择合理：SQLancer（logic/oracle testing）、SQLsmith（random SQL crash）、[[SQUIRREL]]（coverage-guided validity fuzzing）、TXCHECK（transaction graph oracle）代表 DBMS testing 主流方向。48h 窗口、5 次重复、统一 replay 测 branch 的做法有利于公平对比。

需注意的限制：第一，**bug 判定由 DDLumos 自有 oracle 完成**，baseline 工具未必配备 post-recovery metadata check，对比可能部分反映 oracle 能力差异而非纯 input 质量差异。第二，**重叠极少**既证明互补性，也说明 baseline 在 48h 内几乎没触达 DDLumos 的主战场——对比公平但近乎不同测试目标。第三，**vendor confirmation** 作为有效性标准，未报告 false positive 率或人工去重成本。第四，研究样本来自 issue tracker keyword 检索 + 手工复现，可能遗漏未公开的安全漏洞（论文 Threats to Validity 已承认）。

### 系统性缺陷

**实现与运维成本**：10k LOC C++ + 4k Bison/Flex + 1k Python；每个 DBMS 需维护 metadata 查询、grammar adaptor、crash/reboot 流程。对 CI nightly 可行，但对开发者本地快速迭代偏重。

**尾延迟与测试吞吐**：每条 test case 最多 15 步，每步可能触发 kill+reboot；异步 crash 与多 client 并发使单次 fuzz 周期长。论文未报告 hours-per-unique-bug 或 false positive 处理时间。

**隔离与状态污染**：连续 DDL 会累积 schema 状态；论文未详细讨论 database reset 策略、磁盘 tablespace 残留、或 crash 后清理失败导致的 cascade false positive。多 client 并发若未严格隔离，可能引入非确定性。

**可观测性**：工具输出以 detected ADB 为主，对「哪条 conflict point / 哪种 kill timing 触发」的可解释性有限，不利于 developer triage。论文 case study 有 SQL 片段，但缺乏系统化 bug signature 分类。

**兼容性**：仅覆盖六款开源关系型 DBMS；NoSQL、warehouse、云托管 DB（用户无法发 kill signal）场景论文未讨论。

## 局限与 Future Work

- **局限 1**：实证研究仅限 PostgreSQL/MySQL/MariaDB 公开 issue，可能遗漏 security team 私下修复的高危漏洞；结论对 NoSQL/graph DB 外推有限。
- **局限 2**：不修改 plugin/configuration 环境，导致 8/207 rediscovery miss；真实部署中 extension 和 non-default setting 可能承载更高 ADB 风险。
- **局限 3**：单实例 Docker 测试，未覆盖 replication、sharding、云存储 backend 等 production topology；post-recovery inconsistency 在集群环境可能更严重但未被测量。
- **局限 4**：metadata-only oracle 不验证 DML 结果正确性；incorrect result 判定完全依赖 catalog 一致性，可能漏掉或误判数据层异常。
- **Future work 1**：扩展 FD 模型到 **plugin/configuration-aware** synthesis，用 historical 8 个 miss bug 的 recall 作为客观指标。
- **Future work 2**：系统化 **kill timing search**（如在 DDL 各 phase 建模 checkpoint 再采样 crash），针对 3 个需两周触发的 timing-sensitive bug 测量 time-to-find 分布。
- **Future work 3**：在 primary-replica 或 online DDL 副本场景下测量 ADB 率，验证 metadata conflict 假设在分布式 schema 变更中是否仍占 90%+。
- **Future work 4**：与 SQLancer/TXCHECK 等工具 **组合 oracle**——用 DDLumos 生成高 conflict DDL 序列，再用 differential query 或 transaction oracle 交叉验证，降低 metadata-only false positive。

## 相关

- **相关概念**：[[Fuzzing]]、[[DBMS]]、[[Schema-Evolution]]、[[Atomic-DDL]]、[[Differential-Testing]]、[[Coverage-Guided-Fuzzing]]
- **同类系统**：SQLancer、TXCHECK、SQLsmith、[[SQUIRREL]]、Griffin、LEGO
- **相关机制**：[[Transaction]]、[[Crash-Recovery]]、[[Concurrency-Control]]、[[Metadata-Management]]
- **同会议**：[[ATC-2025]]
