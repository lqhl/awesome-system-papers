---
type: concept
aliases: [Fully-Sharded-Data-Parallel, Fully-Sharded Data Parallel]
last_updated: 2026-07-18
tags: [distributed-training, sharding, memory-management]
---

# FSDP

> Fully Sharded Data Parallel (FSDP) is a data-parallel training pattern that shards parameters, gradients, and optimizer state across ranks, materializing parameter shards for computation and releasing or re-sharding them around the layer lifecycle.

## 核心思想

FSDP is closely related to ZeRO stage-3: memory pressure falls because a rank need not permanently retain every model state, but training adds AllGather and ReduceScatter traffic around parameter use. It is therefore a memory–communication trade-off rather than a universal throughput optimization.

The current corpus shows two extension directions. One changes FSDP's sharding/layout primitives for structured optimizers and quantization; another composes it with DP, context parallelism, tensor parallelism, or expert parallelism. These extensions rely on the base FSDP lifecycle but introduce new placement, communication, and correctness constraints.

## 为什么重要

FSDP is a common baseline and integration point for large-model training papers. It determines whether a model fits, affects collective-buffer layout and peak memory, and constrains how non-elementwise optimizer or quantization blocks may be placed. A result that improves FSDP often needs to distinguish memory feasibility from end-to-end training utility.

## 关键观察 / 隐含假设

- **观察**：sharding boundaries must preserve the semantic unit required by the optimizer or quantizer. [[veScale-FSDP-MLSys26]] argues that element- or row-wise placement can split such blocks; its RaggedShard design instead treats the block as the placement unit.
- **观察**：the collective path can dominate once models fit. [[veScale-FSDP-MLSys26]] attributes part of its gain to planned, persistent zero-copy buffers, while [[ProTrain-MLSys26]] treats FSDP/ZeRO memory policy as coupled with checkpointing and offload.
- **假设**：FSDP can compose transparently with other parallelisms. [[FCP-MLSys26]] reshuffles context-parallel blocks around non-attention computation, and [[DP-ZeRO-MLSys26]] combines sharding with differential-privacy clipping; both validate only their stated configurations.

## 设计空间与取舍

- **Uniform vs structured shards**：uniform shards simplify implementation, but structured blocks may require ragged placement and padding-aware planning.
- **Memory saving vs communication**：more aggressive state sharding lowers resident memory but may increase collective traffic and sensitivity to topology.
- **Composable APIs vs semantic constraints**：a stable `fully_shard`-style interface helps adoption, but quantized states, matrix optimizers, DP bookkeeping, and long-context reshuffles can require extra metadata and schedules.

## 引用本概念的论文

- [[veScale-FSDP-MLSys26]] — extends FSDP placement and collective-buffer management for structured training.
- [[FCP-MLSys26]] — combines context-parallel attention scheduling with FSDP and other parallelisms.
- [[DP-ZeRO-MLSys26]] — evaluates DP clipping/noise alongside ZeRO/FSDP-style sharding.
- [[ProTrain-MLSys26]] — searches memory policies spanning ZeRO, FSDP, swapping, and checkpointing.
- [[BOOST-MLSys26]] — identifies FSDP as a future composition target for low-rank tensor parallelism.

## 已知局限 / 开放问题

- Independent shard layouts can cause padding, metadata, and collective-planning overhead on irregular models.
- Most corpus evaluations focus on throughput or memory under fixed clusters; topology changes, failures, and end-to-end convergence remain separate validation problems.
