---
type: paper
name: DecouKV
full_title: "Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling"
authors: [Qingyang Zhang, Yongkun Li, Yubiao Pan, Haoting Tang, Yinlong Xu]
venue: ATC
year: 2025
tags: [lsm-tree, kv-store, hybrid-storage, persistent-memory, compaction]
source_pdf: "[[atc2025-zhang-qingyang.pdf]]"
source_md: "[[atc2025-zhang-qingyang]]"
---

# Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling (ATC 2025)

> **一句话总结**：把 LSM-tree 的 flush/compaction 解耦成 CPU-bound 的 IndexTable merge + I/O-bound 的 AOF append/flush，配合弹性容量与队列调度，在 PM/SSD 混合盘上写吞吐 2.3–4.9× 于 RocksDB，P99 尾延迟降 74.3%–91.4%。

## 问题

LSM-tree KV 存储（RocksDB / LevelDB）依赖 flush 与 compaction 这种 sorting-based 操作管理 KV pair。在 PM + SATA SSD 等 hybrid storage 上，sorting 操作存在三类耦合：(i) 单个操作内 CPU（merge sort、bloom filter 生成）与 I/O（读写）资源消耗交织；(ii) 操作间存在 level 之间的依赖触发链；(iii) 并发 sorting 操作竞争资源。导致 CPU 与 I/O 利用率交替波动，写停顿严重。MatrixKV / ADOC 等只能缓解部分问题。

## 核心方法

**核心 insight**：在 sorting 操作里 CPU 主要耗在 index sort，I/O 主要耗在 data 读写——把 index 与 data 物理分离即可解耦。

- **数据结构解耦**：data 用 Append-Only File（AOF）存于 fast device，index 用 mergeable skip list 形式的 IndexTable 存于 DRAM。AOF 利用 fast device 的随机访问能力，无需排序；省掉 WAL 与 Bloom Filter。
- **三类解耦任务**：CPU-intensive index merge（多线程并行修改 skip list 指针 + 用 CAS 维护的 Merging Index Set 保证查询正确）、I/O-intensive data append、I/O-intensive data flush（把 IndexTable + AOFs 整理为 SSTable 落到 slow device）。
- **队列调度**：Index Merge Queue（IMQ）和 Data Flush Queue（DFQ）的长度反映 CPU 与 I/O 压力，动态调整 IMTN（merge 触发阈值）和 DFTS（flush 触发 size），CPU-bound 时增大 IMTN、降低 DFTS，反之亦然。
- **Elastic capacity high levels**：放宽高 level 的 size 放大因子，允许临时超出阈值，缓解操作间依赖链。

详见 [[atc2025-zhang-qingyang]]。

## 关键结果

- 写密集 workload：相比 RocksDB / MatrixKV / ADOC / PrismDB / SplitDB，CPU 利用率提升 25.4%–32.3%，吞吐提升 2.3–4.9×，P99 尾延迟降 74.3%–91.4%。
- 读密集 workload：吞吐提升 1.2–2.3×。
- Insert P90 延迟从 RocksDB 9.45ms 降至 1.58ms（约 6×）。

## 相关

- **相关概念**：[[LSM-Tree]]、[[Compaction]]、[[Persistent-Memory]]
- **同类系统**：MatrixKV、ADOC、PrismDB、SplitDB
- **同会议**：[[ATC-2025]]
