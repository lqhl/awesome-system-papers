---
type: paper
name: SolFS
full_title: "SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup"
authors: [Riwei Pan, Yu Liang, Lei Li, Hongchao Du, Tei-Wei Kuo, Chun Jason Xue]
venue: ATC
year: 2025
tags: [filesystem, mobile, cloud-backup, versioning, delta-sync]
source_pdf: "[[atc2025-pan.pdf]]"
source_md: "[[atc2025-pan]]"
---

# SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup (ATC 2025)

> **一句话总结**：把 delta sync 的「文件级整篇 hash 比对」替换为文件系统记录每次 write 的 (offset, length) 操作日志，让 mobile 端 backup APP 直接知道修改范围，云同步时间减少 88.8%、CPU 开销降 90%+。

## 问题

手机云备份（Dropbox、OneDrive、厂商内置）要么整文件上传（流量爆炸），要么做 delta sync 但需要把整个文件 hash 一遍（rsync/QuickSync/WebR2sync+ 都跑不掉）。在 Pixel 8 上，整盘 hash 多花 170% 时间和 224% CPU 能耗，还会跟前台应用抢核。CoW 风格的 versioning（reflink/BetrFS/WaybackFS）可以无 hash 标记修改，但带来文件碎片化和双倍存储。

## 核心方法

SolFS 在 F2FS 上加一层「操作日志版本化」，关键设计：

- **MLogging（per-file mergeable operation logging）**：每次 write 把 (offset, length) 作为 mlog 插入一个 in-memory mlog 树（基于 extent tree），相邻/重叠的 mlog 自动合并。Sequential write 用 mlog pointer cache 走 O(1) 快速路径。
- **Compact mlog**：on-disk 把 length 4B + offset 4B 压成 1 个 4B（小文件 / 小 write 占多数），用 length 高位标识 compact 形式。
- **Dynamic granularity**：byte-level → page-level 自动切换，控制单文件 mlog 数量（阈值 5000）防内存爆炸。
- **Backup-driven versioned inode chain**：每次 backup 触发一个新的 versioned inode（用 ext attr 存 ino_ver/ver_link/next_ino，不破坏 F2FS 磁盘 layout），不同 backup APP 可独立追踪自己未上传部分；compaction 通过 reference count 回收冗余版本。
- **Hash-free delta sync**：APP 通过 ioctl `delta_open/delta_getdiff/delta_close` 拿到累计修改范围；额外可对该范围做 rolling checksum 进一步压缩流量。
- **Version consistency**：用 ino_flag 配合 F2FS write-ordering 实现 all-or-nothing，崩溃时退回上传整文件。

## 关键结果

- 随机更新 1MB：sync 时间 -88.8%，流量仅为 HashSync 的 12.3%
- 4 个真实 APP（Facebook、Twitter、Capcut、Dropbox）平均 sync 时间 89s → 29s（-71%），CPU 使用降 70%
- I/O 性能与 F2FS 几乎相同（差距 < 1.5%）
- 18 小时 9 个真实 trace 的额外内存仅 470KB，compact mlog 节省 33% 存储
- versioned inode 链深度 = 10 时搜索 7.6ms，仍远低于 hash

## 相关

- **相关概念**：[[Delta-Sync]]、[[F2FS]]、[[Copy-on-Write]]、[[Inode-Versioning]]
- **同类系统**：rsync、WebR2sync+、QuickSync、NetSync、SAS-Cache
- **同会议**：[[ATC-2025]]
