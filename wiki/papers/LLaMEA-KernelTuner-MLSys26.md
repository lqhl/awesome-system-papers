---
type: paper
name: LLaMEA-KernelTuner
full_title: "Automated Algorithm Design for Auto-Tuning Optimizers"
authors: [Floris-Jan Willemsen, Niki van Stein, Ben van Werkhoven]
venue: MLSys
year: 2026
tags: [auto-tuning, llm, kernel-tuning, hpc, meta-optimization]
source_pdf: "[[a1d0c6e83f027327d8461063f4ac58a6.pdf]]"
source_md: "[[a1d0c6e83f027327d8461063f4ac58a6]]"
---

# Automated Algorithm Design for Auto-Tuning Optimizers (MLSys 2026)

> **一句话总结**：LLaMEA + Kernel Tuner 闭环：LLM 进化生成 auto-tuning 优化算法，用 BAT benchmark performance score 评估；最佳生成算法比 OpenTuner/Kernel Tuner 内置 SOTA 平均 **+72.4%** performance score，加入 search-space 信息再 +30.7%。

## 问题

Auto-tuning search space 大、噪声、非凸，经典 SA/GA/PSO 需仔细调 hyperparameter 且非为 tuning 场景设计。为每个 kernel/architecture 手工设计 optimizer 不可扩展。

## 核心方法

**Closed-loop evolution**：LLaMEA（4 parent + 12 offspring/generation）用 LLM mutation 生成 Kernel Tuner `OptAlg` 子类代码 → BAT benchmark 上算 aggregate performance score P → 选优繁殖。

可选 prompt 注入 application/search-space 特征；错误 stacktrace 反馈给 LLM self-debug。

## 关键结果

- vs OpenTuner + Kernel Tuner SOTA：最佳生成算法 avg performance score **+72.4%**
- 额外 application info **+30.7%**、search-space info **+14.6%**
- dedispersion/convolution/hotspot/GEMM × 6 GPU（24 search spaces）验证

## 相关

- **相关概念**：[[Flash-Attention]]（tuning target 示例）
- **同类系统**：OpenTuner、CLTune、LLaMEA、FunSearch
- **同会议**：[[MLSys-2026]]