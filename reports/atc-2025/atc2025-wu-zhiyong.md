# DDLUMOS: Understanding and Detecting Atomic DDL Bugs in DBMSs

**作者**：Zhiyong Wu, Jie Liang (Beihang University), Jingzhou Fu, Wenqian Deng, Yu Jiang (Tsinghua University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wu-zhiyong
**源文件**：[[atc2025-wu-zhiyong.pdf]]

---

## 一、背景

Atomic DDL（原子数据定义语言）是现代 DBMS 的基础机制，确保 schema 修改（如建表、改表）要么完全成功，要么完全回滚，从而保证数据库完整性。传统 DDL 在执行中途失败时会留下不一致状态，MySQL、PostgreSQL 等主流数据库因此引入了 Atomic DDL 机制。

然而 Atomic DDL 的实现极为复杂，涉及回滚机制、元数据同步、并发控制等多个子系统的协调。实现错误难以避免，且后果严重——可能导致数据损坏、系统崩溃甚至永久性数据丢失。近期 MySQL 的 50 个 Atomic DDL 相关 CVE 中，29 个评分超过 7.0，28% 导致系统崩溃，33% 导致数据损坏或丢失。

现有的 DBMS 测试工具（如 SQLancer、SQLsmith、SQUIRREL）主要关注查询正确性或崩溃检测，缺乏对 Atomic DDL bug 的针对性检测能力。

---

## 二、要解决的问题

1. **缺乏对 Atomic DDL Bug（ADB）的系统性认知**：对 ADB 的表现形式、根因和触发条件没有系统性的研究和分类。
2. **现有测试工具无法有效检测 ADB**：
   - 大多数工具聚焦于 DQL（SELECT 查询），生成的 DDL 语句很少且简单，元数据冲突点不足。
   - 无法检测 DDL 中途中断后的恢复一致性问题。
   - 缺乏对并发 DDL 场景的覆盖。
3. **ADB 的隐蔽性**：很多 ADB 不会立即暴露，而是以潜在的 schema 不一致形式存在，只有在特定查询模式或进一步 schema 修改时才显现。

---

## 三、洞察与设计

**关键洞察**：94% 的 Atomic DDL Bug 由 DDL 语句之间的**元数据冲突**（metadata conflict）触发——即多条 DDL 语句操作或交互于同一元数据元素（表、列、索引、约束）时，最容易暴露 Atomic DDL 实现中的回滚、同步、并发控制和错误处理缺陷。

基于这一发现，作者设计了 DDLUMOS，核心包含两个模块：

### 1. Metadata Conflict-Guided DDL Synthesis（测试用例生成器）

- **Conflict Point Tracking**：维护一个元数据表（Metadata Table），记录每条 DDL 执行后影响的 schema 元素及其冲突点计数。
- **Test Case Synthesis**：在生成测试用例时，DDL 与 DML/DQL 语句交替生成（80% DDL，20% 其他）。选择 DDL 目标时，优先选择冲突点计数较少的元数据元素，确保冲突分布均匀。每条 DDL skeleton 至少包含两个元数据元素以增加冲突可能性。

### 2. Graph-Based Consistency Analysis（元数据一致性分析器）

- **Metadata Graph Construction**：为每个测试用例构建元数据图，以节点表示 schema 元素（表、列、索引、约束、行数等），以边表示依赖或层级关系。每条 SQL 执行后动态更新图。
- **三种 ADB 检测场景**：
  - **Incorrect Result**：比较 metadata graph 期望状态与数据库实际元数据，不一致即报告 bug。
  - **System Unavailability**：执行后检查服务器连接，无响应即报告。
  - **Post-Recovery Data Inconsistency**：异步发送 kill signal 模拟崩溃，重启后比较恢复元数据与期望状态。

---

## 四、实现细节

- **代码规模**：10k 行 C++ 代码 + 4k 行 Bison/Flex 代码 + 1k 行 Python 代码。
- **测试用例长度**：设为 15 条 SQL 语句（基于 207 个已知 bug 中 98% 不超过 15 条语句的观察）。
- **DDL Skeleton 生成**：先随机生成 DDL 骨架（如 `ALTER TABLE [table_name] ADD COLUMN [col1 type], ADD COLUMN [col2 type]...`），再从 metadata table 中填充对象名，优先选择冲突点少的条目。
- **多客户端并发**：启动 2–5 个 client worker 线程分发 SQL 语句，偶尔在前一条未执行完时发送下一条，故意触发并发控制行为。
- **适配新 DBMS**：仅需编写约 10 行元数据查询 SQL + 提供目标 DBMS 的 SQL 语法文件（Yacc），通过 grammar adaptor 自动适配。

---

## 五、实验结果

**实验环境**：Ubuntu 20.04，AMD EPYC 7742 @ 2.25GHz，128 核，504 GiB 内存。每个 DBMS 使用 Docker 容器（5 CPU + 50 GiB RAM）。

### 新发现 Bug（两周测试）

| DBMS | Incorrect Result | System Unavailability | Post-Recovery Inconsistency | 总计 | 已修复 |
|------|-----|-----|-----|-----|-----|
| MySQL | 7 | 4 | 3 | 14 | 2 |
| MariaDB | 8 | 3 | 4 | 15 | 2 |
| Percona | 4 | 4 | 6 | 14 | 3 |
| PolarDB | 4 | 4 | 3 | 11 | 2 |
| GreatSQL | 7 | 3 | 5 | 15 | 2 |
| PostgreSQL | 1 | 2 | 1 | 4 | 3 |
| **总计** | **31** | **20** | **22** | **73** | **14** |

73 个 bug 全部被确认，9 个已分配 CVE ID。

### 与现有工具比较（48 小时）

| 指标 | SQLancer | SQLsmith | SQUIRREL | TXCHECK | DDLUMOS |
|------|----------|----------|----------|---------|---------|
| DDL 相关分支覆盖 | 7,463 | 3,257 | 6,228 | 3,705 | **18,195** |
| 平均元数据冲突点/DDL | 0.30 | 0.03 | 0.18 | 0.45 | **1.24** |
| 检测 bug 数 | 9 | 5 | 4 | 10 | **36** |

### 已知 Bug 重发现（一周测试）

DDLUMOS 在一周内重发现 207 个已知 ADB 中的 196 个（**94.7%**），首两天即达 86.5%。

---

## 六、批判性分析

1. **PostgreSQL 上的发现数明显偏少**（仅 4 个 vs 其他 DBMS 11–15 个）。论文对此几乎没有解释——是因为 PostgreSQL 的 Atomic DDL 实现更成熟，还是因为 DDLUMOS 的测试策略偏向 MySQL/InnoDB 系生态？考虑到 PostgreSQL 使用的是 Atomic DDL Transaction 模型（而非 MySQL 的 Atomic DDL Statement 模型），DDLUMOS 的生成策略可能对 transaction-level atomicity 的覆盖不够充分。

2. **Bug 检测指标可能存在膨胀**：73 个 bug 跨 6 个 DBMS，但 MySQL、Percona、GreatSQL 本质上共享 InnoDB 引擎，MariaDB 也是 MySQL 的分支。同一底层 bug 在多个 fork 中被重复计数是否合理？论文未讨论这些 bug 的去重情况。

3. **实验公平性存疑**：48 小时比较实验中，DDLUMOS 是专为 Atomic DDL 设计的，而 SQLancer 等工具的目标本就不是 DDL 测试。用 DDL 模块的分支覆盖和 ADB 检测数来比较，相当于用跑步成绩来评价游泳选手。

4. **11 个未重发现 bug 的处理过于轻描淡写**：8 个需要特定插件/配置，3 个需要特定执行路径。论文将这些归结为"不修改系统环境"的设计选择，但未讨论这是否意味着 DDLUMOS 无法检测生产环境中配置相关的 Atomic DDL bug——而这恰恰可能是实际部署中最危险的类型。

5. **缺乏端到端性能影响评估**：论文未讨论 DDLUMOS 的测试开销——维护和更新 metadata graph 的成本、每秒生成测试用例数、与传统 fuzzer 的吞吐量对比等。

---

## 七、总结

DDLUMOS 通过对 207 个已知 Atomic DDL Bug 的系统性研究，发现元数据冲突是触发 ADB 的核心条件（94%），并基于此设计了元数据冲突引导的 DDL 合成与图基一致性分析方法。在六个主流 DBMS 上发现 73 个新 bug（全部被确认，14 个已修复，9 个获 CVE）。该工具适用于 DBMS 开发者在 CI/CD 流程中检测 schema 修改的原子性问题，但对 PostgreSQL 生态和需要特定配置/插件的场景覆盖有限。
