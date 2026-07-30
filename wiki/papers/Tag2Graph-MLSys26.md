---
type: paper
name: Tag2Graph
full_title: "Ontology-Guided Long-Term Agent Memory for Conversational RAG"
authors: [Shuang Cao, Rui Li]
venue: MLSys
year: 2026
tags: [rag, agent-memory, conversational-ai, retrieval, personalization, knowledge-graph]
source_pdf: "[[70efdf2ec9b086079795c442636b55fb.pdf]]"
source_md: "[[70efdf2ec9b086079795c442636b55fb]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Tag2Graph：用于会话 RAG 的本体引导长期智能体记忆（MLSys 2026）

> **原题**：Ontology-Guided Long-Term Agent Memory for Conversational RAG

> **一句话总结**：长期多 session 对话里，隐式偏好 query（如「周末看什么？」）与早期偏好陈述词面不重叠，dense-only Recall@10 在 60+ turn 后跌至 0.28；Tag2Graph 用在线学习的用户偏好本体（User→PREFERS_GENRE→Romance）、仅在已验证引用上的 graph×dense 分布对齐、以及 budget-aware router，在 matched P95≈185 ms 下把 Recall@10 从 0.58 提到 0.70、成本约为 long-context 的 18%。

## 问题与动机

[[RAG]] 在单轮 QA 上成熟，但部署到**长期、多 session 对话 agent** 时，用户常隐式引用数周前的偏好（「周末看什么？」其实依赖 session 1 里「我爱 Titanic」），当前 query 与历史事实缺乏 lexical overlap。vanilla dense retrieval 与 long-context prompting 都依赖词面或全文注意力，在 LoCoMo 等 benchmark 上对 temporal/causal reasoning 仍明显落后人类（Maharana et al., 2024）。

作者把这类失败归纳为 **implicit preference recall**：不是语义无关，而是标准 encoder 难以跨越时间 gap 建立概念关联。现有路线分三类——容量型 memory（LongMem、MemGPT）、对话感知 [[RAG]]（DH-RAG）、结构增强检索（HippoRAG、MemoRAG）——但三者均未同时解决「学什么进 graph」「graph 与 dense 何时信谁」「在 latency/cost guard 下选哪条检索路径」。

本文提出 dialogue-aware RAG 系统，核心组件 **Tag2Graph-Learner** 负责把 utterance 提升为可遍历的 typed relations，再配合 **Graph×Dense Consistency** 与 **Learnable Router**，目标是在**不付 long-context 成本**的前提下恢复隐式偏好。

## 关键观察 / 隐含假设

- **观察 1：隐式 recall 随对话长度恶化，且 dense-only 掉得最陡**
  - 内部 Implicit Preference Recall benchmark（500 对话、均 73 turns）显示，dense-only Recall@10 从 turns 1–20 的 0.61 跌到 turns 60+ 的 0.28；graph-only 因 schema 覆盖不足 plateau。
  - **依赖假设**：用户偏好可通过有限 relation 类型（LIKES、PREFERS_GENRE、SIMILAR_TO 等）抽象，且 promotion 门控能压住噪声。
  - **可能失效场景**：高度语境化、反讽或快速漂移的偏好；多租户下 ontology 膨胀超出 guardrail。

- **观察 2：graph 与 dense top-10 在个性化 query 上平均只重叠 3.2 条**
  - 两模态提供互补能力（graph 擅 alias/多跳，dense 擅 broad semantic match），但独立打分再加权无法消解「同一 evidence 排第 2 vs 第 47」的分歧。
  - **依赖假设**：只需在**历史上被验证为有用**的 citation 子集上对齐分布，即可稳定 ranking，而不必全候选对齐。
  - **可能失效场景**：verified-citation 覆盖低（cold-start 仅 25% 时 gains 更小）；新 domain 无足够 engagement 信号训练 consistency regularizer。

- **观察 3：long-context 在 matched budget 下 recall 增益极小但成本极高**
  - 同 guard 下 long-context Recall@10 0.601 vs dense-only 0.580，P95 310 ms；summary-memory 0.622 仍丢 graph 里的 personalization 结构。
  - **依赖假设**：per-query 在 graph-first / dense-first 间动态切换，比固定策略或全历史扫描更接近 Pareto frontier。
  - **可能失效场景**：factoid 为主、几乎无隐式引用的 workload——router 价值下降；counterfactual replay 日志与线上分布漂移。

- **假设 1：BERT-base BIO tagger + 小 MLP 门控 + 离线 LLM validator 足以在 serving hot path 外维持高 precision 三元组**
  - **证据强度**：中——ablation 显示去掉 Tag2Graph promotion 掉 8.5pt Recall@10，但未与更强 OpenIE/专用 NER 基线对比提取质量。

- **假设 2：P95≈185–190 ms、CPU-only serving 的 guard 能代表 production conversational [[RAG]] SLO**
  - **证据强度**：中——multi-shard 32 并发 P95 仍 <200 ms，但实验 batch=1、concurrency=1 测主表；真实 burst 与跨 region 延迟未覆盖。

## 核心方法

三阶段 pipeline：**ingest → query/retrieve → feedback**。

**Phase 1 — 并行写入三 store**：graph store 维护 User-centric typed edges（timestamp、learnable weight）；vector store 存 utterance embedding + metadata；profile cache 记近期检索统计。例：「I loved Titanic」→ `User→LIKES→Titanic` 与 `User→PREFERS_GENRE→Romance`（经 `Titanic→HAS_GENRE→Romance` 提升）。

**Tag2Graph-Learner**（回应 M1）：
1. **Evidence extraction**：BERT-base BIO tagger 过生成 `{head, relation, tail, time}` → 2 层 MLP（256 hidden）门控；仅离线 constrained LLM 校验 canonical relation。低置信 triple 只进 FAISS，不改 graph hot path。
2. **Relation lifting**：重复共现、跨 context 一致、与现有 ontology 兼容的 assertion 由浅层 scorer 晋升为 typed edge；alias 合并保守，矛盾/隐私/配额超限则拒绝 promotion。
3. **Feedback maintenance**：`used-and-correct` 与 `missed-but-needed` 两通道异步 micro-batch 更新 edge weight；重学习不阻塞请求路径。

**Graph×Dense Consistency**（回应 M2）：统一打分 \(s = w_g s_g + w_d s_d + w_p s_p\)（默认 0.55/0.35/0.10），\(s_p\) 来自 per-user profile cache。训练时仅在 verified-useful evidence 上对 graph/dense 分布做双向 KL 正则；serving 时若两视图分歧大或分数平坦，在 latency guard 内允许**一次** capped expansion（多一跳或再多一次 dense probe），否则回退较安全视图。

**Learnable Router**（回应 M3）：2 层 MLP（128 hidden）读 alias risk、距上次相关 mention 时间、query 是否触及 promoted concepts、profile 摘要、近期策略成功率；离线用 time-split logs + counterfactual replay 学 utility（personalization vs cost/latency），在线蒸馏为微秒级 graph-first vs dense-first 决策。graph-first 先短 metapath 再 dense re-rank；dense-first 相反。

实现栈：DGL user-sharded graph、FAISS flat-IP（BGE-large-en-v1.5）、离线 PyTorch 训练后仅部署 distilled MLP；评测 CPU-only，2× Xeon Gold 6248R，P95 guard ≈185 ms。

## 设计取舍

- **保守 ontology promotion vs recall**：高 τ 门控抑制 graph 噪声，但 cold-start verified coverage 低时 consistency 收益受限；论文用 guardrail（矛盾检测、租户配额）换可控增长。
- **窄对齐 vs 全候选对齐**：只在 cited evidence 上 KL 对齐，算力可控且降 47% 跨模态分歧，但依赖 engagement/verification 信号——无反馈时退化为固定权重线性组合。
- **双 store 冗余**：同一 utterance 同时进 graph 与 vector，storage 近线性增长（8× history 时 graph 2.5→18.1 MB/user，FAISS 12→93.1 MB/user），换 keyword-free 遍历与 semantic fallback。
- **离线 LLM validator**：hot path 快，但 12.4% 新 triple 触发 validator、write-path 均 27 ms/turn；relation inventory 演化仍依赖离线 canonicalization。
- **边界条件**：alias-heavy、长 temporal gap、ellipsis 子集增益最大（Recall@10 0.48–0.52→0.64–0.67）；显式 factoid 上系统仍优于 dense-only（0.738 explicit slice）但 router 更常 dense-first。

## 实验与结果

- **内部 implicit slice**（MovieRec / FoodPref / ProductivityAssist，matched budget）：Recall@10 **0.706** / nDCG@10 **0.514** vs dense-only **0.580** / **0.410**；faithfulness **0.93** vs **0.86**；P95 **190 ms** vs **185 ms**；normalized cost **1.31×** dense-only。
- **强基线**：Dense+CE-rerank **0.647**/**0.468**；HippoRAG **0.671**/**0.491**（P95 193 ms，cost 1.68×）；MemoRAG **0.643**/**0.467**（P95 201 ms）；long-context **0.601** Recall@10 但 P95 **310 ms**，成本约 **5.6×** dense-only（本文 **0.18×** long-context，约 **81%** 节省）。
- **LoCoMo implicit slice**（1,847 queries）：**0.576**/**0.451** vs HippoRAG **0.531**/**0.412**、MemoRAG **0.504**/**0.387**；全 7,182 queries Recall@10 **0.693**，无 explicit 退化（Table 19）。
- **消融**（同 guard）：无 Tag2Graph promotion → **0.621**/**0.448**；无 consistency → **0.662**/**0.479**；静态 router → **0.674**/**0.493**。
- **Scaling**：history 1×→8×（87→696 turns）Recall@10 仅 **−5.4%**（0.706→0.668），P95 仍 <190 ms；cold-start（≤10 turns）仍 **0.613** vs dense **0.557**，成熟 profile（>50 turns）**0.718** vs **0.591**。
- **Human eval**（N=240，3 raters）：overall **4.14±0.11** vs HippoRAG **3.89**、dense-only **3.49**（1–5 Likert）；Fleiss' κ=0.71。

## 批判性分析

### 论证链条

observation（隐式 query 词面断裂 + 双模态分歧 + long-context 性价比差）→ 三组件分别针对 extract/lift、narrow alignment、adaptive routing → 主表与 ablation 在数值上闭合：promotion、consistency、router 各贡献约 8.5pt、4.4pt、3.2pt Recall@10。链条在**隐式偏好 slice** 上较强；对「ontology 是否比固定 schema + PPR 更优」的论证主要靠 vs HippoRAG/MemoRAG 与去掉 Tag2Graph 的 ablation，而非独立测量 graph 拓扑质量或 relation 精度。

### 假设压力测试

- **偏好可类型化**：娱乐/食物/生产力三域有效，但 Health & Lifestyle 边际最小（仍 +0.042 vs HippoRAG），可能因 factual query 多、graph 边价值低。
- **Verification 信号可得**：8 个月 12.4K 用户部署靠 periodic retrain（11 次/8 月）维持 Recall@10，说明 drift 存在；新租户或无 engagement 产品可能长期停留在 cold-start 区间（error-route 14.2%）。
- **CPU P95 guard**：multi-shard 子线性吞吐，但未报告 GPU co-located embedding refresh 或跨模态 index 一致性故障行为。
- **LLM validator 成本**：离线校验换 hot path 稳定，但 relation inventory 演化、多语言 alias 的维护成本论文仅定性描述。

### 实验可信度

- **Benchmark**：内部 500 对话 + LoCoMo 外部验证，implicit slice 定义清晰（无 entity/keyword overlap + recommendation/preference/follow-up），时间切分防泄漏合理。
- **Baselines**：覆盖 dense、long-context、summary、CE-rerank、query-rewrite、HippoRAG、MemoRAG，共享 top-64 / top-10 re-rank 与 P95 guard，公平性较好。
- **Metric**：Recall@10、nDCG@10、faithfulness、normalized cost、P95 齐全；主 claim 是 retrieval 质量 + cost，端到端 answer 质量主要靠 human eval 240 样本，规模中等。
- **Ablation**：三组件独立移除，τ/λ 敏感性显示宽 plateau（τ∈[0.60,0.80]），不过拟合阈值风险低。

### 系统性缺陷

- **图维护与回滚**：promotion 带 provenance，但大规模错误 lifting 的在线 undo 路径论文未详述。
- **多用户/隐私**：guardrail 提到 privacy-sensitive promotion 拒绝，却无正式 privacy audit 或跨用户 leakage 实验。
- **尾延迟与故障**：11% query 触发 one-shot backoff；P99、validator 失败、FAISS/graph 分片不一致时行为论文未讨论。
- **可观测性**：Prometheus 监控 Recall、cost、consistency gap、validator rate 有描述，但与 OpenTelemetry 级 tracing 的集成未展开。
- **与 [[KV-Cache]] / 生成侧协同**：工作集中在 retriever；generator 如何利用 graph path explanation 或校准 citation 未被当作一等公民。

## 局限与后续工作

- **局限 1**：依赖用户 engagement 作 supervision（点击/采纳推荐），无反馈时 consistency 与 router 退化；Table 12 显示 verified coverage 25%→100% 单调提升 recall。
- **局限 2**：ontology 学习管线仍含 LLM validator 与离线训练周期，运维复杂度高于纯 dense [[RAG]]；relation 类型虽 data-driven，但 inventory 仍半固定。
- **局限 3**：评测以英文对话为主，多语言 alias 仅原则性处理；MinerU 转写后部分公式（Eq. 1–13）在 markdown 中为空，精确损失函数需回 PDF。
- **Future work 1**：在**无 engagement 冷启动**下测量 promotion/router 下限，并对比固定 schema graph（如仅 OpenIE）需要多少 labeled data 才能追平 Tag2Graph。
- **Future work 2**：端到端联合优化 retriever graph 与 generator faithfulness（而非仅 retrieval metric），在更长 horizon（>8× history）上测 narrative consistency。
- **Future work 3**：production trace 上验证 CPU P95 guard 在混合 factoid+implicit workload、跨 shard 热点用户时的 tail latency 与 retrain 触发频率。

## 相关

- **相关概念**：[[RAG]]、[[KV-Cache]]、agent memory、personalization、knowledge graph retrieval
- **同类系统**：HippoRAG、MemoRAG、DH-RAG、LongMem、MemGPT（文中 baseline；wiki 待建）
- **同会议**：[[MLSys-2026]]
- **对比**：结构增强对话 [[RAG]] vs 纯 dense / long-context serving 成本；graph×vector fusion vs 单模态 Personalized PageRank
