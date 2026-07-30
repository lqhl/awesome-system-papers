---
type: concept
aliases: [EC, Erasure-Code]
last_updated: 2026-07-18
tags: [storage, reliability, distributed-systems, coding]
---

# Erasure Coding

> 纠删码将数据存储为编码片段，以便子集可以重建原始对象，相对于完整复制提高容量效率，同时引入编码、修复、放置和尾部延迟权衡。

## 核心思想

`(k, m)` 样式布局将数据分割为 `k` 数据片段和 `m` 奇偶校验片段；足够的幸存碎片可以重建丢失的数据。系统行为取决于代码选择、片段大小、跨故障域的放置、网络带宽、CPU/加速器编码成本和修复计划。

## 为什么重要

纠删码是一种存储系统机制，而不仅仅是一种容量比率。它改变了写入放大、小写入处理、降低的读取延迟和后台修复流量。结果必须说明故障模型、布局、工作负载以及维修是否共享前台资源。

## 关键观察 / 隐含假设

- **观察**：代码几何和布局与存储管理相互作用。 [[DisCoGC-FAST26]] 在回收陈旧范围时考虑条带对齐。
- **观察**：修复和读取路径在实际部署中可能占主导地位。 [[DRBoost-FAST26]] 和 [[McQueen-FAST26]] 研究可靠性约束下的存储系统机制。
- **假设**：产能节省超过维修和尾部成本。 [[TapeOBS-FAST26]] 和 [[LESS-FAST26]] 表明媒体、工作负载和可观察性边界很重要。

## 设计空间与取舍

- **复制与编码**：编码节省空间，同时增加计算和多片段协调。
- **小写入与条带效率**：部分条带更新会增加读取-修改-写入或缓冲成本。
- **修复带宽与前台SLO**：更快的修复可以应对客户端流量。

## 引用本概念的论文

- [[DRBoost-FAST26]] — reliability/coding storage mechanism.
- [[McQueen-FAST26]] — coded storage evaluation context.
- [[DisCoGC-FAST26]] — stripe-aware reclamation.
- [[TapeOBS-FAST26]] — media/reliability observability boundary.
- [[LESS-FAST26]] — storage-system trade-offs.
