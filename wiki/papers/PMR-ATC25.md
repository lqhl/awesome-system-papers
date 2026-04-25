---
type: paper
name: PMR
full_title: "PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices"
authors: [Wentong Li, Li-Pin Chang, Yu Mao, Liang Shi]
venue: ATC
year: 2025
tags: [mobile, memory-reclaim, android, swap, flash-storage]
source_pdf: "[[atc2025-li-wentong.pdf]]"
source_md: "[[atc2025-li-wentong]]"
---

# PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices (ATC 2025)

> **一句话总结**：通过解耦 page shrinking 与 page writeback 并批量化 unmap，让 Android 内核内存回收吞吐提升 82.8%、应用响应时间降低 43.6%。

## 问题

Android 移动设备内存日益紧张，但内核 memory reclaim 路径性能差：在 12 GB Pixel 6 Pro 上 5 分钟内仍有 26 次 LMKD 进程被杀，回收吞吐稳定在 < 80 MB/s（远低于 UFS 3.1 ~1 GB/s 的写带宽）。瓶颈来自三方面：(1) page shrinking 与 page writeback 串行执行，前者占 55% 时间；(2) shrinking 频繁早退、反复迭代；(3) page-by-page unmap 产生碎片化小写 I/O，无法吃满 flash 内部并行性。

## 核心方法

PMR 在 Linux 内核 mm 子系统插入两个组件：

- **Proactive Page Shrinking (PPS)**：新增 `kshrinkd` 内核线程，独立于 kswapd 提前从 LRU 列表中筛选受害页（标记 `PG_ISOLATED`）放入新维护的 victim page list。配合 `nr_ideal_victim_page`（默认 462 MB ≈ 3 倍单次 swap 量）的 watermark，保证 page writeback 触发时不必等待 shrinking 完成。
- **Storage-friendly Page Writeback (SPW)**：把 unmap 操作按 application 聚合（application-aware unmap），绑定到 big-LITTLE 架构的大核避免抢占；按设备最优 I/O 大小（Pixel 6 Pro 上为 10 MB，Pixel 5 上 1 MB）合并写出，吃满 UFS 内部并行。

PPS 与 SPW 正交于 LRU 替换策略与 ART GC，可与 [[Acclaim-OSDI25|Acclaim]]、Fleet 等正交叠加。深度细节见 [[atc2025-li-wentong]]。

## 关键结果

- 在 Pixel 6 Pro 上将应用响应时间降低 43.6%（vs OriginalMR），与 Fleet 叠加后达 67.4%。
- 峰值 memory reclaim 吞吐从 OriginalMR/Acclaim 的 ~150 MB/s 提升 82.8% 至 ~205 MB/s（Pixel 6 Pro）。
- LMKD 触发次数减少 82%，direct reclaim 次数下降 45%。
- CPU 开销仅增加 5.3%（kshrinkd 占 11.1%，但 kswapd 从 24.31% 降至 14.51%）；flash 写入量增加 12.1%。

## 相关

- **相关概念**：[[Memory-Reclaim]]、[[Swap]]、[[LMKD]]、[[Flash-Storage]]
- **同会议**：[[ATC-2025]]
