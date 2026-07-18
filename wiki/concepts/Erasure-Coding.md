---
type: concept
aliases: [EC, Erasure-Code]
last_updated: 2026-07-18
tags: [storage, reliability, distributed-systems, coding]
---

# Erasure Coding

> Erasure coding stores data as coded fragments so that a subset can reconstruct the original object, improving capacity efficiency relative to full replication while introducing encoding, repair, placement, and tail-latency trade-offs.

## 核心思想

An `(k, m)`-style layout splits data into `k` data fragments and `m` parity fragments; sufficient surviving fragments reconstruct lost data. System behavior depends on code choice, fragment size, placement across failure domains, network bandwidth, CPU/accelerator encoding cost, and repair scheduling.

## 为什么重要

Erasure coding is a storage-system mechanism, not just a capacity ratio. It changes write amplification, small-write handling, degraded-read latency, and background repair traffic. Results must state fault model, layout, workload, and whether repairs share foreground resources.

## 关键观察 / 隐含假设

- **观察**：code geometry and placement interact with storage management. [[DisCoGC-FAST26]] accounts for stripe alignment when reclaiming stale ranges.
- **观察**：repair and read paths can dominate in real deployments. [[DRBoost-FAST26]] and [[McQueen-FAST26]] study storage-system mechanisms under reliability constraints.
- **假设**：capacity savings outweigh repair and tail costs. [[TapeOBS-FAST26]] and [[LESS-FAST26]] show that media, workload, and observability boundaries matter.

## 设计空间与取舍

- **Replication vs coding**：coding saves space while increasing computation and multi-fragment coordination.
- **Small writes vs stripe efficiency**：partial-stripe updates can add read-modify-write or buffering cost.
- **Repair bandwidth vs foreground SLO**：faster repair can contend with client traffic.

## 引用本概念的论文

- [[DRBoost-FAST26]] — reliability/coding storage mechanism.
- [[McQueen-FAST26]] — coded storage evaluation context.
- [[DisCoGC-FAST26]] — stripe-aware reclamation.
- [[TapeOBS-FAST26]] — media/reliability observability boundary.
- [[LESS-FAST26]] — storage-system trade-offs.
