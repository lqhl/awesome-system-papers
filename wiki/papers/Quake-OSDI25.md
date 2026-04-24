---
type: paper
name: Quake
full_title: "Quake: Adaptive Indexing for Vector Search"
authors: [Jason Mohoney, Devesh Sarda, Mengze Tang, Shihabur Rahman Chowdhury, Anil Pacaci, et al.]
venue: OSDI
year: 2025
tags: [vector-search, ann, adaptive-indexing, numa, rag]
source_pdf: "[[osdi25-mohoney.pdf]]"
source_md: "[[osdi25-mohoney]]"
---

# Quake: Adaptive Indexing for Vector Search (OSDI 2025)

> **一句话总结**：Quake 在 partitioned ANN 索引上引入由成本模型驱动的在线 split/merge 维护 + 按查询自适应设置 nprobe + NUMA-aware 并行查询，在动态倾斜负载下查询延迟比 HNSW/DiskANN/SVS 低 1.5–13×、更新延迟低 18–126×。

## 问题

向量搜索（[[RAG]]、推荐、语义搜索的基础设施）的实际负载是**动态且倾斜的**：查询集中在热门实体，插入/删除也成 burst（新 Wikipedia 页、季节性商品、滚动 embedding 版本）。现有 ANN 索引分两派，都适配不好：

- **Graph 索引**（HNSW、DiskANN、SVS）：静态负载下 recall/latency 都好，但更新每次要 rewire 多条边，更新延迟比 partitioned 高几个量级。
- **Partitioned 索引**（Faiss-IVF、SCANN、SPANN、SpFresh）：更新便宜（只追加/剔除 vector），但固定 nprobe 面对分布漂移时要么 recall 掉、要么扫描过量；热分片会让 skewed 负载下延迟恶化；查询延迟本身也比 graph 索引高一个量级（MSTURING10M 上 Faiss-IVF 44 ms vs HNSW 6.8 ms）。

## 核心方法

Quake 是 partitioned 索引，围绕三个设计支柱解决上述痛点：

**1. 成本模型驱动的自适应维护**：每个 partition 有 size $s_{l,j}$ 和访问频率 $A_{l,j}$。partition 成本 $C_{l,j} = A_{l,j} \cdot \lambda(s_{l,j})$，其中 $\lambda$ 是离线标定的扫描延迟函数。总成本就是所有 partition 之和。维护动作（split / merge / add level / remove level）按 $\Delta C < -\tau$ 准入。split 会把 k-means 应用到热/大 partition，再在邻域做 refinement（参考 SpFresh/LIRE）防止重叠。作者证明 bottom-up 的 estimate–verify–commit 流程保证成本单调下降、收敛。

**2. Adaptive Partition Scanning (APS)**：每个查询在运行时估计当前 recall，当估计超过目标就提前终止。估计结合（a）partitioning 的几何关系和（b）目前已 top-k 的中间结果。这绕过了 LAET（需要离线训）、SPANN（需要手调阈值）、Auncel（估计过保守）的问题，能随索引结构变化在线调整。

**3. NUMA-aware 查询**：partition 分布到不同 NUMA node；查询用 affinity-based 调度 + 同 NUMA node 内的 work stealing 来饱和内存带宽——因为 partitioned 向量搜索本质是内存 bound。

作者还贡献了评测 infra：基于 Wikipedia 103 个月的 pageview + 内容演化生成 **WIKIPEDIA-12M** 动态负载，以及一个可配置读/写 skew 的工作负载生成器。

## 关键结果

- 动态负载上查询延迟比 HNSW/DiskANN/SVS 低 **1.5–13×**，更新延迟低 **18–126×**
- 与 SVS/DiskANN/HNSW/SCANN 比，总体查询延迟低 1.5–38×、更新低 4.5–126×
- APS 的 nprobe 选取与 oracle 相近，仅比 oracle 高 17–29% 延迟，且不需要离线调参
- MSTURING100M 上 NUMA-aware 查询比单线程快 **20×**、比非-NUMA-aware 快 **4×**，带宽近线饱和

## 相关

- **相关概念**：ANN (approximate nearest neighbor)、k-means clustering、IVF、graph index、proximity graph、[[NUMA]]
- **同类系统**：Faiss-IVF、HNSW、DiskANN、SVS、SCANN、SPANN、SpFresh、DeDrift
- **应用场景**：[[RAG]]、推荐系统、语义搜索
- **同会议**：[[OSDI-2025]]
