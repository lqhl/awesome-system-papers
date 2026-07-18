---
type: concept
aliases: [Dominant-Resource-Fairness]
last_updated: 2026-07-18
tags: [scheduling, fairness, resource-management]
---

# DRF

> Dominant Resource Fairness (DRF) allocates multi-resource capacity by equalizing users' dominant shares, extending scalar fair sharing to workloads that consume different mixes of CPU, memory, storage, or accelerators.

## 核心思想

A user's dominant share is its largest normalized demand across resource dimensions. DRF seeks allocations that prevent one workload's dominant bottleneck from monopolizing a shared cluster, but the result depends on declared demand vectors, resource granularity, placement constraints, and whether resources are divisible or time-varying.

## 为什么重要

Storage and systems schedulers often face multi-dimensional contention. DRF is a useful fairness reference, but it does not by itself optimize locality, tail latency, deadlines, fragmentation, or application-level value.

## 关键观察 / 隐含假设

- **观察**：fairness objectives can conflict with device or data placement. [[HARE-FAST26]] studies a storage-system scheduling context where resource behavior matters.
- **观察**：runtime constraints can make static demand vectors incomplete. [[Spirit-SOSP25]] uses a system-management context with richer operational boundaries.
- **假设**：resource demands are observable and stable enough for a fair-share policy to act on them; bursty or phase-changing workloads weaken this assumption.

## 设计空间与取舍

- **Fair share vs efficiency/locality**：equal dominant shares can leave capacity unusable when placement or affinity is constrained.
- **Static vs adaptive demand**：adaptive models respond to workload change but add measurement and policy complexity.
- **Cluster resource fairness vs SLOs**：a fair allocation may still violate latency/deadline objectives.

## 引用本概念的论文

- [[HARE-FAST26]] — multi-resource/storage scheduling context.
- [[Spirit-SOSP25]] — operational resource-management context.
