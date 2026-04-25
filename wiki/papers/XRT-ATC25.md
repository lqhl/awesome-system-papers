---
type: paper
name: XRT
full_title: "XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors"
authors: [Neel Patel, Mohammad Alian]
venue: ATC
year: 2025
tags: [runtime, accelerator, scheduling, datacenter, cmp]
source_pdf: "[[atc2025-patel.pdf]]"
source_md: "[[atc2025-patel]]"
---

# XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors (ATC 2025)

> **一句话总结**：为 Intel Xeon 这类带片上 accelerator（DSA/IAA/QAT/DLB）的 XMP 设计 worker-centric runtime，用 notification-aware scheduler + software fallback 解决 Yield 模式的无效唤醒和 accelerator 竞争 stall，吞吐比 unoptimized 高 3.2×、对比无加速器系统最高 32×。

## 问题

datacenter 应用大量算力花在 (de)compression、encryption、memcpy、DB query 等 "datacenter taxes" 上。Intel 4/5 gen Xeon XMP 已经把 DSA/IAA/QAT/DLB 集成在芯片上，但现有 runtime（Concord、Shenango、TinyQuanta）都假设请求全程在 GP core 上跑，导致 offload 给加速器后吞吐反而比纯 CPU 还低：Dispatcher-Centric 中央调度器同时管 NIC 和 accelerator 通知会成瓶颈；Worker-Centric 不知道 offload 何时完成、轮询导致大量无效 context switch；accelerator 工作队列满时核会被 stall。

## 核心方法

XRT 是 worker-centric two-level runtime：dispatcher 用 JSQ (Join-the-Shortest-Queue) 仅做 load balancing，请求调度在 worker 端：

- **Notification-Aware Scheduler**：每个 worker 维护两个 ring buffer（Monitoring Set 存 cacheline-sized completion records、Thread Contexts 存 user-thread 指针）。利用 accelerator FIFO 完成顺序，scheduler 只需轮询「下一个预计完成」的 completion record（L1 命中 2-3 cycles），完成后才唤醒对应 thread，消除 baseline 中每请求平均 21 次的无效唤醒（占 13% 端到端时间）。
- **Software Fallback**：用 ENQCMD 指令写 offload descriptor，硬件返回 success/retry。queue 满时直接 fallback 到 core 上的 software 实现，不等也不重试。
- 通过 SVM + IOMMU + per-flow shared work queue 让多核共享 accelerator。

## 关键结果

- 6 个工作负载（DDH、DC、MC、DMD、MMP、UFH）覆盖 (de)compress / memcpy / matmul + PCA / filter + histogram
- 比无优化的 RR-Worker 吞吐高 3.2×，比纯 CPU NoAcceleration 最高 32×
- DDH/DC（带 decompress）都打过 NoAcceleration；DMD/MC（memcpy 类）只有 XRT 能从 offload 中获益（Block&Wait 和 RR-Worker 都不如不加速）
- 永不出现负向（never slowdown vs unaccelerated）
- 在 Intel Xeon 8571N (5th gen, 4× IAA + 4× DSA) 上验证

## 相关

- **相关概念**：[[On-Chip-Accelerator]]、[[Two-Level-Scheduling]]、[[ENQCMD]]、[[DSA]]、[[IAA]]
- **同类系统**：[[TinyQuanta]]、[[Concord]]、[[Shenango]]、[[Shinjuku]]
- **同会议**：[[ATC-2025]]
