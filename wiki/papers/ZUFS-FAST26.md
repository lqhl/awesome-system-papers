---
type: paper
name: ZUFS
full_title: "Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage"
authors: [Jungae Kim, Jaegeuk Kim, Kyu-Jin Cho, Sungjin Park, Jinwoo Kim, et al.]
venue: FAST
year: 2026
tags: [zoned-storage, mobile-storage, ufs, f2fs, android, garbage-collection]
source_pdf: "[[fast2026-kim-jungae.pdf]]"
source_md: "[[fast2026-kim-jungae]]"
---

# Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage (FAST 2026)

> **一句话总结**：把 [[ZNS]] 思想下放到手机 [[UFS]]（即 ZUFS），通过设备端动态写缓冲（ZABM）+ 端到端写序保证 + 主动 GC 三套跨层改造，在量产手机上实现碎片化场景下 2× 写吞吐、Genshin Impact 加载时间降低 14%，是首个在商用旗舰手机（Pixel 10 Pro）上落地的 zoned storage 部署。

## 问题

手机 UFS 容量从 32 GB 飙升至 1 TB 但片上 SRAM 一直停在 1 MB 左右，导致传统 page-level [[L2P-Mapping|L2P 映射]] cache miss 频发，随机读性能不稳定。10,000 部商用手机的统计显示 30% 设备 [[F2FS]] fragmentation level > 0.7，写延迟 99 分位高达 678 ms/MB。JEDEC 2023 标准化 Zoned UFS（ZUFS）：每 zone 强制顺序写、L2P 表只需 zone 级映射（1 TB 设备 8 KB vs CUFS 1 GB）。但商业部署面临三大障碍：(1) 多 open zone 共享 SRAM 写缓冲极易抖动；(2) 移动端激进时钟门控（clock gating）会破坏块层/SCSI/UFS driver 的端到端写序；(3) 大 zone（1056 MB）使 F2FS section GC 一次需迁移大量有效数据。

## 核心方法

整套设计跨越 device firmware → SCSI/UFS driver → block layer → [[F2FS]] → Android framework。

**Zone-Aware Buffer Management (ZABM)**：核心是 Scatter-Gather Buffer Manager (SGBM) 硬件模块，把 SRAM 切成 4 KB slot，为每个 open zone 维护 slot table。ZUFS 顺序写约束让 slot table 退化为线性索引；当某 zone 数据攒够 superpage 即并行 flush 到 NAND。ZABM 仅占控制器 0.4% 面积，相比 ZMS 的 host-side IOTailor 重 kernel 模块更轻量。

**End-to-End Write Ordering**：识别并修补 SCSI core + UFS driver 的 clock gating requeue 路径，确保 power saving 不破坏 zone write locking (ZWL)；同时修复 block layer 多个角落 case。这部分改动已上游到 Linux kernel。

**Proactive GC**：F2FS 引入 7 个新 sysfs knob（如 `gc_no_zoned_gc_percent=60%`、`gc_boost_zoned_gc_percent=25%`、`gc_valid_thresh_ratio=95%`），按 free section 比例动态切换 cost-benefit 与 greedy 算法，背景态主动回收避免 foreground GC 卡用户 I/O。

设计工程化为 Pixel 10 Pro 量产方案，所有改动开源至 Android framework 与 Linux kernel。

## 关键结果

- 碎片化条件下写吞吐 > 2× CUFS，读性能稳定。
- Genshin Impact 校验 + 加载时间降低 14%。
- ZMT (Zone Mapping Table) 1 TB 设备仅需 8 KB SRAM，对比 CUFS 的 ~1 GB 大幅缩减。
- ZABM 硬件开销仅 0.4% 控制器芯片面积。
- 首个 zoned storage 在 commercial 旗舰手机的部署（2025 Pixel 10 Pro 系列）。

## 相关

- **相关概念**：[[ZNS]]、[[F2FS]]、[[Zone-Append]]、[[Garbage-Collection]]、[[L2P-Mapping]]
- **同类系统**：ZMS（host-side IOTailor 路径）、ZNS+、eZNS、ZNSwap
- **同会议**：[[FAST-2026]]
