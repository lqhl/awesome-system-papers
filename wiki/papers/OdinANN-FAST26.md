---
type: paper
name: OdinANN
full_title: "OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search"
authors: [Hao Guo, Youyou Lu]
venue: FAST
year: 2026
tags: [vector-search, ann, graph-index, on-disk-index, concurrency]
source_pdf: "[[fast2026-guo.pdf]]"
source_md: "[[fast2026-guo]]"
---

# OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search (FAST 2026)

> **一句话总结**：用 direct insert（一条一条写入 on-disk graph index）取代 [[DiskANN]] 的 buffered insert + merge，配合 GC-free update combining 与 approximate concurrency control，把 search 中位延迟波动从 DiskANN 的 2.44× 压到 1.07×，billion-scale 数据集上同时达 5000 QPS 搜索 + 1100 QPS 插入、~3ms 中位延迟。

## 问题

Billion-scale [[ANNS]] 偏好 on-disk graph index（如 [[DiskANN]]）兼顾性能与成本，但需要支持向量更新。现有方案用 **buffered insert**：内存中维护小索引、定期批量 merge 到磁盘。实测三大问题：

1. **Search 性能波动**：merge 时和前端搜索抢 SSD 读带宽，median latency 飙到 1.54×。
2. **内存爆炸**：merge 3% 向量到 billion-scale index 需 125GB（in-memory index + 缓冲磁盘写）。
3. **Merge 时间长**：吞吐在 3000 QPS 封顶，因为 in-memory merge 阶段对每个新 vector 都要做一次 on-disk ANNS 查邻居，无法 batch。

直接 direct insert 看似自然，但有两大挑战：(a) 单次 insert 更新数十到数百个 neighbor record，in-place 写带来海量随机 SSD 写，log-structured 又要频繁 [[Garbage-Collection]]；(b) insert 与 search 的并发若加锁会触发近根 record 锁争用。

## 核心方法

OdinANN 在 fixed-size record 的 on-disk graph 上做两项关键设计：

**GC-Free Update Combining**（§3.2）：利用 graph record 大小固定的特性，在每个 page 上**预留 free slot**（默认双倍空间）。Insert 时把更新后的 record 写入同 page 的空 slot（out-of-place），原 slot 直接标记为 free 给后续插入复用，无需显式 GC。三条 allocation rule：(1) 优先全空 page；(2) 已读入内存的 page；(3) 内存中含 candidate neighbor 的 page。把多个 record update 合并成一次 page 写，相比 log-structured layout 写放大 2× 但消除 GC。

**Approximate Concurrency Control**（§3.3）：放宽到 per-record 隔离而非 per-operation。Search 只需每条 record 是 consistent snapshot 即可正确；insert 把目标 vector 链接到 approximate neighbor snapshot，缩短临界区。两项额外优化分别针对 disk I/O 和 critical section 内的计算。删除仍用 buffered delete（仅记录 ID，merge 时与 search 干扰小）。Search 用 dynamic candidate pool 在含 delete 的 workload 下保证质量。

底层依然是 [[PQ]]-compressed in-memory vector 用于 graph navigation + on-disk full-precision vector + neighbor list（参考 DiskANN layout）。

## 关键结果

- 100M [[BIGANN]] 数据集并发 insert+search：search median latency 波动 1.07×（DiskANN 2.44×）。
- 相比 cluster-based [[SPFresh]]：median search latency 仅 62.1%，accuracy 高约 15%（图 graph-based 优于 cluster-based）。
- Billion-scale：同时 5000 QPS search + 1100 QPS insert，~3ms 中位延迟。
- 内存使用大幅下降（无 in-memory merge index），适合超大规模场景。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Database]]、[[Graph-Index]]、[[PQ]]、[[Garbage-Collection]]、[[Concurrency-Control]]
- **同类系统**：[[DiskANN]]、[[SPFresh]]、[[HNSW]]
- **同会议**：[[FAST-2026]]
