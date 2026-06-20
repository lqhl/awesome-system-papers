---
type: paper
name: PipeANN
full_title: "Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD"
authors: [Hao Guo, Youyou Lu]
venue: OSDI
year: 2025
tags: [vector-search, ann, ssd, graph-index, diskann]
source_pdf: "[[osdi25-guo.pdf]]"
source_md: "[[osdi25-guo]]"
---

# Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD (OSDI 2025)

> **一句话总结**：PipeANN 利用 best-first 搜索中 compute/I/O 的伪依赖，用 PipeSearch 投机预取 + 动态 pipeline 宽度，十亿级数据集上延迟为 DiskANN 的 **35%**、吞吐 **1.71×**，并逼近内存 Vamana 的 **1.14×–2.02×**（高 recall）。

## 问题与动机

图索引 ANNS（Vamana/DiskANN）在磁盘上比内存慢 3–4×（0.9 recall 时 DiskANN 4.18×）。根因是 **best-first** 强制跨 step 有序 compute→I/O，且每步同步 batch 读，SSD 长延迟无法与 compute overlap，I/O pipeline 利用率仅 ~24%。

## 关键观察 / 隐含假设

- **观察 1**：图搜索有多条收敛路径，不必严格按「当前最优未探索点」顺序；候选池已含 neighbor ID 即可决定下一批读（**伪依赖**）。
  - **依赖假设**：投机读未探索 top-k 邻居不破坏 recall 收敛（实验验证）。
  - **可能失效场景**：极低 recall 或极窄 pipeline 时投机浪费主导。
- **观察 2**：搜索后期候选池 top-k 未探索邻居增多，宽 pipeline 的 I/O waste 下降。
  - **依赖假设**：可动态加宽 pipeline 兼顾早期低延迟与后期高吞吐。
  - **证据强度**：强——PipeANN 动态宽度 vs 静态 PipeSearch。
- **假设 1**：限制 miss neighbor 上界（未读+在读未探索）可防止宽 pipeline 堆积恶化决策。
  - **证据强度**：中——吞吐提升且 latency 牺牲小。

## 核心方法

**PipeSearch**：I/O 管线未满即按候选池最近邻异步读；compute 与 I/O overlap。

**PipeANN**：
- **动态 pipeline 宽度**：随搜索进展加宽。
- **miss neighbor 上界**：多 I/O 完成时交替 explore+issue，防 neighbor 堆积。

## 设计取舍

- **取舍 1**：投机 I/O 换 latency，吞吐仍可能低于贪心 best-first（论文承认）。
- **取舍 2**：主要面向 ms 预算搜索/推荐，非极限吞吐离线建库。
- **边界条件**：远程内存等类似高延迟介质可移植，但需重调宽度策略。

## 实验与结果

- vs in-memory Vamana：延迟 1.14×–2.02×（PipeANN 接近内存）。
- vs DiskANN（十亿级）：延迟 35%，吞吐 1.71×；0.9 recall 至少 70.6% 更低延迟、1.35× 吞吐。
- PipeSearch alone ~50% 延迟于 best-first。

## Critical Analysis

### 论证链条

SSD 长延迟+同步 batch → 伪依赖允许重排 → PipeSearch overlap → 动态宽度+上界 → 接近内存延迟。逻辑与 microbenchmark 分解一致。

### 假设压力测试

- recall 目标极高时投机读 waste 可能上升。
- NVMe 队列深度/多租户磁盘干扰未充分讨论。
- 与 [[RAG]] 端到端（含 embedding）延迟预算耦合未测。

### 实验可信度

SIFT 等标准数据集 + billion-scale；对比 Vamana/DiskANN 直接。缺生产推荐 trace。

### 系统性缺陷

论文未讨论：索引更新与搜索并发、功耗、QL 压缩精度与投机读交互。

## 局限与 Future Work

- **局限 1**：峰值吞吐仍低于严格 best-first。
- **局限 2**：参数（宽度曲线、上界）需 per-index 调优。
- **Future work 1**：与 learned early termination 结合。
- **Future work 2**：disaggregated memory 上的宽度自适应。

## 相关

- **相关概念**：[[RAG]]、Approximate Nearest Neighbor
- **同类系统**：DiskANN、Vamana、HNSW
- **同会议**：[[OSDI-2025]]