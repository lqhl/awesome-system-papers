---
type: paper
name: SAND
full_title: "SAND: A New Programming Abstraction for Video-based Deep Learning"
authors: [Juncheol Ye, Seungkook Lee, Hwijoon Lim, Jihyuk Lee, Uitaek Hong, Youngjin Kwon, Dongsu Han]
venue: SOSP
year: 2025
tags: [video-dl, data-pipeline, gpu-utilization, storage-abstraction, preprocessing]
source_pdf: "[[3731569.3764847.pdf]]"
source_md: "[[3731569.3764847]]"
---

# SAND: A New Programming Abstraction for Video-based Deep Learning (SOSP 2025)

> **一句话总结**：view 抽象封装视频预处理 + 跨任务对象复用/预物化/优先级调度，SlowFast 预处理从 2200 行降到 8 行，GPU 利用率最高 **12.3×**（CPU baseline）、**2.9×**（GPU baseline）。

## 问题与动机

Video-based DL (VDL) 预处理（decode、抽帧、augment）常比 GPU 训练慢 **2.2–6.5×**，导致 GPU stall。SlowFast 预处理 **2200** 行 vs 训练 700 行。每 epoch 随机抽帧/augment 使跨 epoch 复用难，但 hyperparameter search、multi-task、DDP 下跨 trial 复用机会大。

## 关键观察 / 隐含假设

- **观察 1**：VDL 瓶颈在 CPU 预处理而非训练 kernel，且同一视频在不同 trial/epoch 的 decode 可部分复用（中间 view 物化）。
  - **依赖假设**：存储容量可容纳 hot intermediate；reuse plan 准确预测跨 trial 重叠。
  - **可能失效场景**：存储受限、每 epoch augmentation 随机性极高导致 reuse 命中率低。
  - **证据强度**：强——Fig. 2 多应用预处理/GPU 利用率测量。
- **观察 2**：开发者愿用 <10 行 view API 换系统自动 pipeline，前提是 POSIX/VFS 兼容。
  - **依赖假设**：view 语义覆盖主流 VDL 框架（PyTorch DDP、Ray HPO）。
  - **可能失效场景**：高度定制 augment 链超出 view type 表达力。
  - **证据强度**：中——SlowFast 等案例，非全覆盖。
- **假设 1**：dependency graph of view types 足以做 materialization planning，无需理解模型结构。
  - **证据强度**：中——三种应用验证，graph 构建自动化程度未细说。

## 核心方法

**View 抽象**：虚拟化预处理阶段，POSIX 兼容。

三机制：
1. **View materialization planning**（dependency graph）
2. **Pre-materialization**（跨 epoch/trial 缓存高 reuse 中间对象）
3. **Priority-based scheduling**（lagging thread boost，平衡预物化与实时喂料）

## 设计取舍

- **取舍 1**：磁盘换 CPU/GPU 时间——storage 成本与命中率 tradeoff。
- **取舍 2**：抽象简化牺牲细粒度 hand-tuned pipeline 极限性能。
- **边界条件**：压缩视频训练管线；非 video 模态需新 view type。

## 实验与结果

- GPU 利用率：**12.3×** vs CPU baseline、**2.9×** vs GPU baseline（HPO 场景）
- 训练时间：HPO 最高 **10.2×** vs CPU、**2.8×** vs GPU
- 代码：SlowFast 2200 → **8** 行
- Ray HPO、DDP、multi-task 场景均测

## Critical Analysis

### 论证链条

「预处理慢 + 代码膨胀」双 pain → view + reuse 三件套，逻辑直接。与 WebDataset、NVMe 直读等方向互补而非替代。

### 假设压力测试

- 十亿级视频库上 metadata/planning 开销？
- NVENC/NVDEC GPU decode 路径与 SAND 协同未深入。
- 跨机器 DDP 时 shared storage 一致性？

### 实验可信度

多 scenario（single/HPO/DDP）好。Baseline 是否含最新 PyTorch DataLoader2 + nvdec 需核对。缺 production 训练 cost $ 数字。

### 系统性缺陷

论文未讨论：物化缓存失效策略 disk 爆满；多 tenant 存储隔离；与 object storage (S3) 后端集成。

## 局限与 Future Work

- **局限 1**：依赖本地/共享存储容量。
- **局限 2**：view 表达力边界未形式化。
- **Future work 1**：learned reuse predictor，按 trial 相似度动态决定 pre-materialize 集合。

## 相关

- **相关概念**：data loading、GPU utilization、video decoding
- **同类系统**：SlowFast、WebDataset、Ray Data
- **同会议**：[[SOSP-2025]]