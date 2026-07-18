---
type: concept
aliases: [Tensor-Cores, NVIDIA-Tensor-Core]
last_updated: 2026-07-18
tags: [gpu, machine-learning, kernels, mixed-precision]
---

# Tensor Core

> Tensor Cores are specialized GPU matrix-multiply units whose realized performance depends on supported precision, tile shape, data layout, sparsity constraints, and kernel scheduling.

## 核心思想

Tensor-Core-capable kernels map dense or structured matrix operations to hardware tiles. Peak FLOPS is only a capability bound: padding, irregular sparsity, memory movement, quantization, launch overhead, and non-matrix operations can prevent an end-to-end workload from approaching it.

## 为什么重要

Many ML systems papers attribute speedups to better use of Tensor Cores. The comparable unit is not nominal peak throughput but a stated model, GPU generation, precision, layout, and workload boundary; otherwise microkernel gains can be mistaken for application gains.

## 关键观察 / 隐含假设

- **观察**：sparsity and layout determine whether specialized matrix paths apply. [[GeneralSparse-ATC25]] and [[Voltrix-SpMM-ATC25]] study these mapping constraints.
- **观察**：lower precision expands throughput opportunity but introduces numerical and system constraints. [[FP8FlowMoE-MLSys26]] and [[FPRev-ATC25]] expose precision-boundary issues.
- **假设**：a kernel-level Tensor-Core metric predicts model speed. [[ParallelKittens-MLSys26]] shows that composition and scheduling remain relevant.

## 设计空间与取舍

- **Precision vs numerical robustness**：FP8/low-precision paths can improve throughput while requiring scale, accumulation, and verification choices.
- **Dense vs structured sparse mapping**：hardware support is conditional on pattern and layout.
- **Kernel efficiency vs end-to-end efficiency**：memory, communication, and non-GEMM work can dominate the full step.

## 引用本概念的论文

- [[FP8FlowMoE-MLSys26]] — FP8/MoE execution constraints.
- [[GeneralSparse-ATC25]] — sparse matrix-kernel mapping.
- [[Voltrix-SpMM-ATC25]] — SpMM hardware/software path.
- [[ParallelKittens-MLSys26]] — GPU kernel composition and scheduling.
- [[FPRev-ATC25]] — numerical behavior around precision paths.
