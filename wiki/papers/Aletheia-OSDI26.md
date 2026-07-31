---
type: paper
name: Aletheia
full_title: "Aletheia: Automated Detection of Data Integrity Violations in Microservices"
authors: [Mafalda Sofia Ferreira, João Ferreira Loff, João Garcia, Rodrigo Rodrigues]
venue: OSDI
year: 2026
tags: [microservices, static-analysis, data-integrity, databases, program-analysis]
source_pdf: "[[osdi26-ferreira.pdf]]"
source_md: "[[osdi26-ferreira]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 微服务数据完整性违规的自动检测（OSDI 2026）

> **原题**：Aletheia: Automated Detection of Data Integrity Violations in Microservices

> **一句话总结**：Aletheia 观察到 microservice 拆分使 foreign key、primary key 和 uniqueness 约束跨越异构 datastore、只能由应用代码维护，于是把 ER/relational-algebra 违规模式编译成 SSA taint 与 abstract call-graph 静态分析；七个开源应用中发现 50 个真问题（46 个此前未报告），precision 81%、recall 69%，500-service synthetic application 在 20 分钟内完成。

## 问题与动机

microservice 允许每个团队独立选择 SQL、NoSQL、cache 或 message broker，却也把原本单库内可声明的关系拆散。跨服务 foreign key 无法由数据库执行，primary key 的同一 entity 副本可能只创建一半，某服务的 uniqueness rejection 也可能与另一服务的成功写入组合成 partial state。

开发者通常无法掌握几十个服务、RPC 与 storage semantics 的全局行为。Aletheia 试图在部署前从代码自动恢复数据 schema 和跨服务关联，再识别可能破坏 referential/entity/uniqueness integrity 的 operation sequence，而不要求用户先手工提供 schema。

## 关键观察 / 隐含假设

- **观察 1：三类经典 ER constraint 虽失去物理共址，逻辑条件并未改变。** 可以用 relational algebra 描述跨 datastore 的 delete cascade 缺失、partial write 和 concurrent uniqueness conflict（§3、图 2）。
  - **依赖假设**：目标数据模型可映射到 table/record/attribute 抽象，事务和 merge semantics 可由有限 operation pattern 表达。
  - **可能失效场景**：CRDT、自定义 compensating saga、event sourcing 或 application 明确容忍 transient dangling state。
- **观察 2：检测只需要保留与 datastore/RPC 相关的数据流，而非完整 interprocedural graph。** SSA taint 被压缩进 abstract call graph 后，可在 graph 上恢复 schema 和查 pattern（§4）。
  - **依赖假设**：静态 call target、serialization 与 datastore wrapper 可解析，reflection/dynamic dispatch 不会隐藏关键流。
- **假设 1：静态 potential violation 接近开发者关心的真实 bug。**
  - **证据强度**：中；50 个 true positive 表明问题真实，但 ground truth 是人工近似，precision 81%/recall 69% 仍留下明显噪声和漏报。
- **假设 2：Blueprint/Go 应用足以代表多语言 production microservice。**
  - **证据强度**：弱；部分 benchmark 需要 port，语言/框架 adapter 成本未在评测中体现。

## 核心方法

形式层把 global application state 定义为各 datastore state 的并集，用 read/write/delete 及跨库 relation 描述 integrity。referential 模式关注写引用后被引用对象不存在或 delete 未 cascade；entity 模式关注同一主键关联的 partitioned records 不完整；uniqueness 模式覆盖 weakly replicated database 上 concurrent writes 与不同 conflict resolution 造成的跨库分歧（§3.2–3.4）。

分析层先把各 service 编译为 [[Static-Single-Assignment|SSA]] IR，对 database operation 的 value、table/collection、key 和 RPC argument 做 taint propagation（图 3）。随后只保留 remote call、datastore operation 与过滤后的 taint，形成跨服务 abstract call graph；迭代传播跨 RPC 的 annotation，恢复实体、key 和 association（图 4）。

最后把形式化 pattern 转为 graph traversal rule，报告可能违规的 source operation 与 call chain。实现以 Go/Blueprint 为分析入口，覆盖 MongoDB、MySQL、Redis/Memcached 和 RabbitMQ 等 backend。

## 设计取舍

- **无用户 schema 换推断误差**：自动 adoption 简单，但变量 alias、wrapper 和业务语义会带来 FP/FN。
- **静态覆盖换运行时精度**：可分析罕见 path，不需要 trace；却无法知道 branch feasibility、database configuration 与 compensating action 是否实际生效。
- **抽象图扩展性换上下文丢失**：压缩 SSA 支持大 graph，但不同 path/context 合并会制造 infeasible sequence。
- **边界条件**：显式 RPC、可识别 datastore API、简单 request chain 最适合；reflection、queue-driven async flow、dynamic schema 与 saga 会变脆。

## 实验与结果

- 七个 3–31 service、2–21 datastore、最多 4,462 LoC/170 RPC 的 e-commerce、social、media 与 booking 应用上，Aletheia 得到 50 [[Tensor-Parallelism|TP]]、12 FP、22 FN，即 precision 81%、recall 69%；46 个 TP 未被既有文献报告（表 2）。
- realistic application 均在 4 秒内完成；TrainTicket 从 13 到 31 services 只使时间由 2.07s 增到 3.52s，remote call 数比 service 数更决定成本（图 5）。
- 基于 Alibaba call-graph 参数的 synthetic apps 最多 500 services、2,887 call graphs；约 130K total invocations 的配置耗时 801–1,152s（约 13–19 分钟），表明总 invocation count 是主要 scaling factor（表 3、§5.4）。
- 系统识别 referential、entity 与 uniqueness 三类问题；较大应用因跨 datastore association 更多而报告更多 violation，例如 TrainTicket 约为 Digota 的八倍（§5.2–5.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 数据完整性 bug 在成熟 microservice benchmark 中普遍存在 | 表 2：50 TP、46 个此前未报告 | 七个 Blueprint/Go 开源应用，人工 ground truth | 中 |
| static pattern detection 有实用但非完整精度 | 表 2：81% precision、69% recall | 50 TP/12 FP/22 FN 的小样本 | 强 |
| realistic codebase 分析可进入开发流程 | 图 5：七个应用均少于 4s | 最大 31 services、4,462 LoC | 强 |
| 方法可扩到 production-like call-graph 数量 | 表 3：500 services/130K invocations 少于 20min | synthetic stub，非完整 production logic | 中 |

## 批判性分析

### 论证链条

从 ER invariant 到 operation pattern、再到 SSA/graph detector 的映射清晰；实际发现新 bug 支撑问题重要性。论文把报告项称为“可能导致 inconsistency 的 programming issue”，这是恰当边界：静态匹配不证明运行中一定发生，也不证明应用不能容忍。

### 假设压力测试

eventual system 常故意经历 intermediate inconsistency，稍后由 saga/reconciler 修复；若分析看不到定时补偿，会误报。反之，dynamic SQL、reflection、message queue consumer、cross-language serialization 和 stored procedure 会断开 taint，造成漏报。数据库实际 unique index、LWW/CRDT 配置也会改变 pattern semantics。

### 实验可信度

公开应用横跨多 domain/backend，手工审计 TP/FP/FN 而非只报检测数，较可信。69% recall 说明 current abstraction 尚不稳；ground truth 本身是作者“广泛人工搜索”的近似。500-service scaling 使用 stub，解析和 alias complexity 远低于 production code，不能等同于真实 500-service deployment。

### 系统性缺陷

报告 19% false positive 会在大型 CI 中累积 triage 成本；缺少 suppression、incremental analysis、ownership routing 和跨 commit regression workflow 的评测。Aletheia 也不生成修复或验证补偿逻辑，开发者仍需理解 transaction/isolation/业务 invariant。

## 局限与后续工作

- **局限 1**：只覆盖三类 canonical constraint，不覆盖 check/not-null、aggregate、temporal 与业务特定 invariant。
- **局限 2**：对动态语言、reflection、async messaging 和 saga compensation 的支持边界有限。
- **后续工作 1**：在多语言 production-like benchmark 中加入 Kafka/event sourcing/saga，分别报告每种 feature 的 precision/recall。
- **后续工作 2**：结合 bounded symbolic execution 检查 branch feasibility，以 FP reduction、analysis time 和 peak memory 衡量代价。
- **后续工作 3**：做 incremental CI 与 developer study，测量每个真实 bug 的确认时间、suppression rate 和修复后 regression detection。

## 相关

- **相关概念**：[[Microservices]]、[[Data-Integrity]]、[[Static-Analysis]]、[[Eventual-Consistency]]
- **同类系统**：[[DeathStarBench]]、[[TrainTicket]]、[[Blueprint]]
- **同会议**：[[OSDI-2026]]
