---
type: concept
aliases: [Non-Uniform-Memory-Access]
last_updated: 2026-07-18
tags: [hardware, memory, scheduling, placement]
---

# NUMA

> Non-uniform memory access (NUMA) systems expose locality-dependent memory and I/O costs: a processor accesses local memory and devices differently from resources attached to another socket or node.

## 核心思想

NUMA topology makes placement part of performance correctness. Threads, pages, queues, accelerators, and storage devices should be mapped with knowledge of socket and interconnect locality; otherwise remote traffic, cache-coherence work, and bandwidth contention can dominate nominal compute or device capability.

## 为什么重要

Many high-core-count and multi-device results in this corpus depend on pinning, allocation policy, and I/O placement. A benchmark that omits topology can be irreproducible or incorrectly attribute a locality effect to an algorithm.

## 关键观察 / 隐含假设

- **观察**：memory/swap or I/O resource partitioning interacts with core locality. [[ScaleSwap-FAST26]] and [[MAIO-FAST26]] evaluate system paths with such constraints.
- **观察**：accelerator/device placement can expose cross-node traffic. [[DSA-2LM-ATC25]] and [[Catur-MLSys26]] use hardware-aware execution contexts.
- **假设**：pinning once is sufficient. Dynamic scheduling, page migration, shared data, and multi-tenant placement can invalidate a static mapping.

## 设计空间与取舍

- **Locality vs load balance**：strict locality can strand capacity; balancing can add remote traffic.
- **First-touch, binding, or migration**：allocation policy changes both steady-state bandwidth and adaptation cost.
- **CPU, memory, and device topology**：optimizing only one layer can move contention to another.

## 引用本概念的论文

- [[ScaleSwap-FAST26]] — core-centric swap-resource management.
- [[MAIO-FAST26]] — memory/I/O placement context.
- [[DSA-2LM-ATC25]] — hardware-aware acceleration path.
- [[Catur-MLSys26]] — device/runtime placement boundary.
- [[SoarAlto-OSDI25]] — system scheduling/locality context.
