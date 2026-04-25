---
type: paper
name: UnICom
full_title: "UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems"
authors: [Riwei Pan, Yu Liang, Sam H. Noh, Lei Li, Nan Guan, Tei-Wei Kuo, Chun Jason Xue]
venue: FAST
year: 2026
tags: [io-completion, nvme, kernel, polling, interrupts, ext4]
source_pdf: "[[fast2026-pan.pdf]]"
source_md: "[[fast2026-pan]]"
---

# UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems (FAST 2026)

> **一句话总结**：通过 TagSched（in-queue tag 调度）+ TagPoll（centralized 内核 polling 线程）+ SKIP（per-file extent tree + dynamic NVMe queue）三件套，在低/高 CPU 利用率下都接近最佳 I/O 性能——4KB 读 IOPS 比 ext4 高 **43.5%**、比 BypassD 高 **88.8%**（与 16 个 C-thread 共存时）。

## 问题

高性能 NVMe SSD（µs 级延迟、百万级 IOPS）下软件栈占总延迟约 50%。现有完成机制各有短板：[[Polling]]（如 BypassD）低延迟但 CPU 闹翻，与 compute thread 共存时严重退化；[[Interrupts]]（ext4 默认）CPU 友好但 sleep/wake-up 开销占 4KB 读延迟约 33%；[[io_uring]] SQ_POLL 仅集中提交、完成仍受底层机制约束，且 per-instance 多进程下互相干扰，对同步 I/O 应用还要重写代码。目标：所有 CPU 利用率场景下都拿到最优、且支持同步 I/O。

## 核心方法

关键 insight：syscall 开销（约 150ns）相对 I/O 延迟可忽略，所以可以陷入内核享用调度器与基础设施，同时绕过 I/O 栈大部分逻辑。

- **TagSched**：在 PCB 加 IO-WAIT/IO-NORMAL 2-bit tag，I/O 线程提交后只更新 tag 不出 run queue；调度器跳过 IO-WAIT；用 increment/decrement 处理 race；用 IPI 抢占 C-thread 避免 head-of-line block。
- **TagPoll**：内核中跑一个集中 polling 完成线程，提交方把 PCB 指针嵌入 NVMe 请求，完成时直接更新对应线程 tag；自适应策略——线程独占 CPU 时让其自己 polling，否则走 TagSched 路径。
- **SKIP（Shortcut Kernel I/O Path）**：UnIDrv 内核模块管理 NVMe queue 池，按 PID hash 动态分配（比 [[BypassD]] 静态 fmap 省）；per-file extent tree 把 file offset 映射到 PBA，无需自定义 IOMMU；Ulib 通过 LD_PRELOAD 拦截 read/write 走 ioctl `user_io_submit`。

实现：基于 ext4 + Linux 6.5.1，UnIDrv 3250 LoC、Ulib 1089 LoC、CFS 调度器加 71 LoC。

## 关键结果

- 4KB 随机读：单线程下平均/P99 延迟比 ext4 减 42%/31.2%
- 与 16 C-thread 共存：4KB IOPS 比 ext4 +39.4%、比 BypassD +88.8%；C-thread 性能与 ext4 接近
- 128KB 大 IO 下避免 BypassD 的极端 P99（16175us → 593us）
- 完成线程极限 \~1820 KIOPS，作者承认这是单线程瓶颈，留多完成线程为 future work

## 相关

- **相关概念**：[[Polling]]、[[Interrupts]]、[[NVMe]]、[[io_uring]]、[[Kernel-Bypass]]
- **同类系统**：[[BypassD]]、[[XRP]]、[[SPDK]]、[[uFS]]、[[FlashShare]]、[[Cinterrupts]]
- **同会议**：[[FAST-2026]]
