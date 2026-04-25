---
type: paper
name: DSA-2LM
full_title: "DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA"
authors: [Ruili Liu, Teng Ma, Mingxing Zhang, Jialiang Huang, Yingdi Shan, et al.]
venue: ATC
year: 2025
tags: [tiered-memory, cxl, intel-dsa, page-migration, kernel]
source_pdf: "[[atc2025-liu-ruili.pdf]]"
source_md: "[[atc2025-liu-ruili]]"
---

# DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA (ATC 2025)

> **一句话总结**：把 Linux 分级内存的页迁移卸载到 Intel Data Streaming Accelerator（DSA），混合 4 KB/2 MB 页自适应批处理 + 多 WQ 并发，比 MEMTIS/TPP/NOMAD 实际应用快 20% / 30% / 16%。

## 问题

CXL/NVM 带来 tiered memory，但 hot/cold 页迁移代价大：MEMTIS 中 73.5% 的迁移 CPU 周期花在 copy；NOMAD 也指出 page copy 是瓶颈。Intel 4/5 代 Xeon 自带 DSA（每设备 32 GB/s，~4 倍单核），可零 CPU 介入做 memory copy，但 (1) 内核现有 DSA 通过 DMA 接口调用，(un)map + buffer 准备 88 ns 远超 DSA 自身 6 ns；(2) DSA 在 < 32 KB 时不如 CPU 快；(3) 实测 78% 内存来自 2 MB Huge Pages（THP）；(4) batch size 与 WQ 数量对吞吐影响巨大（4 WQ 达峰、batch 8 饱和）。

## 核心方法

DSA-2LM 在 Linux 5.13/5.15 实现，约 2K LoC mm 修改 + 8K LoC 后移 IDXD/IOMMU 驱动：

- **Bypass DMA, kernel-direct DSA**：descriptor 用 per-cpu 全局变量避免动态分配；用物理地址绕过 IOMMU pinning。
- **Aggregate data path**：算法对 promote/demote page list 区分处理：每个 2 MB Huge Page 切成 `2MB/limit_chans`（默认 8）份分发到多 WQ 并行；剩余 4 KB 页累积成 batch（按 `nr_base_pages/limit_chans` 均分），每个 WQ 圆 robin 拿一个 batch descriptor 提交；按"短板效应"控制各 WQ 总传输大小差异不超 1 page。
- **真异步等待**：用内核 completion 机制 + idxd_wq_thread MSI-X 中断回调，避免用户态 UMONITOR/UMWAIT 的低响应或 sched_yield 浪费。

继承 MEMTIS 的 PEBS 采样 + 直方图 hotness 检测；因 DSA 释放 CPU 故缩短 kmigrated 唤醒间隔，更激进迁移。代码 https://github.com/madsys-dev/DSA-2LM。深度细节见 [[atc2025-liu-ruili]]。

## 关键结果

- 实际应用（Graph500 / PageRank / XSBench / BTree / Pandas）下相比 MEMTIS / TPP / NOMAD 提升 20% / 30% / 16%（平均），最佳 81.7% / 52.9% / 15.6%。
- copy bandwidth：workload B（1000×4 KB + 24×2 MB）下达 106.3 GB/s，是 CPU/DSA-raw 的 14.38× / 2.19×，已逼近平台峰值 110 GB/s。
- migrate 函数在 perf 中占比从 39.0% 降到 4.24%；Graph500 14.9 s copy 时间降到 1.39 s（9.3%）。
- 1:16 fast/slow 比下平均提升 28%，最高 1.8× 比 MEMTIS。

## 相关

- **相关概念**：[[Tiered-Memory]]、[[CXL]]、[[Page-Migration]]、[[THP]]、[[DMA]]
- **同类系统**：MEMTIS、TPP、NOMAD、AutoNUMA、Nimble、Colloid、NeoMem
- **同会议**：[[ATC-2025]]
