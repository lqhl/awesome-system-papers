---
type: paper
name: LLMQueryReordering
full_title: "Optimizing LLM Queries in Relational Data Analytics Workloads"
authors: [Shu Liu, Asim Biswal, Amog Kamsetty, Audrey Cheng, Luis Gaspar Schroeder, et al.]
venue: MLSys
year: 2025
tags: [llm-inference, data-analytics, prefix-caching, query-optimization, relational-data, area/ai-infra]
source_pdf: "[[b5dc49f44db2fadc5c4d717c57f4a424.pdf]]"
source_md: "[[b5dc49f44db2fadc5c4d717c57f4a424]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# 通过查询重排优化关系数据上的 [[LLM|LLM]] 分析（MLSys 2025）

> **原题**：Optimizing LLM Queries in Relational Data Analytics Workloads

> **一句话总结**：论文观察到批量关系分析的全部 LLM 请求在执行前已知，因而可同时重排行与行内字段来最大化 [[Prefix-Caching|prefix cache]] 复用；最优 OPHR 与统计驱动的 GGR 在 16 类查询、7 个数据集上将 job completion time 最多缩短 3.4×，并按商用 API 价格最多节省 32%（§6，图 8–11）。

## 问题与动机

LLM 被用于表格分类、抽取、翻译和 RAG，但逐行调用成本很高。论文给出的量级是 L4 上 Llama-3-8B 约每秒处理 6 KB 文本，15 GB 数据约需一个月；GPT-4o 处理同量数据约 18,000 美元。

传统数据库优化器主要重排行算子，不改变一个 prompt 内字段顺序；LLM serving 的 prefix cache 又通常按到达顺序被动复用。离线批处理拥有全局请求集合，因此可以主动排列 prompt，让相同字段值或 join-derived context 连续出现。

## 关键观察 / 隐含假设

- **观察 1**：关系表中的重复值、functional dependency、popular item 与共享 RAG context 形成大量非相邻公共前缀（§3.1）。
- **观察 2**：固定一种字段顺序可能比逐行自适应顺序少至多 m 倍 cache hit，行与字段必须联合优化（§3.2）。
- **假设 1**：查询是离线 batch，重排不改变语义，也没有 per-row deadline 或输出顺序副作用。
  - **证据强度**：强；适合 analytics，但不适合在线 arrival-order-sensitive workload。

## 核心方法

作者把每行 prompt 表示为字段 token 序列，目标是选择行顺序和每行字段排列，使相邻请求的最长公共前缀总量最大。OPHR 穷举字段/行组合得到最优解，但复杂度随行数和字段数指数增长。

GGR 使用 functional dependency 与 table statistics 近似搜索：先寻找高复用字段组合，再贪心连接最相似的请求。它只改变序列化和发送顺序，可叠加在现有数据库、API 与 [[vLLM]]/[[SGLang]] serving 之上，不要求改模型。

## 设计取舍

- **纯重排换部署简单**：无需模型训练和 runtime 改造，但依赖 prompt 字段可交换、batch 全部预知。
- **GGR 换可扩展性**：牺牲 OPHR 最优保证以处理现实数据规模。
- **边界条件**：字段顺序影响模型答案、请求有副作用或存在严格 deadline 时，重排可能不可用。

## 实验与结果

- 16 类 LLM query、7 个真实数据集，Llama-3-8B/70B 上相对 naive ordering 的端到端 job completion time 最高改善 3.4×（§6，图 8–10）。
- 按 OpenAI/Anthropic prefix-cache pricing model，成本最高降低 32%（§6.4，图 11）。
- 固定 field order 在构造与真实 workload 中显著落后逐行联合重排，支持“只重排行不够”的核心观察（§3.2、§6.3）。
- 论文报告输出语义保持，但其成立依赖模板声明字段可交换；未覆盖 agent/tool call 的状态副作用。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 行与字段联合重排能提高 prefix reuse | 最高 3.4× JCT 改善（§6，图 8–10） | 16 query、7 dataset、Llama 3 | 强 |
| 成本收益可映射到托管 API | 最高 32% pricing savings（§6.4，图 11） | 指定厂商 2025 cache pricing | 中 |
| 方法不需改 serving engine | 仅改变请求表示与顺序（§4–5） | 仅限 batch、无顺序副作用查询 | 强 |

## 批判性分析

### 论证链条

“离线全局可见”直接导出重排自由度，算法和端到端结果闭合。最大的外推风险是把关系字段视为可交换 token block：模型对 recency、position 和模板语法可能敏感，语义等价需由应用声明或验证。

### 假设压力测试

低重复度表、字段值随机、cache 容量过小或 serving 被其他租户扰动时，共享前缀可能在使用前被驱逐。在线增量到达、deadline 和事务副作用会破坏离线重排条件。

### 实验可信度

query/data 覆盖比单一 benchmark 强，并报告 latency 与货币成本。价格结论随 API 计费变化；缺少准确率差异的细粒度统计以及与数据库 optimizer 联合优化的复杂 workload。

### 系统性缺陷

优化器需要理解 prompt schema、functional dependency 和字段可交换性；错误声明可能造成静默语义变化，而不仅是性能回退。多租户 cache 污染和服务端 cache policy 对收益的影响未系统测量。

## 局限与后续工作

- 用模型输出一致性 checker 验证字段交换，并在不可交换字段上 fail closed。
- 联合考虑 deadline、cache capacity、tenant interference 与数据库 operator ordering。

## 相关

- **相关概念**：[[Prefix-Caching]]、[[KV-Cache]]、[[LLM-Inference]]、[[RAG]]
- **同类系统**：[[SGLang]]、[[vLLM]]
- **同会议**：MLSys 2025
