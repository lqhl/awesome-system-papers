---
type: concept
aliases: [Log-Structured-Merge-Tree, Log Structured Merge Tree]
last_updated: 2026-07-18
tags: [storage, indexing, compaction, write-amplification]
---

# LSM-Tree

> LSM-tree 是一种写优化索引，它将更新吸收到可变组件中，并定期合并已排序的不可变组件；它以压缩、空间放大和读放大管理来交换写入路径效率。

## 核心思想

LSM 树不是就地更新磁盘上的搜索树，而是批量写入、刷新排序运行以及跨级别压缩运行。这种设计将小型随机写入转变为较大的顺序工作，但陈旧条目和重叠运行使垃圾收集、压缩调度和读取查找成为系统稳态控制循环的一部分。

该语料库使用 LSM 树作为数据库索引和存储服务内部的元数据机制。其性能不能仅从数据结构推断：设备、缓存、压缩策略、工作负载偏差和服务级别延迟目标决定结果。

## 为什么重要

LSM 树行为将应用程序更新与闪存写入放大和尾延迟联系起来。因此，它是跨层权衡的常见来源：积极的压缩策略可以回收空间并减少读取工作，同时消耗前台带宽；延迟策略可以保持吞吐量，直到垃圾或元数据压力变得严重为止。

## 关键观察 / 隐含假设

- **观察**：stale-range结构影响回收是否可以避免复制实时数据。 [[DisCoGC-FAST26]] 扫描 LSM 元数据以识别可丢弃范围，并将丢弃与低频压缩相结合。
- **观察**：分离数据和元数据路径可以改变LSM瓶颈。 [[DecouKV-ATC25]] 和 [[DOGI-FAST26]] 在系统中使用抽象，使布局或设备行为明确。
- **假设**：压缩策略可以独立于工作负载进行调整。 [[RASK-FAST26]] 和 [[PolarStore-FAST26]] 说明了为什么偏差、缓存行为和设备约束会使这样一个简单的假设无效。

## 设计空间与取舍

- **分级压缩与分层压缩**：更频繁的合并减少了重叠和读取成本，同时增加了写入放大。
- **逻辑回收与物理回收**：元数据可以廉价地标记过时数据，但物理空间可能保持不可用，直到丢弃、压缩或设备GC运行。
- **前台吞吐量与维护工作**：后台压缩可以保护未来的读取和容量，但可能会与用户 I/O 竞争并恶化尾部延迟。

## 引用本概念的论文

- [[DisCoGC-FAST26]] — 使用 LSM 元数据来协调分布式日志结构存储中的丢弃和压缩。
- [[DecouKV-ATC25]] — 研究 KV 存储设计，其数据和元数据路径公开了 LSM 相关的权衡。
- [[DOGI-FAST26]] — connects storage-device behavior with LSM-oriented update and reclamation paths.
- [[RASK-FAST26]] — evaluates storage-system mechanisms under LSM-style workloads.
- [[PolarStore-FAST26]] — treats compaction and storage management as coupled system controls.

## 已知局限 / 开放问题

- 工作负载转移可以比静态压缩启发法更快地改变空间、写入和读取放大之间的平衡。
- 设备级垃圾收集和主机级压缩可以相互放大；端到端的可观察性仍然至关重要。
