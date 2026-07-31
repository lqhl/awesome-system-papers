---
type: entity
kind: tool
aliases: [Disk-ANN]
status: active
last_updated: 2026-07-30
tags: [vector-search, ann, ssd, indexing]
---

# DiskANN

> DiskANN 是面向 SSD 的图式近似最近邻系统族，以较小 DRAM 导航结构配合磁盘上的压缩向量和邻接数据，把十亿级 [[Vector-Search]] 从全内存容量约束中解放出来。

## 是什么

DiskANN 的核心路线是构建可导航近邻图，查询时在内存中保留必要元数据，并按图搜索结果从 SSD 读取候选向量。它代表“减少随机读取数量”的磁盘 ANN 设计点，长期是 [[HNSW]] 之外的重要基线。最新论文不再只问 DiskANN 是否快，而是问其串行图依赖在大 top-k、多盘和 GPU 分层环境中是否仍合适。

## 关键观察 / 隐含假设

- **观察**：SSD 容量便宜，但逐跳图遍历会把延迟放在依赖链上。[[Helmsman-OSDI26]] 在 top-k 10–3000 的生产负载中发现，DiskANN 类 greedy walk 难以利用全闪存阵列的并行带宽。
- **观察**：图依赖并非完全不可隐藏。[[FlowANN-OSDI26]] 利用节点被发现到真正展开之间的 window，异步从 CPU 取 edge，说明 DiskANN 风格图仍可通过执行重排扩展。
- **观察**：持续更新会改变磁盘布局与搜索质量。[[OdinANN-FAST26]] 将 update path 作为一等目标，而非只优化静态查询。
- **隐含假设**：查询 top-k 较小、图 cache 命中可观、SSD 单次随机读延迟可接受；大 top-k 或设备并行度很高时，该假设会变弱。

## 演进时间线

- **早期**：DiskANN 确立“DRAM 导航 + SSD 向量/图”的十亿级 ANN 路线。
- **2025–2026**：[[PIMANN-ATC25]]、[[LEANN-MLSys26]] 与 [[Terminus-MLSys26]] 从硬件放置、容量和执行路径重新评估其基线边界。
- **2026 OSDI**：[[Helmsman-OSDI26]] 以生产大 top-k 证明 clustering 可在多 SSD 上胜过串行图；[[FlowANN-OSDI26]] 则证明解耦图依赖后仍能保留 graph search 的优势。

## 相关概念

- [[Vector-Search]]
- [[HNSW]]
- [[Approximate-Nearest-Neighbor-Search]]
- [[Graph-Search]]
- [[NVMe]]

## 相关论文

- [[Helmsman-OSDI26]] — 生产大 top-k 下对 DiskANN/Starling/PipeANN 的系统性反例
- [[FlowANN-OSDI26]] — 图依赖解耦与 GPU/CPU 分层执行
- [[OdinANN-FAST26]] — 动态更新导向 ANN
- [[LEANN-MLSys26]] — 内存高效 ANN
- [[PIMANN-ATC25]] — 近存硬件映射
- [[Terminus-MLSys26]] — ANN 执行边界
