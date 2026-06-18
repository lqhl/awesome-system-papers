---
type: concept
aliases: [prefix caching, Prefix Caching, prefix-cache, prefix cache, prompt caching, context reuse]
parent: "[[KV-Cache]]"
last_updated: 2026-06-18
tags: [llm-inference, kv-cache, caching, prefill]
---

# Prefix-Caching

> LLM serving 中复用已有 prompt/context 前缀对应 [[KV-Cache]] 的技术。核心目标是把重复 prefill 从重新计算变成 cache hit：系统识别多个请求共享的 prefix、历史对话片段或检索上下文块，复用其 KV block，只计算新增部分。

## 问题背景

Prefill 通常是长上下文、RAG、agent workflow 的主要延迟来源。真实 workload 又高度重复：

- 多轮对话保留系统 prompt 与历史上下文
- RAG 请求反复引用同一批文档片段
- agent session 在 planning / tool call / reflection 之间共享大量轨迹前缀
- serving benchmark 与生产流量经常有相同模板、相似 few-shot 示例或 shared instruction

如果每次都从头 prefill，同一段文本会反复消耗 GPU 算力并占用 TTFT budget。

## 核心机制

Prefix caching 通常包含三层：

1. **匹配**：按 token prefix、hash、radix tree 或近似 context index 找到可复用片段。
2. **复用**：复用已有 KV block，并只对 suffix 做增量 prefill。
3. **管理**：处理 eviction、引用计数、跨请求隔离、prefix 失效与多租户公平性。

精确 prefix matching 简单可靠，但对文档顺序变化、RAG 重排、多轮上下文插入很脆弱；近似匹配和 context reuse 能提高 hit ratio，但需要控制准确率损失。

## 与相邻概念的关系

- **[[KV-Cache]]**：prefix caching 复用的对象。
- **[[PagedAttention]]**：把 KV 切成 page/block 后，prefix 复用和引用计数更自然。
- **[[RadixAttention]]**：用 radix tree 管理 shared prefix，是 prefix caching 的代表性实现。
- **[[Chunked-Prefill]]**：切小 prefill 计算粒度；prefix caching 减少需要 prefill 的内容，二者互补。
- **[[Disaggregation]]**：prefill/decode 分离后，prefix cache placement 和 KV transfer 成为系统设计问题。

## 引用本概念的论文

- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming prompt 更新时用 LCP 选择性失效 KV block，多租户 RAG 场景 TTFT 最多 11×。
- [[ContextPilot-MLSys26|ContextPilot]] — 用 context index、alignment、de-duplication 在跨 session / 多轮长上下文中做更鲁棒的 context reuse。
- [[SHIP-MLSys26|SHIP]] — Groq LPU serving 中使用两级 prefix cache（SRAM + host DRAM）降低低 batch 延迟。
- [[SpanQueries-MLSys26|SpanQueries]] — 通过声明式 span query 暴露跨请求 locality，让 serving engine 更容易做 KV reuse。
- [[TeleRAG-MLSys26|TeleRAG]] — RAG pipeline 中把 retrieval prefetch 与 KV 复用协同调度。

## 开放问题

- 近似 prefix/context reuse 如何给出可验证的质量边界？
- 多租户环境下 prefix cache 的收益、隔离和隐私如何同时满足？
- agent workflow 的 trajectory cache 是否应成为比 prefix 更高层的复用抽象？
