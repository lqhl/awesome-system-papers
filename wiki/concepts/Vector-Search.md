---
type: concept
aliases: [Vector-Search, ANN-Search, Approximate-Nearest-Neighbor-Search]
last_updated: 2026-07-18
tags: [retrieval, ann, indexing, systems]
---

# Vector Search

> 矢量搜索检索嵌入查询的近似最近邻；系统在召回率、延迟、内存/存储占用、更新成本和工作负载并发性之间进行权衡。

## 核心思想

索引将向量映射到候选探索路径。精确搜索在规模上通常过于昂贵，因此实际系统使用图形、分区、量化、磁盘或硬件放置技术。正确的设计取决于语料库是静态的还是可变的，以及瓶颈是 DRAM、SSD、网络还是加速器计算。

## 为什么重要

矢量搜索是人工智能和数据系统的常见检索基础。报告的性能必须说明召回目标、数据集、索引构建/更新状态、查询分布、并发性和硬件；更快的单查询路径可能会导致更新或尾部延迟更差。

## 关键观察 / 隐含假设

- **观察**：图索引揭示了召回-记忆-更新的权衡。 [[HNSW]] 和 [[DiskANN]] 是 [[OdinANN-FAST26]] 和 [[LEANN-MLSys26]] 中重复出现的基线。
- **观察**：资源布局改变瓶颈。 [[PIMANN-ATC25]] 和 [[Terminus-MLSys26]] 研究硬件和执行路径选择。
- **假设**：基准召回/延迟捕获应用价值。动态摄取、过滤和工作负载偏差可以改变结论。

## 设计空间与取舍

- **图形、分区、量化或扫描**：每个都交换计算、内存或 I/O 的候选质量。
- **内存中与磁盘辅助**：磁盘扩展了容量，但增加了 I/O 和布局敏感性。
- **静态索引与可变索引**：插入/删除和重建/合并策略可以主导持续操作。

## 引用本概念的论文

- [[OdinANN-FAST26]] — update-oriented ANN indexing.
- [[LEANN-MLSys26]] — memory-efficient retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN operations.
- [[Terminus-MLSys26]] — ANN execution boundaries.
- [[HNSW]]、[[DiskANN]] — common index design baselines.

## 已知局限 / 开放问题

- 过滤查询、混合更新/查询工作负载和尾部延迟行为需要与静态基准单独进行验证。
