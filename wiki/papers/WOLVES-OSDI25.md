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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Fast and Synchronous Crash Consistency with Metadata Write-Once File System (OSDI 2025)

> **一句话总结**：WOFS 把每个文件操作打包成 checksum 保护的 package 一次写入（单个 ordering point），PM 文件系统 WOLVES 实测可吃到 97.3–99.1% PM 写带宽，RocksDB 吞吐比现有 PM FS 高 1.20–6.73×。

## 问题与动机

持久内存（Intel Optane、CXL-SSD）使同步 crash consistency（操作返回即持久）可行，可省上层 fsync。但 JFS 冗余 journal 写、LFS/SSU 多次小随机有序 metadata I/O 占 PM 操作时间 22–97%，放大 XPLine、限制并行——现有 PMFS 在写密集场景达不到 50% PM 带宽上限。

## 关键观察 / 隐含假设

- **观察 1**：PMFS/SplitFS/NOVA 的 metadata I/O 时间常超过 data I/O；随机+有序导致 2.8× I/O 放大与等待（Figure 2）。
  - **依赖假设**：FIO/Filebench 六 workload 代表 PM 上 metadata-heavy 部署；单线程分解可定位瓶颈。
  - **可能失效场景**：大顺序写主导、metadata 占比低的 workload 优势缩小。
- **观察 2**：每个操作一个 package（J_M|J_C 合一）+ 单 ordering point D→package，可比 CK 少 MOrd，比 LFS 少多次 m_i。
  - **依赖假设**：CRUD 四类 atomic package（Create/Write/Attr/Unlink）+ compound forward-pointer 可覆盖 Linux 15+ 文件操作语义。
  - **可能失效场景**：复杂 rename 等需多 sub-package 无 ordering，恢复检测依赖 forward-pointer 完整性。
- **假设 1**：Package Translation Layer（PTL）从 package 流重建 inode/dentry 抽象，用户态/内核 API 兼容传统 VFS。
  - **证据强度**：中；设计完整但 PTL 解析开销与内存占用论文有测量但长期运行未充分展开。

## 核心方法

**WOFS model**：每操作生成带 CRC32 header 的 package，PCOMMIT 一次持久化；数据操作 D→package。

**PTL**：pkg-node（C/A/W-node）组织 inode table、dent list、data extent list。

**布局**：非 log 分配 + reallocation 回收（避免 copy-GC）；coarse bitmap persistence 加速 crash recovery。

**WOLVES**：Linux 内核实现 + huge allocation + read ahead；另移植 emulated memory-semantic SSD。

## 设计取舍

- **取舍 1**：package 化 upend 传统 inode/dentry——换 metadata I/O 次数，增 PTL 复杂度。
- **取舍 2**：compound package 不用 dual-pointer（保 64B cache line 对齐）——反向检测 rename 不完整稍繁。
- **边界条件**：Intel PM 为主评测；ext4 作 SplitFS 底层。

## 实验与结果

- Metadata 占比：PMFS 22.9–76.5%、SplitFS 63.8–97.4%、NOVA 11.3–75.5%（六 workload）。
- WOLVES：FIO 写密集达 PM 带宽 97.3–99.1%。
- RocksDB：吞吐 1.20–6.73× 现有 PMFS（PMFS/SplitFS/NOVA/SquirrelFS 等）。
- Crash recovery：可恢复；coarse bitmap 降恢复随机 I/O。

## Critical Analysis

### 论证链条

「metadata 多对象多序点→操作级 package 一次写→PTL 虚拟传统元数据」动机与 §3 测量互证。相对 CK 的进步（少 ordering）与相对 LFS 的进步（无 GC copy）定位清晰。WOFS 不消除 metadata 字节量，但减少次数与序点——对 PM 放大效应针对性强。

### 假设压力测试

- **已证明**：写密集 benchmark 近饱和 PM 带宽；RocksDB 端到端显著提升。
- **可能失效**：读密集/元数据轻 workload；package 堆积导致空间碎片与 recovery 扫描成本；多 socket PM 扩展性。
- **论文未覆盖**：NFS strict fsync 等上层语义长期验证；与 NOVA-Fortis 等新一代 PMFS 全面对照。

### 实验可信度

I/O path 分解严谨；六 workload 覆盖 micro+macro。部分对比 SquirrelFS 在附录。单线程分解可能高估/低估并发场景。

### 系统性缺陷

PTL 内存与解析 CPU 开销；非 log 布局的空间回收策略生产成熟度未知；compound 操作恢复逻辑复杂；emulated CXL-SSD 与真 PM 行为差异常需复核。

## 局限与 Future Work

- **局限 1**：PTL 与 package 堆积的长期空间/恢复成本。
- **局限 2**：对 metadata-light workload 收益有限。
- **Future work 1**：多核并发 metadata 路径与 PM 带宽扩展测量。
- **Future work 2**：与 byte-granular PM 一致性和上层 DB 集成（免 fsync 承诺）的 formal 边界。

## 相关

- **相关概念**：crash consistency、persistent memory
- **同类系统**：NOVA、PMFS、SplitFS、SquirrelFS、WineFS
- **同会议**：[[OSDI-2025]]
