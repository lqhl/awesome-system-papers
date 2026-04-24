---
type: paper
name: BLASST
full_title: "BLASST: Dynamic Blocked Attention Sparsity via Softmax Thresholding"
authors: [Jiayi Yuan, Cameron Shinn, Kai Xu, Jingze Cui, George Klimiashvili, "et al."]
venue: MLSys
year: 2026
tags: [sparse-attention, flash-attention, long-context, prefill, decode]
source_pdf: "[[d82c8d1619ad8176d665453cfb2e55f0.pdf]]"
source_md: "[[d82c8d1619ad8176d665453cfb2e55f0]]"
---

# BLASST: Dynamic Blocked Attention Sparsity via Softmax Thresholding (MLSys 2026)

> **一句话总结**：BLASST 利用 FlashAttention 的 online softmax 正在维护的 running max，若某 block 的 local max 比 running max 小于 ln(λ)，其 post-softmax 贡献近似为零——直接 skip exp / V 加载 / matmul，prefill 1.62× 提速（74.7% 稀疏度），decode 1.48×（73.2% 稀疏度）。

## 问题

Long-context LLM 的 attention O(n²) 仍是瓶颈，[[Flash-Attention]] 只优化了 memory bandwidth 没降复杂度。现有稀疏注意力三大痛点：
1. 非平凡 pre-computation：MInference、XAttention 需要额外 pass 算 importance，吃掉理论加速；
2. 代理分数不准：基于 accumulated attention weight 或 QK similarity 的 importance 易漏关键 token；
3. 只优化 prefill 或 decode 单阶段（如 SpargeAttn 只做 prefill）。

## 核心方法

**核心观察**：FlashAttention block-wise online softmax 本已维护 row-wise running max $m_i^{(j)}$。新 block 的 local max $\tilde m_i^{(j)}$ 若满足：
$$
\tilde m_i^{(j)} - m_i^{(j)} < \ln(\lambda)
$$
则 $\exp(\tilde m_i^{(j)} - m_i^{(j)}) < \lambda \approx 0$，该 block softmax 后必然可忽略。直接跳过三件事：(1) exp / rowsum（CUDA core 指令）、(2) $\tilde P_{ij}V_j$ matmul（tensor core MMA）、(3) 从 HBM 载入 $V_j$（内存带宽）。

三步直觉：理想是 $S_{ij}$ 相对全局 max；全局 max 在线算不了，用 running max 代理；token-level 比较太细，用 block-level 最大值。零 pre-compute、零代理分数，在 FlashAttention 基础上只加一行判断。

**自动校准**：经验发现 λ = a/L（与 context length 成反比），给定目标 sparsity 可自动求阈值。

**Sparsity-aware training**：训练时注入稀疏 pattern 让模型更鲁棒，进一步推高 accuracy-sparsity 前沿。

支持 MHA / GQA / MQA / MLA，同时覆盖 prefill 和 decode。

## 关键结果

- Prefill 1.62× 提速 @ 74.7% 稀疏度（H200 / B200）。
- Decode 1.48× 提速 @ 73.2% 稀疏度。
- 在 RULER (NIAH_MULTI, VT, FWE)、Llama 3.1 8B 上 60-70% 稀疏度内无精度下降；阈值按 λ = a/L 自动跨 8K-64K 上下文。
- 相比 SpargeAttention：(1) 同时覆盖 prefill + decode；(2) skip decision 零开销（复用 running max）；(3) decode kernel 跳过 V 加载缓解 memory-bound。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、Online Softmax、Sparse Attention、[[KV-Cache]]
- **同类系统**：MInference、XAttention、FlexPrefill、SpargeAttention、SeerAttention、StreamingLLM、H2O、Quest、InfLLM
- **新型变体**：Native Sparse Attention (NSA)、DeepSeek Sparse Attention (DSA)
- **同会议**：[[MLSys-2026]]
