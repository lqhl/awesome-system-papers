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
last_reviewed: 2026-07-30
---

# 感知值语义的 DBMS 变形测试

> **原题**：ValScope: Value-Semantics-Aware Metamorphic Testing for Detecting Logical Bugs in DBMSs

## 一句话总结

ValScope 把 SQL approximation oracle 从 result-set inclusion 扩展到数值变化的方向与幅度，并沿 AST 传播局部 mutation 的全局语义，在 6 个 DBMS 中找到 67 个独立逻辑 bug，其中 57 个获确认。

## 问题与动机

DBMS logical bug 静默返回错误结果，难点是复杂 query 没有 ground truth。NOREC/TLP 用等价变换，但原、变形 query 可能共同触发同一 buggy operator；PINOLO 放宽为 set-semantic over/under approximation，却只能比较 tuple containment。`SUM(DISTINCT x*2)` 等 aggregation、arithmetic、ordering bug 可能保持 tuple set 不变，只破坏 scalar value，因此仍不可见。

ValScope 建立统一的 SQL query approximation：set dimension 描述结果 tuple 的 inclusion/equivalence；value dimension 描述在 tuple set 保持或可控变化时，computed value 应增加、减少、相等或满足幅度关系。两者组合成为无需已知正确输出的 metamorphic oracle。

## 关键观察 / 隐含假设

### 关键观察

- 很多 aggregation/arithmetic mutation 具有可预测的 monotonic relation，即使无法预测精确值。
- 局部 AST node 的 approximation 可按 operator transfer rule 向 root 传播，得到最终 result relation。
- set 与 value 不是互斥 oracle；cross-dimension propagation 能覆盖 predicate relaxation 与 aggregation change 的组合。
- 高质量 oracle 比单纯增加随机 SQL 数量更重要：61 个首日 bug 中 48 个超出现有 oracle 检测范围。

### 隐含假设

- mutator 的前置条件、SQL type、NULL 与 numeric domain 足以保证预期 approximation sound。
- DBMS vendor-specific semantics 可通过手工规则区分 bug 与合法差异。
- floating-point tolerance 不会掩盖真实小幅错误，也不会把 rounding difference 当 bug。
- 以 earliest affected version 聚类能近似 deduplicate root cause，但不同 bug 可能共享版本。

## 核心方法

### 统一近似模型

set-semantic relation表示 original/mutated result 的子集、超集或等价；value-semantic relation记录 scalar 或 tuple field 的相等、单调方向和可推断 magnitude。mutation 只在满足 schema、domain、functional dependency 等约束时使用，以避免生成本身语义未定义的 oracle。

### 生成、变形、传播与验证

系统先依据 schema/data 生成含 join、subquery、grouping 与 expression 的有效 original query，再用预定义 mutator 改 predicate、aggregate、arithmetic/operator 等 AST node。approximation propagation 从 mutation point 沿 parent operator 计算 relation；若 operator 无法安全传播则放弃 test。执行 query pair 后，同时按 set containment、value relation、NULL-aware 和 epsilon numeric comparison 检查违反。

### 报告处理

ValScope 用 SQLESS delta debugging 删除 clause/expression/subquery，同时重复执行保持 violation；再沿用 PINOLO 的 version-based grouping 去重，最终人工确认并向 developer 提交。实现已开源。

## 实验与结果

**证据定位**：§6.2–§6.3、表 3–5；在 6 个 DBMS benchmark 上，相比 PINOLO 等 baseline，ValScope 在共同支持目标中最多多发现 40 个 logical bug。

目标为 MySQL、MariaDB、OceanBase、Percona、PolarDB 与 TiDB，campaign 近一个月。

- 共发现 67 个 unique logical bug：MySQL 23、MariaDB 10、OceanBase 7、Percona 10、PolarDB 12、TiDB 5；57 个获确认。
- 61/67（超过 90%）在前 24 小时发现，说明并非只靠超长 fuzzing 累积。
- execution success rate 分别为 93%、88%、87%、91%、72%、87%，PolarDB 上有效 query 比例相对较低。
- 在双方共同支持 DBMS 上，ValScope 比 PQS、NOREC、TLP、DQP、PINOLO、EET 分别多找 28、10、20、36、40、23 个 bug。
- 对首日 61 个 bug 人工构造 baseline oracle 后，PINOLO/TLP/NOREC/DQP 只能覆盖 12/4/2/6 个；ValScope 独有 48 个，即 78.9%。
- false positive 主要来自 float、NULL 和 vendor semantics；系统用 absolute/relative epsilon 与 NULL-aware rule，confirmed bug 中未观察持续误报。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| value semantics 扩大 DBMS oracle 覆盖 | 67 个 bug；首日 48/61 为现有 oracle 无法检测 | baseline coverage 部分依赖人工构造变形 query | 强 |
| 方法能跨多 DBMS 工作 | 6 个系统均发现 bug，57 个获确认 | 多数是 MySQL 生态，SQL engine 多样性有限 | 强 |
| 生成与约束足够实用 | success rate 72%–93%，超过 90% bug 首日出现 | 长期 campaign 的 compute/throughput 未完整归一化 | 强 |
| 比现有 MT 更有效 | 共同目标上比 PINOLO 多 40 个 bug | 最新版本可能已修复 baseline 擅长的旧 bug | 强 |
| 报告质量可接受 | SQLESS reduction、版本聚类、人工确认；confirmed 中无持续 false positive | 未确认的 10 个不一定都是真 bug | 强 |
## 批判性分析

### 论证链条

论文准确识别了 set-based oracle 的盲区，并把 value relation 纳入同一 propagation framework，而不是堆叠零散 aggregate special case。真实 DBMS bug 数量与 baseline-oracle 回放强力支持 novelty；生成、简化、去重和提交组成了完整工程闭环。

### 假设压力测试

- approximation rule 的 soundness 是可信核心，论文没有对完整 SQL/NULL/type-coercion 语义做形式化证明。
- version-based dedup 可能把同版本多个 root cause 合并，也可能把同一 root cause 的版本差异拆开。
- MySQL、MariaDB、Percona、PolarDB、OceanBase 共享大量 lineage，67 个结果并非 6 个完全独立 engine 的证据。
- 与 baseline 的 bug 数比较受 target version、运行时长、query validity 与 tuning 影响。
- epsilon comparison 存在两难：阈值大则漏掉 precision bug，阈值小则产生平台相关误报。
- ordering、window function、nondeterminism 和 collation 的 value semantics 仍很难稳定建模。

### 实验可信度

6 个 DBMS、developer confirmation 与 baseline-oracle 回放提供强实证；但多个目标共享 MySQL lineage，version-based dedup 和人工构造 baseline query 可能影响独立 bug 数。

## 局限与后续工作

- **局限**：approximation rule、NULL 和 type coercion 是未形式化验证的可信核心。
- **后续工作**：应扩展不同 lineage DBMS，并用 patch/stack trace 做 root-cause dedup 与 oracle soundness 验证。

后续应形式化 approximation algebra；扩展 window、JSON、temporal、collation 与 user-defined function；用 execution plan/coverage 引导 mutator；采用 stack trace、patch 或 optimizer rule 做 root-cause dedup；并在 PostgreSQL、SQLite、DuckDB 等不同 lineage 上复验。

## 相关概念

- [[Metamorphic-Testing]]
- [[DBMS-Correctness]]
- [[SQL-Fuzzing]]
- [[Test-Oracle]]
- [[Delta-Debugging]]
