---
type: paper
name: ScaleSwap
full_title: "ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays"
authors: [Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son]
venue: FAST
year: 2026
tags: [os-swap, ssd, scalability, linux-kernel, many-core]
source_pdf: "[[fast2026-ahn.pdf]]"
source_md: "[[fast2026-ahn]]"
---

# ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays (FAST 2026)

> **一句话总结**：通过把 swap 资源从 all-to-all 共享改造成 one(core)-to-one(resource) 的 core-centric 模型 + 跨核 opportunistic delegation + 每核 LRU 列表，在 128 核 + 8 块 NVMe SSD 上把 Linux swap 吞吐拉到 3.4×、平均延迟降到 1/11.5。

## 问题

Linux swap 子系统设计于单盘时代，采用 all-to-all 模型：所有核可访问任意 swap space，靠 `si_lock`、`lru_lock` 这类全局锁串行化。在 all-flash swap array（多块 [[NVMe]] SSD 拼成的 swap 池）上，这种共享锁结构导致：(1) 多核高并发下 swap metadata（`swap_info`）锁竞争剧烈；(2) 每 NUMA node 一份的 LRU 列表在 direct reclaim 时被所有核抢同一把 `lru_lock`；(3) Linux 仅支持 23 个 swap space，远低于现代多核数。结果是 swap 吞吐随 SSD 数量几乎不增长，128 核时反而比 raw device 慢 2.6×。

随着 ML 训练、图处理、Common Crawl 这类 TB 级内存负载常态化，DRAM/[[CXL]] 扩展成本高（DRAM 单价是 NVMe SSD 的 26×），all-flash swap array 成为性价比极高的最后一层内存兜底，但软件栈跟不上硬件并行度。

## 核心方法

ScaleSwap 的核心是把 swap 资源「去中心化」成 per-core 私有，三个策略：

1. **Core-centric swap resource management**：每核独占 swap metadata、swap cache、swap space（per-core swap file），打破全局 round-robin 分配，绕开 `si_lock`。为支持 > 23 个 swap space，扩展 swap entry 的 `type` 字段从 5 bit 到 8 bit（最多 247 个 swap file），代价是 offset 从 50 bit 缩到 47 bit（仍可寻址 128 TB/file）。
2. **Opportunistic inter-core swap assistance**：当本核 swap space 满或要访问共享页时，通过 per-core delegator + 每核 task queue 把 swap metadata 操作 delegate 给目标核（FIFO 单消费者，天然保序），延迟约 30 ns。delegation 期间引入 cooperative swapping：等待方主动帮自己的 delegator 处理任务队列，避免 spin/sleep 开销。
3. **Core-affinity page & LRU management**：每核独立 LRU list，page 分配时把核号写进 page flag（占用 unused 4 bit + 借 node 字段 3 bit，支持 128 核 / 64 node），swap-in 时按 page flag 回插原核的 LRU。彻底拆掉 `lru_lock` 竞争。

实现于 Linux 6.6.8，开源在 syslab-CAU/ScaleSwap。

## 关键结果

- 128 核 + 8 NVMe SSD 上比 Linux swap 提升 3.4× 吞吐、降低 11.5× 平均延迟
- 比 [[ZNSwap]]/TMO 高 64%，比 ExtMEM 高 5×
- 8 SSD 时 Linux swap 吞吐恒定在约 4 GB/s（不 scale），ScaleSwap 接近 raw device 的 11.2 GB/s
- 在 Apache Spark + Common Crawl 预处理（128 文件 × 300 GB）上避免了 OOM

## 相关

- **相关概念**：[[NVMe]]、[[LRU]]、[[Direct-Reclaim]]、[[NUMA]]
- **同类系统**：[[ZNSwap]]（基于 [[ZNS]] SSD 的 swap）、TMO（Meta 的 transparent memory offloading）、ExtMEM
- **同会议**：[[FAST-2026]]
