---
type: paper
name: Soul
full_title: "Efficient and Scalable Synchronization via Generalized Cache Coherence"
authors: [Yanpeng Yu, Seung-seob Lee, Lin Zhong, Anurag Khandelwal]
venue: OSDI
year: 2026
tags: [cache-coherence, synchronization, disaggregated-memory]
source_pdf: "[[osdi26-yu-yanpeng.pdf]]"
source_md: "[[osdi26-yu-yanpeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 通过广义缓存一致性实现高效可扩展同步
> **原题**：Efficient and Scalable Synchronization via Generalized Cache Coherence

## 问题与动机

在 cache-coherent disaggregated memory 上叠加传统 lock，会重复触发 cache 间通信；5–10 µs 的远端 coherence latency 使真实同步密集型应用最多退化 1000×。绕过 coherence 的独立 lock service 又难以共享优化与硬件资源。

## 关键观察 / 隐含假设

- lock 可视为 cache coherence 在时间和空间上的推广。
- wait queue 与 variable-size cache line 足以表达常见同步语义。
- 假设 coherence substrate 可做小幅协议扩展。

## 核心方法

论文提出 Generalized cache-Coherence Protocol（GCP）：以 wait queue 做时间推广，以可变大小 cache line 做空间推广。[[Soul]] 在解耦共享内存平台实现 GCP，并通过 userspace library 提供标准 lock API；协议正确性经 model checking 验证。

## 实验与结果

在 key-value store、database 等未修改真实应用上，Soul 相对 state-of-the-art lock 在规模扩展时提高性能 1–2 个数量级，storage overhead 少于 8%（§7，图 13）。边界是 page-based cache-coherent disaggregated shared memory。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 分层 lock 的冗余 coherence 是扩展瓶颈 | 真实 workload 最坏退化 1000× | §2.2 | 强 |
| 协议层融合可消除冗余 | 应用性能提升 1–2 个数量级 | §7 | 强 |

## 批判性分析

### 论证链条
抽象统一、协议设计、model checking 和端到端系统形成较完整证据链。

### 假设压力测试
复杂条件变量、事务语义和异构 coherence domain 可能超出 wait queue/line 的表达边界。

### 实验可信度
真实应用与协议验证兼具，但专用 substrate 的硬件成本和跨实现移植性仍需更多证据。

## 局限与后续工作

- 可扩展到更多同步原语、故障容错及 [[CXL|CXL]]/标准 coherence fabric，并验证公平性与 starvation。

## 相关

- [[OSDI-2026]]
- [[Cache-Coherence]]
- [[Disaggregated-Memory]]
