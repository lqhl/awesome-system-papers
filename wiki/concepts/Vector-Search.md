---
type: concept
aliases: [Vector-Search, ANN-Search, Approximate-Nearest-Neighbor-Search]
last_updated: 2026-07-18
tags: [retrieval, ann, indexing, systems]
---

# Vector Search

> Vector search retrieves approximate nearest neighbors for an embedding query; the systems trade-off is among recall, latency, memory/storage footprint, update cost, and workload concurrency.

## 核心思想

An index maps vectors to candidate exploration paths. Exact search is often too expensive at scale, so practical systems use graph, partition, quantization, disk, or hardware-placement techniques. The right design depends on whether the corpus is static or mutable and whether the bottleneck is DRAM, SSD, network, or accelerator compute.

## 为什么重要

Vector search is a common retrieval substrate for AI and data systems. Reported performance must state recall target, dataset, index build/update state, query distribution, concurrency, and hardware; a faster single-query path may be worse for updates or tail latency.

## 关键观察 / 隐含假设

- **观察**：graph indexes expose a recall–memory–update trade-off. [[HNSW]] and [[DiskANN]] are recurring baselines in [[OdinANN-FAST26]] and [[LEANN-MLSys26]].
- **观察**：resource placement changes the bottleneck. [[PIMANN-ATC25]] and [[Terminus-MLSys26]] study hardware and execution-path choices.
- **假设**：benchmark recall/latency captures application value. Dynamic ingestion, filtering, and workload skew can change the conclusion.

## 设计空间与取舍

- **Graph, partition, quantization, or scan**：each exchanges candidate quality for compute, memory, or I/O.
- **In-memory vs disk-assisted**：disk expands capacity but adds I/O and layout sensitivity.
- **Static vs mutable index**：insertion/deletion and rebuild/merge policy can dominate sustained operation.

## 引用本概念的论文

- [[OdinANN-FAST26]] — update-oriented ANN indexing.
- [[LEANN-MLSys26]] — memory-efficient retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN operations.
- [[Terminus-MLSys26]] — ANN execution boundaries.
- [[HNSW]]、[[DiskANN]] — common index design baselines.

## 已知局限 / 开放问题

- Filtered queries, mixed update/query workloads, and tail-latency behavior require separate validation from static benchmarks.
