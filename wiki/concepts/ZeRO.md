---
type: concept
aliases: [Zero-Redundancy-Optimizer, ZeRO-1, ZeRO-2, ZeRO-3]
last_updated: 2026-07-18
tags: [distributed-training, sharding, memory-management]
---

# ZeRO

> ZeRO is a family of data-parallel sharding strategies that remove replicated optimizer state, gradients, and eventually parameters across ranks to make larger models fit within aggregate accelerator memory.

## 核心思想

The stages progressively shard optimizer state, gradients, and parameters. The memory benefit is coupled to collective communication: parameter materialization and gradient reduction occur around computation, so the useful comparison is always against a stated model, batch, topology, and implementation.

In this corpus ZeRO is both a baseline and a composition point. Memory-management systems tune policies around it; privacy, quantization, and structured-optimizer work add semantic constraints that simple uniform sharding may violate.

## 为什么重要

ZeRO/FSDP-style sharding changes the feasibility boundary of model training. It also makes collective-buffer layout, checkpointing, offload, and optimizer semantics first-class systems concerns rather than local implementation details.

## 关键观察 / 隐含假设

- **观察**：more aggressive stages reduce resident state but increase communication and materialization work. [[DP-ZeRO-MLSys26]] measures this trade-off with differential-privacy bookkeeping under specified A100 configurations.
- **观察**：uniform shards may conflict with structured state. [[veScale-FSDP-MLSys26]] argues for ragged placement when quantization blocks or matrix optimizers cannot cross shard boundaries.
- **假设**：a memory policy can be optimized around fixed training behavior. [[ProTrain-MLSys26]] searches ZeRO, offload, and checkpointing choices, but its conclusions are bounded by the profiled models and sequences.

## 设计空间与取舍

- **Stage depth vs communication**：sharding more state lowers memory but increases collective dependence.
- **Offload vs accelerator residency**：offload can expand capacity while introducing host-device bandwidth and scheduling constraints.
- **Uniform vs semantic shards**：simple placement eases implementation; structured operators can require padding or richer placement metadata.

## 引用本概念的论文

- [[DP-ZeRO-MLSys26]] — composes ZeRO stages with differential privacy.
- [[veScale-FSDP-MLSys26]] — changes FSDP/ZeRO-style placement for structured training.
- [[ProTrain-MLSys26]] — searches memory strategies including ZeRO and offload.
- [[FSDP]] — related fully-sharded data-parallel abstraction.

## 已知局限 / 开放问题

- Communication topology, failure recovery, and composability with TP/EP/CP can dominate once the basic memory problem is solved.
- Full-training utility and convergence must be measured separately from feasibility or microbenchmark throughput.
