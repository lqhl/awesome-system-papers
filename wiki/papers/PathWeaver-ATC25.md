---
type: paper
name: PathWeaver
full_title: "PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search"
authors: [Sukjin Kim, Seongyeon Park, Si Ung Noh, Junguk Hong, Taehee Kwon, et al.]
venue: ATC
year: 2025
tags: [ann, vector-search, multi-gpu, graph-search, cagra]
source_pdf: "[[atc2025-kim.pdf]]"
source_md: "[[atc2025-kim]]"
---

# PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search (ATC 2025)

> **一句话总结**：通过流水线化 path extension + ghost staging + direction-guided selection，让多 GPU graph-based ANNS 在 95% recall 下相对 CAGRA/GGNN 平均加速 3.24×、最高 5.30×。

## 问题

Graph-based ANNS（如 CAGRA、GGNN）是向量数据库主流方案，但现有多 GPU 方案靠 sharding：把数据集随机切片，每个 GPU 独立做查询并取 top-k 再 reduce。这种 query-parallel 设计有三个瓶颈：

1. **scale efficiency 低**：4 GPU 上 Sift-1M 只加速 1.39×（35% 效率），GGNN 也只 1.7×（43%）。每个 query 在每个 shard 都要从头跑，shard 数变多时 total iteration 反而上升
2. **大量随机起点是浪费**：beam search 头几轮就把大多数邻居丢掉，只保留少数优质起点的后代——大量距离计算无用
3. **每次访问邻居开销大**：proximity graph 度数几十，但 80%+ 邻居最终被丢弃，没进 top-k

## 核心方法

**Pipelining-based path extension**：在 sharding 基础上为每个 shard 建到下一个 shard 最近邻的 inter-shard edge（环形单向连接）。query 在 GPU i 完成局部搜索后，把局部 top-k 通过这些 edge 传给 GPU (i+1) 继续搜——相当于把搜索路径跨 shard 延伸，而非每个 shard 从随机点重新搜。inter-shard edge 在建图阶段一次性算好。

**Ghost staging**：解决「第一阶段没有 path extension 收益」的问题。每个 shard 抽样建一个小的 ghost graph 作为辅助层（hierarchical search），先在 ghost nodes 上几步定位接近 query 的高质量起点，再下沉到原图。ghost nodes 充当中心枢纽与高速公路。

**Direction-guided selection**：观察到 80%+ 距离计算最终被丢弃。预处理阶段构建 compressed direction table（存源节点到邻居差向量的 sign bits）。运行时把 query 与当前节点的方向 sign bits 与候选邻居的 direction sign 做匹配，按方向相似度选 top-n 候选，避免对方向偏离的邻居算 L2 距离。最后 30% 迭代为 cool-down 不做 selection 以保 accuracy。

实现基于 CAGRA 的 query-per-threadblock 架构、warp 大小 threadblock。深度细节回 [[atc2025-kim]]。

## 关键结果

- 95% recall 下相对 SOTA multi-GPU ANNS 平均 3.24× geomean、最高 5.30× 加速
- Sift-1M 4 GPU 上从 sharding 的 35% scale 效率显著提升
- inter-shard edge 构建为一次性开销，可跨多次搜索复用
- direction table 几乎不损失 accuracy 而显著降低距离计算次数

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[Graph-Index]]、[[Beam-Search]]
- **同类系统**：CAGRA（NVIDIA 单 GPU graph ANNS）、GGNN（多 GPU 分片 ANNS）、HNSW
- **同会议**：[[ATC-2025]]
