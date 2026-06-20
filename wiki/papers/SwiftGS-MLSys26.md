---
type: paper
name: SwiftGS
full_title: "SWIFTGS: ALGORITHM AND SYSTEM CO-OPTIMIZATION FOR FAST 3D GAUSSIAN SPLATTING ON GPUS"
authors: [Lingjun Gao, Zhican Wang, Zhiwen Mo, Hongxiang Fan]
venue: MLSys
year: 2026
tags: [3d-gaussian-splatting, gpu, rendering, co-design]
source_pdf: "[[f457c545a9ded88f18ecee47145a72c0.pdf]]"
source_md: "[[f457c545a9ded88f18ecee47145a72c0]]"
---

# SWIFTGS: ALGORITHM AND SYSTEM CO-OPTIMIZATION FOR FAST 3D GAUSSIAN SPLATTING ON GPUS (MLSys 2026)

> **一句话总结**：[[3DGS]] 排序+光栅化占主导时间，存在 tile 重复排序（交集列表可达 Gaussian 数 **7.61×**）与 per-pixel **66.67%** 冗余 SASS；SwiftGS 用 adaptive early sorting（复杂度 **-28.9%** max **43.56%**）+ axis-shared rasterization（α 阶段 **-19.79%** SASS）+ dynamic thresholding（过滤浪费 **-25%**），相对 gsplat **1.41×** 加速且画质近无损。

## 问题与动机

[[3D-Gaussian-Splatting]] 百万级 Gaussian 并行，排序与 rasterization 是瓶颈。既有 pruning 减数量，少优化管线内冗余。论文 profiling 揭示三类浪费：跨 tile 重复深度排序、同列/同行线程重复 α 指令、被 threshold 滤掉 Gaussian 的前置无效计算。

## 关键观察 / 隐含假设

- **观察 1：每 Gaussian 多 tile 相交导致交集列表长度可达 Gaussian 计数 **7.61×**。**
  - **依赖假设**：early sort（先深度序+lookup）再建 tile 列表可减复杂度；adaptive 在 coalescing 差时回退原排序。
  - **可能失效场景**：场景 tile 覆盖极均匀时 early sort 收益小。

- **观察 2：per-pixel rasterization 中 α-compute **66.67%** SASS 指令在同列/行重复。**
  - **依赖假设**：axis-shared shared-term 阶段可安全复用中间量。
  - **可能失效场景**：不同 GPU 架构 shared memory 压力变。

- **观察 3：被 **α<1/255** 滤掉的 Gaussian 仍做过 pixel-independent 计算；dynamic thresholding 将独立部分前移可再省 **25%** 相关 SASS。**
  - **依赖假设**：分解 pixel-independent/dependent 保持正确性。
  - **可能失效场景**：极低阈值场景前移收益有限。

- **假设 1**：算法+系统协同与多数现有 3DGS 加速正交可叠加。**
  - **证据强度**：**中**——claim 正交但未与所有 SOTA 联合测。

## 核心方法

**Adaptive early sorting**：两阶段深度+tile 交集；运行时选 early vs legacy。

**GPU axis-shared rasterization**：shared-term 复用降 α-compute 指令。

**Dynamic thresholding**：过滤前完成可共享计算，避免 waste。

## 设计取舍

- **Early sort 自适应 vs 总是 early**：避免 coalescing 退化拖慢。
- **Shared raster vs 简单 per-pixel**：增 shared memory 协调，换算力。
- **1.41× vs 极致画质**：评测称 negligible quality drop。
- **边界条件**：相对 gsplat baseline；机器人/数字孪生场景动机。

## 实验与结果

- End-to-end：**1.41×** speedup vs gsplat，画质近无损。
- Sorting complexity：平均 **-28.90%**，最大 **-43.56%**。
- α-compute SASS：**-19.79%**；filtered Gaussian 路径额外 **-25%**。

## Critical Analysis

### 论证链条

Profiling 驱动三类冗余 → 针对性算法/内核优化 → 1.41×，co-design 范例。自适应切换增加分支，极端场景需更多 ablation。

### 假设压力测试

更大场景 million+ Gaussian 时 sort 仍可能主导；与 neural pruning 联合时 Gaussian 数变影响各优化占比。

### 实验可信度

相对 gsplat 公平；质量 negligible 需读者查 PSNR/SSIM 表。缺：多 GPU、实时 SLAM 闭环延迟。

### 系统性缺陷

论文未讨论移动端功耗、不同 tile size 迁移调参。

## 局限与 Future Work

- **局限 1**：收益随场景几何变化大。
- **局限 2**：绑定 CUDA 实现细节。
- **Future work 1**：与 pruning/level-of-detail 正交叠加 benchmark。
- **Future work 2**：auto 选择 early sort 的 online profiler。

## 相关

- **相关概念**：[[3D-Gaussian-Splatting]]、[[NeRF]]、[[GPU-Kernels]]
- **同类系统**：gsplat
- **同会议**：[[MLSys-2026]]