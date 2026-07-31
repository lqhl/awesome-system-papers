---
type: entity
kind: tool
aliases: [Rocks-DB]
status: active
last_updated: 2026-07-30
tags: [storage, kv-store, lsm-tree, benchmark]
---

# RocksDB

> RocksDB 是生产级 [[LSM-Tree]] key-value engine；在系统论文中既是可改造 storage stack，也是评测 cache、compaction、I/O path、remote memory 与 device behavior 的标准载体。

## 是什么

RocksDB 组合 WAL、memtable、SSTable、block cache、Bloom filter 与多层 compaction。其性能不是单一常数：key/value size、read/write mix、cache、compression、compaction thread、direct I/O 与 storage device 都会显著改变结果。

因此 RocksDB 适合检验新机制能否进入成熟 engine，但论文必须说明配置与 workload；只报告默认 YCSB throughput 难以代表生产行为。

## 关键观察 / 隐含假设

- **观察：compaction/GC 与前台 I/O 共享 CPU、cache 和 device bandwidth。** [[DOGI-FAST26]]、[[RASK-FAST26]] 从 device-aware path 减少干扰。
- **观察：成熟引擎会依次暴露新的共享瓶颈。** [[SBB-OSDI26]] 用 RocksDB 类 service 检验多核 user-level scheduling，[[DeLFS-OSDI26]] 展示解除一层锁后下一层会接棒。
- **观察：内存和 metadata placement 可不改 API 地改变瓶颈。** [[MAC-OSDI26]]、[[DecouKV-ATC25]] 分别探索 page metadata offload 与解聚 KV path。
- **假设：benchmark configuration 代表目标部署。** cache warmness、compaction debt 与 skew 不一致时，结论可能反转。

## 演进时间线

- 2025 ATC：[[DecouKV-ATC25]]、[[HotRAP-ATC25]] — 解聚路径与 workload-aware placement。
- 2026 FAST：[[DOGI-FAST26]]、[[RASK-FAST26]]、[[UnICom-FAST26]] — device/compaction 与 completion path 优化。
- 2026 OSDI：[[ARCTIC-OSDI26]]、[[Svalinn-OSDI26]] — 用 RocksDB 验证新 storage/reliability 机制。
- 2026 OSDI：[[MAC-OSDI26]] — 加速 Linux page metadata path，RocksDB 是代表性 memory/storage workload。
- 2026 OSDI：[[Xkernel-OSDI26]] — 用可扩展 kernel path 支撑 RocksDB 等真实应用。

## 相关概念

- [[LSM-Tree]]、[[Garbage-Collection]]、[[Write-Amplification]]、[[NVMe]]、[[Key-Value-Store]]

## 相关论文

- [[ARCTIC-OSDI26]] — RocksDB storage workload 的系统验证。
- [[Svalinn-OSDI26]] — 以 RocksDB 检验持久性/可靠性路径。
- [[MAC-OSDI26]] — Linux page metadata acceleration。
- [[DOGI-FAST26]] — device-aware LSM behavior。
- [[UnICom-FAST26]] — completion mechanism 与 KV workload。
