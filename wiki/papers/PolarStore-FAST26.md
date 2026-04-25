---
type: paper
name: PolarStore
full_title: "PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases"
authors: [Qingda Hu, Xinjun Yang, Feifei Li, Junru Li, Ya Lin, et al.]
venue: FAST
year: 2026
tags: [cloud-database, compression, computational-storage, polardb, hardware-software-codesign]
source_pdf: "[[fast2026-hu.pdf]]"
source_md: "[[fast2026-hu]]"
---

# PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases (FAST 2026)

> **一句话总结**：阿里云 PolarDB 的双层压缩共享存储：软件层把 16 KB DB 页压成 4 KB 对齐块（保留算法/输入大小灵活性），硬件层 PolarCSD（计算存储盘）再把 4 KB 块压成字节级，借 FTL 实现字节级索引而无软件开销；已部署 1000+ 服务器、100+ PB，压缩比 3.55，存储成本降 60%，性能与未压缩集群持平。

## 问题

云原生 RDBMS（AWS Aurora、Azure Hyperscale、PolarDB）在存算分离架构下，存储成本成为用户主要支出。现有压缩方案陷入两难：软件压缩（B+-Tree 内嵌 / LSM-Tree / log-structured 块存储）灵活但索引粒度粗（4 KB 浪费 80.5% 空间）或 GC 开销大；硬件压缩（in-storage [[CSD]]、PCIe FPGA、Intel QAT）性能好但被 4 KB [[NVMe]] 输入和固化算法束缚，无法对冷热数据用不同压缩参数。此外大规模部署（每机 10–12 块 PolarCSD）暴露主机稳定性与集群空间利用率两个新挑战。

## 核心方法

**双层压缩 + DB 优化 + 大规模部署经验**：

- **双层压缩**：软件层用 lz4/zstd 把 16 KB 页压到 4 KB 对齐块，维护简单的 hashtable 索引和 bitmap allocator；PolarCSD 硬件层在 [[FTL]] 中扩展 8-byte 映射条目（增加 12-bit length + 12-bit offset），把 4 KB LBA 映射到字节级 PBA，压缩算法 hardcode 为 gzip level 5。整盘 7.68 TB 逻辑容量配 3.2 TB NAND（压缩比 2.4 兜底）。
- **DB-oriented 优化**（绕开关键 I/O 路径上的压缩开销）：
  - **Opt#1 redo log 旁路压缩**：用独立 Intel Optane SSD 写 redo log，no-compression flag + 高性能存储双绕过。
  - **Opt#2 lz4/zstd 自适应选择**：在双层压缩里 zstd 优势从 58.9% 缩到 9.0%（硬件 gzip 已对 lz4 输出做 Huffman），所以 page-level 决策——若 zstd 节省的 4 KB I/O 数 / 多花的 µs > 300 B/µs（约等于 4 KB I/O 的 12–14 µs / 4096 B），选 zstd，否则 lz4。
  - **Opt#3 per-page log**：利用 CSD 物理-逻辑空间解耦，给每个 16 KB 页预留 4 KB 稀疏 log 空间，把分散的 redo log 合并写入单个 4 KB，page consolidation 一次 I/O 完成，P95 延迟降 28.9–39.5%。
- **PolarCSD 2.0 + 调度优化**：1.0 用 host-based open-channel FTL 导致 CPU/内存争抢和故障域扩大（18 个月 26 次 slow I/O），2.0 改回 device-managed FTL、L2P 条目压到 7 byte（offset 粒度从 1 B 改 16 B）；集群级用 compression-ratio 感知调度算法，按四象限迁移 chunk 平衡逻辑/物理空间。

## 关键结果

- 生产部署 1000+ 服务器（PolarCSD 1.0）+ 1200+ 服务器（PolarCSD 2.0），管理 100+ PB。
- C2 集群（PolarCSD 2.0 + 双层压缩）压缩比 3.55，单 GB 成本降至 P5510 baseline 的 0.37（约 60% 降本），Sysbench 性能与无压缩 N2 持平；C1（仅硬件压缩）压缩比 2.35，性能下降 10%。
- PolarCSD 2.0 比 1.0 大于 4 ms 的尾延迟比例降低 36.7–38.8×。
- 算法选择机制：lz4/zstd 比例随数据集差异显著（金融 73% zstd vs F&B 41% zstd）。

## 相关

- **相关概念**：[[CSD|Computational Storage Drive]]、[[FTL]]、[[NVMe]]、[[LSM-Tree]]、page compression
- **同类系统**：AWS Aurora、Azure Hyperscale、InnoDB table compression、MyRocks、Pangu
- **同会议**：[[FAST-2026]]
