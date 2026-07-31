---
type: concept
aliases: [Hierarchical-Navigable-Small-World]
last_updated: 2026-07-30
tags: [vector-search, ann, graph-index]
---

# HNSW

> HNSW 是分层近似最近邻图索引：上层稀疏图负责远距离导航，底层稠密图负责局部搜索，以较高 DRAM 占用和更新维护成本换取高召回、低延迟。

## 核心思想

HNSW 为每个向量随机分配最高层级，并在各层维护有限度数的近邻边。查询从最高层贪婪下降，到底层后用候选队列扩大搜索；`M`、`efConstruction` 与 `efSearch` 分别控制图度、建图质量和查询探索宽度。它把高维检索转化为不规则的 pointer chasing，因此算法效果强，但性能高度依赖图布局、cache locality 与并行策略。

## 为什么重要

HNSW 是内存型 [[Vector-Search]] 的主流强基线，也是判断新系统究竟在节省容量、降低依赖深度，还是改善更新路径时最常用的参照。[[Helmsman-OSDI26]] 的生产结果尤其说明：HNSW 并非总是绝对最优；当 top-k 很大、数据到十亿级且 DRAM 成本主导时，依赖无关的聚类批量 I/O 可能比图遍历更适合全闪存阵列。

## 关键观察 / 隐含假设

- **图搜索的关键成本不只是访问节点数，还有串行依赖深度。** [[Helmsman-OSDI26]] 指出大 top-k 会让每跳候选达到 1500–4000，SSD 上的逐跳等待难以吃满阵列带宽。
- **容量边界决定图放在哪里。** [[LEANN-MLSys26]]、[[PIMANN-ATC25]] 分别从内存压缩与硬件放置重审图索引；[[FlowANN-OSDI26]] 则利用“发现节点到展开节点”的时间窗异步取边。
- **动态数据会把维护成本提升为一等问题。** [[OdinANN-FAST26]] 关注更新导向索引，说明只报告静态构建后的 recall/QPS 会遗漏持续插入、删除和重建成本。
- **隐含假设**：所选 recall、top-k 和 `efSearch` 能代表应用效用；若过滤条件、查询分布或 embedding 模型变化，最优参数和索引结构都会改变。

## 设计空间与取舍

- **图度与容量**：更多边通常提高导航性与召回，但扩大 DRAM/SSD footprint、建图和更新成本。
- **探索宽度与尾延迟**：增大候选队列提高召回，也放大不规则访存和 P99 波动。
- **全内存、分层或磁盘图**：全内存延迟最低但昂贵；分层/磁盘方案扩大容量，却必须隐藏 PCIe/SSD latency。
- **图索引与聚类索引**：小 top-k、热点图可缓存时 HNSW 很强；大 top-k、多 SSD 并行时 [[Helmsman-OSDI26]] 的批量 cluster scan 更有优势。
- **静态质量与在线更新**：高质量离线图通常构建昂贵；可变索引需要 tombstone、delta graph、merge 或周期重建。

## 引用本概念的论文

- [[Helmsman-OSDI26]] — 生产大 top-k 场景中以 all-flash clustering 反驳“少 I/O 的图必然更快”，成本较 DRAM HNSW 降 90% 以上
- [[FlowANN-OSDI26]] — 解耦图的 discovery–expansion 依赖，在 GPU/CPU 分层中隐藏取边延迟
- [[OdinANN-FAST26]] — 面向持续更新的 ANN 索引
- [[LEANN-MLSys26]] — 内存高效的 ANN 检索设计
- [[PIMANN-ATC25]] — 将 ANN 操作映射到近存计算硬件
- [[PathWeaver-ATC25]] — 图搜索执行与布局取舍
- [[Terminus-MLSys26]] — ANN 执行边界与系统资源权衡
- [[Snary-ATC25]] — 图索引相关的检索系统设计

## 已知局限 / 开放问题

- 缺少统一覆盖 recall、top-k、过滤、更新率、P99 与总建图成本的生产基准。
- embedding/model drift 会同时改变图质量和热点分布，何时局部修补、何时全量重建仍缺少可靠判据。
- 多租户场景中，候选队列与不规则访存带来的 cache/带宽干扰难以隔离。
- HNSW 与聚类、压缩、SSD tier 的混合结构如何自动选择，仍取决于 workload trace 与硬件拓扑。
