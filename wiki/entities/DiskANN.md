---
type: entity
kind: tool
aliases: [Disk-ANN]
status: active
last_updated: 2026-07-18
tags: [vector-search, ann, ssd, indexing]
---

# DiskANN

> DiskANN 是一种面向磁盘的近似最近邻索引系统，也是大规模矢量搜索中涉及召回率、延迟、更新成本和 SSD I/O 行为的论文的通用基线。

## 是什么

DiskANN 风格的设计保留了图表索引和数据布局，使 SSD 辅助遍历变得实用。在本 wiki 中，它通常是基线而不是通用最佳值：静态搜索、动态插入、内存占用和硬件布局强调设计的不同部分。

## 关键观察 / 隐含假设

- **观察**：更新行为改变相关基线。 [[OdinANN-FAST26]] 将直接插入和合并相关的成本与面向磁盘的图索引进行了对比。
- **观察**：内存和存储布局可以改变人工神经网络的权衡。 [[LEANN-MLSys26]] 和 [[PIMANN-ATC25]] 研究围绕 ANN 搜索的不同资源布局。
- **假设**：召回/延迟比较捕获系统效用。 [[Terminus-MLSys26]] 说明工作负载、更新速率和设备行为可能会引入额外的边界。

## 演进时间线

- 2025 ATC：[[PIMANN-ATC25]] — explores an alternative hardware placement for ANN operations.
- 2026 FAST：[[OdinANN-FAST26]] — addresses update-oriented ANN indexing trade-offs.
- 2026 MLSys：[[LEANN-MLSys26]] — 将内存占用和检索行为视为耦合约束。

## 相关概念

- [[ANNS]]、[[Vector-Search]]、[[HNSW]]、[[NVMe]]

## 相关论文

- [[OdinANN-FAST26]] — update-oriented comparison with graph indexing.
- [[LEANN-MLSys26]] — memory-efficient ANN retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN search.
- [[Terminus-MLSys26]] — system boundaries in ANN execution.
