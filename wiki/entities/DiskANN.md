---
type: entity
kind: tool
aliases: [Disk-ANN]
status: active
last_updated: 2026-07-18
tags: [vector-search, ann, ssd, indexing]
---

# DiskANN

> DiskANN is a disk-oriented approximate-nearest-neighbor indexing system and a common baseline for papers that trade recall, latency, update cost, and SSD I/O behavior in large-scale vector search.

## 是什么

DiskANN-style designs keep a graph index with data laid out to make SSD-assisted traversal practical. In this wiki it is most often a baseline rather than a universal optimum: static search, dynamic insertion, memory footprint, and hardware placement stress different parts of the design.

## 关键观察 / 隐含假设

- **观察**：update behavior changes the relevant baseline. [[OdinANN-FAST26]] contrasts direct insertion and merge-related costs with disk-oriented graph indexing.
- **观察**：memory and storage placement can alter ANN trade-offs. [[LEANN-MLSys26]] and [[PIMANN-ATC25]] study different resource placements around ANN search.
- **假设**：a recall/latency comparison captures system utility. [[Terminus-MLSys26]] illustrates that workload, update rate, and device behavior can introduce additional boundaries.

## 演进时间线

- 2025 ATC：[[PIMANN-ATC25]] — explores an alternative hardware placement for ANN operations.
- 2026 FAST：[[OdinANN-FAST26]] — addresses update-oriented ANN indexing trade-offs.
- 2026 MLSys：[[LEANN-MLSys26]] — treats memory footprint and retrieval behavior as coupled constraints.

## 相关概念

- [[ANNS]]、[[Vector-Search]]、[[HNSW]]、[[NVMe]]

## 相关论文

- [[OdinANN-FAST26]] — update-oriented comparison with graph indexing.
- [[LEANN-MLSys26]] — memory-efficient ANN retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN search.
- [[Terminus-MLSys26]] — system boundaries in ANN execution.
