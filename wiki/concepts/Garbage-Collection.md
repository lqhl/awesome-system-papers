---
type: concept
aliases: [GC, Storage-Garbage-Collection]
last_updated: 2026-07-30
tags: [storage, reclamation, compaction, write-amplification]
---

# Garbage Collection

> 存储垃圾收集（garbage collection，GC）通过识别失效数据、迁移有效数据并回收 segment/zone，决定日志结构系统能否持续提供容量、吞吐与尾延迟。

## 核心思想

GC 的成本由 victim 中有效数据比例、失效范围几何、设备 erase/reset 语义和前后台 I/O 竞争共同决定。回收不是孤立后台任务：它会形成 write amplification、cache pollution、metadata contention，并与文件系统和 SSD firmware 的第二层 GC 互相放大。

## 为什么重要

OSDI 2026 的论文把 GC 扩展到多层资源管理。[[DeLFS-OSDI26]] 将 GC 划入 per-core domain，避免集中锁在 128 核写路径上接棒；[[DGC-OSDI26]]、[[GraCE-OSDI26]] 关注何时、何地回收；[[jwmalloc-OSDI26]] 表明内存 allocator 的 delayed reclamation 也存在类似容量—前台延迟取舍。

## 关键观察 / 隐含假设

- **观察：失效数据的空间连续性决定 discard 是否有效。** [[DisCoGC-FAST26]] 对长连续范围 discard，对碎片范围 compaction。
- **观察：集中式 GC metadata 会在多核上成为前台瓶颈。** [[DeLFS-OSDI26]] 用 per-core ownership 与延迟协调解除全局锁。
- **假设：后台资源可预测。** [[PolarStore-FAST26]]、[[DOGI-FAST26]] 显示 burst 和 device behavior 会破坏这一假设。

## 设计空间与取舍

- **Copy / discard / reset**：复制通用但有写放大；discard/reset 低复制但受范围和设备语义限制。
- **Reactive / proactive**：前者少做无用功却可能 emergency stall，后者平滑 latency 但长期占资源。
- **Global / partitioned ownership**：全局选择质量高；分区设计扩展好但可能局部失衡。

## 引用本概念的论文

- [[DeLFS-OSDI26]] — per-core GC 与日志结构文件系统扩展。
- [[DisCoGC-FAST26]] — discard 与 compaction 的混合回收。
- [[ZUFS-FAST26]] — zoned mobile storage 的主动 GC。
- [[WARP-FAST26]] — FDP hint 与设备 GC/WAF。
- [[Timelock-Drive-OSDI26]] — storage lifecycle 与受控回收。

## 已知局限 / 开放问题

- host 与 device GC 缺乏共享 lifetime/pressure 接口。
- 应建立同时约束 WAF、tail latency、wear 与能耗的可验证 policy。
