---
type: paper
name: WOLVES
full_title: "Fast and Synchronous Crash Consistency with Metadata Write-Once File System"
authors: [Yanqi Pan, Wen Xia, Yifeng Zhang, Xiangyu Zou, Hao Huang, Zhenhua Li, Chentao Wu]
venue: OSDI
year: 2025
tags: [persistent-memory, file-system, crash-consistency, storage]
source_pdf: "[[osdi25-pan.pdf]]"
source_md: "[[osdi25-pan]]"
---

# Fast and Synchronous Crash Consistency with Metadata Write-Once File System (OSDI 2025)

> **一句话总结**：WOFS 把每个文件操作打包成带 checksum 的 package 一次写入（单个 ordering point），PM 文件系统 WOLVES 实测可吃到 97.3–99.1% PM 写带宽，RocksDB 吞吐比现有 PM FS 高 1.20–6.73×。

## 问题

持久内存（PM）——Intel Optane、CXL-SSD——让 PM 文件系统有望提供同步 crash consistency：每个操作返回即持久，免 fsync，可大幅简化上层（DB、NFS）的持久性逻辑。但现有两类 crash consistency 方案在 PM 上都漏了：

- **带额外写的方案**（journaling FS 如 PMFS、带事务 checksum 的 SplitFS）：需要 `D → JM → JC → M`，多次元数据写和有序 commit block。
- **无额外写的方案**（log-structured FS 如 NOVA、synchronous soft update 如 SquirrelFS）：要在多个 metadata 对象上做严格有序更新（inode、dentry、log entry/tail …），产生很多小、随机、有序的元数据 I/O。

动机测量显示：PMFS/SplitFS/NOVA 在 6 个基准上花在 crash-consistency 相关 metadata I/O 的时间占总 I/O **22.9%–97.4%**；持久缓冲区（如 XPLine）256B 粒度与小 metadata 不匹配导致 2.8× I/O 放大；这些因素把 PM 实际带宽压在理论值的不到 50%。

## 核心方法

论文提出 **Metadata Write-Once File System (WOFS)** 模型——每个文件操作生成一份专属、自包含的 metadata package（带 CRC32 checksum 和 type/timestamp 头），整包用一次 `PCOMMIT` 写下，单个 ordering point（数据操作为 `D → JM|JC`，纯 metadata 操作只有 `JM|JC`）。

为落地这一模型，WOFS 引入五件组件：

1. **原子 package 设计**：CRUD 归纳出 4 种原子包——create pkg (256 B)、write pkg (64 B)、attr pkg (64 B)、unlink pkg (64 B)。复合操作（如 rename = link+unlink）用 forward-pointer 串起子包实现 crash consistency。
2. **Package Translation Layer (PTL)**：解析 packages 组装成传统 metadata 对象（inode table、data list、dent list），保持对 Linux 文件/目录抽象的兼容。
3. **非 log 布局 + reuse GC**：不再强制 copy-GC，按 causal order 判定过时 package 回收其空间。
4. **Coarse Persistence (CP) 快速恢复**：把 package 组成 4 KiB pkg-group，把 pkg-group 地址及时持久到一个 bitmap（开销约 0.012% PM 空间），重启时扫 bitmap 定位 packages 后再重建 PTL，避免扫全盘。
5. **PM 细节优化**：huge allocation + read-ahead，提升顺序 I/O 吞吐。

原型 **WOLVES**（12,000+ LoC，Linux 5.1 kernel）在 Intel Optane PM 上实现，并 port 到模拟 memory-semantic SSD 平台验证通用性。

## 关键结果

- 写密集 benchmark 达到 **97.3–99.1% PM 写带宽**上限
- RocksDB 实测吞吐相比 PMFS/NOVA/SplitFS 等 PM FS 高 **1.20–6.73×**
- 元数据 I/O 数从其他方案的 ≥2–N 次降至约 **1 次**；ordering point 降至 **1**
- 同时保留 causal order 的 crash safety 语义，可从崩溃恢复并通过基准测试验证正确性

## 相关

- **相关概念**：persistent memory、crash consistency、journaling、log-structured file system、soft update、[[CoW]] (copy-on-write)、checksum transaction
- **同类系统**：PMFS、NOVA、SplitFS、SquirrelFS、ext4 journal
- **相关硬件**：Intel Optane PM、CXL-SSD
- **同会议**：[[OSDI-2025]]
