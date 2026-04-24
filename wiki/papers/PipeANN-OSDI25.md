---
type: paper
name: PipeANN
full_title: "Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD"
authors: [Hao Guo, Youyou Lu]
venue: OSDI
year: 2025
tags: [vector-search, ann, ssd, storage, rag]
source_pdf: "[[osdi25-guo.pdf]]"
source_md: "[[osdi25-guo]]"
---

# Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD (OSDI 2025)

> **一句话总结**：打破 best-first 搜索的 compute-I/O 顺序依赖，用推测式流水线搜索在 SSD 图索引上把延迟打到内存 Vamana 的 1.14-2.02×，billion-scale 下比 DiskANN 延迟低 65%、吞吐高 1.71×。

## 问题

高维向量近邻搜索（ANNS）是 RAG、推荐、检索的核心，billion-scale 索引只能放 SSD。基于图的 best-first search（[[DiskANN]]、[[HNSW]] 等）在 SSD 上延迟比内存版 Vamana 高 3-4×。原因是算法与 SSD I/O 特性不匹配：(1) 每个 search step 批量读 top-W 邻居、再探索它们，跨 step 天然有 compute-I/O 顺序依赖，I/O 延迟（tens of µs）是 compute 的 7×，却无法和 compute 重叠；(2) 每个 step 内同步等待 W 个并行 I/O，尾延迟拖慢整批，W=8 时 I/O 流水线只有 76% 利用率，W=32 时仅 58%。在 recall≥0.9 的严苛场景这两个问题尤其致命。

## 核心方法

核心洞察：图索引有多条等效搜索路径（每个点有多个 in-edge），best-first 只是启发式选一条——可以打破它。PipeSearch 基于 "compute-I/O 伪依赖"：每个 step 要读的邻居其实只依赖内存里的 candidate pool，不需要等 ongoing I/O 或 compute 完成。算法把 I/O 和 neighbor exploration 解耦：只要 I/O pipeline 没满就异步发射当前 candidate pool 里最近的未读邻居，exploration 以 best-effort 方式推进，拿到已读邻居就更新 candidate pool。这样 compute 与 I/O 完全 overlap，流水线始终充盈。代价是推测性 I/O 带来 waste，单纯静态 W 下吞吐掉 12-18%。

PipeANN 系统在 PipeSearch 之上解决 latency-throughput 两难：(1) 把搜索分为 approach phase（离目标远，用 in-memory 小图做 entry point 优化，起始 W=4）和 converge phase（接近 top-k，W 动态扩大）——作者发现 I/O waste 随搜索步数递减（后期 candidate pool 里未探索的 top-k 多，推测命中率高）；(2) 限制 missed neighbor 上界——多个 I/O 同时完成时不立刻把 pipeline 填满，而是 "发一个 I/O、探一个邻居" 交替推进，让第 n 次 I/O 由第 $(n-W)$ 次 compute 的信息决定，提升 I/O 精度。

## 关键结果

- SIFT/SPACEV 100M 数据集、recall 0.9 下，延迟为 DiskANN/Starling 的 39.1%/48.5%（平均）；吞吐比各基线高 1.35×
- 比 cluster-based SPANN 延迟低 70.6%（recall 0.9 时）
- billion-scale SIFT1B/SPACEV1B 上 0.9 recall 延迟 0.719/0.578 ms，是 DiskANN 的 35.0%，吞吐 1.71×
- 比内存版 Vamana 延迟仅高 1.14-2.02×（显著收窄内存-SSD 差距）
- 代价：0.99 高 recall 时吞吐略低于 Starling（0.80×），因 Starling 重排了 on-disk graph

## 相关

- **相关概念**：[[Vector-Search]]、[[ANNS]]、[[RAG]]
- **同类系统**：[[DiskANN]]、[[HNSW]]、[[SPANN]]、[[Starling]]
- **同会议**：[[OSDI-2025]]
