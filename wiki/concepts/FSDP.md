---
type: concept
aliases: [Fully-Sharded-Data-Parallel, Fully-Sharded Data Parallel]
last_updated: 2026-07-18
tags: [distributed-training, sharding, memory-management]
---

# FSDP

> 完全分片数据并行（FSDP）是一种数据并行训练模式：跨 rank 分片参数、梯度与优化器状态，在计算前物化参数分片，并在 layer 生命周期内释放或重新分片。

## 核心思想

FSDP 与 ZeRO stage 3 密切相关：每个 rank 不必永久保留全部模型状态，内存压力因而下降；代价是在参数使用前后增加 AllGather 与 ReduceScatter 流量。因此它首先是内存—通信取舍，不是无条件的吞吐优化。

当前语料库显示了两个扩展方向。一是改变 FSDP 的分片/布局原语以实现结构化优化器和量化；另一种是用 DP、上下文并行、张量并行或专家并行来组合。这些扩展依赖于基本 FSDP 生命周期，但引入了新的放置、通信和正确性约束。

## 为什么重要

FSDP 是大型模型训练论文的通用基线和集成点。它确定模型是否适合、影响集体缓冲区布局和峰值内存，并限制非元素优化器或量化块的放置方式。提高 FSDP 的结果通常需要区分内存可行性和端到端训练实用性。

## 关键观察 / 隐含假设

- **观察**：分片边界必须保留优化器或量化器所需的语义单元。 [[veScale-FSDP-MLSys26]] 认为元素或行的放置可以分割这些块；相反，它的 RaggedShard 设计将块视为放置单元。
- **观察**：一旦模型适合，集体路径就能占主导地位。 [[veScale-FSDP-MLSys26]] 将其增益的一部分归因于计划的持久零复制缓冲区，而 [[ProTrain-MLSys26]] 将 FSDP/ZeRO 内存策略视为与检查点和卸载相结合。
- **假设**：FSDP 可以与其他并行方式透明组合。[[FCP-MLSys26]] 围绕非注意力计算重排上下文并行 block，[[DP-ZeRO-MLSys26]] 则组合分片与差分隐私裁剪；两者都只验证了论文声明的配置。

## 设计空间与取舍

- **统一分片与结构化分片**：统一分片简化了实现，但结构化块可能需要参差不齐的放置和填充感知规划。
- **内存节省与通信**：更积极的状态分片会降低常驻内存，但可能会增加集体流量和对拓扑的敏感性。
- **可组合 API 与语义约束**：稳定的 `fully_shard` 风格的接口有助于采用，但量化状态、矩阵优化器、DP 簿记和长上下文重新洗牌可能需要额外的元数据和时间表。

## 引用本概念的论文

- [[veScale-FSDP-MLSys26]] — extends FSDP placement and collective-buffer management for structured training.
- [[FCP-MLSys26]] — combines context-parallel attention scheduling with FSDP and other parallelisms.
- [[DP-ZeRO-MLSys26]] — evaluates DP clipping/noise alongside ZeRO/FSDP-style sharding.
- [[ProTrain-MLSys26]] — searches memory policies spanning ZeRO, FSDP, swapping, and checkpointing.
- [[BOOST-MLSys26]] — 将 FSDP 确定为低阶张量并行性的未来组合目标。

## 已知局限 / 开放问题

- 独立的分片布局可能会导致不规则模型上的填充、元数据和集体规划开销。
- 大多数语料库评估侧重于固定集群下的吞吐量或内存；拓扑变化、故障和端到端收敛仍然是单独的验证问题。
