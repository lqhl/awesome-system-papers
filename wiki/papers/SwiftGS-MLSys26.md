---
type: paper
name: SwiftGS
full_title: "SwiftGS: Algorithm and System Co-Optimization for Fast 3D Gaussian Splatting on GPUs"
authors: [Lingjun Gao, Zhican Wang, Zhiwen Mo, Hongxiang Fan]
venue: MLSys
year: 2026
tags: [3d-gaussian-splatting, gpu-optimization, rendering, cuda, algorithm-system-codesign]
source_pdf: "[[f457c545a9ded88f18ecee47145a72c0.pdf]]"
source_md: "[[f457c545a9ded88f18ecee47145a72c0]]"
---

# SwiftGS: Algorithm and System Co-Optimization for Fast 3D Gaussian Splatting on GPUs (MLSys 2026)

> **一句话总结**：SwiftGS 针对 3DGS 排序与 rasterization 的细粒度冗余做算法–系统协同优化：adaptive early-sorting 降排序复杂度最高 **43.56%**，axis-shared rasterization + dynamic thresholding 减 α-compute SASS 指令 **19.79%** 并再省 **25%**，在 gsplat 上端到端加速 **1.41×**、画质几乎无损。

## 问题

3D Gaussian Splatting 推理要并行处理百万级 Gaussian，pipeline 三阶段中 **sorting + rasterization 占 >80%** 时间。现有 pruning / bounding-box 工作多在粗粒度减 Gaussian 数，未深入两阶段内部冗余：

1. **Sorting redundancy**：同一 Gaussian 深度在多个 tile 重复排序，intersection 列表可达 Gaussian 数的 **7.61×**
2. **Rasterization redundancy**：per-pixel α-compute 中约 **66.67%** SASS 指令在同列/同行线程间重复
3. **Filtered Gaussian waste**：α 低于阈值才丢弃，但此前计算已白费

## 核心方法

**Adaptive early-sorting（算法层）**：
- 先按深度 radix sort Gaussian 建 lookup table，再建 tile intersection 列表（仅 32-bit tile ID 排序）
- 复杂度从 O(64m) 降到 O(32(n+m))，平均减 **28.90%**、最高 **43.56%**
- 训练末用 20% 数据对比 early-sort vs 原排序，推理时自适应切换（缓解 lookup table 带来的 coalescing 损失）

**GPU axis-shared rasterization（系统层）**：
- 在 thread block 内用两行线程预计算 x/y 共享项（mini-batch 8 Gaussian），α-compute 复用
- **Dynamic thresholding**：把 α 拆成 pixel-independent 与 pixel-dependent，先算阈值 ln(255·o)，未过阈就跳过 3 条 SASS
- 共享项用 half precision 存 shared memory，减轻 bank conflict

基于 gsplat fork，~800 行 CUDA + 100 行 Python。

## 关键结果

- Mip-NeRF 360 七场景、RTX 3090：平均 **1.20×**（最高 **1.31×**）；L40S 平均 **1.24×**、最高 **1.41×**；PSNR 几乎不变（30k iter 仅 29.17→29.04）
- 室内场景 intersection/Gaussian 比更高，加速优于室外（1.25× vs 1.12×）
- Ablation：axis-shared rasterization 室内 +20%、室外 +14%；dynamic thresholding 再 +6–7%；early-sorting 在 L40S 室内 sorting 最高 **−46.94%**
- 与 PUP-GS 正交：vanilla 3DGS **1.48×**；PUP-GS 上再 **1.43×**（31.02ms→20.66ms，13.42ms→9.28ms）

## 相关

- **相关概念**：3D Gaussian Splatting、GPU Kernel Fusion、Radix Sort
- **同类系统**：gsplat、FlashGS、PUP-GS、LightGaussian、MetaSapiens
- **同会议**：[[MLSys-2026]]