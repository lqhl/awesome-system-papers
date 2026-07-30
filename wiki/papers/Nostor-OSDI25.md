---
type: paper
name: Nostor
full_title: "Stripeless Data Placement for Erasure-Coded In-Memory Storage"
authors: [Jian Gao, Jiwu Shu, Bin Yan, Yuhao Zhang, Keji Huang]
venue: OSDI
year: 2025
tags: [erasure-coding, in-memory-storage, rdma, key-value-store, fault-tolerance]
source_pdf: "[[osdi25-gao.pdf]]"
source_md: "[[osdi25-gao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Nostor：用于纠删码内存存储的无条带数据放置（OSDI 2025）

> **原题**：Stripeless Data Placement for Erasure-Coded In-Memory Storage

> **一句话总结**：Nostor 用 SBIBD 决定 primary→backup 亲和、节点独立 XOR parity，去掉 stripe 放置开销；在真实 workload 上吞吐为 stripe 方案 **1.61×–2.60×**、延迟相近或更低，内存比主备复制少 **18.7%–57.4%**，最差 degraded read 慢 **35%–62.4%**。

## 问题与动机

[[RDMA]] 内存 KV 需容错但复制贵。传统纠删码依赖 **stripe**：intra-object 拆 chunk 导致高 fanout（小对象也要碰 k 节点）；inter-object 需 MDS 或静态 hash，空 chunk 浪费内存。快内存上「决定对象属于哪条 stripe」本身成为瓶颈。

## 关键观察 / 隐含假设

- **观察 1**：去掉 stripe 后，每节点可把本地 chunk 复制到 backup 并 XOR 成 parity，写路径极大简化；关键是 backup 亲和必须避免「两 primary 共享同一 backup 集」导致双失败不可恢复。
  - **依赖假设**：(v,k,λ=1) SBIBD 存在且参数适配集群规模。
  - **可能失效场景**：v 不满足 SBIBD 构造条件时需换参数或近似。
- **观察 2**：in-memory 小对象普遍（~80% <1KB），intra-object stripe 的 k 路 fanout 尤其亏。
  - **依赖假设**：workload 以独立对象 PUT/GET 为主，非大 blob 顺序条带。
  - **证据强度**：强——与 Cocytus/EC-Cache 等对比。
- **假设 1**：XOR parity 足够，重建读 ≤k 块，与 RS 类似 amortized 成本。
  - **证据强度**：中——fault tolerance 有证明，degraded path 更贵。

## 核心方法

**Nos 方案**：参数 (k,p)——每数据复制 p+2 份（1 primary + p+1 backup）；每节点 XOR k 个 replica 成一个 parity；亲和矩阵为 SBIBD（任意两行至多 1 列同为 1）。

**Nostor**：Rust 实现分布式 KV，RPC over RDMA；versioning 保证一致性与修复。

## 设计取舍

- **取舍 1**：放弃 RS 线性组合，换 XOR 简单与 stripeless 放置。
- **取舍 2**：degraded read 可能读更多无关对象换正常路径吞吐。
- **边界条件**：最坏 degraded latency +35%–62.4% vs 传统 EC。

## 实验与结果

- 真实 workload：吞吐 1.61×–2.60× vs stripe baselines；延迟相似或更低。
- 内存：比 primary-backup 复制少 18.7%–57.4%，性能常相当。
- 节点修复时间 -16.4%。
- degraded read worst case 更差（见上）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Avoiding in-path MDS improves synthetic throughput | dummy MDS lowers GET 89.2% and PUT 72.4% (§6.2.4, Fig.7) | centralized no-work MDS isolates in-path service only | high |
| Stripeless placement helps small reads | ≤256B GET 3.92×/6.06× Split at k=4/6 (§6.2.1, Fig.3) | 50M-key Zipf CloudLab microbenchmark | high |
| Traced workload throughput improves over evaluated EC designs | 1.61–2.60× on four Twitter traces (§6.3, Fig.9–10) | 16 CloudLab nodes, selected traces, Cocytus/PQ/Split comparisons | high |
| Memory use is lower than replication in tested configurations | Repl 1.23–2.35× Nostor memory (§6.5, Fig.12) | 50M objects, listed EC configurations | high |
| Recursive degraded reads expose worst-case tradeoff | (6,3) 35.0% above Cocytus, 62.4% above Split (§6.4.2, Fig.11b) | 64B reads and deliberately chosen failure placement | high |

## 批判性分析

### 论证链条

stripe 放置开销 → stripeless + SBIBD 保恢复 → Nostor 工程化 → 吞吐/内存 win。链条在评测 KV workload 闭合；非 KV 大对象场景未claim。

### 假设压力测试

- 节点数变化需重新构造 SBIBD；动态扩缩容论文需细读。
- XOR 非 MDs 级灵活纠删，某些云偏好的 RS 策略不兼容。
- degraded tail 对 latency-SLO 服务可能是硬伤。

### 实验可信度

开源 Rust 实现可复现；baseline 含 Cocytus 等。worst-case degraded 诚实报告。

### 系统性缺陷

论文未讨论：跨 rack 故障域与 SBIBD 映射运维、与 disaggregation 内存池整合。

## 局限与后续工作

- **局限 1**：degraded read tail 明显变差。
- **局限 2**：SBIBD 参数与集群规模耦合。
- **Future work 1**：hybrid stripeless+stripe 自适应对象大小。
- **Future work 2**：与 [[Disaggregation]] 内存 tier 协同编码。

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]
- **同类系统**：Cocytus、Ceph、EC-Cache、Hydra
- **同会议**：[[OSDI-2025]]
