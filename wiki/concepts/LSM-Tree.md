---
type: concept
aliases: [Log-Structured-Merge-Tree, Log Structured Merge Tree]
last_updated: 2026-07-18
tags: [storage, indexing, compaction, write-amplification]
---

# LSM-Tree

> An LSM-tree is a write-optimized index that absorbs updates into mutable components and periodically merges sorted immutable components; it exchanges write-path efficiency for compaction, space amplification, and read-amplification management.

## 核心思想

Instead of updating an on-disk search tree in place, an LSM-tree batches writes, flushes sorted runs, and compacts runs across levels. This design turns small random writes into larger sequential work, but stale entries and overlapping runs make garbage collection, compaction scheduling, and read lookup part of the system's steady-state control loop.

The corpus uses LSM-tree both as a database index and as a metadata mechanism inside storage services. Its performance cannot be inferred from the data structure alone: the device, cache, compaction policy, workload skew, and service-level latency objective determine the outcome.

## 为什么重要

LSM-tree behavior links application updates to flash write amplification and tail latency. It is therefore a common source of cross-layer trade-offs: an aggressive compaction policy can reclaim space and reduce read work while consuming foreground bandwidth; a deferred policy can preserve throughput until garbage or metadata pressure becomes acute.

## 关键观察 / 隐含假设

- **观察**：stale-range structure affects whether reclaim can avoid copying live data. [[DisCoGC-FAST26]] scans LSM metadata to identify discardable ranges and combines discard with lower-frequency compaction.
- **观察**：separating data and metadata paths can change LSM bottlenecks. [[DecouKV-ATC25]] and [[DOGI-FAST26]] use the abstraction in systems that make placement or device behavior explicit.
- **假设**：compaction policy can be tuned independently of the workload. [[RASK-FAST26]] and [[PolarStore-FAST26]] illustrate why skew, cache behavior, and device constraints can invalidate such a simple assumption.

## 设计空间与取舍

- **Leveled vs tiered compaction**：more frequent merging reduces overlap and read cost, while increasing write amplification.
- **Logical reclaim vs physical reclaim**：metadata can mark stale data cheaply, but physical space may remain unavailable until discard, compaction, or device GC runs.
- **Foreground throughput vs maintenance work**：background compaction protects future reads and capacity, but may contend with user I/O and worsen tail latency.

## 引用本概念的论文

- [[DisCoGC-FAST26]] — uses LSM metadata to coordinate discard and compaction in distributed log-structured storage.
- [[DecouKV-ATC25]] — studies a KV-store design whose data and metadata paths expose LSM-related trade-offs.
- [[DOGI-FAST26]] — connects storage-device behavior with LSM-oriented update and reclamation paths.
- [[RASK-FAST26]] — evaluates storage-system mechanisms under LSM-style workloads.
- [[PolarStore-FAST26]] — treats compaction and storage management as coupled system controls.

## 已知局限 / 开放问题

- Workload shifts can change the balance among space, write, and read amplification faster than static compaction heuristics adapt.
- Device-level garbage collection and host-level compaction can amplify each other; end-to-end observability remains essential.
