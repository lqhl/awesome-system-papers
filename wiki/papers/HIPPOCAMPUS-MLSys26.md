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

Agentic AI 在 observe-plan-act-learn 循环里频繁读写外部记忆。现有 contextual memory（RAG dense vector、knowledge graph、hybrid）插入慢（embed/chunk）、检索慢（vector 相似度占 47–85% 延迟），MemGPT/A-Mem 精度高但 token 成本高，MemoryBank 轻量但 recall 差，没有系统同时占据高精度+低延迟+低 token 成本。

## 核心方法

放弃 embedding-heavy 表征，采用 compression-native 双表征：

1. **Content DWM**：lossless token-ID 序列的比特矩阵，支持 access/rank/select 精确恢复原文。
2. **Signature DWM**：每 token 经 Random Indexing (LSH) 投影为紧凑二进制 signature。
3. **Dynamic Wavelet Matrix**：把静态 Wavelet Matrix 扩展为 append-only，每符号 O(log σ) 增量追加，适合 agent 流式写入。
4. **Hamming-ball 查询**：query signature 在 Signature DWM 上快速过滤，用 metadata 指针 (α, β) 到 Content DWM 精确取回；全在压缩域、bitwise 完成。

## 关键结果

- 端到端检索延迟降最多 **31×**，per-query token 降 **14×**。
- LoCoMo、LongMemEval 精度与 SOTA 持平或更高。
- 线性 scale 随 memory 大小增长。

## 相关

- **相关概念**：Agent Memory、RAG、Locality-Sensitive Hashing、Succinct Data Structure
- **同类系统**：ReadAgent、MemoryBank、MemGPT、A-Mem、MemoryOS、LangChain memory
- **同会议**：[[MLSys-2026]]