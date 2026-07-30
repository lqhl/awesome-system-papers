---
type: concept
aliases: [GC, Storage-Garbage-Collection]
last_updated: 2026-07-18
tags: [storage, reclamation, compaction, write-amplification]
---

# Garbage Collection

> 存储垃圾收集回收陈旧或无法访问的数据占用的物理空间；在日志结构和闪存支持的系统中，它与写放大、碎片和前台延迟密不可分。

## 核心思想

与语言运行时 GC 不同，存储 GC 通常会识别过时的范围或段，在必要时迁移实时数据，并将可回收容量返回到文件系统或设备。维护工作与用户 I/O 竞争，并可能触发进一步的设备级重新定位，因此回收策略必须平衡当前的容量压力与未来的写入和读取成本。

## 为什么重要

GC 确定大量追加的系统是否能够维持其宣传的容量和延迟。它将元数据/索引决策与SSD行为联系起来：最小化主机复制的策略仍然会留下设备碎片，而积极的压缩可以以写入放大为代价来减少碎片。

## 关键观察 / 隐含假设

- **观察**：陈旧数据几何很重要。 [[DisCoGC-FAST26]] 使用长的连续陈旧范围进行丢弃，并保留丢弃无法有效回收的片段的压缩。
- **观察**：区域大小和写入顺序约束在 GC 支付的地方发生变化。 [[ZUFS-FAST26]] 将部分问题转移到分区移动存储的主机端主动 GC 上。
- **假设**：可以在不损害前台 SLO 的情况下安排后台维护。 [[PolarStore-FAST26]] 和 [[DOGI-FAST26]] 表明设备和工作负载条件可能会使这一假设变得脆弱。

## 设计空间与取舍

- **复制/压缩 vs 丢弃/重置**：复制实时数据可以整合空间；丢弃/重置避免在陈旧范围和设备语义允许的情况下进行复制。
- **反应式 vs 主动式策略**：反应式 GC 保留短期工作，但存在前台停滞的风险；主动GC会消耗后台资源以避免出现紧急情况。
- **主机与设备回收**：主机知识可以改善布局，而设备固件保留隐藏的磨损均衡和媒体管理约束。

## 引用本概念的论文

- [[DisCoGC-FAST26]] — combines discard and compaction in distributed log-structured storage.
- [[ZUFS-FAST26]] — adds proactive filesystem GC for zoned mobile storage.
- [[DOGI-FAST26]] — relates device behavior to storage-system reclamation.
- [[PolarStore-FAST26]] — treats GC and storage-management policy as coupled controls.
- [[WARP-FAST26]] — evaluates storage behavior involving reclamation paths.

## 已知局限 / 开放问题

- 主机级指标无法完全暴露设备级 GC、磨损或固件队列。
- 策略需要在持续写入压力下进行工作负载感知验证，而不仅仅是稳态微基准。
