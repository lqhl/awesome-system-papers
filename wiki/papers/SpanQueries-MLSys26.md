---
type: paper
name: SpanQueries
full_title: "Using Span Queries to Optimize for Cache and Attention Locality"
authors: [Paul Castro, Nick Mitchell, Nathan Ordonez, Thomas Parnell, Mudhakar Srivatsa, Antoni Viros i Martin]
venue: MLSys
year: 2026
tags: [kv-cache, rag, agent, vllm, inference-api, ai-infra]
source_pdf: "[[3416a75f4cea9109507cacd8e2f2aefc.pdf]]"
source_md: "[[3416a75f4cea9109507cacd8e2f2aefc]]"
---

# Using Span Queries to Optimize for Cache and Attention Locality (MLSys 2026)

> **一句话总结**：提出「span query」——一个把 chat/RAG/inference-time scaling/agentic 工作负载统一表达为带交换律约束的表达式树的声明式 IR，只改 [[vLLM]] 492 行代码就实现了 10–20× TTFT 降低，还顺带优化了 attention locality，让 2B 模型准确率超过 stock 8B。

## 问题

[[vLLM]] 这类推理服务器围绕 chat 的 prefix reuse 设计 [[KV-Cache]]：每轮 chat 历史线性累积，prefix 保持不变，hit rate 趋近 100%。

但新兴工作负载打破这个假设：
- **RAG**：检索片段 F1、F2 顺序可在不同请求中换位，prefix 一变就 miss，hit rate 趋向 0%。
- **Nested generation**（judge-generator、agentic）：inner call 产物 $A_1, A_2$ 以任意顺序喂给 outer judge，也没共同 prefix。

前人方案（CacheBlend、Block Attention）要么假设 order matters，要么硬编码单一用例（RAG）。本文观察到：是否允许重排 = 操作符是否满足**交换律**，这是个应用层决策，应该由用户声明而非系统猜。

## 核心方法

**Span Query IR**

- 一个表达式树，operator 集包括 `C`（chat completion）、`R`（corpus retrieval）、`F`（fragment）、`G`（generate）、`S/A/U`（system/assistant/user message）、`+`（交换的 join）、`✶`（非交换的 join）。
- 每种 use case 都是特例：chat 用 `✶`、RAG 的检索片段用 `+`、judge-generator 在 inner output 处加 `+` 来放松顺序约束。
- High-level optimizer 在表达式树上做 desugaring（C→G、R→F+G）和 `+` simplification 的固定点迭代；low-level optimizer 重写 token 序列以最大化块级 prefix 命中。

**vLLM 改动**

只修改 492 行（总 vLLM 260k 行），分布在 block_pool、kv_cache_manager、scheduler、gpu_model_runner 等处，支持跨请求的非 prefix 块复用。

**attention locality 优化**

惊喜产物：利用 `+` 的交换律，把 expression tree 当 map-reduce，让 small model 的 attention 能聚焦在「当前应处理的片段」而避开 lost-in-the-middle。2B 模型能超过 8B stock 的准确率。

## 关键结果

- **TTFT 降低**：RAG + nested generation 两个非 chat 场景下 10–20× TTFT 降低，远超 CacheBlend 的 3–4×。
- **cache miss 时**：attention sparsity 让 prefill 再省 3×。
- **accuracy**：attention-locality 优化的 span query 跑在 2B 模型上，准确率**超过** stock 服务器跑 8B。
- **工程量**：vLLM 改动 492 行 Python。

## 相关

- **相关概念**：[[KV-Cache]]、[[Chunked-Prefill]]、[[PagedAttention]]、[[Attention]]
- **同类系统**：[[vLLM]]、CacheBlend、Block Attention
- **同会议**：[[MLSys-2026]]
