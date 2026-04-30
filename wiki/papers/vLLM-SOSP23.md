---
type: paper
name: vLLM
full_title: "Efficient Memory Management for Large Language Model Serving with PagedAttention"
authors: [Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph E. Gonzalez, Hao Zhang, Ion Stoica]
venue: SOSP
year: 2023
tags: [llm-serving, kv-cache, pagedattention, memory-management, continuous-batching]
source_pdf: "[[sosp23-kwon-pagedattention.pdf]]"
source_md: "[[sosp23-kwon-pagedattention]]"
---

# vLLM: Efficient Memory Management for LLM Serving with PagedAttention (SOSP 2023)

> **一句话总结**：把 [[KV-Cache]] 当 OS 虚存分页管理——切固定大小 block + block table 映射 + on-demand 分配 = 零碎片 + copy-on-write prefix 共享，吞吐比 FasterTransformer/Orca 高 2-4×。这是后续几乎所有 KV cache 系统工作的基础抽象，PagedAttention 已成为 LLM serving 事实标准。

## 问题

LLM serving 中，[[KV-Cache]] 是每个请求的动态内存对象——随 token 生成持续增长，长度和生命周期不可预知。现有系统（FasterTransformer、Orca）把 KV cache 存在连续内存中，导致：

- **内部碎片**：按 max_seq_len 预分配（如 2048 token），实际生成通常远小于此
- **外部碎片**：不同请求预分配大小不同，释放后形成 fragmented hole
- **无法共享**：beam search / parallel sampling 等解码方法产生的多个序列有共享前缀，但连续内存方案无法表达共享

实测仅 20.4%-38.2% 的 KV cache 内存真正用于存储 token state（vLLM Fig 2）。

## 核心方法

**PagedAttention**：把 KV cache 切成固定大小的 **physical block**（如 16 token/block），每个 sequence 维护一张 **block table**（逻辑 block index → 物理 block address），attention kernel 按 block table 间接寻址。

三重收益：
1. **零内部碎片**：按需分配 block（序列每生成 16 token 才分配一个），而非预分配整段
2. **零外部碎片**：所有 block 等大，自由分配/释放
3. **Copy-on-write 共享**：相同前缀的多个序列共享 physical block，fork 时增加 ref count，写时复制

**vLLM 系统**：基于 PagedAttention 构建的分布式 serving 引擎，co-design block-level 内存管理 + **preemptive scheduling**（GPU 显存不足时 evict/swapping block 到 CPU），支持 GPT/OPT/LLaMA 等模型和 tensor parallelism。引入了 **[[Continuous-Batching]]**（iteration-level batching）：每步迭代动态加减请求（新请求加入、已完成请求退出），与 PagedAttention 的按需分配天然契合。

## 关键结果

- 比 FasterTransformer/Orca 吞吐 **提升 2-4×**（同等延迟）
- 长序列、大模型、复杂解码（beam search/parallel sampling）场景收益更显著
- KV cache 内存利用率从 20-38% → **~100%**
- 开源后成为 LLM serving 领域的 **de facto baseline**（几乎所有后续系统论文都在 vLLM 上对比或插件化）

## 相关

- **核心创新**：[[PagedAttention]]、[[Continuous-Batching]]
- **后续系统**：[[SGLang-NeurIPS24|SGLang]]（RadixAttention）、[[Jenga-SOSP25|Jenga]]（异构 attention KV）、[[DiffKV-SOSP25|DiffKV]]（KV 压缩）、[[CacheBlend-EuroSys25|CacheBlend]]、[[LMCache-arXiv25|LMCache]] 等均基于 vLLM 构建
- **同会议**：SOSP 2023
