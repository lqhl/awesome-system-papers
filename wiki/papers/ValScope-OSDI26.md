---
type: paper
name: ValScope
full_title: "ValScope: Value-Semantics-Aware Metamorphic Testing for Detecting Logical Bugs in DBMSs"
authors: [Li Lin, Liehang Chen, Rongxin Wu]
venue: OSDI
year: 2026
tags: [dbms, testing, metamorphic-testing, sql, correctness]
source_pdf: "[[osdi26-lin-li.pdf]]"
source_md: "[[osdi26-lin-li]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 感知值语义的 DBMS 变形测试（OSDI 2026）

> **原题**：ValScope: Value-Semantics-Aware Metamorphic Testing for Detecting Logical Bugs in DBMSs

> **一句话总结**：ValScope 发现“结果行集合没变”不代表 SQL 结果正确，于是把集合包含关系和数值单调关系放进同一个变形测试模型，再沿 SQL AST 推导局部变形对最终结果的影响；它在 6 个 DBMS 中报告 67 个此前未知的逻辑 bug，其中 57 个获开发者确认，首日发现的 61 个 bug 中有 48 个不能由论文复查的已有 oracle 暴露。

## 问题与动机

DBMS 的逻辑 bug 不会让进程崩溃，而是静默返回错误结果。测试复杂 SQL 时，测试者通常不知道正确答案，这就是测试预言问题（test oracle problem）。差分测试要求多个 DBMS 对同一方言和语义给出可比结果；PQS 一类方法只检查预先选定的 pivot row；变形测试（metamorphic testing）则把一条查询变成另一条查询，只检查两次输出是否满足预期关系。

已有变形测试主要有两类。NOREC、TLP 要求原查询与变形查询完全等价，但两条查询可能继续使用同一个有 bug 的算子，得到“同样错误”的结果。PINOLO 把等价放宽为结果多重集合的包含关系，能检查放宽或收紧谓词后行数是否合理，却仍只看哪些 tuple 出现。

这个盲区在聚合和数值计算中尤其明显。论文图 1 的 MySQL bug 中，`SUM(DISTINCT t1.c4 * 2)` 返回 72；去掉乘 2 后，正确结果应为 36，DBMS 却返回 `NULL`。两次查询涉及的 tuple 没变，集合包含 oracle 看不出问题，但聚合值违反了明确的大小和比例直觉。ValScope 的核心问题因此是：怎样把“值应该变大或变小”变成可执行、可沿复杂 SQL 结构传播的 oracle。

## 关键观察 / 隐含假设

- **观察 1：许多 SQL 变形无法预测精确答案，却能预测结果的偏序关系。** 例如放宽 `WHERE` 通常扩大结果集，`MAX` 在加入更多候选值后不会变小，`COUNT(DISTINCT c)` 不会大于 `COUNT(c)`。
  - **依赖假设**：数据域、NULL、溢出、类型转换和函数语义满足该单调关系。`SUM` 等算子若允许负数，单调方向就需要额外前置条件。
  - **可能失效场景**：`SIN`、`ABS`、`ROUND`、复杂 `CASE` 等非单调函数，以及 `RAND()`、`NOW()` 等非确定函数（§7）。
- **观察 2：集合语义和值语义会在 SQL AST 中相互转换。** 谓词能把值的变化变成行集合变化，聚合又能把集合变化变成标量变化；只在 mutation 点检查局部关系不够。
  - **依赖假设**：每个父算子的输入输出语义层级和保序/逆序方向都被规则表正确描述，并且父节点确实依赖被修改的子节点。
  - **可能失效场景**：vendor-specific coercion、collation、NULL 三值逻辑或未建模算子改变了传播方向。
- **观察 3：真实 bug 多集中在跨层组合，而不是单一简单谓词。** 57 个已确认 bug 中，45 个涉及 subquery、22 个涉及 `GROUP BY`/`HAVING`，32 个需要集合与值之间的跨维传播（§6.2）。
  - **依赖假设**：查询生成器能稳定产出足够复杂但仍可执行的组合；各 DBMS 的执行成功率为 72%–93%。
- **假设 1：用“最早受影响版本”加人工复查可以近似根因去重。**
  - **证据强度**：中；SQLESS 会先最小化 query pair，作者也人工检查，但同一版本中仍可能同时引入多个独立根因。

## 核心方法

### 两种近似关系

集合语义近似（set-semantic approximation）把查询结果视为多重集合。若 `R(q1,D)` 是 `R(q2,D)` 的子多重集合，就记为 `q1 ⪯ˢ q2`；反向则是 over-approximation。它适合描述谓词收紧、`UNION` 与 `UNION ALL` 等对 tuple 成员关系的影响。

值语义近似（value-semantic approximation）比较目标列。若有 `GROUP BY`，系统在相同分组键内对齐结果；否则按非目标列的确定顺序对齐 tuple。对每个可比较分组和目标列，若 `q1` 的值都不小于 `q2`，则记为 `q1 ⪰ᵛ q2`，反之为 under-approximation。论文的可执行检查核心是这种 `≤/≥` 单调关系，并不要求为所有变形预测任意精确的变化幅度。

### 生成原始查询和局部变形

ValScope 先随机建立多张表，并按数据类型生成合法值和边界值。为需要符号前提的算术规则，生成器还能限制列取正值或负值。它从头生成原查询，保证表、列、函数参数和表达式类型之间的依赖一致；支持 JOIN、CTE、nested subquery、`GROUP BY`、`HAVING`、`ORDER BY`、cast 和 `CASE` 等结构。SQLGlot 把查询解析为 AST。

系统共有 26 个近似变形器，其中 17 个处理集合语义，9 个处理值语义（§4.3，表 1）。代表例子包括：`UNION` 改为 `UNION ALL`、`WHERE cond` 改为 `TRUE`、`<` 改为 `<=`、`INNER JOIN` 改为 `LEFT JOIN`、`COUNT(DISTINCT c)` 改为 `COUNT(c)`、`AVG(c)` 改为 `MAX(c)`，以及给表达式加正数。每条规则都携带作用范围、变形方式、语义层级和 over/under 方向。

### 沿 AST 传播近似关系

算法 1 从 mutation 节点建立到查询根节点的祖先链。谓词或 subquery 以集合层开始，表达式或聚合以值层开始；之后只经过真正依赖该子节点的父算子。规则表为每个算子给出两项信息：语义层级怎样变化，以及它保持还是翻转偏序方向。

传播共有四类：Set→Set、Set→Value、Value→Value、Value→Set。例如，放宽过滤条件先扩大集合，外层 `MAX` 再把集合变化变成“值不会减小”；把 `MAX` 换成 `MIN` 先改变值，外层谓词可能把它变成 tuple 集合缩小。算法把每一层的方向符号相乘，到根节点后得到整条原查询和变形查询应满足的集合或值关系。

### 执行、检查和整理报告

两条查询在目标 DBMS 上执行后，集合 oracle 检查子集或超集，值 oracle 检查对齐目标列的单调关系。浮点数使用绝对误差或相对误差容忍区间；`NULL` 被当作单独语义类别，不与普通标量直接比较；厂商特有行为需要人工判断。

不一致 query pair 先交给 SQLESS 做 delta debugging，反复删除 clause、expression 或 subquery，只保留仍能触发问题的最小形式。随后按能复现问题的最早 DBMS 版本分组，再由作者人工去重和提交。实现约 13,455 行 Python，并为 MySQL、MariaDB、Percona、TiDB、OceanBase 和 PolarDB 提供运行脚本。

## 设计取舍

- **偏序 oracle 换取覆盖范围**：不必知道精确结果，就能检查 aggregation 和 arithmetic；代价是只能覆盖能证明单调关系的函数和数据域。
- **规则驱动换取可解释性**：每个 bug 都能追溯到具体 mutator 和传播链，但规则表本身成为正确性可信核心，新方言和新算子都需维护。
- **丰富 SQL 语法换取执行失败**：复杂 subquery、JOIN 和 grouping 提高 bug 触发率，但不同 DBMS 上仍有 7%–28% 查询执行不成功。
- **最早版本去重换取低成本**：比逐个 patch 做根因分析容易，却可能错误合并同版本的不同 bug，或拆开跨分支存在的同一根因。
- **边界条件**：方法最适合确定、可比较、具有单调结构的 DQL；非确定函数和无法可靠排序或比较的结果不适合直接使用值 oracle。

## 实验与结果

- 作者在一台 104 核 Intel Xeon Gold 6230R、500 GB 内存的 Ubuntu 20.04 服务器上，持续约一个月测试 6 个 DBMS。共报告 67 个此前未知的独立逻辑 bug：MySQL 23、MariaDB 10、OceanBase 7、Percona 10、PolarDB 12、TiDB 5；57 个已确认，10 个仍待核实（§6.1–§6.2，表 3–4）。
- 57 个已确认 bug 中，45 个涉及 subquery、17 个涉及聚合、6 个涉及数值表达式、19 个涉及 JOIN、22 个涉及 `GROUP BY`/`HAVING`，类别可重叠。43 个最终违反值语义关系，32 个需要集合和值之间的跨维传播（§6.2）。
- 67 个 bug 中有 61 个在前 24 小时找到。生成速度约为每秒 1,923–2,000 个 query pair；六个 DBMS 的执行成功率依次为 93%、88%、87%、91%、72%、87%（§6.2）。
- 在各工具共同支持的最新 DBMS 上运行 24 小时，ValScope 比 PQS、NOREC、TLP、DQP、PINOLO、EET 分别多发现 28、10、20、36、40、23 个 bug。对首日 61 个 bug 人工构造已有 oracle 所需的查询后，PINOLO、TLP、NOREC、DQP 分别只能暴露 12、4、2、6 个；48 个只被 ValScope 暴露，占 78.9%（§6.3，表 5）。
- 57 个已确认 bug 中，48 个最早出现在 2020 年前，53 个出现在 2023 年前；每个目标 DBMS 都至少有一个潜伏超过 3 年的 bug，最长为 MySQL 的 20 年（§6.3，表 6）。MariaDB 案例中，`AVG()` 漏设 collation，使 `UNION ALL` 的结果被错误提升为 binary 类型；开发者补上 metadata 初始化后修复（图 6）。
- 开发者反馈提供了严重性旁证：一个 MySQL bug 被标为 serious，MariaDB 的 10 个 bug 均被标为 Major。不过这些标签不是统一的跨 DBMS 严重性量表；10 个 pending 报告也不能视为已证实 bug（§6.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 值语义 oracle 能发现集合 oracle 看不到的逻辑错误 | 43/57 已确认 bug 违反值关系；首日 48/61 不能由复查的已有 oracle 暴露（§6.2–§6.3） | 已有 oracle 的覆盖通过人工构造对应变形查询判断 | 强 |
| 集合和值之间的传播对复杂查询有实际作用 | 32/57 已确认 bug 需要跨维传播；45 个涉及 subquery（§6.2） | 论文没有移除 propagation 后的同生成器消融 | 中 |
| 方法在多个工业 DBMS 上可用 | 六个系统都有报告，57/67 获确认（表 4） | 目标均采用或兼容 MySQL 语法，DBMS 家族多样性有限 | 强 |
| 相比已有工具，首日找 bug 效率更高 | 24 小时对比中在共同支持目标上领先所有六个基线（表 5） | 只运行一次最新版本；支持范围、生成器和调参不完全相同 | 中 |
| 方法能找到长期漏检的问题 | 48 个已确认 bug 在 2020 年前已存在，最长潜伏 20 年（表 6） | 年代来自最早可复现版本，不等于精确根因引入时间 | 强 |

## 批判性分析

### 论证链条

论文先用 MySQL 的 `SUM(DISTINCT)` 案例指出集合语义盲区，再定义值偏序、四类 AST 传播和具体 mutator，最后以开发者确认 bug、oracle 回放和历史版本验证覆盖增量。问题、抽象、实现和结果之间的链条清楚，尤其是 43 个值语义 bug 和 32 个跨维传播 bug，直接对应方法的两个新部件。

但“收益来自值语义模型”与“收益来自更丰富生成器、26 个变形器和更复杂 SQL 语法”没有完全拆开。论文没有用同一个生成器分别关闭 value mutator、传播算法或某类语法做消融，因此 bug 总数不能全部归因于统一近似模型。作者给出的 bug 分类是支持性证据，不是严格的因果分解。

### 假设压力测试

值关系的正确性取决于隐藏的数学前提。例如，向输入集合加入负数会让 `SUM` 下降；整数溢出、decimal rounding、隐式 cast 和不同 collation 也可能改变偏序。实现通过类型、符号、NULL 规则和人工确认降低风险，但论文没有给出覆盖完整 SQL 标准和六个方言的形式化证明。

非单调但确定的函数可以被当作原子表达式，再在外层加 `+2` 或乘正数来测试；这只能检查外层变换，不能直接推导函数自身随输入如何变化。`RAND()`、`NOW()` 等非确定函数则完全超出当前稳定性假设。并发事务、隔离级别和 DML 也不在本文 DQL oracle 的范围内。

### 实验可信度

开发者确认、最小化案例、历史版本复现和真实修复案例让“确实找到 bug”这一结论很强。评测还列出每个 DBMS 的成功率、生成速度、bug 类型和发现时间，证据比只报总数完整。六个 baseline 都在最新版本上运行相同 24 小时，是有价值的实测对比。

不过，最新版本可能已经修复旧工具最擅长的 bug，而 ValScope 的新 oracle 尚未被针对性修复；这会放大当下差距，但不否定补充性。不同工具支持的 DBMS 数不同，表 5 的 increment 只能在各自共同集合上计算，不能横向当成统一总分。论文没有报告重复实验的方差、代码覆盖或每个工具的调参预算，也没有直接用 patch/stack trace 证明 67 个分组都对应不同根因。

### 系统性缺陷

ValScope 依赖人工工作：vendor-specific 语义要人工判定，SQLESS 简化后仍要人工去重和提交，baseline oracle 覆盖也靠人工构造。随着 dialect、函数和变形器增加，规则正确性与维护成本会持续上升。论文说适配新方言通常只需几百行或可借助 QTRAN，但没有在 PostgreSQL、SQLite 或 DuckDB 等不同语法和实现家族上验证。

浮点容忍区间存在不可消除的取舍：阈值过大可能掩盖小幅数值 bug，过小则把合法 rounding 当成问题。confirmed 集合中没有持续 false positive，只说明最终报告质量较高，不能量化生成期间候选误报率或人工筛选成本。近一个月 campaign 所需的 CPU 时间、候选总数和每个确认 bug 的人工工时也未报告。

## 局限与后续工作

- **局限 1**：值语义传播只覆盖能建立稳定单调关系的算子；`SIN`、`ABS`、`ROUND`、复杂 `CASE` 和非确定函数没有通用 oracle（§7）。
- **局限 2**：NULL、浮点误差、类型提升和厂商特有语义仍需专门规则或人工确认，传播规则没有端到端形式化证明。
- **局限 3**：测试集中在 6 个 MySQL 语法兼容系统和 DQL，不能直接外推到不同家族 DBMS、事务逻辑或并发执行。
- **后续工作 1**：在同一查询生成流上分别关闭 9 个 value mutator、跨维传播和复杂语法，以 24 小时确认 bug 数、有效 query 数和代码覆盖量化每个部件的独立贡献。
- **后续工作 2**：用修复 patch、堆栈或 optimizer rule 替代“最早版本”做根因聚类，并公开候选数、误报数和人工处理时间。
- **后续工作 3**：把规则扩展到至少两个非 MySQL 家族 DBMS，并为每条传播规则生成可由参考解释器或 SMT 检查的边界测试，重点覆盖 NULL、overflow、cast 和 collation。

## 相关

- **相关概念**：变形测试、SQL fuzzing、测试预言、delta debugging、DBMS 正确性
- **同类系统**：PINOLO、NOREC、TLP、EET、PQS
- **同会议**：[[OSDI-2026]]
