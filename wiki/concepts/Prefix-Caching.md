---
type: concept
aliases: [prefix caching, Prefix Caching, prefix-cache, prefix cache, prompt caching, context reuse]
parent: "[[KV-Cache]]"
last_updated: 2026-06-20
tags: [llm-inference, kv-cache, caching, prefill]
---

# Prefix-Caching

> LLM serving 中复用已有 prompt/context 前缀对应 [[KV-Cache]] 的技术。核心目标是把重复 prefill 从重新计算变成 cache hit：系统识别多个请求共享的 token prefix、历史对话片段或检索上下文块，复用其 KV block，只计算新增 suffix。

## 核心思想

Prefix caching 处理的是 prefill 阶段的结构性浪费。长上下文、[[RAG]]、agent workflow 中，大量 token 在跨 session、跨 turn、跨请求间重复出现，但若不缓存，每次 query 都要从头算 attention 生成 [[KV-Cache]]。典型实现分三层：**匹配**（按 token prefix、hash、radix tree 或 context index 找可复用片段）、**复用**（命中 block 直接挂接，仅 prefill suffix）、**管理**（eviction、引用计数、跨请求隔离、失效语义）。

精确 prefix matching 与 [[PagedAttention]] block 粒度天然契合：[[vLLM-SOSP23|vLLM]] 的 copy-on-write block 共享是 prefix cache 的基础抽象。[[RadixAttention]] 则把匹配从「必须从序列首 token 对齐」扩展到 radix tree 上的最长前缀匹配，适合 LM Program 中分支、中间段复用。[[LMCache-arXiv25|LMCache]] 进一步把 KV 提升为跨请求、跨引擎、跨存储层的 first-class 对象，用大 chunk 搬运与 controller API 支撑 enterprise-scale reuse。

但生产 workload 往往不满足「整段前缀逐 token 一致」。[[ContextPilot-MLSys26|ContextPilot]] 测量到 RAG 场景 exact prefix hit 仅约 **5%**，主因是检索文档**顺序变化**而非内容不重叠；[[SpanQueries-MLSys26|SpanQueries]] 把根因归结为输入块的**可交换性**（commutativity）未被 engine 感知。于是 prefix caching 的设计空间从「精确匹配」扩展到 **context reuse**（alignment、de-duplication、annotation）、**声明式 locality**（span query IR）、**动态失效**（LCP 选择性释放 block，如 [[Stream2LLM-MLSys26|Stream2LLM]]）和 **ahead-of-time 全局优化**（[[BatchLLM-MLSys26|BatchLLM]] 在离线批处理中预建 prefix 树）。

## 为什么重要

Prefill 是长上下文与 RAG 的主要 TTFT 来源。[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 在阿里通义生产 trace 上测得 ideal hit ratio 仅 **54%–62%**（低于合成 workload 常报的 80%+），且 **10%** 的 block 贡献 **77%** 复用——说明 cache policy 与 workload 假设错一点，收益就会大幅缩水。[[LMCache-arXiv25|LMCache]] 的企业部署还揭示两个常被忽略的边界：**remote KV loading 在 32Gbps 下需 context >256K tokens 才优于 re-prefill**；**context truncation 可把 hit ratio 从约 85% 打到 45%**。

这些论文共同假设：**KV 复用不是单请求内存优化，而是端到端 serving pipeline 的一等公民**——与 [[Chunked-Prefill]]、[[Continuous-Batching]]、[[Disaggregation]] 的调度顺序、placement 和传输粒度深度耦合。对 agent、多轮对话、批量推理而言，prefix caching 往往决定 TTFT 能否从秒级压到亚秒级。

## 关键观察 / 隐含假设

- **观察 1：真实 workload 的重叠常在「块级」而非「整段前缀级」。** [[ContextPilot-MLSys26|ContextPilot]] 报告跨 session 检索 **79%** 问题来自 top 20% 热门文档，但 relevance 排序不同使 exact prefix 失效；[[SpanQueries-MLSys26|SpanQueries]] 在 RAG 第二次请求仅 **33%** prefix hit。这些论文共同假设：必须把 retriever 输出结构暴露给 serving engine，或在 context 层做 alignment/dedup。
- **观察 2：cache hit 不只取决于内容，还取决于调度与 eviction。** [[ContextPilot-MLSys26|ContextPilot]] 指出未按共享前缀分组执行时，后到请求会 evict 刚写入的共享 prefix；[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 发现 KV block lifespan 极短（P99 仅 **97s**），LFU 失效，需 workload-aware 指数分布淘汰。依赖假设：生产 gateway 能提供 request category，且 eviction 与 admission 协同。
- **观察 3：动态 prompt 演化需要 selective invalidation，而非全量重算。** [[Stream2LLM-MLSys26|Stream2LLM]] 在 ANNS update mode 下用 LCP 保留未变前缀 block，相对 naive 全失效在 memory pressure 下 P99 仍快 **8–10×**；但 LCP≈0 时退化为大量 recompute。
- **观察 4：prefix cache 层级正在从 GPU HBM 扩展到 host/remote。** [[SHIP-MLSys26|SHIP]] 在 Groq LPU 上用 SRAM + **1 TB**/节点 DRAM 两级 cache，DRAM hit **50–75%**；[[LMCache-arXiv25|LMCache]] 把 stored KV 总量推到 **30T+ bytes**，non-GPU 复用成为主增长源。
- **观察 5：离线全局可知时，runtime LRU 显著次优。** [[BatchLLM-MLSys26|BatchLLM]] 测得 vLLM LRU 仅节省 **35.8%** prefill token，全局 prefix 树可达 **58.1%**。

## 设计空间与取舍

- **精确 prefix vs context reuse**：精确匹配实现简单、语义安全，但对 RAG 重排、多轮插入极其脆弱；[[ContextPilot-MLSys26|ContextPilot]] 用 alignment + annotation 把 hit 拉到 **38–60%** 且多数场景几乎不损准确率，但依赖模型遵循 order/location 指令，且跨 session reuse 带来隐私隔离问题。
- **被动 engine cache vs 主动 cache layer**：[[vLLM]]/[[SGLang]] 内置 prefix cache 部署门槛低；[[LMCache-arXiv25|LMCache]] 用 connector + controller API 支持 pin/move/compress 和 PD 传输，但多租户安全语义与 controller failure model 仍开放。
- **在线 LRU vs workload-aware / ahead-of-time**：[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 的 WA policy 仅比 LRU 高 **1.5%–3.9%** hit，说明 characterization 价值大于 policy 本身；[[BatchLLM-MLSys26|BatchLLM]] 的静态全局树赢吞吐但牺牲在线公平性。
- **共享 cache vs 租户隔离**：[[KVCacheInTheWild-ATC25|KVCacheInTheWild]] 测得跨用户 hit 几乎为零，支持 intra-user 策略；[[SHIP-MLSys26|SHIP]] 强制 org 级隔离。共享提高 hit，隔离满足合规。
- **与相邻机制**：[[RadixAttention]] 提供更细粒度跨序列索引；[[Chunked-Prefill]] 切 compute 粒度，prefix caching 减少 compute 量；[[Disaggregation]] 使 prefix placement 与 KV transfer 成为系统设计问题。

## 引用本概念的论文

- [[SGLang-NeurIPS24]] — 提出 [[RadixAttention]]，把 prefix caching 从「请求级」扩展到 LM Program 跨调用复用。
- [[vLLM-SOSP23]] — PagedAttention block 级 copy-on-write 是主流 prefix cache 的内存抽象基础。
- [[LMCache-arXiv25]] — 把 [[Prefix-Caching]] 做成跨引擎、跨存储层的 enterprise cache layer，并量化 load-vs-prefill crossover 与 truncation 对 hit 的冲击。
- [[ContextPilot-MLSys26|ContextPilot]] — context index + alignment + de-duplication，把 RAG/agent 场景 hit 从约 **5%** 拉到 **38–60%**。
- [[SpanQueries-MLSys26|SpanQueries]] — span query IR 用 `+`/`✶` 声明可交换性，非 chat workload TTFT 降 **10–20×**。
- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming RAG 下 LCP 选择性失效 + 两阶段调度，多租户 TTFT 最多 **11×**。
- [[TeleRAG-MLSys26|TeleRAG]] — retrieval prefetch 与 KV 复用协同，降低 retrieval-to-generation 间隙。
- [[SHIP-MLSys26|SHIP]] — SRAM + host DRAM 两级 prefix cache，服务低 batch 低延迟场景。
- [[KVCacheInTheWild-ATC25|KVCacheInTheWild]] — 生产 trace 刻画 ideal hit、lifespan、single-turn 主导等假设，驱动 workload-aware eviction。
- [[BatchLLM-MLSys26|BatchLLM]] — 离线批处理的全局 prefix 树 + 重排，吞吐 **1.3–10.8×**。
- [[CacheBlend-EuroSys25|CacheBlend]] — 近似 KV 匹配提高 reuse，但准确率可降 **9–11%**，与精确 prefix 路线形成对照。

## 已知局限 / 开放问题

- 近似 prefix/context reuse（CacheBlend 类）如何给出可验证的质量边界，并与精确 hit 的 SLO 共存？
- 多租户环境下 prefix cache 的收益、隔离、隐私与 cache poisoning 如何同时满足？[[ContextPilot-MLSys26|ContextPilot]] 与 [[LMCache-arXiv25|LMCache]] 均指出跨 tenant namespace 语义缺失。
- cache-vs-prefill / cache-vs-load 的自适应决策：何时 remote load、何时 recompute、何时 prefetch？[[LMCache-arXiv25|LMCache]] 的 crossover 强烈依赖带宽与 context length。
- agent workflow 的 trajectory cache 是否应成为比 token prefix 更高层的复用抽象？[[FlashAgents-MLSys26|FlashAgents]] 的 intra-turn radix cache 是初步探索。
- prefix caching 与 [[Disaggregation]]、[[KV-Cache-Compression]]、speculative decoding 组合时的端到端一致性与尾延迟尚未系统量化。