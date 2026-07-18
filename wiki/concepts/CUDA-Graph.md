---
type: concept
aliases: [CUDA-Graphs]
last_updated: 2026-07-18
tags: [gpu, runtime, scheduling, kernel-launch]
---

# CUDA Graph

> CUDA Graph captures a GPU work graph so that repeated launches can be replayed with lower CPU launch overhead and more explicit dependency scheduling; it is most effective when execution structure is stable enough to amortize capture and update costs.

## 核心思想

A graph records kernels, memory operations, and dependencies for later instantiation/replay. It can reduce per-operation dispatch overhead and enable runtime scheduling optimizations, but dynamic shapes, control flow, memory addresses, and changing batch composition can require graph rebuilds or fallback paths.

## 为什么重要

GPU-serving and training systems often become CPU-launch or synchronization bound at small kernels or high request rates. CUDA Graph is a common mechanism, but a graph microbenchmark does not establish end-to-end benefit without capture, update, concurrency, and workload-mix boundaries.

## 关键观察 / 隐含假设

- **观察**：launch overhead matters most for repetitive fine-grained work. [[EventTensor-MLSys26]] and [[DynaFlow-MLSys26]] use GPU-runtime contexts with this boundary.
- **观察**：preemption and dynamic scheduling can conflict with fixed captured graphs. [[GPreempt-ATC25]] and [[Torpor-ATC25]] examine runtime control concerns.
- **假设**：the graph shape remains reusable. [[LAPS-MLSys26]] illustrates why changing execution conditions require explicit fallback or update evaluation.

## 设计空间与取舍

- **Capture/replay vs dynamic execution**：replay lowers overhead but constrains variation.
- **CPU overhead vs memory/update cost**：graph management itself consumes resources and synchronization.
- **Single-stream vs concurrent requests**：benefits can change with batching and multi-tenant scheduling.

## 引用本概念的论文

- [[EventTensor-MLSys26]] — GPU runtime/execution context.
- [[DynaFlow-MLSys26]] — dynamic execution and scheduling context.
- [[GPreempt-ATC25]] — GPU preemption boundary.
- [[Torpor-ATC25]] — runtime scheduling context.
- [[LAPS-MLSys26]] — dynamic workload conditions.
