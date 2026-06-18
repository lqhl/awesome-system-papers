---
type: paper
name: OPKV
full_title: "OPKV: A High-Throughput Plugin-Driven Framework for Recallable Sparsity in Paged KV Cache Systems"
authors: [Huazheng Lao, Xiaofeng Li, Rui Xu, Long Chen, Xia Zhu, Jinquan Zhang]
venue: MLSys
year: 2026
tags: [kv-cache, sparse-attention, paged-attention, recallable-sparsity, llm-inference]
source_pdf: "[[1afa34a7f984eeabdbb0a7d494132ee5.pdf]]"
source_md: "[[1afa34a7f984eeabdbb0a7d494132ee5]]"
---

# OPKV: A High-Throughput Plugin-Driven Framework for Recallable Sparsity in Paged KV Cache Systems (MLSys 2026)

> **一句话总结**：用 plugin 把 token 级 recallable sparsity 无缝接入 [[PagedAttention]] 体系，以 OP Block 聚合 + hot page 复用 + 层内 Sub Block Manager 把 InfiniGen/OmniKV 在高 batch 下的 recall 开销压住，在 [[vLLM]] 上解码吞吐提升 **1.3–1.8×**。

## 问题

长上下文推理中 [[KV-Cache]] 线性膨胀是主要瓶颈。Recallable sparsity（把非关键 KV offload 到 CPU、按需召回）在准确率上优于永久丢弃，但现有实现是算法原型：**token 级选择与 page 级 [[PagedAttention]] 管理粒度不匹配**，直接按 page 召回会产生约 **4× I/O 放大**；且 recall 开销随 batch 线性增长，高 batch 下吞吐平台化甚至受限 batch=1。

此外，[[Continuous-Batching]] 框架在 iteration 级更新 block metadata，而 sparsity 需在 **attention layer 间**召回，毫秒级层计算要求本地化、低开销的 metadata 管理。

## 核心方法

OPKV 提出 **model-sparsity-cache** 三层解耦 + 算法无关 recall 优化：

**1. Plugin Interface（五回调）**
- `register` / `preprocess` / `select` / `fetch` / `recall` 贯穿 attention 各 stage。
- Sparsity 算法（InfiniGen、OmniKV 等）只实现插件，不改 transformer 与 cache engine 核心逻辑。

**2. KV Recall：OP Block + hot page**
- **Ordered Block**：prefill/decode 顺序生成的原始 page。
- **OP Block**：把离散 critical token 重聚合为 page，利用 temporal locality 在 GPU 上复用。
- 贪心 page retrieval（Algorithm 1）：page hit ratio ρ 控制 I/O 放大；vectorized filter 降低检索开销；未覆盖 token 再从 Ordered Block 聚合为新 OP Block。
- 整体复杂度 O(N)，object aggregation 仅 O(k)。

**3. Sub Block Manager**
- 本地管理 layer 级 metadata，避免 server-worker RPC 在层间同步。
- `transfer` / `realloc` / `free` 三原语把请求 block table 交给 worker；GPU/CPU 双池 + S3FIFO 等 eviction（KV recall 负载下 LRU 表现差）。
- recall 与 GPU attention **流水线重叠**。

基于 vLLM v0.7.2 实现约 7000 行 Python + 少量 CUDA；扩展 PagedAttention backend 支持 op mask 抑制重复 token attention。

## 关键结果

**InfiniGen（OPT-6.7B / LLaMA-8B）**
- batch 2–10：吞吐提升 **37–77%**；GPU page hit ratio **77.64%**。
- block size 16、page hit ratio 60%、KV budget 25% 为默认 sweet spot；10% budget 仍比原型快 **46%**。

**OmniKV（LLaMA-8B / Yi-9B）**
- 用更低 GPU 预算（~24% vs 原版 30%）仍提升 **33–56%** 吞吐。
- S3FIFO 在 17% 总 KV budget 下比 OmniKV 原型高 **33.55%**。

**Ablation（batch=8）**
- 禁用 OP Block 聚合：InfiniGen **-33%**、OmniKV **-24%** 吞吐。
- 禁用 hot page reuse：**-14% / -12%**。
- 全量 prefetch 替代选择性召回：**-20%** 左右。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Sparse-Attention]]
- **相关系统**：[[vLLM]]、InfiniGen、OmniKV、Quest、ClusterKV
- **同会议**：[[MLSys-2026]]