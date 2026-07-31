---
type: paper
name: POEGA
full_title: "Efficient GPU-Centric Evolving Graph Processing at Scale"
authors: [Yunmo Zhang, Jiacheng Huang, Xizhe Yin, Junqiao Qiu, Hong Xu, et al.]
venue: OSDI
year: 2026
tags: [gpu, graph-processing, out-of-core]
source_pdf: "[[osdi26-zhang-yunmo.pdf]]"
source_md: "[[osdi26-zhang-yunmo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 大规模 GPU 中心演化图处理
> **原题**：Efficient GPU-Centric Evolving Graph Processing at Scale

## 问题与动机

演化图分析需要连续处理多个相似度常超过 99% 的 snapshot，但大图超出 GPU memory；直接 out-of-core incremental execution 受 I/O 限制，多版本 vertex state 又吞噬并发所需容量。

## 关键观察 / 隐含假设

- 小型 proxy graph 可保留决定计算结果的关键拓扑。
- 先近似、后精确 refinement 能减少 full-graph I/O。
- 额外计算可由 GPU 并发处理多个 snapshot 摊销。

## 核心方法

[[POEGA]] 先在 resident proxy graph 上产生近似结果并指导 out-of-memory refinement；fused kernel 和 bound-based pruning 并行处理 snapshots，adaptive state compaction 压缩多版本 vertex state。

## 实验与结果

在多种真实 graph dataset 与 EGA query 上，POEGA 相对 state-of-the-art solution 获得 3.7–23.5× speedup；相对通用 GPU data-management technique 平均快 8.9×（§6，图 11）。边界是相邻 snapshot 高相似的演化图。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| proxy-guided refinement 可降低 I/O | 相对通用管理方案平均 8.9× | §6 | 强 |
| snapshot 并发可摊销近似计算 | 端到端最高 23.5× | 图 11 | 强 |

## 批判性分析

### 论证链条
proxy graph 解决 I/O，跨 snapshot 并发补偿计算，state compaction 再解除并发容量瓶颈，设计闭环清晰。

### 假设压力测试
图剧烈变化、proxy fidelity 低或 query 难以给出有效 bound 时，refinement 和额外计算可能放大。

### 实验可信度
真实数据、多 query 和多基线覆盖较好，但 online latency、proxy maintenance cost 与突发更新需单独量化。

## 局限与后续工作

- 可支持分布式多 GPU、动态 proxy 重建、持续流式输入和更复杂图算法。

## 相关

- [[OSDI-2026]]
- [[Graph-Processing]]
- [[Out-of-Core]]
