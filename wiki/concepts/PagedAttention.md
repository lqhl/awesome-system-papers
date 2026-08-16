---
type: concept
aliases: [PagedAttention, Paged Attention, paged attention, paged KV]
parent: "[[KV-Cache]]"
introduced_by: "[[vLLM-SOSP23]]"
last_updated: 2026-08-14
tags: [memory, attention, kv-cache, llm-inference]
---

# PagedAttention

> PagedAttention 把逻辑上连续的 [[KV-Cache]] 切成固定 token 数的 block，用 block table 将逻辑 block 映射到任意物理 block。它借鉴操作系统虚拟内存，但不是 GPU 页表本身：attention kernel 必须显式按 block table 间接寻址。

## 核心思想

[[vLLM-SOSP23]] 对准的问题是，请求输出长度在到达时未知，但早期 serving 系统会按 max sequence length 为每条序列预留一块连续 KV tensor。这会产生三种浪费：未来 token 的预留空间、最后未填满部分，以及 allocator 不能拼合的外部碎片。论文实测只有 20.4%–38.2% 的 KV 显存真正存 token state。

PagedAttention 将这块连续预分配改成三个机制：

1. **按需 block pool**：prefill 只为 prompt 已需的部分分配 block，decode 填满当前 block 后才取新 block。单序列内部碎片上界缩到最后一个 block。
2. **block table**：逻辑第 i 段 KV 可以放到任意物理 block，attention kernel 在计算时查表。
3. **copy-on-write 共享**：多条 sequence 可将同一 prefix 映射到同一物理 block，只在某分支继续写入共享 block 时复制。

PagedAttention 保留 exact attention 数学语义，不是压缩或稀疏 attention。它也不等于 [[vLLM]] 整个系统：FCFS、sequence-group preemption、CPU swap/recompute、[[Continuous-Batching]] 和分布式 scheduler 都是上层策略。

## 为什么重要

分页将 LLM serving 的内存对象从“一条 sequence 对应一块大 tensor”改成“可增长、可共享、可回收的 block 集合”。这与 iteration-level batching 互补：每轮完成的请求释放 block，新请求只为当前 token 分配，因而能将更多序列放进 batch。

它还建立了后续 KV 系统的公共粒度：[[RadixAttention]] 在 block 之上建 prefix tree，[[Prefix-Caching]] 用 block hash/COW 复用上下文，[[FlexiCache-MLSys26]] 将管理粒度扩到 per-head/per-layer，[[FluxMoE-arXiv26]] 甚至将逻辑–物理映射推广到 expert 权重。

但 OSDI 2026 也清楚揭示了新代价：对 GPU 计算合适的小页，未必是 CPU/SSD/network 传输的好粒度；一个静态大 KV pool 也未必能在多模型之间让出物理页。

## 关键观察 / 隐含假设

- **间接寻址会让单 kernel 变慢，系统仍可变快。** [[vLLM-SOSP23]] 的 PagedAttention kernel 比 FasterTransformer attention 慢 20%–26%，但因为更多请求能进 batch，在论文的 ShareGPT/Alpaca、OPT/LLaMA 配置上端到端吞吐高 2–4 倍。这个取舍只在 KV capacity 限制 batch 时有利；短序列或计算已饱和时收益会缩小。
- **block 共享的收益取决于解码树。** 原论文的 Alpaca trace 中，parallel sampling 节省 6.1%–9.8% block，beam search 节省 37.6%–55.2%。如果生产几乎只用 greedy single sample，这部分价值会很小，剩下的主要收益是减少预留与碎片。
- **block size 是计算、碎片、hash 与 I/O 的联合参数。** vLLM 默认常用 16 token；太大会增加最后 block 浪费并降低 prefix 匹配粒度，太小会增加 table/hash/transfer metadata。[[SHIP-MLSys26]] 在 Groq 平台选 128–512 token page，说明 16 不是跨硬件常数。
- **小页适合分配，却会将分层 KV 变成碎片 I/O。** [[Strata-OSDI26]] 指出，1–32-token page 使 8,192-token KV 用传统 copy 时只达 PCIe 5.0 理论带宽约 22%，Grace–Hopper 上约 5%。它在 host/SSD 用 page-first 大块布局，搬运时转成 GPU layer-first。这个结果否定的是“计算 page 直接当 I/O page”，不是分页内存管理本身。
- **静态虚拟大 tensor 仍可以阻止多模型共享物理显存。** [[Prism-OSDI26]] 的 kvcached 为每个 engine 预留稳定 VA，但按需映射/解映射 2 MB 物理页。PagedAttention kernel 仍看到普通大 tensor，冷模型未使用的物理页却可让给权重或其他 KV pool。
- **稀疏 attention 需要比标准 block table 更细的映射。** [[ECHO-OSDI26]] 为每层维护 host/GPU 双向映射和 priority，并为 GPU-side allocation/free/recall 保留约 610 MB metadata。[[FlexiCache-MLSys26]] 也将 vLLM block table 扩到 per-head-layer 稀疏页。“已分页”不代表 token/head/layer 稀疏性已被表达。
- **离线批处理可把 page 当作可迁移 sequence state。** [[BatchGen-OSDI26]] 的 decode manager 为每个 active sequence 预留两个 future pages，需要时再扩；host 保存全部 sequence KV。它用这一机制在跨 GPU coroutine 迁移时恢复状态，但对应的数据搬运和重配开销不适合严格低延迟在线场景。
- **新 GPU 不会自动跑好 PagedAttention。** [[Alibaba-ASI-OSDI26]] 将 decode PagedAttention/SplitKV 移植到新 GPU 时，Triton compiler 反转 thread-block layout，让线程组重复计算整个矩阵，需要新 compiler pass 修复。这说明 block 抽象稳定，kernel/compiler 适配仍是每代硬件的真实成本。

## 设计空间与取舍

| 决策 | 偏小 / 偏细 | 偏大 / 偏粗 | 要同时考虑 |
|---|---|---|---|
| token/block | 碎片少、prefix 粒度细 | metadata 少、传输更易聚合 | 序列长度、hash、kernel、I/O |
| block manager | 中央统一映射 | 分布式/分层所有权 | 一致性、调度延迟、失败恢复 |
| sharing | copy-on-write | 不共享/提前复制 | prefix 命中、ref count、写入冲突 |
| preemption | recompute | CPU/SSD swap | GPU 计算与链路、存储尾延迟 |
| 稀疏粒度 | token/head/layer 级 | sequence/block 级 | metadata 与节省的 KV bytes |
| 布局 | GPU layer-first | host/storage page-first | 在线转置开销与多份副本 |

[[RadixAttention]] 等结构解决“怎样索引可复用的 block”，PagedAttention 解决“attention 怎样读非连续 block”；两者相关但不应混为一个机制。

## 引用本概念的论文

- [[vLLM-SOSP23]] — 提出非连续 exact attention、block manager、按需分配和 COW 共享。
- [[SGLang-NeurIPS24]] — 在分页 KV 之上用 radix tree 自动复用 LM program prefix。
- [[Strata-OSDI26]] — 明确证明小 KV page 与慢层 I/O 大粒度的冲突。
- [[Prism-OSDI26]] — 在不改 PagedAttention kernel 大 tensor 界面的前提下，弹性映射底层物理 GPU page。
- [[ECHO-OSDI26]] — 在原生稀疏 attention 中加入 per-layer 双向 block 映射与 recall。
- [[BatchGen-OSDI26]] — 用 paged KV manager 支持离线 sequence coroutine 暂停与迁移。
- [[Alibaba-ASI-OSDI26]] — 展示 PagedAttention/SplitKV 迁移到新 GPU 需要 compiler 和 thread-block mapping 修正。
- [[OPKV-MLSys26]] — 在 page 管理上桥接 token-level recallable sparsity。
- [[SuperInfer-MLSys26]] — 用 block-first 布局和批量传输改善 Grace–Hopper C2C 利用率。
- [[FlexiCache-MLSys26]] — 将 vLLM block table 扩展为 per-head/per-layer 稀疏页管理。
- [[SHIP-MLSys26]] — 在 Groq LPU 上使用更大 page 和 SRAM/DRAM 分层 KV。
- [[IceCache-arXiv26]] — 按 key embedding 而非时间顺序组 page，优化 query-aware offload。
- [[SpanQueries-MLSys26]] — 用 span 语义和 block hash 调整可交换 context 的复用与位置。
- [[FluxMoE-arXiv26]] — 将逻辑–物理映射抽象推广到 MoE expert 权重。
- [[MPK-OSDI26]] — 在固定 offline batch 中保留 paged attention/continuous batching，但将 operator graph 降到 persistent mega-kernel。

## 已知局限 / 开放问题

- **分页不降低 exact attention 的读取复杂度。** block 内仍要读所需历史 K/V；百万 token 上下文还需稀疏/压缩/线性 attention 或更大存储层。
- **跨层管理缺少统一 page 契约。** compute page、allocator 物理页、network chunk 和 SSD extent 不必同大；现有系统常靠专用转置/聚合 kernel 桥接。
- **ref count 和回滚变复杂。** beam search、[[Speculative-Decoding]] rejection、request cancellation、跨 worker 迁移和版本切换都可让 block ownership 快速变化。
- **分布式 block manager 的容错与公平性证据少。** 原始 vLLM 使用中央 scheduler 和 all-or-nothing preemption；多租户、跨机 cache 和 overload 下如何不暂停入队、不让大请求长期占 pool，仍是开放问题。
- **硬件/编译器迁移并非自动。** block table 是稳定抽象，高效 kernel 却依赖 head dimension、page size、warp/block layout、TMA/C2C 能力和 compiler 映射。
