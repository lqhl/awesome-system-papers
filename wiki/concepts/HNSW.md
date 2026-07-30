---
type: concept
aliases: [Hierarchical-Navigable-Small-World]
last_updated: 2026-07-18
tags: [vector-search, ann, graph-index]
---

# HNSW

> HNSW 是一种基于分层图的近似最近邻索引，它从稀疏的上层导航到密集的下层图，以内存和更新成本换取高召回率低延迟搜索。

## 核心思想

搜索贪婪地遍历图形层进行查询，并扩展目标附近的候选集。施工选择邻近连接以维持通航性。这种抽象对于内存中向量检索来说非常强大，但图形内存、插入/删除维护和存储布局是其实际成本的一部分。

## 为什么重要

HNSW 是一个常见的 ANN 基线，因为它暴露了清晰的回忆-延迟-记忆边界。该语料库中的面向磁盘、面向更新、PIM 和压缩检索工作使用它来显示其设计更改的资源或维护成本。

## 关键观察 / 隐含假设

- **观察**：图维护对于可变索引很重要。 [[OdinANN-FAST26]] 将面向更新的设计选择与图形索引行为进行对比。
- **观察**：记忆容量是一阶极限。 [[LEANN-MLSys26]] 和 [[PIMANN-ATC25]] 评估改变内存或硬件布局的替代方案。
- **假设**：所选搜索参数的召回/延迟捕获效用。 [[Terminus-MLSys26]] 和 [[PathWeaver-ATC25]] 说明了为什么工作负载和部署边界也很重要。

## 设计空间与取舍

- **召回率与延迟**：更大的候选探索往往会提高召回率，同时增加工作量。
- **图度与内存**：更多的边可以提高导航性，但会增加占用空间和更新成本。
- **静态与动态操作**：插入/删除和合并/重建策略可以主导持续的工作负载性能。

## 引用本概念的论文

- [[OdinANN-FAST26]] — update-oriented ANN indexing.
- [[LEANN-MLSys26]] — memory-efficient ANN retrieval.
- [[PIMANN-ATC25]] — hardware placement for ANN operations.
- [[Terminus-MLSys26]] — ANN execution boundaries.
- [[PathWeaver-ATC25]] — graph-search system trade-offs.
