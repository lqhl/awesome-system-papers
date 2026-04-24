---
type: concept
aliases: [PagedAttention, Paged Attention, paged attention, paged KV]
parent: "[[KV-Cache]]"
introduced_by: "[[vLLM-SOSP23]]"
last_updated: 2026-04-24
tags: [memory, attention, kv-cache, llm-inference]
---

# PagedAttention

> 把 [[KV-Cache]] 当 OS 虚存分页管理。每个 sequence 的 KV 不连续存放，而是切成固定大小的 block，用一张 block table 把逻辑位置映射到物理 block——消除内外部碎片，并自然支持 copy-on-write 的 prefix 共享。这是 [[vLLM]] 的核心 contribution，也是后续大量 LLM serving 系统的事实基线。

## 核心思想

传统 KV cache 实现：每个 sequence 在 HBM 里预分配 `max_seq_len × hidden_size × 2` 的连续内存。问题：

- **内部碎片**：实际生成长度远小于 max_seq_len 时，剩余空间浪费
- **外部碎片**：序列结束后释放，但 fragmented hole 难以重用
- **无法共享**：相同 prompt 的两个序列的 prefix KV 不能复用

PagedAttention 借鉴 OS 虚存：
- 把 KV cache 切成固定大小的 **physical block**（如 16 token / block）
- 每个 sequence 维护一张 **block table**（逻辑 block index → physical block address）
- attention kernel 改为按 block table 间接寻址（增加一次 lookup，但 block 内访存仍连续）

带来的能力：
- **零外部碎片**：所有 block 等大，自由分配/释放
- **按需分配**：序列每生成 16 token 才分配一个新 block
- **Copy-on-write**：相同 prompt 的多个序列共享前缀的 physical block（[[Prefix-Caching]] 的基础）
- **Beam search / parallel sampling 共享**：分支点之前的 block 共享，分支后再 fork

## 为什么这样做

[[vLLM]] 作者的 key insight：**LLM serving 的内存压力本质上是「varying-length sequences + finite memory」的拮抗，与 OS 解决程序间内存复用的问题同构**。OS 的 paging 已经验证 50 年，把它搬到 attention 层是自然的工程决策。

## 实现要点

- **Block size 选择**：典型 16 token / block。太小则 metadata（block table）开销大，太大则碎片回潮
- **Attention kernel 改造**：custom CUDA kernel 接受 block table 参数，scatter-gather 形式访问 K/V
- **Copy-on-write**：fork 出新序列时增加 ref count；写时复制保证 prefix 不被 sibling 修改
- **配合 [[Continuous-Batching]]**：每步可以加入新 sequence、踢掉完成的 sequence，与 PagedAttention 的按需分配天然契合

## 相关工作

- 上游 inspiration：[[Virtual-Memory]]、operating systems 的 page table
- 后继 / 变体：
  - [[RadixAttention]]（[[SGLang]]）：用 radix tree 替代 block table，更细粒度的 prefix 共享
  - [[Prefix-Caching]]：基于 block table 的跨请求 prefix 复用
  - [[Block-Sparse-Attention]]：在 block 粒度上做稀疏化（用于长 context）

## 引用本概念的论文

- *[[vLLM-SOSP23|vLLM 原始论文]]*（SOSP 2023, Kwon et al.）— 提出
- [[TransferEngine-arXiv25|TransferEngine]] — KvCache transfer 的 page-wise WRITE 与 PagedAttention 的 block 抽象兼容
- [[MSA-arXiv26|MSA]] — 在 sparse attention 场景仍保留 block-wise KV 抽象

## 已知局限

- block 内访问仍然是顺序的，不能完全摆脱 attention 的 O(L) decode 复杂度
- 极短 prompt + 极小 batch 时 metadata 开销占比偏高
- 与 [[Speculative-Decoding]] 等需要回退的机制配合时 ref count 管理偏复杂
