---
type: concept
aliases: [RAG, Retrieval-Augmented Generation, retrieval augmented generation, retrieval-augmented generation, 检索增强生成]
last_updated: 2026-06-18
tags: [llm-inference, retrieval, serving, agent]
---

# RAG

> Retrieval-Augmented Generation，把外部检索结果作为 LLM 上下文输入，以降低幻觉、注入新知识或让模型访问私有语料。系统层面看，RAG 不只是应用模式，而是把 retrieval latency、context assembly、prefill、[[KV-Cache]] 复用和 answer generation 串成一条端到端 serving pipeline。

## 系统问题

RAG 把单次 LLM 调用拆成多个阶段：

1. 查询改写 / embedding
2. 向量或混合检索
3. rerank / filtering
4. context packing
5. LLM prefill + decode

这些阶段引入新的瓶颈：

- retrieval 与 generation 串行导致 TTFT 增大
- 检索结果长度和顺序不稳定，破坏 [[Prefix-Caching]]
- 多轮 RAG 中 context 大量重复，却常被重新 prefill
- 向量索引、embedding、KV cache 争用 GPU/CPU/内存资源
- top-k recall 与下游答案质量之间没有稳定的一一对应关系

## 系统优化方向

- **检索-生成重叠**：提前预取候选文档或边检索边 prefill。
- **context reuse**：识别跨 session / 多轮重复上下文，复用 [[KV-Cache]]。
- **声明式 locality**：把 RAG 的 span / document / query 结构暴露给 serving engine。
- **早停与 rank-aware recall**：按下游效用决定检索何时停止，而不是固定 I/O 或固定 top-k。
- **端侧索引压缩**：在边缘设备上减少 embedding / vector index 存储。

## 引用本概念的论文

- [[TeleRAG-MLSys26|TeleRAG]] — 把 retrieval prefetch 与 KV 复用协同，降低 retrieval-to-generation 间隙。
- [[ContextPilot-MLSys26|ContextPilot]] — 长上下文 RAG/agent 的 context reuse 调度，提升 prefix hit。
- [[SpanQueries-MLSys26|SpanQueries]] — 用 span query IR 统一 chat、RAG、agent 和 inference-scaling 的 locality 表达。
- [[Terminus-MLSys26|Terminus]] — rank-aware early termination，让向量检索按下游效用提前停止。
- [[LEANN-MLSys26|LEANN]] — 端侧 RAG 索引不存 embedding，查询时重算，显著降低存储占用。
- [[Tag2Graph-MLSys26|Tag2Graph]] — ontology-guided 对话 RAG 记忆，把长期个性化信息组织为图。

## 相关概念

- 推理内存：[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]
- 推理调度：[[Chunked-Prefill]]、[[Continuous-Batching]]、[[Disaggregation]]
- Agent：RAG 常作为 agent memory / tool-use 的知识入口
