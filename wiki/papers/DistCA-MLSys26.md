---
type: paper
name: DistCA
full_title: "Efficient Long-Context Language Model Training by Core Attention Disaggregation"
authors: [Yonghao Zhuang, Junda Chen, Bo Pang, Yi Gu, Yibo Zhu, Yimin Jiang, Ion Stoica, Eric Xing, Hao Zhang]
venue: MLSys
year: 2026
tags: [llm-training, long-context, attention, disaggregation, load-balancing]
source_pdf: "[[93db85ed909c13838ff95ccfa94cebd9.pdf]]"
source_md: "[[93db85ed909c13838ff95ccfa94cebd9]]"
---

# Efficient Long-Context Language Model Training by Core Attention Disaggregation (MLSys 2026)

> **一句话总结**：把无参数的 core attention（softmax(QKᵀ)V）从其余层解耦到独立 attention server pool，token 级 CA-task 动态 rebatch 消除 DP/PP stragglers；512 H200、512K context 下端到端吞吐最高 **1.35×**。

## 问题

长 context 训练用 document packing 时，attention FLOPs 随序列长度二次增长、其余层近似线性，同 token 数的 chunk 负载差异大，造成 DP gradient barrier 和 PP bubble stragglers（已有工作报告 1.34–1.44× slowdown）。variable-length chunk 平衡 compute 却 inflate memory；per-document context parallelism 有 all-gather 和 tiny shard 低效问题。

## 核心方法

**Core Attention Disaggregation (CAD)**：利用 CA 的 statelessness（无参数、极少中间态）和 composability（任意 token shard 可 fuse 进 [[Flash-Attention|FlashAttention]] kernel），把 CA 调度到专用 attention server。

**DistCA 实现**：(1) in-place GPU time-sharing、(2) ping-pong overlap 完全隐藏通信、(3) workload-balanced scheduler 优化 shard 划分。

## 关键结果

- 最多 512 H200、512K context：端到端吞吐最高 **1.35×**，DP/PP stragglers 消除
- near-perfect compute/memory balance，weak scaling 近线性

## 相关

- **相关概念**：[[Attention]]、[[Flash-Attention]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：Megatron、context parallelism、variable-length chunking
- **同会议**：[[MLSys-2026]]