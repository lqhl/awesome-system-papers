---
type: paper
name: SparseSpec
full_title: "Accelerating Large-Scale Reasoning Model Inference: Self-Speculative Decoding with Sparse Attention"
authors: [Yilong Zhao, Jiaming Tang, Kan Zhu, Zihao Ye, Chi-Chih Chang, "et al."]
venue: MLSys
year: 2026
tags: [reasoning-models, speculative-decoding, sparse-attention, kv-cache, inference]
source_pdf: "[[6f4922f45568161a8cdf4ad2299f6d23.pdf]]"
source_md: "[[6f4922f45568161a8cdf4ad2299f6d23]]"
---

# Accelerating Large-Scale Reasoning Model Inference: Self-Speculative Decoding with Sparse Attention (MLSys 2026)

> **一句话总结**：同一模型 self-speculate，draft 用 PillarAttn 从 verify 的 attention score 白嫖 top-K 稀疏模式，配合 unified scheduler、delayed verification、动态 KV offload，Qwen3 RLM 上比 [[vLLM]] 最多 2.13×，比 MagicDec/N-Gram/TriForce 最高 1.76×。

## 问题

Reasoning LLM 长 CoT 使 attention memory-bound；[[KV-Cache|KV]] 加载占 Qwen3-8B+H100+batch128+8K 输出约 70% 延迟。现有 [[Speculative-Decoding]] 需额外 draft 模型或 acceptance 不适应 RLM context dynamics。

## 核心方法

**PillarAttn**：每 k 步 verify 时 dump attention score，Top-K 定下一 k 步 draft 稀疏模式，零额外存储。

**Unified batch scheduler**：draft/verify 混批，均衡 GEMM 负载；fused sparse+full attention persistent kernel。

**Delayed verification**：verify 请求延后一迭代，CPU metadata 与 GPU 重叠。

**Dynamic KV-Cache manager**：激进提高并发，OOM 时 chunk-wise 异步 offload 到 host。

## 关键结果

- vs [[vLLM]]：最高 **2.13×** throughput（AIME/OlympiadBench/LiveCodeBench）
- vs vLLM-NGram / MagicDec / TriForce：最高 1.56× / 1.36× / 1.76×
- Qwen3-14B AIME 平均输出 13542 tokens（非推理 Qwen2.5-32B 的 7×）
- 稀疏 5% 时 attention 延迟理论降 6.78×（k=16, α=0.75）

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[PagedAttention]]、[[Sparse-Attention]]
- **同类系统**：[[vLLM]]、MagicDec、TriForce
- **同会议**：[[MLSys-2026]]