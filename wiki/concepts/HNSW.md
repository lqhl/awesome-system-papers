---
type: concept
aliases: [Hierarchical-Navigable-Small-World]
last_updated: 2026-07-18
tags: [vector-search, ann, graph-index]
---

# HNSW

> HNSW is a hierarchical graph-based approximate-nearest-neighbor index that navigates from sparse upper layers to a dense lower graph, trading memory and update cost for high-recall low-latency search.

## 核心思想

Search greedily traverses graph layers toward a query and expands a candidate set near the target. Construction chooses neighbor connections to maintain navigability. The abstraction is powerful for in-memory vector retrieval, but graph memory, insertion/deletion maintenance, and storage placement are part of its practical cost.

## 为什么重要

HNSW is a frequent ANN baseline because it exposes a clear recall–latency–memory frontier. Disk-oriented, update-oriented, PIM, and compressed-retrieval work in this corpus use it to show which resource or maintenance cost their design changes.

## 关键观察 / 隐含假设

- **观察**：graph maintenance matters for mutable indexes. [[OdinANN-FAST26]] contrasts update-oriented design choices with graph-index behavior.
- **观察**：memory capacity is a first-order limit. [[LEANN-MLSys26]] and [[PIMANN-ATC25]] evaluate alternatives that alter memory or hardware placement.
- **假设**：recall/latency at a chosen search parameter captures utility. [[Terminus-MLSys26]] and [[PathWeaver-ATC25]] show why workload and deployment boundaries also matter.

## 设计空间与取舍

- **Recall vs latency**：larger candidate exploration tends to improve recall while increasing work.
- **Graph degree vs memory**：more edges can improve navigability but raise footprint and update cost.
- **Static vs dynamic operation**：insertion/deletion and merge/rebuild policy can dominate sustained workload performance.

## 引用本概念的论文

- [[OdinANN-FAST26]] — update-oriented ANN indexing.
- [[LEANN-MLSys26]] — memory-efficient ANN retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN operations.
- [[Terminus-MLSys26]] — ANN execution boundaries.
- [[PathWeaver-ATC25]] — graph-search system trade-offs.
