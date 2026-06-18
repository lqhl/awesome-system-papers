---
type: paper
name: CDLM
full_title: "CDLM: Consistency Diffusion Language Models for Faster Sampling"
authors: [Minseo Kim, Chenfeng Xu, Coleman Hooper, Harman Singh, Ben Athiwaratkun, Ce Zhang, Kurt Keutzer, Amir Gholami]
venue: MLSys
year: 2026
tags: [diffusion-lm, consistency-model, kv-cache, inference]
source_pdf: "[[7cbbc409ec990f19c78c75bd1e06f215.pdf]]"
source_md: "[[7cbbc409ec990f19c78c75bd1e06f215]]"
---

# CDLM: Consistency Diffusion Language Models for Faster Sampling (MLSys 2026)

> **一句话总结**：对 bidirectional DLM teacher 蒸馏出 block-causal student，consistency+distillation+DLM 三目标联合训练，Dream/LLaDA 上 refinement steps 降 3.4–7.9×、latency 降 3.6–14.5×，并支持 block [[KV-Cache|KV cache]]。

## 问题

开源 DLM 双向 attention 无法标准 KV cache，且 denoising steps ≈ 序列长度，推理远慢于 AR。

## 核心方法

**Block-causal mask**（B=32）：prompt+已完成 block 可见，块内 parallel unmask。

**三损失**：teacher logits 蒸馏（多 token finalize）、y 与 block-completion y* 的 consistency KL、masked DLM loss。

**推理**：confidence threshold 并行 reveal；块边界 early stop。

## 关键结果

- CDLM–Dream：steps **4.1–7.7×**↓，latency 最高 **14.5×**（MBPP），GSM8K-CoT **11.2×**
- CDLM–LLaDA：GSM8K 28.3s→**3.3s**；吞吐比 naive DLM **3–21×**，部分超同尺寸 AR **1.1–4.2×**
- 训练：Dream 8h、LLaDA 16h（4×A100）

## 相关

- **相关概念**：[[KV-Cache]]、[[Continuous-Batching]]
- **同类系统**：Fast-dLLM、dLLM-Cache、D2F
- **同会议**：[[MLSys-2026]]