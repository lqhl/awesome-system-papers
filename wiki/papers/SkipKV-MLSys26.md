---
type: paper
name: SkipKV
full_title: "SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models"
authors: [Jiayi Tian, Seyedarmin Azizi, Yequan Zhao, Erfan Baghaei Potraghloo, Sean McPherson, Sharath Nittur Sridhar, Zhengyang Wang, Zheng Zhang, Massoud Pedram, Souvik Kundu]
venue: MLSys
year: 2026
tags: [kv-cache, reasoning, cot, eviction, llm-inference]
source_pdf: "[[92cc227532d17e56e07902b254dfad10.pdf]]"
source_md: "[[92cc227532d17e56e07902b254dfad10]]"
---

# SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models (MLSys 2026)

> **一句话总结**：针对 LRM 冗长 CoT 的 [[KV-Cache]] 膨胀，提出 training-free 的 SkipKV：句子级冗余检测做 selective eviction + adaptive steering 抑制重复生成，在 2× 压缩下比 H2O/R-KV 准确率高最多 **26.7%**，生成长度少 **1.6×**、吞吐 **1.7×**。

## 问题

Large reasoning models（DeepSeek-R1 等）单题可生成 32K+ token，[[KV-Cache]] 随 CoT 线性增长，batch=10 时 KV 可达权重的 2.5×。token 级 eviction（H2O、SnapKV、R-KV）在 multi-batch 下 accuracy 骤降（padding 吃掉有效 KV budget），且碎片化 eviction 导致 overthinking、生成更长。

## 核心方法

**Sentence-level skipping**：用 last-layer hidden state 算 Pairwise Sentence Similarity（PSS），evict 高相似句子对应 KV range，保留语义连贯。

**Adaptive steering**：动态调整 steering vector 抑制 non-execution thoughts，缩短推理链。

**Batch grouping**：减少 padding token，提升 multi-batch eviction 稳定性。

## 关键结果

- DeepSeek-R1-Qwen/Llama 系列，AIME-24、MATH-500 等：6.7% 更高 accuracy、22% 更短生成（vs SoTA）
- 2× KV 压缩下 accuracy 最多 +26.7%，吞吐最高 **1.7×**，生成长度 **1.6×** 更短

## 相关

- **相关概念**：[[KV-Cache]]、[[Speculative-Decoding]]
- **同类系统**：H2O、SnapKV、R-KV、DEER
- **同会议**：[[MLSys-2026]]