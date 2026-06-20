---
type: paper
name: MoE-Serving-Tax
full_title: "DEMYSTIFYING THE MIXTURE OF EXPERTS SERVING TAX"
authors: [Pratyush Patel, Dayeol Lee, Shintaro Iwasaki, Arvind Krishnamurthy]
venue: MLSys
year: 2026
tags: [moe, llm-serving, performance-modeling, disaggregation]
source_pdf: "[[fbd7939d674997cdb4692d34de8633c4.pdf]]"
source_md: "[[fbd7939d674997cdb4692d34de8633c4]]"
---

# DEMYSTIFYING THE MIXTURE OF EXPERTS SERVING TAX (MLSys 2026)

> **一句话总结**：同 per-token FLOP 的 [[MoE]] 相对 DenseFA 实际慢 **2–3×**（云定价甚至 **2.5–10×**）；tax 在 prefill（padding/straggler/细粒度 expert）与 decode（weight amplification）形态相反，且 decode 上 routing skew 反而可能降激活 expert 数而**加速**——论文用 balls-bins-buckets 框架分解并指导优化。

## 问题与动机

[[MoE]] 承诺「大模型质量、小模型算力」，但条件计算带来 padding、AllToAll、权重放大、路由不平衡等 **MoE tax** τ=Latency_MoE/Latency_DenseFA。服务商需可解释框架量化 tax 并选型 TP/EP/DP。

## 关键观察 / 隐含假设

- **观察 1：相对 FLOP 对齐稠密模型 DenseFA，MoE tax **2–3×** 常见；DeepSeek decode peak **~3×** @ bs128。**
  - **依赖假设**：DenseFA 构造公平（top-K 放大 FFN intermediate）。
  - **可能失效场景**：极小 batch 单请求 decode tax 可低至 **~1.05×**（Mixtral）。

- **观察 2：prefill tax 随 batch 增大而降（Mixtral min **1.28×** @1024，Qwen @2048）；细粒度 expert（DeepSeek）small batch 近 DensePA。**
  - **依赖假设**：padding/straggler 在大批次摊销。
  - **可能失效场景**：极端 routing skew 仍伤 prefill EP。

- **观察 3：decode 由 **weight amplification** 主导，MoE 接近总参数量级 DensePA；但 skew routing 可减少激活 expert，**反直觉**可能更快。**
  - **依赖假设**：节省的内存带宽 > imbalance 代价。
  - **可能失效场景**：EP AllToAll 在大模型（DeepSeek）仍抬高 tax。

- **假设 1**：microbenchmark + E2E 可分解 tax 为可分析组件（Table 1 baseline vs token distribution effects）。**
  - **证据强度**：**强**——Mixtral/Qwen/DeepSeek 三架构 × TP/EP × 数据集。

## 核心方法

**τ 定义**：MoE step latency / DenseFA 同资源同 batch。

**Tax sources**：per-expert GEMM 强度低、AllToAll、padding、straggler、weight amplification。

**Balls-bins-buckets**：分析 fine-grained experts、DP attention、token 分布效应。

**Guidelines**：contextualize 已有优化（kernel、disaggregation）与新方向。

## 设计取舍

- **表征论文 vs 新系统**：不交付 serving stack，交付测量与模型。
- **DenseFA vs DensePA 双基线**：FA 表理想稀疏，PA 表内存下界。
- **vLLM+DeepEP/DeepGEMM**：反映 SOTA 实现但绑定特定栈。
- **边界条件**：A100 8卡 Mixtral/Qwen；B200 8卡 DeepSeek-V3。

## 实验与结果

- Prefill：tax 随 bs 变化；DeepSeek min **1.7×** @1024。
- Decode：bs32 Mixtral **2.08×**、Qwen **2.57×**；bell-shaped vs batch。
- Microbenchmarks 分类 padding/straggler/weight amplification。
- 云价 Fig.1：MoE 推理定价 **2.5–10×** Dense 同激活参数。

## Critical Analysis

### 论证链条

FLOP 等价误导 → 分 phase/arch/parallel 测 tax → 反直觉 skew 洞察 → 优化指南，极具运维价值。τ 相对指标跨硬件需重标定。

### 假设压力测试

[[PD-Disaggregation]] 改变 phase 占比；与 [[BOUTE]] 异构 GPU 定价联动未做。EP+DP attention 新发展需更新 buckets。

### 实验可信度

三模型覆盖粗/细 expert；HumanEval 等 routing 数据集。缺：与 [[MorphServe]] 动态 morph 联合 tax。

### 系统性缺陷

论文不实现 tax 自动预测器给 autoscaler。Quality side 完全外生。

## 局限与 Future Work

- **局限 1**：τ 非绝对 SLA 预测器。
- **局限 2**：实现栈演进快，数字会老化。
- **Future work 1**：tax-aware router+placement（接 [[BOUTE]]）。
- **Future work 2**：live trace 拟合 balls-bins-buckets 参数服务 autoscaler。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism|Expert-Parallel]]、[[Disaggregation]]、[[Tensor-Parallelism|Tensor-Parallel]]
- **同类系统**：[[vLLM]]、DeepEP
- **同会议**：[[MLSys-2026]]