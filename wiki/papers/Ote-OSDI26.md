---
type: paper
name: Ote
full_title: "Extracting Database Access-Control Policies From Web Applications"
authors: [Wen Zhang, Dev Bali, Jamison Kerney, Aurojit Panda, Scott Shenker]
venue: OSDI
year: 2026
tags: [access-control, web-application, database, concolic-execution, policy-extraction]
source_pdf: "[[osdi26-zhang-wen.pdf]]"
source_md: "[[osdi26-zhang-wen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 从 Web 应用中抽取数据库访问控制策略（OSDI 2026）

> **原题**：Extracting Database Access-Control Policies From Web Applications

> **一句话总结**：Ote 假设真正决定 SQL 是否发出的代码核心只包含少量简单操作，于是用有界的 [[Concolic-Execution]] 记录“路径条件—SQL”关系、用可人工复核的 LLM judge 跳过无关分支，再把 trace 化简成 SQL view；它在三款真实 Rails 应用上于 59 分钟至 4.7 小时内生成 24–144 个 view，并由此发现手写策略过宽、过窄以及一个被外部 library 静默关闭的 access check，但不保证策略完整或最紧。

## 问题与动机

传统 Web 应用很少先写一份独立的 [[Access-Control]] 策略。权限逻辑通常散在 controller、ORM scope、模板 helper 和 SQL filter 中：某个条件决定是否继续，前一条查询结果又成为后一条查询参数。漏掉或写错一个 check 就可能泄露数据；更根本的问题是，开发者离开或代码演化后，没有人能准确说出“应用实际上允许用户读哪些数据”。

论文把任务定义为**策略抽取（policy extraction）**：总结应用在什么条件下可能发出哪些数据库读查询。输出不是对开发者意图的猜测，而是参数化 SQL view 的集合；只有能由这些 view 回答的查询才被允许。Session 参数（例如已认证 user ID）可以限定 view，HTTP request 参数不可信，必须从最终策略中消去。人先审查策略是否符合隐私意图，随后可以选择用 [[Blockaid]] 一类外部 enforcer 约束未来版本（§2.2、图 1）。

难点是路径爆炸。Rails 程序整体有大量分支，但绝大多数只控制 HTML、日志或格式化，与数据访问无关。完整符号执行既难覆盖 Ruby 的动态语义，也会浪费在这些分支上。Ote 采用选择性 concolic execution，并让 coding agent 判断一个 branch 是否会影响后续查询；这换来了几小时内完成的可用性，也同时引入了不完备和 LLM 误判风险。

## 关键观察 / 隐含假设

- **观察 1：复杂 Web 应用通常有一个简单的“query-issuing core”。** 三个应用中，决定查询的代码主要是结果是否为空、基本值比较、遍历查询结果且无 loop-carried dependency，以及把前一查询的字段传给后一查询（§4.1）。
  - **依赖假设**：所有影响数据访问的关键操作都被 Ote 的 JRuby instrumentation 覆盖，查询使用参数化 SQL，而不是在 Ruby 中拼字符串。
  - **可能失效场景**：regex、字符串格式化、reflection、native extension 或外部 service 参与控制流时，符号值会被 concretize，Ote 可能漏 query、漏条件，或生成大量带常量的错误条件。
- **观察 2：只要保存“此前查询、分支条件、当前查询”，就能把程序路径转换成关系策略。** Ote 将每次查询与此前 QUERY/BRANCH transcript 组合成 conditioned query，再逐条 conjoin 成 SQL view（算法 1–2）。
  - **依赖假设**：项目—选择—连接（PSJ）查询足以表达目标策略，且 request parameter 能通过与非空数据库列的等式安全消去。
  - **可能失效场景**：否定条件、一般 outer join、复杂 aggregation、ordering 或 bag semantics 超出当前 policy language；近似可能让策略过宽或过紧。
- **观察 3：大量被追踪的分支与查询无关，跳过它们是完成探索的必要条件。** 五个启用 relevance judge 的 handler 在关闭剪枝后运行 10 小时仍未完成，作者估计需要数天；开启后，diaspora 和 Autolab 各自所选 6 个 handler 的顺序总时间为 4.7 与 3.9 小时（表 2、§7.4）。
  - **依赖假设**：coding agent 能读懂 branch、stack trace、Rails/library 行为，人工也会审阅所有 irrelevant verdict。
  - **证据强度**：中。评测中的 635 个 irrelevant verdict 经人工确认无误，但只来自五个 handler，并使用了七条人工 relevance hint。
- **假设 1：小的有界数据库足以暴露真实控制依赖。** 原型为每张表建最多 2 个 symbolic row，并进一步限制每次查询最多返回 1 行（§4.4）。
  - **证据强度**：弱到中。三个案例产生了有用策略，但没有 coverage proof；依赖多行交互、排序或聚合的路径可能在这个边界内消失。

## 核心方法

使用者先指定要分析的 Rails handler、把应用装入 Docker，并提供数据库约束。约束支持两类：列组合唯一，以及一个查询结果包含于另一个查询结果；后者可表达 foreign key。Ote 从 Rails schema、validator、association 和继承结构自动生成大多数约束，用户再补充只存在于业务逻辑或外部环境中的不变量（图 1、§3.1、§6）。

探索阶段由一个 driver 和多个 executor 组成。Driver 用 prefix tree 保存已走路径，依次否定最后一个 path condition，再调用 Z3 生成新输入；executor 在修改后的 JRuby 与 Rails 中运行 handler。数据库、session 参数和 request 参数同时带 concrete 值与 symbolic expression；修改后的数据库层记录每个 `QUERY(sql, params, isEmpty)`，JRuby 的真假判断记录 `BRANCH(condition, outcome)`，并保存 stack trace 供审计（§4.3–4.5）。

Ote 只 instrument String、Fixnum 等 10 个类及等式、null check 等简单操作，其余 Ruby 正常具体执行。SQL 求解模型支持 inner/left join、count/sum 等一部分语义；输入生成还复用 Z3 AST、增量求解并缓存 unsat core。这个“按需付费”的选择性跟踪减少实现量和路径数，但未 instrument 的关键操作不会自动报成 soundness failure（§4.2、§4.4）。

遇到可能相关的 branch 时，Ote 把 branch、stack trace 和“何为无关”的定义发给 Codex coding agent。Agent 可浏览源码并回答 relevant、irrelevant 或 unsure；unsure 和格式错误一律按 relevant 处理。调用是异步的，driver 先继续探索，收到 irrelevant 后再跳过该条件、覆盖已有等价路径。Verdict、解释和来源都留给人审查，用户还可用 `RELEVANCE-HINT` 注释补充 library 语义（§4.6）。

策略生成分三步。第一步把每条 query 连同此前的 QUERY/BRANCH 组成 conditioned query；由于当前策略不能表达否定，前序查询为空的条件会被丢弃。第二步传播等式、删除必然分支和重复查询、合并只差一个 branch outcome 的路径，并移除被更宽条件覆盖的记录。第三步把每条记录转为 relational algebra 后逐次 conjoin，最后消去 request parameter、生成 SQL view；再调用 Blockaid 做信息包含检查，删除可由其他 view 推出的冗余项（§5.1–5.4）。

输出仍需人审阅。过宽的 view 可能暴露应用 bug；过紧或只反映 business logic 的大量 view 可以由人写一个更宽、符合隐私意图的 view，再让 pruning 自动删掉被覆盖项。Ote 为每个 view 保存来源 execution ID，使审阅者能恢复输入并重跑到具体 query（§6、§7.7）。

## 设计取舍

- **以选择性 instrumentation 换可实现性**：只跟踪 query core 让动态 Ruby 可分析，却牺牲了完整性；漏掉控制条件既可能让策略过宽，也可能让策略过紧。
- **以有界 concolic execution 换终止性**：2-row 数据库和单行 query result 控制状态空间，但不能证明覆盖生产数据库中的多行、排序和 aggregation 行为。
- **以 [[LLM|LLM]] 剪枝换运行时间**：五个难 handler 从超过 10 小时降到可完成，代价是安全关键分析中加入非确定 judge 和人工 review。
- **以 SQL view 换精确来源链**：SQL 与现有数据库 enforcement 对接自然，每条 view 可追到 trace；但 PSJ 难表达否定，复杂 view 对非数据库专家不友好。
- **边界条件**：参数化 SQL、简单 query core、Rails/MySQL、只读访问和愿意投入人工审计时最合适；动态 SQL、复杂多行语义、其他语言或要求形式完备性时不适用。

## 实验与结果

- **设置、比较对象与指标**：实验在 Google Compute Engine `c3-standard-176` 实例上运行 48 个 executor，使用 Z3 4.11.2、修改的 JRuby 9.3.13.0、OpenJDK 21 和 MySQL/tmpfs；relevance judge 是 Codex CLI 0.58.0 + gpt-5 medium，最多并行 16 个调用。论文没有可直接比较的同类策略抽取 baseline；可比对象是“不启用 relevance pruning”的 Ote，以及作者此前手写的 diaspora/Autolab 策略。指标包括路径数、conditioned query/view 数、各阶段时间和发现的策略/代码错误（§7.2）。
- **应用规模与策略大小**：diaspora、Autolab、The Odin Project 分别有 50/26/17 张表、387/269/152 列，共分析 18 个明确选定的 handler，而不是覆盖应用的全部 endpoints。最大单 handler 探索 217,543 条路径、把 391,621 个 conditioned query 化简为 1,592 个，再 pruning 到 138 个 view；跨所选 handler 合并后，三个应用最终分别得到 134、144、24 个 view（表 2、表 4）。
- **端到端时间**：三次运行取 exploration time 中位数后，diaspora、Autolab、Odin 的所选 handlers 顺序总时间分别为 4.7 小时、3.9 小时和 59 分钟。五个超过 15 分钟的 handler 使用 relevance pruning；关闭它后，五个都在 10 小时超时，作者据路径增长估计会需要数天（表 2、§7.4）。这是云 VM 上真实执行 Rails/MySQL，不是模拟器，但数据库内容是最多 2 symbolic row 的合成输入，不是生产数据或 production trace。
- **LLM 剪枝审计**：五个 handler 共收到 127 个 relevant、635 个 irrelevant verdict，judge 从未返回 unsure；单次平均耗时 1.0–1.9 分钟。作者逐一人工确认所有 irrelevant verdict，并加入 1 条 diaspora、6 条 Autolab hint；Odin 分支少，没有启用 judge（表 3、§7.1.2、§7.5）。这说明当前案例可审计，不等价于未见应用上的准确率保证。
- **人工设置仍然显著**：约束生成器自动产生 diaspora/Autolab/Odin 的 347/185/116 条约束，但仍需人工写 63/42/9 条业务不变量和 2/4/1 条专为 Ote 缩小范围的约束。应用还需少量参数化 SQL、受支持 query 形式和变量复用修改；复杂 SQL 的 lossy approximation 也要人批准（表 1、§7.1、§7.3）。
- **实际发现**：手写 Autolab 策略错误地允许 course assistant 读取 disabled course 的五类记录；手写 diaspora 策略漏掉 remote person 的 pod 和两类 notification，Autolab 策略漏掉 instructor 读取课程全部 attachment。审查抽取策略还发现早年改造 Autolab 时把 `exam` 写成 `exam?`，使 `lazy_column` 将 access check 静默变成永远 falsy（§7.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Ote 能把真实 Rails handler 的大量路径压缩成人可审阅的策略 | 表 2、表 4 | 3 个开源应用、18 个 handler；最终 24–144 个 PSJ view | 强 |
| relevance judge 是难 handler 在数小时内完成的关键 | 表 2–3、§7.4–7.5 | 5 个 handler；无剪枝均在 10 小时超时；使用 7 条人工 hint | 强 |
| 抽取策略比已有手写策略更能暴露实际数据访问 | §7.6 | 只对 diaspora、Autolab 有手写对照，且原手写者也是本文作者 | 中 |
| Ote 能帮助发现真实 access-control bug | §7.6 | 发现 1 个 `lazy_column` 配置 bug；是深度案例证据，不是 bug recall 测试 | 中 |
| Ote 不能保证输出策略完整或最紧 | §3.2、§4.7、§7.3 | 有界路径、未 instrument 操作、LLM 与 SQL approximation 都可使策略过宽或过紧 | 强（作者明确） |

## 批判性分析

### 论证链条

论文没有把“抽取策略”偷换成“恢复开发者意图”：它明确只总结在有界探索中观察到的代码行为，再由人决定哪些条件属于隐私边界。简单 query core 支撑选择性 concolic execution，irrelevant branch 数量支撑 LLM 剪枝，最终发现手写策略和代码错误则证明输出有实际审计价值。没有闭合的部分是 completeness：三个成功案例不能证明未探索路径没有新 query，也不能证明生成 view 最紧；作者在 §3.2 主动承认这一点。

### 假设压力测试

若 query 是否发出取决于 regex、字符串拼接、外部 API、循环中多行关系或排序，instrumentation 可能漏掉 symbolic dependency。数据库最多 2 行、query 最多返回 1 行，也会隐藏“只有第三行出现才走此分支”或跨行 aggregation。LLM judge 若把相关 branch 判成 irrelevant，会静默删除条件或路径；当前防线主要是人工逐条 review，而不是 sound conservative analysis。上述都是设计允许的失败模式，部署前必须把“未覆盖”当成显式风险，而不是把输出视为证明。

### 实验可信度

三个应用都是真实、非玩具 Rails 项目，schema 和路径规模足够大；Odin 是作者此前未接触的新案例，减轻了完全依赖既有知识的问题。可是 diaspora 和 Autolab 早已为 Blockaid 修改，作者也写过其手工策略，样本只有三款 Rails/MySQL 应用。论文没有同类 extractor baseline、独立安全专家的 blind review、已知 ground-truth policy 或系统性的 precision/recall；“找到错误”证明 usefulness，却不能量化遗漏率。运行还依赖 176-vCPU 级云实例、48 executor 和外部模型调用，金钱成本没有报告。

### 系统性缺陷

Ote 需要修改 JRuby/Rails、准备 Docker、补数据库约束、审查 LLM verdict、判断 SQL approximation，再审阅与 broaden 最终策略；这不是一键工具。当前只支持 SELECT 和 PSJ view，不表达否定，也不评测最终 enforcer 的运行时开销。把私有应用代码交给外部 coding agent 还可能带来代码保密和合规问题，论文未讨论本地模型、脱敏或 prompt/模型版本漂移。最后，策略审阅仍直接面对最长 144 个 SQL view，作者自己也承认需要更易读的 DSL 和更好的 UI。

## 局限与后续工作

- **局限 1：没有 coverage 保证。** 应输出按 handler、query site 和未 instrument operation 分类的 coverage/uncertainty，并用已知隐藏路径的测试集测漏报率。
- **局限 2：语言和 SQL 范围窄。** 在另一种 Web framework 上实现同一 trace IR，并加入 multi-row、negation、aggregation 与 outer join，比较策略宽松度变化。
- **局限 3：人工成本未量化为人时。** 对未参与开发的安全工程师做 blind study，记录配置、verdict review、policy review 和 broadening 的实际时间与错误率。
- **后续工作 1：让 LLM 只做可验证子任务。** 对 irrelevant verdict 生成静态/动态证据或反例测试；无法验证时保持 relevant，以减少 silent omission。
- **后续工作 2：验证持续 enforcement。** 将审过的策略接入 Blockaid，跨多个应用版本回放真实请求，测合法请求误拒、越权 query 阻断率和 P99 数据库延迟。

## 相关

- **相关概念**：[[Access-Control]]、[[Concolic-Execution]]、[[Policy-Mining]]、[[Database-Security]]
- **相关系统**：[[Blockaid]]
- **同会议**：[[OSDI-2026]]
