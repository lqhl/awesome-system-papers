---
type: concept
aliases: [sparse attention, Sparse Attention, sparse-attention, sparsity, Attention Sparsity, attention sparsity, Block-Sparse-Attention, block sparse attention]
parent: "[[Attention]]"
last_updated: 2026-05-24
tags: [attention, long-context, efficiency, llm-inference, llm-training]
---

# Sparse-Attention

> 放弃 exact dense attention 中的 O(N²) 全对全计算，只让每个 query token 看到全序列的一个子集。子集的选择策略是这个领域的核心设计空间：按位置选（fixed pattern）、按内容选（content-dependent）、按分数选（score-aware）、或学习选（learned/trainable）。

## 核心思想

Dense attention: `softmax(QKᵀ/√d)V` 计算每对 token 之间的交互，复杂度 O(N²)。Sparse attention 的核心赌注是**大部分 token pair 之间的 attention 对最终输出几乎没有贡献**——如果能把那些无信息的 pair 识别出来并跳过，就能在几乎不损失质量的前提下大幅降计算/内存。

## 设计空间

| 维度 | 选项 | 代表工作 |
|------|------|----------|
| **稀疏模式** | 固定位置模式 (sliding/block/strided/dilated) | Longformer, BigBird, Star-Transformer |
| | 内容依赖选择 (content-dependent routing) | NSA, DSA, SSA |
| | 分数感知剪枝 (score-aware pruning) | BLASST, Twilight |
| | 端到端可微学习 | MSA (document routing), ReSSFormer |
| **稀疏粒度** | Token 级 | NSA selection branch |
| | Block 级 (连续 chunk) | BLASST (128 tokens), NSA compression branch |
| | Document 级 | MSA |
| | 层/头级自适应 | Twilight (adaptive per-layer budget) |
| **应用阶段** | 仅推理时 (post-hoc) | BLASST, Twilight, MAC-Attention, DAM |
| | 预训练原生 (natively trainable) | NSA, ReSSFormer |
| | 从 dense 微调 | SubQ SSA（推测） |

## 关键转折：稀疏可以从劣化变为正则化

NSA (ACL 2025 Best Paper) 首次在大规模实验（27B MoE, 270B tokens）上证明：**原生可训练的稀疏注意力不仅可以匹配 full attention 的质量，还可以超越**（7/9 benchmark 反超）。其解释是稀疏化过滤了噪声 token，起到正则化效果。这个发现改变了 sparse attention 的定位——从"不得已的妥协"变为"可能的设计选择"。

## 与相邻概念的关系

- **vs [[Flash-Attention]]**：FA 保留 exact dense 计算，通过 IO tiling 减少 HBM 访问。Sparse attention 改变计算本身。两者正交且可叠加（如 BLASST 在 FA kernel 上做 block skipping）
- **vs sequence parallelism**：[[db-SP-MLSys26|db-SP]] 解决 block-wise sparse attention 与 Ulysses/Ring SP 叠加时的 head/block 双级负载不均（ρ_s 最高 1.513）
- **vs [[Linear-Attention]]**：Linear attention 去掉 softmax 换 kernel function，O(N) 但 fixed-size state 限制精确检索。Sparse attention 保留 softmax 和 exact attention 的计算形式，只是限制 token 数量
- **vs [[KV-Cache-Compression]]**：压缩减少 KV cache 内存占用；sparse attention 减少计算量。两者常组合出现（如 CSA/HCA）
- **vs SSM (Mamba)**：SSM 用循环状态替代 attention，O(1) memory 但牺牲精确检索；sparse attention 保留检索能力

## 2025-2026 的核心演进

```
固定位置稀疏                     内容依赖 + 可训练
(Longformer/BigBird)                
        ↓                              
BLASST (score-aware block skip) ──→ Twilight (adaptive budget)
MAC-Attention (query reuse)            ↓
                                  NSA (硬件对齐 + 原生训练)
                                  DSA (lightning indexer)
                                  SSA/SubQ (完全 sparse, 无 dense fallback)
                                  CSA+HCA (DeepSeek-V4, sparse + compressed dense 混合)
```

## 开放问题

- 不同稀疏策略在 100B+ / 2T+ tokens 规模下的相对质量排序未知
- 完全无 dense fallback（SSA 路线）vs 保留少量 dense（HCA 路线）的优劣未有头对头对比
- Content-dependent selection 的额外开销（DSA indexer 的 O(N²)）在多大 context length 下吞噬节省的 attention FLOPs
- 稀疏注意力在 thinking/reasoning 模型长 CoT trace 上的行为未系统性研究

## 引用本概念的论文

- [[FlashAttention-NeurIPS22|FlashAttention]] — 在 exact FA 之外给出 block-sparse FlashAttention，证明 sparse attention 也需要 IO-aware kernel 才能兑现 wall-clock speedup
- [[NSA]]（外部，ACL 2025 Best Paper）— 硬件对齐 + 原生可训练，三条分支
- [[MSA-arXiv26]] — 可微 document-wise sparse routing 替代 RAG
- [[BLASST-MLSys26]] — 动态 block 级 softmax threshold sparse
- [[MTraining-MLSys26|MTraining]] — 训练期 Vertical-Slash 动态稀疏 + balanced sparse ring attention，512K 上下文 6× 吞吐
- [[SparseSpec-MLSys26]] — 自投机解码中的动态 sparse attention
- [[MAC-Attention-MLSys26]] — query 复用减少 KV 访问
- [[db-SP-MLSys26]] — block-sparse attention 序列并行
- [[OPKV-MLSys26|OPKV]] — recallable sparsity（InfiniGen/OmniKV）的系统化集成框架，非永久丢弃 KV 而是 CPU offload + 按需召回
- [[FlexiCache-MLSys26|FlexiCache]] — 按 head 稳定性分层 sparse decode，stable head 每 16 步 rerank top-K page
