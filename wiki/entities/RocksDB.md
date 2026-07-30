---
type: entity
kind: tool
aliases: [Rocks-DB]
status: active
last_updated: 2026-07-18
tags: [storage, kv-store, lsm-tree, benchmark]
---

# RocksDB

> RocksDB 是一个 LSM 树键值存储，在此语料库中既充当可部署的存储引擎，又充当研究压缩、缓存、I/O 路径和设备感知优化的基线。

## 是什么

RocksDB 将 LSM 树设计转变为具有预写日志记录、内存表、排序文件、压缩、块缓存和可插拔存储行为的可配置引擎。它的配置和工作负载组合会对观察到的性能产生重大影响，因此它可用作系统基线，但不能作为单个固定比较点。

## 关键观察 / 隐含假设

- **观察**：压缩和设备行为共同决定写入和尾部延迟成本。 [[DOGI-FAST26]] 和 [[RASK-FAST26]] 使用 RocksDB 相关工作负载来公开此交互。
- **观察**：数据和元数据放置可以在不改变应用程序界面的情况下改变瓶颈。 [[DecouKV-ATC25]] 和 [[MlsDisk-FAST26]] 研究此类存储路径选择。
- **假设**：基准配置代表部署行为。 [[HotRAP-ATC25]] 和 [[UnICom-FAST26]] 说明了为什么工作负载分配和 I/O 模式需要明确的边界。

## 演进时间线

- 2025 ATC：[[DecouKV-ATC25]] — explores decoupled KV-storage paths.
- 2025 ATC：[[HotRAP-ATC25]] — examines storage behavior under application workload constraints.
- 2026 FAST：[[DOGI-FAST26]] — connects LSM/KV behavior with storage-device mechanisms.

## 相关概念

- [[LSM-Tree]]、[[Garbage-Collection]]、[[Write-Amplification]]、[[NVMe]]

## 相关论文

- [[DOGI-FAST26]] — device-aware storage evaluation.
- [[RASK-FAST26]] — storage-system mechanism under KV workloads.
- [[DecouKV-ATC25]] — decoupled data and metadata paths.
- [[MlsDisk-FAST26]] — storage placement and engine behavior.
