---
type: concept
aliases: [RadixAttention, radix attention, Radix Attention]
parent: "[[KV-Cache]]"
introduced_by: "[[SGLang-NeurIPS24]]"
last_updated: 2026-04-30
tags: [memory, attention, kv-cache, llm-inference, caching]
---

# RadixAttention

> 用 radix tree 管理跨请求的 [[KV-Cache]] 共享。不同于 [[PagedAttention]] 要求前缀完全匹配，radix tree 可以自动识别任意非对齐 prefix 重叠，结合 LRU eviction + cache-aware scheduling 最大化 KV cache 复用率。

## 核心思想

[[vLLM-SOSP23|vLLM]] 的 PagedAttention + block table 方案支持 copy-on-write 的 prefix 共享，但要求共享的 prefix 从序列的第一个 token 开始（即「对齐的」前缀）。在实际 LM Program 中（多次 LLM 调用、分支合并、多轮对话），不同请求很可能共享中间某段 context 而非整段前缀。

RadixAttention 把 KV cache 组织为 **radix tree**（压缩前缀树）：每个节点对应一个 token，从根到任意节点的路径是一个可能被复用的 KV cache segment。新请求到达时，沿着树做最长前缀匹配——匹配到的节点对应的 KV cache 直接复用，只需 prefill 未匹配的 suffix。

## 为什么这样做

SGLang 的定位不是单次推理加速，而是 **LM Program 的执行引擎**。在 agent workflow / few-shot / branch-solve-merge / multi-turn chat 等场景中，同一 session 内会有大量不同的 LLM 调用共享部分 context。RadixAttention 让这些共享自动发生，不需要程序员手动管理。

## 与 PagedAttention 的关系

- [[PagedAttention]] 解决的是**单序列内** KV cache 的内存碎片和序列分叉问题（virtual memory paging）
- RadixAttention 解决的是**跨序列间** KV cache 的 prefix 共享问题（radix tree cache）
- SGLang Runtime 底层仍使用 PagedAttention-style 的 block 分配（与 vLLM 共享 block 抽象），radix tree 是更高一层的 cache 索引结构

## 引用本概念的论文

- [[SGLang-NeurIPS24]] — 提出
- [[Libra-ICLR26|Libra]] — 基于 SGLang Runtime 的 MoE LB
