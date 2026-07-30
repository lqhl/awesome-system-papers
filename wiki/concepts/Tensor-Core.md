---
type: concept
aliases: [Tensor-Cores, NVIDIA-Tensor-Core]
last_updated: 2026-07-18
tags: [gpu, machine-learning, kernels, mixed-precision]
---

# Tensor Core

> 张量核心是专门的 GPU 矩阵乘法单元，其实现的性能取决于支持的精度、图块形状、数据布局、稀疏性约束和内核调度。

## 核心思想

支持 Tensor-Core 的内核将密集或结构化矩阵运算映射到硬件块。峰值 FLOPS 只是一个能力限制：填充、不规则稀疏性、内存移动、量化、启动开销和非矩阵操作可能会阻止端到端工作负载接近它。

## 为什么重要

许多机器学习系统论文将加速归因于更好地使用 Tensor Core。可比较的单位不是标称峰值吞吐量，而是规定的模型、GPU 生成、精度、布局和工作负载边界；否则，微内核增益可能会被误认为是应用程序增益。

## 关键观察 / 隐含假设

- **观察**：稀疏性和布局决定是否应用专门的矩阵路径。 [[GeneralSparse-ATC25]] 和 [[Voltrix-SpMM-ATC25]] 研究这些映射约束。
- **观察**：较低的精度扩大了吞吐量机会，但引入了数值和系统限制。 [[FP8FlowMoE-MLSys26]] 和 [[FPRev-ATC25]] 暴露了精度边界问题。
- **假设**：内核级 Tensor-Core 指标预测模型速度。 [[ParallelKittens-MLSys26]] 表明组成和调度仍然相关。

## 设计空间与取舍

- **精度与数值鲁棒性**：FP8/低精度路径可以提高吞吐量，同时需要规模、累积和验证选择。
- **密集映射与结构化稀疏映射**：硬件支持取决于模式和布局。
- **内核效率 vs 端到端效率**：内存、通信和非 GEMM 工作可以主导整个步骤。

## 引用本概念的论文

- [[FP8FlowMoE-MLSys26]] — FP8/MoE execution constraints.
- [[GeneralSparse-ATC25]] — sparse matrix-kernel mapping.
- [[Voltrix-SpMM-ATC25]] — SpMM hardware/software path.
- [[ParallelKittens-MLSys26]] — GPU kernel composition and scheduling.
- [[FPRev-ATC25]] — numerical behavior around precision paths.
