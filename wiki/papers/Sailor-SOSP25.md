---
type: paper
name: Sailor
full_title: "Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters"
authors: [Foteini Strati, Zhendong Zhang, George Manos, Ixeia Sánchez Périz, Qinghao Hu, et al.]
venue: SOSP
year: 2025
tags: [distributed-training, heterogeneous-gpus, geo-distributed, parallelization-planning, elasticity]
source_pdf: "[[3731569.3764839.pdf]]"
source_md: "[[3731569.3764839]]"
---

# Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters (SOSP 2025)

> **一句话总结**:面向异构/跨 zone/动态可用资源的端到端分布式训练系统,通过剪枝启发式 + 动态规划使 128 GPU 规划 < 1 秒,比异构 baseline 吞吐高 1.1-2.87×、跨 zone 场景比 DTFM cost-efficient 9.8×、给定吞吐约束下比次优 baseline 省 40% 成本。

## 问题

高端 GPU 稀缺,同一 zone 内往往凑不齐大规模同构 A100/H100 集群。把训练扩展到跨代 GPU (A100 + V100) 或跨 zone 能拿到更多算力,但现有框架假设同构、同带宽,一旦资源异构/跨地就水土不服。三大挑战:

1. **搜索空间爆炸**:需要联合优化资源分配 + 并行化计划 (DP/PP/TP 度),还要考虑跨 zone/跨 region 数据传输费用。Metis 处理 16 GPU 需数小时,Cephalo 64 GPU 需 300 秒,Atlas/DTFM 不处理异构 GPU 类型。
2. **仿真不准**:Varuna 忽略 optimizer/通信内存,估计误差 25-95%,常推荐 OOM 配置;FlashFlex runtime 估计也不准。
3. **框架不支持异构**:Megatron/[[DeepSpeed]] 假设每 stage 并行度一致,无法在异构 GPU 之间做 per-stage 异构 TP 度和异构 microbatch size;响应资源变化的重配置也慢。

## 核心方法

Sailor 由 profiler + planner + simulator + 训练框架四部分组成:

1. **Profiler**:PyTorch hooks + CUDA Events 在单节点上对模型按 layer 测 forward/backward/update,用 NCCL 测任意两种机器类型之间的带宽-消息大小曲线,拟合多项式。
2. **Planner(核心贡献)**:通过 6 条启发式剪枝(H1: [[Tensor-Parallelism]] 限制在节点内;H2: 按内存提前剔除 OOM 配置;H3/H4: 依据目标单调搜索 DP 度;H5: DP 通信限制在单 region 内;H6: 同 region 内合并多个 zone)+ 动态规划(按 stage 分解优化问题,重用子问题结果)。128 A100 规划时间 < 1 秒,远快于 Metis(小时级)、Aceso(200 秒)等。
3. **Simulator**:精确建模异构 stragglers、per-stage 内存 footprint(包括 optimizer state、activation、通信、碎片),解决 baseline 25-95% 误差。
4. **训练框架**:基于 Megatron-DeepSpeed 扩展,支持异构 per-stage TP 度、异构 microbatch size、以及动态资源变化下的快速重配置(弹性)。

核心发现:最优配置经常需要"同一 pipeline 内不同 stage 用不同 TP 度",以平衡不同 GPU 的算力/内存——这是现有框架的盲点。

## 关键结果

- **搜索时间**:128 A100 集群 < **1 秒**,对比 Metis(小时)、Aceso(200s)、DTFM(125s)
- **异构吞吐**:比 Metis/FlashFlex/AMP 高 **1.1-2.87×**
- **跨 zone/region**:比 DTFM 吞吐高 **5.9×**、cost 低 **9.8×**
- **成本约束下**:给定吞吐要求,比次优 baseline 省 **40%** monetary cost
- 内存估计误差降到远低于 Varuna/Atropos 等
- 是首个同时支持异构并行计划 + 弹性的开源训练框架

## 相关

- **相关概念**:[[Data-Parallelism]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Elasticity]]、[[Dynamic-Programming]]、[[Heterogeneous-GPU]]、[[Spot-Instance]]
- **同类系统**:[[Megatron-LM]]、[[DeepSpeed]]、Piper、AMP、Varuna、Oobleck、Metis、FlashFlex、Galvatron、Aceso、DTFM、Atlas、Cephalo
- **同会议**:[[SOSP-2025]]
