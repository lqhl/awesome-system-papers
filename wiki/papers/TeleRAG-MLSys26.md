---
type: paper
name: TeleRAG
full_title: "TELERAG: Efficient Retrieval-Augmented Generation Inference with Lookahead Retrieval"
authors: [Chien-Yu Lin, Keisuke Kamahori, Yiyu Liu, Xiaoxiang Shi, Madhav Kashyap, Yile Gu, Rulin Shao, Zihao Ye, Kan Zhu, Rohan Kadekodi, Stephanie Wang, Arvind Krishnamurthy, Luis Ceze, Baris Kasikci]
venue: MLSys
year: 2026
tags: [rag, llm-inference, ivf, prefetch, kv-cache]
source_pdf: "[[a3f390d88e4c41f2747bfa2f1b5f87db.pdf]]"
source_md: "[[a3f390d88e4c41f2747bfa2f1b5f87db]]"
---

# TELERAG: Efficient Retrieval-Augmented Generation Inference with Lookahead Retrieval (MLSys 2026)

> **一句话总结**：利用 pre-retrieval 与 retrieval 阶段 query 的 IVF cluster 高重叠，在 LLM pre-retrieval generation 时 lookahead prefetch 相关 cluster 到 GPU，GPU+CPU hybrid search；单卡 RTX4090 跑 61GB index + Llama-3-8B，E2E latency **1.53–1.98×**、batched throughput **1.83×**，4 GPU 扩展 **3.8×**。

## 问题

现代 RAG datastore 数十–数千 GB，全放 GPU 挤占 [[KV-Cache]]；CPU retrieval 慢（占 E2E 41–60%）。runtime fetch 到 GPU 则 PCIe 传输成新瓶颈。

## 核心方法

**Lookahead retrieval**：用 user query q_in 预测 retrieval query q_out 所需 IVF clusters，异步 DMA prefetch 与 pre-retrieval LLM 并行。

**Hybrid search**：GPU 搜 prefetched clusters，CPU 补 miss，merge top-k。

**Batch/multi-GPU**：prefetching scheduler 按语义聚类 query 最大化 cluster overlap；cache-aware scheduler 路由 query 到已缓存 cluster 的 GPU。

## 关键结果

- 6 RAG pipeline、Wikipedia 61GB index：单 query latency avg **1.53×**（RTX4090），batch-8 throughput **1.98×**（H100）
- 单 RTX4090（24GB）同时跑 61GB index + 16GB Llama-3-8B
- 4× H200 throughput vs 1 GPU：**3.8×**；prefetch cluster overlap >61.6%（nprobe=256）

## 相关

- **相关概念**：[[KV-Cache]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、Faiss GPU、CPU-offload RAG
- **同会议**：[[MLSys-2026]]