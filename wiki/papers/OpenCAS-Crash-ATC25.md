---
type: paper
name: OpenCAS-Crash
full_title: "Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study"
authors: [Shaohua Duan, Youmin Chen]
venue: ATC
year: 2025
tags: [crash-consistency, caching, persistent-memory, file-system, reliability]
source_pdf: "[[atc2025-duan-shaohua.pdf]]"
source_md: "[[atc2025-duan-shaohua]]"
---

# Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study (ATC 2025)

> **一句话总结**：首个对 block-level 持久缓存（Open CAS）做系统化 crash consistency 研究：用 workload-oriented testing 触发 implicit cache 操作，发现写命中与 write-around 写场景下崩溃会返回坏数据，且 Open CAS 与 ext-3/4/xfs/btrfs 的可靠性特性存在兼容性问题。

## 问题

NVM (Optane PMem) 让 block-level cache 能像 page cache 一样加速 HDD/SSD，同时具备持久性，但缓存层 crash consistency 缺乏第三方系统化测试：(1) Open CAS 6 个 cache mode 比 page cache 复杂得多；(2) eviction/cleaning 是 implicit 操作，需要重负载触发，传统 fuzz 工具无法精确插入 crash；(3) 文件系统的 journaling/COW 都假设 cache 易失，与持久缓存结合后是否兼容未知。

## 核心方法

提出 **WLOT (Workload-Oriented Test)** 框架，分两阶段：

1. **Trace mode**：跑 FIO 负载（16 线程、4 KB cache line 时性能下降信号最明显），用 `casctl static` 监控吞吐降级作为 implicit cache 操作正在执行的「隐式信息」，据此设置 crash point 并 flush 出 oracle 数据。
2. **Test mode**：回放 trace + 注入 synthetic crash（unmount + `casctl stop`）→ 触发 Open CAS post-recovery → 与 oracle 对比读出数据。

针对 5 种 cache mode (WT/WB/WO/WA/WI) × cache miss/hit/eviction/cleaning/flushing，组合 SW/SR/RW/UR 4 种 workload 全覆盖。兼容性测试用 ext-2/3/4 (writeback/ordered/journal/nodealloc)、xfs、btrfs 作为 backend，同时对 cache 层与 backend 注入 crash。详细 cache mode 状态机见 [[atc2025-duan-shaohua]]。

## 关键结果

- Observation 1：在 ack 后 crash，Open CAS 全部 mode 都正确恢复（符合 design 承诺）。
- Observation 2：cache miss / eviction 期间 crash 也能保持一致性，因为 cache line 初始为 invalid，损坏数据不会被读出。
- **Observation 3 (新发现)**：write cache hit 期间 crash，除 WA mode 外其他 mode 全部返回坏数据 (B)——update 操作没有先把 valid 位置 invalid。
- **Observation 4**：WA mode 下，先写 backend 后 invalidate cache metadata 的两步若中断，旧 cache 数据会返回给用户。
- 兼容性测试发现 ext-3/4 的 journaling、btrfs 的 COW 与 Open CAS 持久缓存层 co-recovery 时存在 durability loss / 不一致问题。
- 在 NVCache 上做了同样测试，重现类似问题。

## 相关

- **相关概念**：[[Crash-Consistency]]、[[Persistent-Memory]]、[[Page-Cache]]、[[Journaling]]、[[Copy-on-Write]]
- **同类系统**：Open CAS、NVCache、bcache、flashcache、OrthusCAS、First Responder、Assise
- **同会议**：[[ATC-2025]]
