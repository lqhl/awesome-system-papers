---
type: paper
name: Spira
full_title: "Spira: Exploiting Voxel Data Structural Properties for Efficient Sparse Convolution in Point Cloud Networks"
authors: [Dionysios Adamopoulos, Anastasia Poulopoulou, Georgios Goumas, Christina Giannoula]
venue: MLSys
year: 2026
tags: [sparse-convolution, point-cloud, gpu, autonomous-driving, voxel]
source_pdf: "[[a87ff679a2f3e71d9181a67b7542122c.pdf]]"
source_md: "[[a87ff679a2f3e71d9181a67b7542122c]]"
---

# Spira: Exploiting Voxel Data Structural Properties for Efficient Sparse Convolution in Point Cloud Networks (MLSys 2026)

> **一句话总结**：SpC 引擎在 kernel map 构建的 pre/post-processing 上开销大且 dataflow 支持不全；Spira 利用 voxel **整数/有界/表面邻域** 三性质：one-shot z-delta search 消 preprocessing、packed-native 索引、网络级并行建图、hybrid dataflow，端到端 **1.68×** 均速（最高 **3.04×**），层级 **2.11×**（最高 **3.44×**）优于 TorchSparse++/Minuet。

## 问题与动机

点云 [[Sparse-Convolution]] 两阶段：voxel indexing（建 kernel map）+ feature computation（output/weight-stationary）。SOTA（TorchSparse++、Minuet）仍有显著 pre/post-processing 与单 dataflow 局限。

## 关键观察 / 隐含假设

- **观察 1：首层 lex 排序后，submanifold 层保持有序，downsample 层排序去重后仍有序——可 one-shot search 无需每层 rebuild query structure。**
  - **依赖假设**：标准 stride/downsample 流程；首层一次排序成本可摊销。
  - **可能失效场景**：动态 voxel 注入破坏全局排序假设时需重排。

- **观察 2：同 (x,y) 下 z 方向连续整数坐标 → 锚点 binary search + 至多 K−1 步局部线性搜索，将 |Vq|×K³ 次全二分降为 |Vq|×K² 锚点搜索。**
  - **依赖假设**：integer stride 对齐；submanifold 为主（>70% 层）。
  - **可能失效场景**：极大 K 或极稀疏场景局部搜索退化。

- **观察 3：submanifold 层 kernel map 列密度随 weight offset L1-norm 增大而降（Fig. 3b）→ hybrid dataflow 可按密度选 output/weight-stationary。**
  - **依赖假设**：邻域表面连续性在 Waymo 等数据集稳定。
  - **可能失效场景**：噪声极多点云破坏邻域性质。

## 核心方法

**One-shot z-delta search**：K² 组、每组 K 个 z 连续 offset；packed 32/64-bit 坐标。

**Network-wide indexing**：各层 kernel map 构建无依赖，启动时多 SM 并行。

**Adaptive hybrid dataflow**：按列密度在 OS/WS 间切换，减 atomic 或无效乘。

开源：https://github.com/SPIN-Research-Group/Spira

## 设计取舍

- **消 preprocessing vs 通用 query structure**：赢速度，依赖排序不变式。
- **Packed 坐标 vs 三 int**：位宽溢出需按场景选 32/64。
- **Hybrid vs 单 dataflow**：实现复杂，层间最优不同。
- **边界条件**：室内/户外 LiDAR 网络；六档 GPU 评测。

## 实验与结果

- E2E inference：**1.68×** avg，**3.04×** max vs TorchSparse++/Minuet。
- Layer-wise：**2.11×** avg，**3.44×** max。
- Fig. 2：search 7.83× vs TorchSparse++ OS；hybrid 1.98× vs TS++ 某层。

## Critical Analysis

### 论证链条

三性质→四机制→分层/端到端加速，ablation 在 Fig. 2 清晰。性质对外部数据集泛化靠多数据集验证，仍偏 3D 检测分割栈。

### 假设压力测试

首层未排序输入成本；training backward SpC 未强调；新 SpConv 算子变体需重新 pack 规则。

### 实验可信度

强 baselines（TS++、Minuet）；多 GPU。缺与 NVIDIA 闭源 kernel 对比。

### 系统性缺陷

仅 inference 侧重；multi-GPU SpC 扩展未讨论；packed 坐标范围溢出需运维注意。

## 局限与 Future Work

- **局限**：依赖 voxel 排序传播；训练路径与反向传播优化有限。
- **Future work**：与 TorchSparse 生态合并；动态点云在线重索引；auto dataflow 选择器。

## 相关

- **相关概念**：[[Sparse-Convolution]]
- **同类系统**：TorchSparse++、MinkowskiEngine
- **同会议**：[[MLSys-2026]]