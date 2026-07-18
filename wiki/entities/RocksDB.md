---
type: entity
kind: tool
aliases: [Rocks-DB]
status: active
last_updated: 2026-07-18
tags: [storage, kv-store, lsm-tree, benchmark]
---

# RocksDB

> RocksDB is an LSM-tree key-value store that serves in this corpus as both a deployable storage engine and a baseline for studying compaction, caching, I/O paths, and device-aware optimization.

## 是什么

RocksDB turns an LSM-tree design into a configurable engine with write-ahead logging, memtables, sorted files, compaction, block cache, and pluggable storage behavior. Its configuration and workload mix materially affect observed performance, so it is useful as a systems baseline but not a single fixed point of comparison.

## 关键观察 / 隐含假设

- **观察**：compaction and device behavior jointly determine write and tail-latency costs. [[DOGI-FAST26]] and [[RASK-FAST26]] use RocksDB-related workloads to expose this interaction.
- **观察**：data and metadata placement can change the bottleneck without changing the application interface. [[DecouKV-ATC25]] and [[MlsDisk-FAST26]] study such storage-path choices.
- **假设**：a benchmark configuration represents deployment behavior. [[HotRAP-ATC25]] and [[UnICom-FAST26]] show why workload distribution and I/O mode need explicit boundaries.

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
