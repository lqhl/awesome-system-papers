---
type: paper
name: Terminus
full_title: "When Enough is Enough: Rank-Aware Early Termination for Vector Search"
authors: [Jianan Lu, Asaf Cidon, Michael J. Freedman]
venue: MLSys
year: 2026
tags: [vector-search, rag, ann, disk-io, early-termination]
source_pdf: "[[45c48cce2e2d7fbdea1afc51c7c6ad26.pdf]]"
source_md: "[[45c48cce2e2d7fbdea1afc51c7c6ad26]]"
---

# When Enough is Enough: Rank-Aware Early Termination for Vector Search (MLSys 2026)

> **一句话总结**：Terminus 用 rank-weighted per-I/O utility 动态终止磁盘 ANN 搜索，在 Starling 上相对无早停基线吞吐最高 **3.2×**、相对现有早停 **1.4×**，RAG 准确率影响极小。

## 问题

磁盘驻留 graph ANN（DiskANN/Starling）受 IOPS 限制，每 query 数十至数百随机读。搜索常在已找到 top-ranked 结果后仍继续 I/O 以完善 tail，而 RAG 准确率主要由前几位文档主导（top-20 饱和后增益有限）。传统 Recall 不反映 rank 重要性。

## 核心方法

**Rank-aware utility**：每轮 I/O 根据新插入结果在相似度队列中的 rank，用指数衰减权重 $w(r)$ 累加 utility $U_t$，强调高位 rank 改进。

**Dynamic termination**：滑动窗口内连续 I/O utility 低于阈值 ε 则停止，避免固定 I/O 预算的 brittleness。

**Ranked Recall**：按 rank 加权匹配质量的新指标，更贴合 [[RAG]] 类下游。

## 关键结果

- 相同准确率目标：较现有早停方案吞吐 **1.4×**；较无早停 **3.2×**
- top-0/1 结果多在 I/O 3–7 即发现；第 19 名所需 I/O 约为第 0 名 **2×**
- Natural Questions RAG：丢弃第 i 位文档的 normalized accuracy loss 随 rank 急降

## 相关

- **相关概念**：[[KV-Cache]]
- **同类系统**：DiskANN、Starling
- **同会议**：[[MLSys-2026]]