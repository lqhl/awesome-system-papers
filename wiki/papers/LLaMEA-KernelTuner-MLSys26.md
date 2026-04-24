---
type: paper
name: LLaMEA-KernelTuner
full_title: "Automated Algorithm Design for Auto-Tuning Optimizers"
authors: [Floris-Jan Willemsen, Niki van Stein, Ben van Werkhoven]
venue: MLSys
year: 2026
tags: [auto-tuning, llm-code-generation, evolutionary-algorithm, gpu-kernels, meta-optimization]
source_pdf: "[[a3f390d88e4c41f2747bfa2f1b5f87db.pdf]]"
source_md: "[[a3f390d88e4c41f2747bfa2f1b5f87db]]"
---

# Automated Algorithm Design for Auto-Tuning Optimizers (MLSys 2026)

> **一句话总结**：用 LLM + 进化算法（LLaMEA）自动生成针对 auto-tuning 问题的优化算法，集成进 Kernel Tuner，生成的优化器平均比 SOTA 人工设计 baseline 高 72.4%。

## 问题

HPC kernel auto-tuning 的搜索空间通常大、不规则、noisy，经典 metaheuristic（SA、GA、PSO）并非为 auto-tuning 场景设计，需要细致的超参 tuning 才能跨问题鲁棒。问题：能否让 LLM 自动合成针对特定 auto-tuning 搜索空间的优化算法？

## 核心方法

把 LLaMEA（LLM Evolutionary Algorithm）与 Kernel Tuner 集成：

- **Closed-loop evolution**：LLM 生成一批候选优化算法代码 → Kernel Tuner 按 performance score P 评估 → 高分者被选为 parent → LLM 用 mutation prompt（探索/利用两种风格）生成子代。参数：4 parent + 12 offspring/iteration，elitism。
- **Prompt 注入**：可选加入 tuning problem 描述（可调参数、允许值、约束）和 search space 特征（Cartesian size、constrained size、dimensions），让 LLM 生成 problem-specific 优化器。
- **Performance score P**：基于先前工作的 autotuning 方法论，P_t = (S_baseline(t) - F_t) / (S_baseline(t) - S_opt)，归一化到 [0,1]，aggregate 跨多个 kernel/hardware/input 的曲线。
- **Robust to错误代码**：生成的坏算法会被 EA selection 淘汰，stacktrace 作为 context 反馈给 LLM 实现 self-debug，不污染 kernel 执行路径。

评估用 BAT benchmark（dedispersion、2D convolution、hotspot、GEMM）x 6 GPU 架构。

## 关键结果

- 加入 application-specific 信息生成的算法平均提升 30.7%；加 search-space 信息提升 14.6%。
- 最优生成算法相对 SOTA baseline 平均 72.4% 的性能提升。
- 最佳算法已 merge 进 Kernel Tuner 供社区使用。

## 相关

- **相关概念**：[[Evolutionary-Search]]、[[LLM-for-Code]]
- **同类系统**：FunSearch、EoH、ReEvo
- **同会议**：[[MLSys-2026]]
