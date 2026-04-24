---
type: paper
name: CDLM
full_title: "CDLM: Consistency Diffusion Language Models for Faster Sampling"
authors: [Minseo Kim, Chenfeng Xu, Coleman Hooper, Harman Singh, Ben Athiwaratkun, "et al."]
venue: MLSys
year: 2026
tags: [diffusion-language-model, distillation, consistency-model, kv-cache, fine-tuning]
source_pdf: "[[7cbbc409ec990f19c78c75bd1e06f215.pdf]]"
source_md: "[[7cbbc409ec990f19c78c75bd1e06f215]]"
---

# CDLM: Consistency Diffusion Language Models for Faster Sampling (MLSys 2026)

> **一句话总结**：通过 block-wise causal mask fine-tuning + consistency-guided 蒸馏，把 bidirectional Diffusion LM 蒸成 block-causal student，同时解决 KV cache 不兼容和 denoising 步数过多两个瓶颈；在 Dream-7B 和 LLaDA-8B 上实现 3.6-14.5× 端到端 latency 降低，准确率与 baseline 持平。

## 问题

Diffusion Language Model（DLM）以 parallel generation 作为对 AR LLM 的替代，但开源 DLM 比 AR 还慢，两个根因：

1. **Bidirectional attention 不兼容 KV caching**：每步 denoising 都重算所有位置的 attention
2. **Denoising 步数多**：高保真度需要与 sequence length 相当的 refinement 步数

现有加速方法分两派：training-free（approximate caching、confidence-threshold 并行采样）和 training-based（fine-tune 成 block-wise causal 架构）。前者精度下降，后者只解决了 caching 没解决 step 数。

## 核心方法

CDLM 用 fine-tuning 同时拿下两个瓶颈：

**1. Block-wise causal attention mask**（缓解 KV cache）：
- Teacher：原 DLM，full bidirectional attention
- Student：block-wise causal mask——attend 到 prompt + 已完成的 block + 当前 decoding block，与 AR 类似可做 block-level KV cache 和 early stopping
- Block size B=32，generation length $L_g = 256$

**2. Consistency-guided distillation**（减少步数）：
从 teacher 用 low-confidence remasking 策略（每步 finalize 一个 top-confidence token）离线跑 trajectory $\mathcal{T}_x$ 和 hidden state buffer $\mathbf{H}_x$，学生 fine-tune 三个 loss 组合：

- **Distillation loss**：在 state $y$ 的 newly unmasked 位置（$\mathcal{U}_y$）用 student 预测对齐 teacher logits（通过 lm_head 从 stored hidden 重建），forward KL。给 student multi-token finalization 的主 anchor
- **Consistency loss**：在同一 block 内比较 student 在 state $y$ 和 block-completion state $y^\star$ 上的预测，仅对 still-masked 位置 $\mathcal{S}_y$ 施加 KL；$q_{\phi^-}$ 是 stop-gradient target（consistency model 风格）。鼓励 student 在 trajectory 上做稳定的多步跳跃
- **DLM loss**：保留标准 masked denoising 目标防止能力退化

**3. 推理**：
- block-wise decoding + block-causal mask + prompt 和已完成 block 的 KV cache
- 块内 confidence-threshold 并行 finalize（$\tau_{conf}=0.9$，参考 Fast-dLLM）
- block 内产生 `<endoftext>` 就 early stop
- 不用 inter-block parallelism 等引入 hyperparameter 的 trick

**训练成本**：Dream-7B 约 8h、LLaDA-8B 约 16h，4× A100 80GB，LoRA attach 到 attention 和 MLP。

## 关键结果

跨 GSM8K / MATH / HumanEval / MBPP 评估，B=32、$L_g=256$、greedy、$\tau_{conf}=0.9$：

**CDLM-Dream**：
- GSM8K-CoT：latency **11.2×** lower（2.1s vs 23.5s），TPS 12.6×，steps 5.8×，score 78.8 vs 79.1
- HumanEval-Instruct：latency 6.1×，steps 5.2×，score **50.0 vs 48.2**
- MBPP-Instruct：latency **14.5×**，TPS 20.9×，score 53.0 vs 51.8

**CDLM-LLaDA**：
- GSM8K：latency 8.6× (3.3s vs 28.3s)，score 73.9 vs 77.1
- HumanEval：latency 5.9×，steps **7.9×**，score **40.2 vs 37.8**

综合：refinement steps 减少 3.4-7.9×，latency 降低 3.6-14.5×，且 TPS 超过同等大小的 AR 模型（Qwen2.5-7B、Llama-3.1-8B）。

## 相关

- **相关概念**：[[Diffusion-Language-Model]]、[[KV-Cache]]、Consistency-Model、[[LoRA]]、Distillation、Block-Causal-Attention
- **同类系统**：Dream-7B、LLaDA-8B、Fast-dLLM、dLLM-Cache、D2F
- **同会议**：[[MLSys-2026]]
