---
type: paper
name: LEANN
full_title: "LEANN: A Low-Storage Overhead Vector Index"
authors: [Yichuan Wang, Zhifei Li, Shu Liu, Yongji Wu, Ziming Mao, et al.]
venue: MLSys
year: 2026
tags: [vector-search, ann, rag, storage-efficiency, hnsw]
source_pdf: "[[093f65e080a295f8076b1c5722a46aa2.pdf]]"
source_md: "[[093f65e080a295f8076b1c5722a46aa2]]"
---

# LEANN: A Low-Storage Overhead Vector Index (MLSys 2026)

> **一句话总结**：端侧向量索引不存 embedding，查询时用原 encoder 现场重算，配合两级搜索（PQ 近似+精确重算）+ 高度节点保留图剪枝，把 76 GB 语料的索引从 188 GB 压到 4 GB（50×），RAG 端到端只多 10% 延迟、保持 SOTA 召回。

## 问题

向量索引存储 high-dim embedding + 图元数据，体积常是原数据的 2–3 倍：76 GB Wiki 文本的 HNSW 索引要 188 GB（173 GB 向量 + 15 GB 图），远超个人设备 RAM。

已有压缩方案：
- PQ 极致压缩（35×）把向量压到 5 GB，但量化误差让 RAG 下游准确率掉到比 BM25 还低
- PQ 压不了图元数据（adjacency list 本身占 15 GB，64 邻居 × 4B = 256 B/node）

关键观察：**RAG 端到端延迟被 LLM 生成主导**（4090 上生成 > 20 s，搜索只几十 ms），可以用少量搜索延迟换巨大存储节省。

## 核心方法

两个核心洞见：

**1. Graph-based recomputation**：HNSW 这类 proximity graph 每次查询只访问 O(log N) 个节点，**不存 embedding、查询时用同一 encoder 现算**。配两个优化：

- *Two-level search*：每步先用 PQ approximate distance 填 approximate queue AQ，从 AQ 选 top α% 送去精确重算，更新 exact queue EQ。EQ 用精确距离保证遍历质量，AQ 剪枝掉不必要的重算。比 DiskANN "先 PQ 全搜再 rerank"更鲁棒（高压缩比 PQ 误差大时 rerank 救不回来）
- *Dynamic batching*：放宽 best-first search 的严格依赖，跨多步累积重算节点到固定 batch size（如 64），把 GPU 吃满

**2. High-degree preserving graph pruning**：实测 HNSW 图中一小撮 high-degree "hub" 节点被访问频率远高于 low-degree 节点。Algorithm 3 给 top β%（如 2%）的高度节点保留完整度数 M，其余节点限 m = M/5，保持图连通性的同时显著降边数。

**其他**：
- 分片合并（soft k-means + 分片建图 + 合并）在给定存储预算下建索引，峰值存储可控
- 支持动态插入/删除（soft delete + buffered batch add）
- 在 FAISS 上实现

## 关键结果

- 索引尺寸比传统最多降 **50×**，仅原数据的 **5%**
- 76 GB Wiki → LEANN 索引 4 GB（vs HNSW 188 GB, PQ 20 GB）
- RAG 端到端延迟：23.34 s vs HNSW 20.95 s（+10%），下游准确率 25.5%（与 HNSW 持平，远超 PQ 17.9% 和 BM25 18.3%）
- 1 秒内 top-3 recall 超 90%
- 评估覆盖 NQ / TriviaQA / GPQA / HotpotQA / FinanceBench / Enron / LAION
- 在 32GB RAM 的 4090 和 M1 Ultra 上都能跑（HNSW 直接 OOM）

## 相关

- **相关概念**：RAG、Product-Quantization、HNSW、[[Quantization]]
- **同类系统**：FAISS、DiskANN、HNSW、IVF
- **同会议**：[[MLSys-2026]]