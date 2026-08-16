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
last_reviewed: 2026-08-14
---

# 自动检测微服务中的数据完整性违规（OSDI 2026）

> **原题**：Aletheia: Automated Detection of Data Integrity Violations in Microservices

> **一句话总结**：微服务把原本可由单库约束的数据关系拆到多个异构 datastore 后，完整性只能靠应用代码维护；Aletheia 把 ER/relational algebra 中的五类危险操作模式转成 SSA taint 与抽象调用图分析，在七个开源应用上取得 81% precision、69% recall，并找出 46 个此前未报告的 true positive。

## 问题与动机

[[Microservices]] 允许每个服务独立开发、部署并选择 MySQL、MongoDB、Redis、message broker 等存储，但数据的逻辑关系并不会因为物理拆分而消失。单体数据库中的 foreign key、primary key 和 unique index 能原子检查同一 schema；拆分后，关系可能跨越服务和数据库，任何单个 datastore 都看不到完整状态，也无法执行跨库 constraint。

这会产生三类问题。引用完整性（referential integrity）可能因删除未级联或并发创建引用而留下 dangling record；实体完整性（entity integrity）可能因同一 entity 的不同分片没有同时可见，使一个 primary key 只能找到部分记录；唯一性（uniqueness）可能在一个弱一致数据库解决并发冲突时丢掉一次写入，但另一个数据库仍保留同一请求的副作用，形成 partial result（§2、图 1–2）。

这些不是仅靠把每个数据库配置为“更强一致”就能统一解决的问题：服务会使用不同事务和复制语义，跨库 transaction 往往不存在，saga 也通常不提供 isolation。开发者必须在应用代码中维护全局关系，但几十个服务、RPC、队列和 datastore 让人工审计很难覆盖完整调用链。Aletheia 的目标是在运行前从代码自动恢复这些关系，不要求用户先提供 ER schema，再报告可能破坏约束的操作位置。

## 关键观察 / 隐含假设

- **观察 1：物理 schema 被拆散后，经典 ER constraint 的逻辑条件仍可跨库表达。** 论文用 relational algebra 枚举 read、write、delete 的组合，得到 3 个 referential、1 个 entity 和 1 个 uniqueness 危险模式（§3、图 2）。
  - **依赖假设**：datastore 都能抽象为 table/record/field 与有限的 read/write/delete，且应用关心的异常属于这五种模式。
  - **可能失效场景**：event sourcing、CRDT、自定义 merge、aggregate/temporal invariant，或业务明确容忍短暂 dangling state 并稍后修复。
- **观察 2：只保留 RPC、datastore operation 及相关 value flow，就足以检测这些模式。** 每个 service 内先做完整 SSA taint，跨服务时压缩成 abstract call graph，避免把所有 service 的 SSA graph 直接拼在一起（§4.1–§4.2、图 3–4）。
  - **依赖假设**：RPC endpoint、call site、database API、serialization field 和 call target 都可静态识别。
  - **可能失效场景**：dynamic query、reflection、运行时生成 key、跨语言序列化、stored procedure，或由用户在两个独立请求之间传递关联值。
- **观察 3：同一值先后流入两个 datastore operation，可以用来推断隐式 foreign key。** Aletheia 根据 read/write 类型、先后顺序以及值是 read key 还是 return value，推断哪个 field 引用哪个 field（§4.3）。
  - **依赖假设**：共享值代表实体关联，而不是碰巧相同的业务值；操作顺序能可靠表示引用方向。
  - **可能失效场景**：hash、组合表达式、非唯一查询字段或同一 ID 在不同 namespace 中复用，会产生错误关系或方向。
- **假设 1：静态匹配到的 potential violation 可以作为开发者可行动的 bug warning。**
  - **证据强度**：中。七个应用有 50 个 true positive，且多个项目作者确认；但仍有 12 个 false positive、22 个 false negative，ground truth 也是论文作者人工近似得到。
- **假设 2：Blueprint 的统一 service/storage abstraction 能代表真实多语言微服务的分析难度。**
  - **证据强度**：弱。当前实现只直接分析 Go SSA 和 Blueprint，四个应用经过移植；其他 framework 只被作者描述为未来可接入，并未评测 adapter 或语义损失。

## 核心方法

论文先建立一个与物理存储无关的模型：全局状态是各 datastore 状态的组合，数据对象用 table、record、field 表示；document collection、key-value table 也映射到同一抽象。基于 read/write/delete，作者定义五个需要检测的模式（§3、图 2）：

- `RI-1`：删除被引用记录，却没有在同一请求中删除引用它的记录，即缺少 cascade delete。
- `RI-2`：一个请求创建引用，另一个并发请求删除被引用记录，最后留下 dangling reference。
- `RI-3`：同一请求向两个异步复制的 datastore 写入被引用记录和引用记录，其他请求可能在两次写尚未同时可见时读到中间状态。
- `EI-1`：同一 entity 的分片以相同 primary key 写入两个 datastore，但异步可见性使读者只能看到其中一半。
- `Un-1`：并发请求写入两个弱一致 datastore；其中一个 datastore 的 uniqueness conflict resolution 丢弃一方，但另一个仍保留双方的 dependent write。

第一阶段在每个 service 内构建静态单赋值（Static Single Assignment，[[Static-Single-Assignment|SSA]]）graph。Aletheia 识别 database operation 和 remote-service invocation，把 database/table/field、RPC parameter/return value 等 annotation 作为 taint，沿定义—使用边传播。分析也跨越同一 service 内的普通函数调用，但只把到达 service boundary 的 taint 带到下一阶段。对 NoSQL object、map 和 queue binary payload，只要字段能从静态类型或固定 key 恢复，同样可以追踪（§4.1、图 3）。

第二阶段构建抽象调用图（abstract call graph）。node 是 service endpoint 或 datastore instance，edge 是 RPC、database access，或者由 queue/event 触发的反向调用；parameter 和 return value 被压缩成带 taint 的 abstract object。从每个 frontend entry point 遍历时，系统在 caller argument、callee parameter 和 return object 之间合并 annotation，使一个值的 provenance 跨越多个 service，而不再保留无关 SSA instruction（§4.2、图 4）。

当同一 abstract object 同时带有两个 datastore operation 的 taint 时，schema extractor 推断 association。`(read, write)`、`(write, read)` 和 `(write, write)` 依据 operation 顺序判断引用方向；两个 read 时还区分值来自查询 key 还是返回 field。这个规则自动生成跨库 foreign key，但也把业务语义压缩成顺序启发式，是精度损失的主要来源之一（§4.3）。

最后，detector 遍历抽象调用图中的 database operation，匹配 `RI-1` 到 `Un-1` 五个公式，报告相关 source location 和 call chain（§4.4）。实现使用 Go 的 SSA IR。它依赖 [[Blueprint]] 把 remote invocation 表示成普通函数调用、把不同 database driver 包装成统一接口；因此论文能够分析 MongoDB、MySQL、Redis、Memcached 和 RabbitMQ，但当前能力来自 framework 提供的静态识别点，而不是自动理解任意微服务代码（§4.5）。

## 设计取舍

- **零 schema 输入换关系推断误差**：开发者无需维护跨服务 ER 图，但 shared value、operation 顺序和 taint merge 可能制造不存在的 foreign key，也会漏掉只存在于业务语义中的关系。
- **静态覆盖换 execution feasibility**：不需要生产 trace，理论上能看到罕见路径；却不知道两个 branch 是否能同时发生、数据库实际配置如何，或业务是否用补偿流程恢复状态。
- **抽象调用图换上下文精度**：去掉无关 SSA node 后能扩到大量 call graph，但 path/context 合并会把不可达的 operation sequence 拼在一起。
- **统一 framework 换生态覆盖**：Blueprint 简化 RPC 和 storage 识别，也限制了对真实 polyglot、reflection-heavy、framework-specific code 的外部有效性。
- **保守 warning 换 triage 成本**：宁可报告 potential violation，也会把业务允许的不级联删除或已有协调当成问题；系统允许 suppress cascade warning，但论文没有评测 suppression workflow。
- **边界条件**：显式 RPC、静态 query、固定 schema、单个 request 内能看见完整 value flow 时最可靠；cross-request association、dynamic query 和后台 cleanup 最容易漏报。

## 实验与结果

- 测试机是两颗 Xeon Gold 5320（合计 52 cores）、256 GB RAM，每个结果取 5 次平均。七个 realistic application 覆盖 3–31 个 service、2–21 个 datastore、173–4,462 LoC、6–170 个 RPC 和 3–58 个 call graph；四个应用被移植到 Blueprint，MediaMicroservices 与 TrainTicket 还补了作者认为缺失的 endpoint（§5.1、表 2）。
- 人工审计得到 50 true positives、12 false positives、22 false negatives，对应 81% precision 和 69% recall；50 个 true positive 中 46 个此前未在文献报告。TrainTicket、Digota、PostNotification、SocialNetwork、MediaMicroservices 的开发者确认了报告问题；EShopMicroservices 只对最初的 `RI-1` 报告作了确认与修复建议（§5.2、表 2）。
- true positive 包括 Digota 4 个、EShopMicroservices 8 个、PostNotification 1 个、SocialNetwork 3 个、MediaMicroservices 5 个和 TrainTicket 29 个。TrainTicket 的 29 个由 10 个 `RI-1`、15 个 `RI-2`、4 个 `RI-3` 组成；MediaMicroservices 还覆盖 1 个 `EI-1` 和 1 个 `Un-1`（§5.3）。
- 12 个 false positive 中，SockShop 的 6 个来自业务有意不 cascade cart deletion 或已有安全协调，TrainTicket 有 3 个类似语义误报；另 3 个来自过度 taint，把表达式中不同来源的值合并成错误 foreign key。22 个 false negative 中，8 个来自非 key query filter，14 个来自跨请求 user-input association（TrainTicket 12、EShopMicroservices 2）（§5.2）。
- 七个 realistic application 都在 4 秒内完成，时间从 1.35 s 到 3.52 s；SocialNetwork 的 13 services 到 TrainTicket 的 31 services 只从 2.07 s 增到 3.52 s，RPC/total invocation 比 service 数更能预测时间，且 parsing 占主要成本（§5.4、图 5）。
- synthetic 配置基于 Alibaba trace 的 call-depth/fan-out/request-volume 分布。500-service 的 APP3/APP4 分别用 800.95/908.03 s、9.94/10.08 GB；最大 2,887 call graph 的 APP5 其实只有 50 services，耗时 1,151.69 s、峰值 11.32 GB。所有配置都少于 20 分钟，但这两个“最大规模”不是同一次实验（§5.4、表 3、图 5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 跨服务数据完整性问题在常用 benchmark 中确实存在 | 表 2、§5.3：50 true positives，46 个此前未报告 | 七个 Go/Blueprint 开源应用，部分经过移植或补 endpoint | 中 |
| 自动恢复 schema 与 pattern matching 有用，但离完整检测仍有距离 | 表 2：81% precision、69% recall | 人工近似 ground truth，50 TP/12 FP/22 FN | 强 |
| 五个形式化模式能覆盖三类 canonical integrity constraint 的实例 | §3、图 2；MediaMicroservices 同时命中 RI/EI/Un | 只覆盖作者定义的 read/write/delete 模型 | 中 |
| realistic benchmark 的分析速度足以放入开发流程 | 图 5：七个应用 1.35–3.52 s | 最大 31 services、4,462 LoC、170 RPC | 强 |
| abstract call graph 能扩展到 production-like 图规模 | 表 3、图 5：约 130K invocation 时 801–1,152 s | synthetic stub；峰值 memory 约 10–11.32 GB | 中 |

## 批判性分析

### 论证链条

论文的主线清楚：先从 ER constraint 推导危险 operation pattern，再说明哪些 value-flow 信息足以匹配公式，最后用 SSA 和抽象调用图实现。50 个 true positive 证明问题和方法都有实际价值。不过形式化的“完备”只针对作者限制后的三种 operation 组合，不等于对真实微服务完整性 invariant 的完备覆盖；check、not-null、aggregate、temporal 和业务特定 constraint 都不在模型中。

### 假设压力测试

`RI-3`、`EI-1`、`Un-1` 是否真的发生，取决于复制、session guarantee、transaction 和 conflict-resolution 配置；代码中出现模式只能证明有风险，不能证明某个部署一定违规。相反，saga、reconciler 或周期性 cleanup 可能在 request path 外恢复数据，Aletheia 看不到时会误报。用户把一个 service 的返回值带到另一次请求、dynamic query 只把值用于 filter，都会切断静态 taint 并漏掉真实关系。

### 实验可信度

论文不只报告 warning 数，还人工区分 TP/FP/FN、解释错误来源，并把问题提交给开发者，这比没有 ground truth 的 case study 更可信。但 ground truth 由同一团队“广泛人工搜索”近似得到，69% recall 已显示漏报明显。四个应用经过 Blueprint port，两个 benchmark 又增加 endpoint；虽然多组开发者确认问题，这些改动仍改变了被分析的 code path，必须和原始 production code 区分。

scalability 实验的 graph 参数来自 Alibaba production trace，但 service body 是生成的 stub，只包含可配置数量的 write/delete。它证明 graph traversal 能处理约 130K invocation，不证明系统能处理 500 个真实 service 中的 alias、generic、reflection、复杂 query 和构建依赖。最大配置还需要 9.94–11.32 GB memory，CI 资源成本并不小。

### 系统性缺陷

实现目前依赖 Blueprint；接入 gRPC codegen、REST framework、Kafka、ORM、不同语言和自定义 database wrapper 都需要新的识别逻辑，论文没有量化工程量。系统只报告风险，不验证 runtime execution，也不生成 transaction、coordination 或 compensation 修复。大型代码库中的 ownership routing、incremental analysis、baseline suppression、重复 warning 合并和修复后 regression detection 均未评测，19% 的 false-positive 比例可能积累成显著 triage 成本。

## 局限与后续工作

- **局限 1**：只覆盖 referential、entity、uniqueness 三类 constraint 与五个 operation pattern，不覆盖更广的业务 invariant。
- **局限 2**：实现只直接支持 Go SSA 与 Blueprint 的统一 abstraction，多语言和常见 production framework 尚未验证。
- **局限 3**：动态 query/filter 与跨请求 user-input association 会漏报；后台 cleanup 或惰性 enforcement 会误报。
- **局限 4**：precision/recall 基于作者人工近似 ground truth，且部分应用经过移植或增加 endpoint。
- **局限 5**：大规模结果来自 synthetic stub；最多 2,887 call graph 的配置峰值 memory 达 11.32 GB。
- **后续工作 1**：建立保留原 framework 的 polyglot benchmark，包含 gRPC、REST、Kafka、ORM、saga 和 event sourcing，并按 feature 分别报告 precision/recall。
- **后续工作 2**：把 datastore consistency、unique index、transaction、LWW/CRDT 和 cleanup policy 作为显式配置输入，测每类信息对 FP/FN 的变化。
- **后续工作 3**：结合 bounded path feasibility 或轻量 runtime trace，比较 warning reduction、漏报变化、analysis time 和 peak memory，而不是只追求更少告警。
- **后续工作 4**：实现 incremental CI、owner routing 与 suppression 生命周期，用开发者确认时间、每千行 warning 数和修复后 regression recall 评估可用性。

## 相关

- **相关概念**：[[Microservices]]、[[Data-Integrity]]、[[Static-Analysis]]、[[Eventual-Consistency]]、[[Static-Single-Assignment]]
- **同类系统**：[[Blueprint]]、[[DeathStarBench]]、[[TrainTicket]]、[[MAD]]
- **同会议**：[[OSDI-2026]]
