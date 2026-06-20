---
type: concept
aliases: [RAG, Retrieval-Augmented Generation, retrieval augmented generation, retrieval-augmented generation, 检索增强生成]
last_updated: 2026-06-20
tags: [llm-inference, retrieval, serving, agent]
---

# RAG

> Retrieval-Augmented Generation，把外部检索结果作为 LLM 上下文输入，以降低幻觉、注入新知识或让模型访问私有语料。系统层面看，RAG 不只是应用模式，而是把 retrieval latency、context assembly、prefill、[[KV-Cache]] 复用和 answer generation 串成一条端到端 serving pipeline。

## 核心思想

RAG 把单次 LLM 调用拆成多阶段流水线：查询改写 / embedding → 向量或混合检索 → rerank / filtering → context packing → LLM prefill + decode。每一阶段都引入独立瓶颈，且阶段间往往是**串行**的——[[TeleRAG-MLSys26|TeleRAG]] 测得 IVF 检索可占 E2E **41–60%**；[[LEANN-MLSys26|LEANN]] 则指出在端侧场景 generation 常占 **>20s** 而检索仅 ms–百 ms 级，使「用检索延迟换存储」成为合理 trade-off。

系统优化的核心矛盾是：**检索结果在跨请求间高度重叠，但顺序与组装方式不稳定，破坏 [[Prefix-Caching]] 的精确匹配**。[[ContextPilot-MLSys26|ContextPilot]] 在 MultihopRAG 上测得 exact prefix hit 仅 **4.6%**；[[SpanQueries-MLSys26|SpanQueries]] 把失败根因归结为 fragment 顺序可交换性未被 engine 感知。因此 RAG serving 的演进方向包括：检索-生成重叠（[[TeleRAG-MLSys26|TeleRAG]] lookahead prefetch、[[Stream2LLM-MLSys26|Stream2LLM]] streaming prefill）、context 层 reuse（[[ContextPilot-MLSys26|ContextPilot]] alignment/dedup）、声明式 locality（[[SpanQueries-MLSys26|SpanQueries]] span query IR）、rank-aware 早停（[[Terminus-MLSys26|Terminus]]）和端侧索引压缩（[[LEANN-MLSys26|LEANN]] 50× 存储压缩）。

RAG 也在向 **agent memory** 与 **结构化检索** 扩展。[[Tag2Graph-MLSys26|Tag2Graph]] 针对长期对话 agent 的 implicit preference recall，用 ontology-guided 图检索补 dense retrieval 的 temporal gap；[[MSA-arXiv26|MSA]] 则用可微 document routing 把 retrieve-then-read 压进单一 attention，挑战传统两阶段 RAG 架构。

## 为什么重要

RAG 是长上下文 serving 最具代表性的 workload 之一：context 长 → prefill 贵 → [[KV-Cache]] 大 → 与 [[Continuous-Batching]]、GPU 内存争用。[[Quake-OSDI25|Quake]] 揭示向量检索负载本身动态倾斜（热门实体集中、embedding 版本滚动），固定 nprobe 在结构变化后 recall 崩塌；[[Terminus-MLSys26|Terminus]] 进一步说明磁盘 graph ANN 受 IOPS 限制，而 RAG 准确率主要由 top-ranked 文档主导，检索与下游效用严重错位。

这些论文共同假设：**RAG 的系统瓶颈已从「模型能不能答」转向「pipeline 各段能否协同」**——检索延迟、索引 footprint、context 组装、prefix hit ratio、TTFT/TPOT SLO 必须联合优化。忽视任一环节，端到端体验都会卡在 retrieval gap 或重复 prefill 上。

## 关键观察 / 隐含假设

- **观察 1：RAG 的 TTFT = retrieval + prefill，且二者常可重叠。** [[TeleRAG-MLSys26|TeleRAG]] 发现 pre-retrieval 改写前后 IVF cluster 重叠率常 **>61%**，可在 LLM 生成时异步 prefetch；[[Stream2LLM-MLSys26|Stream2LLM]] 把 TTFT 从 \(T_{retrieve}+T_{prefill}\) 压到近似 \(\max\) 量级，但多租户 memory pressure 下 naive streaming P99 可恶化 **10×**。
- **观察 2：检索结果重叠高，但顺序变化使 prefix cache 失效。** [[ContextPilot-MLSys26|ContextPilot]] 报告 top 20% 文档贡献大部分 query，alignment 后 hit 可达 **38–60%**；[[SpanQueries-MLSys26|SpanQueries]] 用 commute 声明使 RAG TTFT 降 **10–20×**。
- **观察 3：下游效用集中在高 rank 文档，检索可早停。** [[Terminus-MLSys26|Terminus]] 在 Natural Questions 上 k≥20 后 EM 饱和，rank-aware utility 早停相对无早停 Starling 吞吐 **3.2×** 且 EM 影响极小。
- **观察 4：端侧 RAG 的瓶颈常是索引体积而非检索毫秒数。** [[LEANN-MLSys26|LEANN]] 在 76 GB 语料上把索引从 **188 GB** 压到 **4 GB**，端到端延迟仅多 **<20%**；假设 generation 主导 latency budget。
- **观察 5：对话 RAG 需要跨 session 结构，不仅是单次 top-k。** [[Tag2Graph-MLSys26|Tag2Graph]] 指出 vanilla dense retrieval 难处理 implicit preference recall；图×向量 fusion 在 P95≈**185–190 ms** CPU-only guard 下服务。
- **观察 6：parametric memory 与 RAG 形成替代谱系。** [[Cartridges-ICLR26|Cartridges]] 用可训练 KV prefix 压缩语料，serving 侧无需动态换权重，但牺牲 citation/provenance，窄域 extractive 任务可能仍不如 [[RAG]] 便宜。

## 设计空间与取舍

- **两阶段 retrieve-then-read vs 单阶段 attention routing**：传统 RAG 模块清晰、可解释；[[MSA-arXiv26|MSA]] 类方法减少 pipeline 段数但改变训练与评测边界。取舍在可解释性、延迟与架构迁移成本。
- **全量 embedding 索引 vs 重算/压缩索引**：[[LEANN-MLSys26|LEANN]]、[[TeleRAG-MLSys26|TeleRAG]] 用 partial GPU residency + 查询时重算/prefetch 省显存给 LLM/KV；代价是检索算力、encoder 吞吐与 tail latency。
- **精确 prefix vs context 变换**：[[ContextPilot-MLSys26|ContextPilot]] 不改权重，靠 alignment/annotation；[[CacheBlend-EuroSys25|CacheBlend]] 用近似 KV 匹配，准确率可降 **9–11%**。收益是 hit ratio，代价是质量边界与运维复杂度。
- **rank-aware 早停 vs 完整遍历**：[[Terminus-MLSys26|Terminus]] 在中等 recall 区间收益最大；极高 recall 或 rerank-heavy pipeline 需保守阈值。
- **dense vs 结构化/图检索**：[[Tag2Graph-MLSys26|Tag2Graph]] 用 ontology 补 temporal/causal gap，但运维复杂度高于纯 dense [[RAG]]。
- **与推理栈协同**：[[Prefix-Caching]]、[[PagedAttention]]、[[Chunked-Prefill]]、[[Disaggregation]] 决定 RAG context 进入 engine 后的 prefill 成本与 KV 生命周期。

## 引用本概念的论文

- [[TeleRAG-MLSys26|TeleRAG]] — lookahead IVF prefetch，使大索引 + 8B 模型在 24GB GPU 可运行，E2E **1.53×**、batch 吞吐 **1.98×**。
- [[ContextPilot-MLSys26|ContextPilot]] — 长上下文 RAG/agent 的 context reuse，prefill 吞吐 **1.5–3×**，hit 从约 **5%** 到 **38–60%**。
- [[SpanQueries-MLSys26|SpanQueries]] — span query IR 统一 chat、RAG、agent 的 locality 表达，非 chat TTFT **10–20×**。
- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming RAG 检索与 prefill 重叠，crawler/ANNS trace 上 TTFT **3.9–11×**。
- [[Terminus-MLSys26|Terminus]] — rank-aware 向量搜索早停，RAG EM 几乎无损下吞吐 **3.2×**。
- [[LEANN-MLSys26|LEANN]] — 端侧 RAG 索引不存 embedding、查询重算，存储 **50×** 压缩。
- [[Tag2Graph-MLSys26|Tag2Graph]] — ontology-guided 对话 RAG 记忆，解决 implicit preference recall。
- [[Quake-OSDI25|Quake]] — 动态倾斜向量检索负载下的自适应 nprobe，服务 [[RAG]]/语义搜索场景。
- [[MSA-arXiv26|MSA]] — 可微 document-wise sparse routing，挑战传统 retrieve-then-read 两阶段架构。
- [[Cartridges-ICLR26|Cartridges]] — KV-prefix 参数化语料，与 [[RAG]] 在 serving 成本与可解释性上形成对照。
- [[CacheBlend-EuroSys25|CacheBlend]] — 多 chunk KV 复用加速 RAG prefill，揭示近似匹配的质量代价。
- [[HedraRAG-SOSP25|HedraRAG]]、[[METIS-SOSP25|METIS]] — 异构检索与 RAG pipeline 系统优化（见各 paper 页）。

## 已知局限 / 开放问题

- top-k recall 与下游答案质量之间没有稳定一一对应；[[Terminus-MLSys26|Terminus]] 指出 embedding 噪声使早停参数需 per-task 重标定。
- 多跳/agent RAG 对 tail 文档更敏感，rank-aware 早停与短 context reuse 假设可能失效。
- 跨 session context reuse 的隐私、隔离与 cache poisoning 语义未定义（[[ContextPilot-MLSys26|ContextPilot]]、[[LMCache-arXiv25|LMCache]]）。
- Cartridge 类 parametric memory 与 [[RAG]] 混合时，faithfulness、citation 与增量更新成本仍开放（[[Cartridges-ICLR26|Cartridges]]）。
- RAG pipeline 与 [[Disaggregation]]、speculative decoding、多租户 fair scheduling 的端到端 SLO 联合评测缺失。