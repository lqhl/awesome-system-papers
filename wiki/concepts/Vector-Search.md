---
type: concept
aliases: [Vector-Search, ANN-Search, Approximate-Nearest-Neighbor-Search]
last_updated: 2026-07-30
tags: [retrieval, ann, indexing, systems]
---

# Vector Search

> 向量搜索（Vector Search）按 embedding 距离检索近邻；系统设计的本质是在召回率、延迟、容量、更新成本与并发之间分配计算、内存、存储和网络预算。

## 核心思想

精确扫描随数据规模和维度线性增长，生产系统通常用 [[HNSW]] 等图索引、IVF/聚类、量化、磁盘分层或加速器缩小候选集，再对候选重排。索引并不只是算法对象：查询依赖链、数据布局、I/O 批量度、构建和更新路径往往决定同一 recall 下的真实吞吐与尾延迟。

## 为什么重要

向量搜索是 RAG、推荐、搜索和广告的共同基础设施。[[Helmsman-OSDI26]] 的数百亿向量生产经验与 [[FlowANN-OSDI26]] 的 GPU 图搜索共同表明，“少算/少读”并不自动等于更快：串行依赖可能让 SSD 空闲，而将图全部放入 GPU 又会碰到容量墙。因而系统结论必须绑定 top-k、recall、更新率、并发和硬件层级。

## 关键观察 / 隐含假设

- **依赖深度和 I/O 并行度与访问量同等重要。** [[Helmsman-OSDI26]] 以批量 cluster scan 利用 12 块 Gen5 NVMe；[[FlowANN-OSDI26]] 则在图中利用 discovery–expansion window 异步取边。
- **动态性会改变最优结构。** [[OdinANN-FAST26]] 把插入、删除与维护成本纳入设计；静态 benchmark 无法代表持续摄取服务。
- **硬件映射能重写瓶颈。** [[PIMANN-ATC25]]、[[LEANN-MLSys26]] 与 [[Terminus-MLSys26]] 分别探索近存计算、内存压缩与执行边界。
- **隐含假设**：benchmark recall/top-k 与下游业务质量一致；若 reranker、过滤器或 query mix 改变，QPS 排名可能反转。

## 设计空间与取舍

- **图、聚类、量化或扫描**：图减少候选但有依赖链；聚类便于批量 I/O但可能过扫；量化省容量却增加近似误差。
- **DRAM、GPU、SSD 或 PIM**：越靠近计算延迟越低、容量越贵；分层方案需要预取、缓存与 placement。
- **静态与可变索引**：离线结构通常质量高；在线更新需要 delta index、tombstone、merge 或周期重建。
- **固定与 learned pruning**：学习策略能适应 query/top-k，但引入 drift、recall violation 与回退机制。
- **平均吞吐与尾部 SLA**：宽批次易提高 QPS，却可能放大单请求等待和热点 cluster 冲突。

## 引用本概念的论文

- [[Helmsman-OSDI26]] — 面向生产大 top-k 的 all-flash 聚类 ANNS，40 台机器替代约 0.35 PB DRAM 资源
- [[FlowANN-OSDI26]] — GPU/CPU 分层图搜索，通过解耦依赖隐藏 host fetch
- [[OdinANN-FAST26]] — update-oriented ANN indexing
- [[LEANN-MLSys26]] — memory-efficient retrieval
- [[PIMANN-ATC25]] — ANN 的硬件放置与近存执行
- [[PathWeaver-ATC25]] — 图搜索系统取舍
- [[Terminus-MLSys26]] — ANN 执行边界
- [[HedraRAG-SOSP25]] — RAG 检索系统中的向量搜索路径

## 已知局限 / 开放问题

- 公开基准很少同时报告过滤、混合读写、P99、构建时间与持续更新放大。
- learned pruning 的 drift 与 rare-query recall 需要在线 canary 和保守回退。
- embedding 升级时全量重建、双版本服务与一致性切换的成本仍常被忽略。
- QPS/$ 结论对 SSD 数量、DRAM 价格、polling CPU 与能耗模型高度敏感。
