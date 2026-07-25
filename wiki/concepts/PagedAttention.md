---
type: concept
aliases: [PagedAttention, Paged Attention, paged attention, paged KV]
parent: "[[KV-Cache]]"
introduced_by: "[[vLLM-SOSP23]]"
last_updated: 2026-07-23
tags: [memory, attention, kv-cache, llm-inference]
---

# PagedAttention

> 把 [[KV-Cache]] 切成固定大小的 physical block，用 block table 做逻辑→物理间接寻址——类比 OS 虚存分页，消除 varying-length 序列带来的内外部碎片，并自然支持 copy-on-write prefix 共享。[[vLLM]] 的核心 contribution，也是后续 LLM serving 的事实基线。

## 核心思想

传统实现为每条序列在 HBM 预分配 `max_seq_len × hidden_size × 2` 连续内存，带来三类浪费：为未来 token 预留的 reserved space、实际长度远小于上限的内部碎片、以及 buddy allocator 造成的外部碎片。[[vLLM-SOSP23|vLLM]] 测量 FasterTransformer/Orca 类系统仅 20.4%–38.2% KV 显存真正存 token state。

PagedAttention 借鉴 OS paging：
- KV 切成固定 **physical block**（典型 16 token/block）
- 每序列维护 **block table**（逻辑 block index → physical address）
- attention kernel 按 block table 间接寻址，block 内访存仍连续

带来能力：零外部碎片、按需分配（每满一 block 才分配）、copy-on-write prefix 共享（[[Prefix-Caching]] 基础）、beam search / parallel sampling 在分支点 fork。

## 为什么重要

PagedAttention 把 LLM serving 的内存问题从「连续 tensor 预分配」改写为「可增长、可共享、可驱逐的 block pool」——这使 [[Continuous-Batching]] 的 iteration 级动态 batch 在工程上可行：请求每步进出 batch 时，block 按需分配/释放，而非整条序列占满 max length。

block 抽象也成为后续扩展的公共接口：[[RadixAttention]] 用 radix tree 替代 flat block table；[[OPKV-MLSys26|OPKV]] 在 page 上叠加 recallable sparsity；[[FluxMoE-arXiv26|FluxMoE]] 把分页思想推广到 MoE expert 权重（PagedTensor）；[[fabric-lib-MLSys26|fabric-lib]] 的 page-wise KV transfer 与 block 布局兼容。这些论文共同假设 **block 是 KV 管理与跨系统传输的自然粒度**。

## 关键观察 / 隐含假设

- **观察 1：LLM serving 内存压力本质是 varying-length sequences + finite memory，与 OS 程序间内存复用同构。** [[vLLM-SOSP23|vLLM]] 作者 key insight：分页已验证 50 年，搬到 attention 层是自然的工程决策。
- **观察 2：间接寻址的 kernel 开销可被更大 batch 抵消。** PagedAttention kernel 比 FasterTransformer 慢 20–26%，但端到端吞吐高 2–4×，因为瓶颈在 memory capacity 而非单 kernel FLOPs（[[vLLM-SOSP23|vLLM]]）。
- **观察 3：block 级共享对 parallel sampling / beam search 收益显著。** Alpaca trace 上 parallel sampling 省 6–10% block、beam search 最多省 55% block（[[vLLM-SOSP23|vLLM]]）。
- **观察 4：碎片化小段导致 GH200 C2C 严重 under-utilize。** [[SuperInfer-MLSys26|SuperInfer]] 测得 [[vLLM]] 在 GH200 上有效 KV 传输仅 ~10 GB/s（<5% 峰值），根因是 layer-first 64KB segment + 数千次 `cudaMemcpyAsync` launch。
- **观察 5：token 级 sparsity 与 page 级管理需桥接。** [[OPKV-MLSys26|OPKV]] 用 OP Block 聚合离散 critical token + Sub Block Manager 本地化层间 recall，避免 iteration 级 RPC 与 token-page 粒度错配。

## 设计空间与取舍

- **Block size（典型 16 token）**：太小则 metadata 开销大，太大则内部碎片回潮；Alpaca 短序列对过大 block 敏感（[[vLLM-SOSP23|vLLM]] §7.2）。
- **Copy-on-write vs eager sharing**：COW 在写冲突时复制单 block，避免 beam/search 大规模 eager copy；代价是 ref count 管理与 [[Speculative-Decoding]] rejection 回滚复杂度上升。
- **Centralized block manager**：简化 tensor-parallel 一致性，但 scheduler 单点可能成为 scale-out 瓶颈（[[vLLM-SOSP23|vLLM]] 未深入讨论）。
- **All-or-nothing preemption + FCFS**：符合 attention 需完整历史 KV 的语义；swapping 时停止接新请求，overload 下尾延迟可能恶化。
- **Radix tree 变体（[[RadixAttention]]）**：更细粒度 prefix 共享与自动去重；实现复杂度高于 flat block table。
- **语义 page layout（[[IceCache-arXiv26|IceCache]]）**：保留 block 抽象但改变填充逻辑——按 key embedding 聚类而非时间顺序，提升 query-aware offload 命中率。
- **Per-head 稀疏页（[[FlexiCache-MLSys26|FlexiCache]]）**：扩展 block table 为 per-head-layer 管理，适配 head 级时序稳定性差异。

## 引用本概念的论文

- [[vLLM-SOSP23|vLLM]]（SOSP 2023）— 提出 PagedAttention 与 block manager
- [[Transformer-NeurIPS17|Attention Is All You Need]] — K/V 数据结构上游
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 异构 KV + on-disk storage 在 block 抽象上继续演化
- [[fabric-lib-MLSys26|fabric-lib]] — page-wise WRITE 与 block 抽象兼容的 KV transfer
- [[FluxMoE-arXiv26|FluxMoE]] — PagedTensor 把分页推广到 MoE expert；virtual→physical 映射移到 kernel 启动前
- [[OPKV-MLSys26|OPKV]] — token 级 recallable sparsity 与 page 级管理的粒度桥接
- [[SuperInfer-MLSys26|SuperInfer]] — block-first layout + batched transfer 修复 C2C 低利用率
- [[MAC-Attention-MLSys26|MAC-Attention]] — 与 paged-KV manager 正交组合，长上下文 decode 复用 summary
- [[SHIP-MLSys26|SHIP]] — Groq 自研 PagedAttention（128–512 token page）配合 SRAM 全驻留 KV
- [[FlexiCache-MLSys26|FlexiCache]] — 扩展 vLLM block table 为 per-head-layer 稀疏页管理
- [[IceCache-arXiv26|IceCache]] — DCI-tree 重排 page layout 提升 query-aware retrieval 命中率
- [[MSA-arXiv26|MSA]] — sparse attention 场景仍保留 block-wise KV 抽象
- [[GhostServe-MLSys26|GhostServe]] — parity checkpoint 在 block 粒度保护流式 KV
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — vLLM 启动阶段 KVCache profiling 依赖 block 分配行为
- [[SpanQueries-MLSys26|SpanQueries]] — span query IR 优化跨请求 block 局部性
- [[DeepScientist-ICLR26|DeepScientist]] — 自动化科研系统在优化 agent 代码时将 PagedAttention 作为已有机制参照，体现研究 agent 需要区分新贡献与成熟 serving 基线

## 已知局限 / 开放问题

- block 内访问仍顺序，不能完全摆脱 attention 的 O(L) decode 复杂度
- 极短 prompt + 极小 batch 时 metadata 开销占比偏高
- 与 [[Speculative-Decoding]] rejection 场景下 ref count / synced block 管理偏复杂
- 跨卡 irregular TP 下 block placement 不均衡（[[RaidServe-MLSys26|RaidServe]] 关注）
