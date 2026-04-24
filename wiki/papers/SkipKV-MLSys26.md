---
type: paper
name: SkipKV
full_title: "SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models"
authors: [Jiayi Tian, Seyedarmin Azizi, Yequan Zhao, Erfan Baghaei Potraghloo, Sean McPherson, "et al."]
venue: MLSys
year: 2026
tags: [kv-cache, reasoning, cot, eviction, steering, inference]
source_pdf: "[[92cc227532d17e56e07902b254dfad10.pdf]]"
source_md: "[[92cc227532d17e56e07902b254dfad10]]"
---

# SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models (MLSys 2026)

> **一句话总结**：面向 CoT 推理模型的句级 [[KV-Cache]] eviction + adaptive steering，在 R1-Qwen-14B AIME-24 上 2× KV 压缩下比 SoTA (R-KV) 高 6.7% 准确率，生成长度短 22%，吞吐最高 1.7×。

## 问题

Large Reasoning Models (LRM, 如 DeepSeek-R1 distill) 生成冗长 CoT token 导致 [[KV-Cache]] 线性爆炸（8B 模型 batch=10 时 KV 是模型权重 2.5×）。现有 eviction 方法在 LRM 上失效：
1. **多 batch 降准**：batch=1 和 batch=10 差距大，padding token 侵占预算并扰乱 attention 分布（MATH-500 R-KV、H2O 都明显掉）。
2. **生成变长**：token 级 eviction 丢失上下文，模型补偿性重新验算 → 生成长度比 FullKV 还长。
3. **Token 碎片化**：R-KV 可能留下来自最终答案的零散片段（如 "(6,9)" 留成 ",9"），触发反复 re-validation。

**观察**：错误响应比正确响应含更多高相似句对（up to 1.7×）和 non-execution thoughts（最高 2.6×）。

## 核心方法

**(1) 句级 skip KV storage**：用最后一层 hidden state 的句均值作为句 embedding（避开独立 sentence transformer 的开销），计算 Pairwise Sentence Similarity (PSS)，PSS ≥ 0.95 标记为冗余集 P。最终 eviction score 在 token importance（[[Attention]] 分数 pooling）+ token redundancy（R-KV 式 K·K^T）基础上再减去句级 similarity 分数，使整句冗余优先于 token 级冗余被 evict。配套 KV cache sentence range monitoring logic（映射函数 Φ：generation space → cache space）在每次压缩步更新句范围。

**(2) Adaptive steering skip KV generation**：用 latent-space steering vector 动态调整 hidden activation，抑制 non-execution thoughts 生成，缩短输出长度。

**(3) Batch grouping**：减少 padding token 数，挽回多 batch 下的有效 KV 预算。

## 关键结果

- DeepSeek-R1-Distill-Qwen-7B/14B、R1-Llama-8B，在 AIME-24、LiveCodeBench、MATH-500、GSM8K 上评估。
- R1-Qwen-14B AIME-24 2× KV 压缩：**+6.7% accuracy**、生成长度 **-22%** vs SoTA。
- 同 budget 下相比替代方案最多 **+26.7% accuracy**。
- 相比 SoTA：生成长度 **1.6× 少**，吞吐 **1.7× 高**。

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention]]
- **同类系统**：R-KV、H2O、SnapKV、Quest
- **同会议**：[[MLSys-2026]]
