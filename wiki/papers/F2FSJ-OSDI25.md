---
type: paper
name: F2FSJ
full_title: "Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery"
authors: [Yaotian Cui, Zhiqi Wang, Renhai Chen, Zili Shao]
venue: OSDI
year: 2025
tags: [filesystem, journaling, f2fs, crash-recovery, mobile-storage]
source_pdf: "[[osdi25-cui.pdf]]"
source_md: "[[osdi25-cui]]"
---

# Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery (OSDI 2025)

> **一句话总结**：F2FSJ 为 out-of-place update 的 F2FS 设计第一套 ordered-mode journaling，用 per-inode 分散日志 + epoch 解耦 data/control 平面，checkpoint 时延降低 4.9×、端到端延迟降低 35%。

## 问题

F2FS（Flash-Friendly File System）是 Android 系统的主力 flash 文件系统，但其 crash recovery 依赖粗粒度 checkpointing：一旦触发就阻塞所有 read/write，最坏情况尾延迟达到 293 ms，而且 checkpoint 间隔内（默认 60 秒）新写入数据/元数据在 crash 后直接丢失（最多 9.1%）。

EXT4 风格的 journaling（如 JBD2）无法直接搬到 F2FS。根因：F2FS 是 out-of-place update，inode 位置不固定，仅 journal inode 会因 NAT/SIT/SSA 等 on-disk 文件系统元数据过期而无法正确恢复；若把 inode + 文件系统元数据都 journal 又要把 metadata 写两遍。再加上 JBD2 的集中式 log list、全局 transaction ticket 引入的锁争用（约占总 journaling 时间的 25-29%）和 journal period 切换等待（7-16%），直接照搬不划算。

## 核心方法

F2FSJ 提出 metadata-change-based、ordered-mode 的新型 journaling，针对 F2FS 的 append-only 特性做了四项设计：

- **只 journal 元数据变化**：不是像 JBD2 那样把整个 4KB metadata page 写进 journal，而是只记录被改的字段；减少 I/O 与存储放大。
- **去中心化 per-inode log 列表**：每个 inode 自带一个 log list，按 epoch 组织多版本（通过 `e2l_mapping` 表）。log 插入无需全局锁，inode 间无相互干扰。
- **Epoch-based data/control 平面解耦**：epoch 只做控制面（注册参与本周期的 inode 号），数据面（具体 metadata change）住在 per-inode log list 里。fsync/timeout 触发时可立即开启新 epoch，不必等旧周期文件操作全部落地——消除 period transfer 等待时间。
- **Fast-forward-to-latest journal apply**：引入新页状态 `F2FSJ_Dirty`（不会被 page cache manager 驱逐），按 epoch 顺序直接 flush 最终 in-memory metadata，一次性合并跨 epoch 对同一元数据的小更新，避免小写放大。out-of-place update 的"旧位置保留"特性保证这不破坏一致性。

实现上改动约 3000 行 C 代码，基于 Linux 5.15 内核；给 non-blocking journal commit（因只记 change 不锁 page），开源在 GitHub。

## 关键结果

- Checkpoint 时间降低最多 **4.9×**，端到端延迟降低最多 **35%**（相比 F2FS 原生 checkpointing）
- Crash recovery 恢复率提升：F2FS 默认 60 秒间隔丢失 9.1% 数据/元数据，F2FSJ 明显更低
- ARM 嵌入板（RK3588S）上 metadata-intensive workload 相比 F2FS-CKPT 加速 1.36-1.83×，相比 EXT4+JBD2 加速 1.41-2.39×
- Android 应用：Twitter/Facebook workload 相比 F2FS-CKPT 节省执行时间 28.5%/47.3%，SQLite DELETE/TRUNCATE 模式相比 F2FS-CKPT 最高 2.24×
- 存储开销：journal 文件 256 MB（占 256 GB SSD 的 0.1%），仅为 JBD2（1 GB）的 25%；内存/CPU 开销相比 F2FS 分别 +1.4% 和 +1.8%，可忽略

## 相关

- **相关概念**：[[Journaling]]、[[Crash-Recovery]]、[[Log-Structured-Filesystem]]、[[F2FS]]、[[JBD2]]
- **相关工作**：NOVA（per-inode log for NVM）、WineFS、Btrfs、Z-Journal、Fast-commit、I-journaling
- **同会议**：[[OSDI-2025]]
