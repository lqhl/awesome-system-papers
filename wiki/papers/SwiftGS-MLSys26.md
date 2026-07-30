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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SwiftGS：GPU 上快速 3D 高斯分布的算法和系统协同优化（MLSys 2026）

> **原题**：SWIFTGS: ALGORITHM AND SYSTEM CO-OPTIMIZATION FOR FAST 3D GAUSSIAN SPLATTING ON GPUS

> **一句话总结**：SwiftGS 重组 3DGS sorting/rasterization。MipNeRF360 的 7 个场景中，RTX 3090 平均 **1.20×**、L40S 平均 **1.24×**，最高 **1.41×**；30k checkpoint PSNR 从 **29.17** 到 **29.04**，不是绝对无损。

## 问题与动机

[[3D-Gaussian-Splatting]] 百万级 Gaussian 并行，排序与 rasterization 是瓶颈。既有 pruning 减数量，少优化管线内冗余。论文 profiling 揭示三类浪费：跨 tile 重复深度排序、同列/同行线程重复 α 指令、被 threshold 滤掉 Gaussian 的前置无效计算。

## 关键观察 / 隐含假设

- **观察 1：每 Gaussian 多 tile 相交导致交集列表长度可达 Gaussian 计数 7.61×。**
  - **依赖假设**：early sort（先深度序+lookup）再建 tile 列表可减复杂度；adaptive 在 coalescing 差时回退原排序。
  - **可能失效场景**：场景 tile 覆盖极均匀时 early sort 收益小。

- **观察 2：per-pixel rasterization 中 α-compute 66.67% SASS 指令在同列/行重复。**
  - **依赖假设**：axis-shared shared-term 阶段可安全复用中间量。
  - **可能失效场景**：不同 GPU 架构 shared memory 压力变。

- **观察 3：被 α<1/255 滤掉的 Gaussian 仍做过 pixel-independent 计算；dynamic thresholding 将独立部分前移可再省 25% 相关 SASS。**
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

**指标、基线与边界**：rendering latency、PSNR accuracy、sorting/raster instructions；SwiftGS vs gsplat；MipNeRF360 7-scene workload、7k/30k checkpoints、RTX3090/L40S（§7）。

- RTX 3090 平均 **1.20×**（1.11–1.31×），L40S 平均 **1.24×**、最高 **1.41×**（§7.1–7.2，Table 1）。
- 30k checkpoint PSNR **29.17→29.04**，7k 不变（§7.2，Table 1）。
- axis-shared rasterization 总 SASS instructions 减 **19.79%**；dynamic thresholding 对 skipped Gaussians 的 α-compute 额外减 **25%**（§5.3）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| E2E rendering 加速限于被测 GPU/场景 | RTX3090 1.20×、L40S 1.24×/最高1.41× | vs gsplat、7 MipNeRF360 scenes、7k/30k | §7.1–7.2，Table 1 | high |
| quality 有小而非零的代价 | PSNR 29.17→29.04；7k unchanged | vanilla gsplat、评测 checkpoints | §7.2，Table 1 | high |
| raster 优化指标不是端到端百分比 | SASS -19.79%；skipped α-compute -25% | original gsplat raster kernel；25%仅 skipped Gaussians | §5.3 | high |
| early sorting 可退化，adaptive 防回退 | RTX3090 outdoor +28.39%，L40S indoor -46.94% | plain early vs adaptive sorting、Fig.9 scenes/GPUs | §7.3.2，Fig.9 | high |
| 组合实验只覆盖 PUP-GS | 31.02→20.66ms；13.42→9.28ms | vanilla/PUP-GS 各自 baseline；PUP-GS pruning约90% | §7.4，Table 4 | high |

## 批判性分析

### 论证链条

Profiling 驱动三类冗余 → 针对性算法/内核优化 → 1.41×，co-design 范例。自适应切换增加分支，极端场景需更多 ablation。

### 假设压力测试

更大场景 million+ Gaussian 时 sort 仍可能主导；与 neural pruning 联合时 Gaussian 数变影响各优化占比。

### 实验可信度

相对 gsplat 公平；质量 negligible 需读者查 PSNR/SSIM 表。缺：多 GPU、实时 SLAM 闭环延迟。

### 系统性缺陷

论文未讨论移动端功耗、不同 tile size 迁移调参。

## 局限与后续工作

- **局限 1**：收益随场景几何变化大。
- **局限 2**：绑定 CUDA 实现细节。
- **Future work 1**：与 pruning/level-of-detail 正交叠加 benchmark。
- **Future work 2**：auto 选择 early sort 的 online profiler。

## 相关

- **相关概念**：[[3D-Gaussian-Splatting]]、[[NeRF]]、[[GPU-Kernels]]
- **同类系统**：gsplat
- **同会议**：[[MLSys-2026]]
