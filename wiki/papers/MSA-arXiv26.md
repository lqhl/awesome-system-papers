---
type: paper
name: MSA
full_title: "MSA: Memory Sparse Attention for Efficient End-to-End Memory Model Scaling to 100M Tokens"
authors: [Yu Chen, Runkai Chen, Sheng Yi, Xinda Zhao, Xiaohong Li, et al.]
venue: arXiv
year: 2026
tags: [long-context, sparse-attention, kv-cache, llm-memory, rag, retrieval]
source_pdf: "[[arxiv26-chen-msa.pdf]]"
source_md: "[[arxiv26-chen-msa]]"
---

# MSA: Memory Sparse Attention for Efficient End-to-End Memory Model Scaling to 100M Tokens (arXiv 2026)

> **一句话总结**：把"retrieve-then-read" RAG pipeline 替换为单一可微的 sparse attention：对每个文档生成压缩的 routing key + content KV，runtime 用 cosine similarity top-k 选文档；配合 document-wise RoPE 让训练上 64K context 可外推到 100M tokens；2×A800 GPU 上跑通 100M context，长文 QA 全面超 SOTA RAG，1M token NIAH 准确率 94.84%（baseline Qwen3-4B 跌到 24.69%）。

## 问题

LLM 的「长期记忆」面临 capacity-precision 三难：
- **Parameter-based**（LoRA / continual pre-training / Titans）：兼容性好但容量瓶颈，会 catastrophic forgetting
- **External storage**（[[RAG]] / MemAgent）：能 scale 但**不可微**——retrieval 与 generation 解耦，retrieval metric 与 reasoning 目标错位
- **Latent state-based**：DSA/MemGen 等保留 KV 但算力不可扩；linear attention（RWKV/DeltaNet）虽 O(L) 但 fixed-size state 在 100M token 量级 catastrophic forgetting

实际有效 context 长度大都卡在 1M tokens，而人类终生记忆约 200-300M tokens 量级，存在两个数量级的 gap。

## 核心方法

**关键洞察**：把 retrieval 直接做成可微的 sparse attention 操作，让 "what to attend" 由 LLM 自己学，避免 retrieval 与 generation 之间的优化 gap。同时用 document-wise positional encoding 解决「train-on-short, infer-on-long」的位置外推问题。

**架构**：
- 每文档独立做 self-attention 拿 K/V/K^R（额外的 routing key projector），然后 chunk-wise mean pool 压缩
- Query 对所有文档的压缩 routing key 做 cosine similarity，取 top-k 文档
- Top-k 文档的压缩 K/V 与 query 的本地 K/V 拼接做最终 attention
- 仅在模型后半层使用 sparse routing（前半层 hidden states 还没形成检索所需的高级语义抽象）

**Document-wise RoPE**：每个文档独立从 0 起 position id；query 与生成用 global RoPE 偏移 k。让位置语义与文档总数解耦，自然外推。

**训练**：
- Continuous pre-training 158.95B tokens with 双 loss：generation loss + 对比 routing loss（auxiliary supervised contrastive）
- 两阶段 SFT：8K context（基础指令）→ 64K context（外推鲁棒性）

**Memory Parallel 推理**：
- **Tiered storage**：routing key 上 GPU VRAM（~56GB for 100M），content K/V offload 到 host DRAM；top-k 选定后异步 fetch
- **Memory-Parallel scoring**：模型权重在每 GPU 复制，routing key shard，scoring 矩阵 tile 防 OOM
- 2×A800（160GB total）跑通 100M token 推理

**Memory Interleave**：多跳推理时迭代式 generate-doc-id → fetch-doc → 添加到 query → 重新 retrieve，直到模型决定有足够证据后切到 final answer 生成

## 关键结果

- **9 个 QA benchmark**：MSA-S2 平均 3.760（0-5 scale），全面胜过 same-backbone RAG（Qwen3-4B + reranker：3.355），并在 4/9 datasets 上超过 best-of-breed RAG（KaLMv2-Embedding + Qwen3-235B 等）
- **NIAH 1M tokens**：MSA 94.84% accuracy（vs baseline Qwen3-4B 24.69%、Qwen3-Next-80B-A3B 80.78%、Qwen2.5-14B-1M 89.97%）
- **Scaling 16K → 100M tokens**：< 9% degradation
- **Ablation**：
  - Curriculum learning (8K→64K SFT) 平均 +7.6%
  - Memory interleave +5.3%（HotpotQA +19.2%）
  - 去掉 continual pre-training -31.3%（HotpotQA -43.1%）
  - 去掉 original text injection -37.1%（DuReader -46.2%）
- **复杂度**：训练 O(LG)（G 是文档长度），推理 online routing O(ML/P) + generation 与 L 无关

## 相关

- **相关概念**：[[Sparse-Attention]]、[[KV-Cache]]、[[RoPE]]、[[Long-Context]]、[[RAG]]
- **同类方法 / 对比对象**：DSA（保 KV 但不能 scale）、MemGen、RWKV / DeltaNet（linear attention，bounded state）、Titans（test-time training）、Memory³（pre-encode KV 但仍依赖 model-agnostic embedding）、MemAgent（RL-based memory management）
- **RAG baseline**：HippoRAG2、KaLMv2-Embedding、Qwen3-Embedding/Rerank
- **Backbone**：Qwen3-4B-Instruct-2507
- **数据集**：MS MARCO v1, NQ, DuReader, TriviaQA(10M), NarrativeQA, PopQA, 2WikiMultiHopQA, HotpotQA, MuSiQue + RULER NIAH
