---
type: paper
name: HIPPOCAMPUS
full_title: "HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI"
authors: [Yi Li, Lianjie Cao, Faraz Ahmed, Puneet Sharma, Bingzhe Li]
venue: MLSys
year: 2026
tags: [agent, memory, wavelet-matrix, retrieval, succinct-data-structure]
source_pdf: "[[d645920e395fedad7bbbed0eca3fe2e0.pdf]]"
source_md: "[[d645920e395fedad7bbbed0eca3fe2e0]]"
---

# HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI (MLSys 2026)

> **一句话总结**：HIPPOCAMPUS 用 Dynamic Wavelet Matrix (DWM) 把 agent 记忆存为「token-ID 流 + 二进制 signature」双表征，在压缩域做 Hamming-ball 搜索，检索延迟降最多 31×，per-query token 降 14×，对齐 LoCoMo / LongMemEval 精度。

## 问题

Agentic AI（AutoGPT、BabyAGI、ReAct 等）在 observe-plan-act-learn 循环里频繁读写外部记忆。现有 contextual memory 三类（RAG dense vector、knowledge graph、hybrid）有共同瓶颈：

- **插入慢**：要 embed、chunk、summarize；
- **检索慢**：vector 相似度或多跳图查询；ReadAgent 85% 延迟花在检索、MemoryBank 81%、A-Mem/MemoryOS 约一半。
- **Trade-off**：MemGPT / A-Mem 精度高但 latency 和 token 成本高；MemoryBank 轻量但 recall 差。

没有系统同时占据「高精度 + 低延迟 + 低 token 成本」象限。

## 核心方法

放弃 token-centric、embedding-heavy 表征，拥抱 compression-native 数据结构：

1. **双表征**：
   - **Content DWM**：lossless token-ID 序列的比特矩阵，支持 access/rank/select 精确恢复原文；
   - **Signature DWM**：每 token 经 Random Indexing (LSH) 投影为紧凑二进制 signature，同样存 DWM。

2. **Dynamic Wavelet Matrix**：把经典静态 Wavelet Matrix 扩展为 append-only。每新符号 s 做 O(l) = O(log σ) 的逐层 bit 追加，每层位置由 rank 操作递推；避免 agent 流式写入下频繁重建。

3. **Hamming-ball 查询**：query 经同一 random indexing 变 signature，在 Signature DWM 上做 rank/select 找相近 signature 的 co-occurrence，拿 metadata 中 start/end 索引（α, β）再到 Content DWM 精确取回。搜索全在压缩域、bitwise、native CPU 指令可加速。

## 关键结果

- 端到端检索延迟降 最多 **31×**，per-query token 降 **14×**。
- 精度在 LoCoMo、LongMemEval 两个 long-horizon agent benchmark 上与现有 SOTA 持平甚至更高。
- 线性 scale 随 memory 大小增长，适合 long-horizon 部署。

## 相关

- **相关概念**：Agent Memory、RAG (Retrieval-Augmented Generation)、Knowledge Graph、Locality-Sensitive Hashing、Succinct Data Structure、Wavelet Matrix
- **同类系统**：ReadAgent、MemoryBank、MemGPT、A-Mem、MemoryOS、MemOS、LangChain memory、CrewAI memory
- **同会议**：[[MLSys-2026]]
