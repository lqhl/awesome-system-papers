---
type: paper
name: WSBuffer
full_title: "Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs"
authors: [Yekang Zhan, Tianze Wang, Zheng Peng, Haichuan Hu, Jiahao Wu, et al.]
venue: FAST
year: 2026
tags: [buffered-io, page-cache, ssd, file-system, linux-kernel]
source_pdf: "[[fast2026-zhan.pdf]]"
source_md: "[[fast2026-zhan]]"
---

# Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs (FAST 2026)

> **一句话总结**：高带宽 [[NVMe]] SSD 时代 Linux page cache 把所有写都强行 buffer 在关键路径上反成为瓶颈；WSBuffer 引入 scrap buffer 把小写/非对齐写放进缓冲，把大且对齐的写直接送 SSD，吞吐和尾延迟相比 EXT4/F2FS/BTRFS/XFS 与 SOTA ScaleCache 最多提升 **3.91×** 和 **82.80×**。

## 问题

PCIe5.0 NVMe SSD 写带宽已超 10GB/s，但 Linux 传统 buffered I/O（page cache）三大瓶颈使其无法 scale：(C1) 所有写都过 page cache，分配/查找/LRU/状态维护开销在快盘下显形（direct I/O 实测比 buffered 高 1.10–4.46×）；(C2) page 管理并发受限于 XArray 的非可扩展自旋锁 `xa_lock`，每次脏页状态翻转都要争锁，foreground 写和 background flush 互相阻塞；(C3) partial-page write 必须 read-before-write 把整页填回，延迟比 full-page write 高 1.51–84.37×。已有方案要么继续优化 page cache（[[ScaleCache]]、StreamCache、uncached buffered I/O），潜力受 mem/storage 带宽鸿沟收窄限制；要么部分/完全 bypass page cache（Lustre AutoIO、OrchFS、SPDK），需改应用代码、放弃通用性。

## 核心方法

WSBuffer = scrap buffer + buffer-minimized data access + opportunistic two-stage flush（OTflush）+ concurrent page management。在 [[Linux]] kernel 6.8 上基于 [[XFS]] 实现。

**Scrap Buffer（§3.2）**：新型 page 结构，包含 128B header（counter/segments/SSD-id/tag + 15 个 8B index entries）+ 256KB data-zone（= 2 × 128KB，对齐 8 通道 × 16KB SSD-page，最大化内部并行）。实测 95% 场景下每页 segment 数 < 15。批量分配 32 个 scrap-page，header 与 data-zone 分离布局（4KB headers + 8MB data-zones），避免 page 内跨界访问。写入按 merge-friendly 方式：先直接写 partial-page 再合并相邻 segment，避免 read-before-write，从而**异步**化原本同步的 read-fill 过程。

**Buffer-Minimized Data Access（§3.3）**：写路径阈值（默认 1MB）内的小写全进 scrap buffer；大写按 scrap-page-data-zone 边界（256KB，非 4KB）切成 partial-aligned 部分（进 scrap buffer）和 large-aligned 部分（直送 SSD）。对齐到 256KB 同时实现 file-fragmentation resistance 和 OTflush friendliness。读路径先查 scrap buffer，未命中再走 page cache + SSD page-fault 路径——page cache 因此专注做读，享受现有 folio batch alloc 等优化。数据一致性靠分离 dirty scrap-page / clean memory-page 来保证。

**OTflush（§3.4）**：双阶段。Stage-1 异步把 unfilled scrap-page 的 read-before-write 在 idle SSD 上跑完；Stage-2 把 full scrap-page 按 data-zone 粒度大块 writeback。维护 per-SSD `Bcount` 感知 SSD 忙闲（默认阈值 4MB），避免把 flush 排到忙 SSD 上 head-of-line block 别人。

**Concurrent Page Management（§3.5）**：分离 scrap-page（dirty）和 memory-page（clean）的索引/锁路径，最小化 free 插入、invalid 删除、flush 三者间的锁争抢，缓解 [[XArray]] 全局锁瓶颈。

## 关键结果

- 相比 EXT4/F2FS/BTRFS/XFS 和 SOTA buffered I/O 优化 [[ScaleCache]]，吞吐最多 **3.91×**、延迟最多 **82.80×** 改善。
- 与 page cache 优化方向**正交**——可与现有改进组合。
- 实现完全保留 buffered I/O 的 POSIX 语义和 alignment-free 编程接口，无需改应用代码。
- WSBuffer 节省下来的内存可被 page cache 用作纯读缓存，进一步加速读。

## 相关

- **相关概念**：[[Page-Cache]]、[[Buffered-IO]]、[[Direct-IO]]、[[NVMe]]、[[XArray]]
- **同类系统**：[[ScaleCache]]、StreamCache、Lustre AutoIO、OrchFS、SPDK
- **同会议**：[[FAST-2026]]
