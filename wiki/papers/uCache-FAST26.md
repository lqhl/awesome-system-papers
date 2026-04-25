---
type: paper
name: uCache
full_title: "uCache: A Customizable Unikernel-based IO Cache"
authors: [Ilya Meignan-Masson, Masanori Misono, Viktor Leis, Pramod Bhatotia]
venue: FAST
year: 2026
tags: [io-cache, unikernel, mmap, nvme, page-cache]
source_pdf: "[[fast2026-meignan-masson.pdf]]"
source_md: "[[fast2026-meignan-masson]]"
---

# uCache: A Customizable Unikernel-based IO Cache (FAST 2026)

> **一句话总结**：基于 OSv unikernel 把 mmap 风格的 OS 级 IO cache 做成应用可定制（VMA + 策略 hookpoint + uVFS），相对 mmap 提升随机访问吞吐 **55×**，相对 SPDK 仅有 3.5% 平均开销，同时保留文件系统兼容。

## 问题

数据密集型云应用在 IO caching 上长期面临两难选择：用 OS 级 cache（[[mmap]] + page cache）简单但伴随严重的全局锁、TLB shootdown、缺乏应用级控制（POSIX `madvise`/`mlock` 太粗粒度）；用 userspace cache（vmcache、tricache 等基于 [[SPDK]]）性能强、控制细，但实现复杂、与现有文件系统不兼容、不支持远程 object store 这种非 FS 后端。

## 核心方法

uCache 利用 **unikernel** 的单地址空间架构（基于 [[OSv]]）打通 OS 与应用边界，提出三件事：

- **共享 VMA + 策略 hookpoint**：每个 cache region 对应单一 VMA，应用通过 `setPolicy()` 注册回调（`needToEvict`、`chooseEvictionBuffers`、`isEvictable`、`choosePrefetchBuffers` 等），灵感来自 [[eBPF]] 但因 unikernel 无隔离需求所以原生执行无沙箱开销。
- **Lock-free 缓存操作**：用 CAS 在 PTE 上做 page insertion/eviction，eviction 时先 IPI 触发 TLB invalidation 再 CAS 清地址，支持非硬件页大小（4KiB-64KiB Buffer）批量操作。
- **uVFS + uStore 抽象**：解耦 cache 与 IO 后端。提供 NVMe-optimized uStore（zero-copy、per-core queue pair、polling/interrupt 双模），并通过 MiniFS 把控制路径委托给现有 ext4，数据路径绕过 block layer。

三个 use case：mmap drop-in 替换、移植 vmcache 作 DBMS buffer manager（仅删 400 LoC、改 100 LoC）、给 DuckDB 的 Parquet 访问加自定义预取策略。

## 关键结果

- 4KiB 顺序插入吞吐相对 mmap 提升 **55×**（64 线程读），随线程数线性扩展
- NVMe uStore 相对 SPDK 平均仅 3.5% overhead，相对 libaio 提升 50% 平均、最高 150%
- vmcache 移植到 uCache 在 TPC-C 上接近 exmap（118k vs 121k tps），仅 3% 开销，且保持事务安全
- 内存 footprint 仅占物理内存的 1.7%（1TiB 文件、128GiB cache、4KiB Buffer）

## 相关

- **相关概念**：[[mmap]]、[[KV-Cache]]（无关，但同类「应用级 cache 控制」议题）、[[NVMe]]、[[Page-Cache]]
- **同类系统**：[[vmcache]]、[[exmap]]、[[SPDK]]、[[BypassD]]
- **同会议**：[[FAST-2026]]
- **相关 Unikernel 工作**：[[OSv]]、[[Unikernel]]
