---
type: paper
name: SpanQueries
full_title: "Using Span Queries to Optimize for Cache and Attention Locality"
authors: [Paul Castro, Nick Mitchell, Nathan Ordonez, Thomas Parnell, Mudhakar Srivatsa, Antoni Viros i Martin]
venue: MLSys
year: 2026
tags: [kv-cache, rag, agent, vllm, inference-api, prefix-caching]
source_pdf: "[[3416a75f4cea9109507cacd8e2f2aefc.pdf]]"
source_md: "[[3416a75f4cea9109507cacd8e2f2aefc]]"
---

# Using Span Queries to Optimize for Cache and Attention Locality (MLSys 2026)

> **一句话总结**：提出 span query 声明式 IR，用交换律约束统一 chat/RAG/inference-time scaling/agentic 工作负载，仅改 [[vLLM]] 492 行即实现 10–20× TTFT 降低，并借 attention locality 优化让 2B 模型准确率超过 stock 8B。

## 问题

[[vLLM]] 等推理服务器围绕 chat 的 prefix reuse 优化 [[KV-Cache]]：历史线性追加，prefix 稳定，cache hit rate 趋近 100%。

但 RAG、judge-generator、agentic 等工作负载的复用块顺序随请求变化，prefix 一错位就 miss，hit rate 趋向 0%。CacheBlend、Block Attention 要么假设 order matters，要么硬编码 RAG 单一场景。核心缺口：是否允许重排是应用语义，应由用户声明（交换律），而非系统猜测。

## 核心方法

**Span Query IR**：表达式树，operator 含 `C`（chat）、`R`（retrieval）、`G`（generate）、`S/A/U`（消息类型）、`+`（可交换 join）、`✶`（不可交换 join）。chat/RAG/nested generation 均为特例。

**两级优化**：high-level optimizer 做 desugaring 与 `+` 分布，解决 dual output paradox；low-level optimizer 做 block alignment 与 token 序列重写。用括号 special token 序列化后送入 [[vLLM]]，配合 CIDRA 算法做跨请求 batch 的 ReRoPE repositioning。

**attention locality**：把 expression tree 当 map-reduce，利用 `+` 交换律缓解 lost-in-the-middle，无需改 model server 即可提升小模型准确率。

## 关键结果

- RAG 与 nested generation 场景 TTFT 降低 **10–20×**（CacheBlend 约 3–4×）
- cache miss 时 attention sparsity 再省 **3×** prefill
- attention 优化后 **2B 模型准确率超过 stock 8B**
- [[vLLM]] 改动仅 **492 行** Python

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Chunked-Prefill]]、[[Attention]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]