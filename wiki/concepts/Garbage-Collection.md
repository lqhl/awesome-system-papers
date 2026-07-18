---
type: concept
aliases: [GC, Storage-Garbage-Collection]
last_updated: 2026-07-18
tags: [storage, reclamation, compaction, write-amplification]
---

# Garbage Collection

> Storage garbage collection reclaims physical space occupied by stale or unreachable data; in log-structured and flash-backed systems it is inseparable from write amplification, fragmentation, and foreground latency.

## 核心思想

Unlike language-runtime GC, storage GC commonly identifies stale ranges or segments, migrates live data when necessary, and returns reclaimable capacity to a filesystem or device. The maintenance work competes with user I/O and may trigger further device-level relocation, so a reclaim policy must balance immediate capacity pressure against future write and read costs.

## 为什么重要

GC determines whether append-heavy systems can sustain their advertised capacity and latency. It connects metadata/indexing decisions to SSD behavior: a policy that minimizes host copying can still leave device fragmentation, while aggressive compaction can reduce fragmentation at the cost of write amplification.

## 关键观察 / 隐含假设

- **观察**：stale-data geometry matters. [[DisCoGC-FAST26]] uses long contiguous stale ranges for discard and retains compaction for fragments that discard cannot reclaim efficiently.
- **观察**：zone size and write-order constraints change where GC is paid. [[ZUFS-FAST26]] moves part of the problem to host-side proactive GC for zoned mobile storage.
- **假设**：background maintenance can be scheduled without harming foreground SLOs. [[PolarStore-FAST26]] and [[DOGI-FAST26]] show that device and workload conditions can make this assumption fragile.

## 设计空间与取舍

- **Copy/compaction vs discard/reset**：copying live data can consolidate space; discard/reset avoids copying where stale ranges and device semantics allow it.
- **Reactive vs proactive policy**：reactive GC preserves short-term work but risks foreground stalls; proactive GC consumes background resources to avoid emergencies.
- **Host vs device reclamation**：host knowledge can improve placement, while device firmware retains hidden wear-leveling and media-management constraints.

## 引用本概念的论文

- [[DisCoGC-FAST26]] — combines discard and compaction in distributed log-structured storage.
- [[ZUFS-FAST26]] — adds proactive filesystem GC for zoned mobile storage.
- [[DOGI-FAST26]] — relates device behavior to storage-system reclamation.
- [[PolarStore-FAST26]] — treats GC and storage-management policy as coupled controls.
- [[WARP-FAST26]] — evaluates storage behavior involving reclamation paths.

## 已知局限 / 开放问题

- A host-level metric cannot fully expose device-level GC, wear, or firmware queueing.
- Policies need workload-aware validation under sustained write pressure, not only steady-state microbenchmarks.
