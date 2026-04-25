---
type: paper
name: CoFS
full_title: "CoFS: A Filesystem for Fast Container Startup"
authors: [Li Wang, Jinxiu Du, Yang Yang, Qingbo Wu, Tao Liu, Haoze Wu]
venue: FAST
year: 2026
tags: [container, filesystem, fuse, mphf, lazy-pulling]
source_pdf: "[[fast2026-wang-li.pdf]]"
source_md: "[[fast2026-wang-li]]"
---

# CoFS: A Filesystem for Fast Container Startup (FAST 2026)

> **一句话总结**：在 [[FUSE]] 之上利用「container image 构建后只读」的特性，在 build 时为 filesystem tree 预构造 minimal perfect hash function（MPHF），把 metadata lookup 从 userspace daemon 拉回 kernel 单次 I/O，并用 sparse file 镜像缓存数据，相比 fuse-loopback 平均 lookup 时间降低 73-86%，cold startup 比 Nydus-fuse/Nydus-erofs/eStargz 都快。

## 问题

Container cold start 中拉镜像占 76% 时间但只用到 6.4% 数据。on-demand pulling（Overlaybd、Nydus-fuse、Nydus-erofs、eStargz）能边运行边按需拉，但各有缺陷：

- FUSE-based（Nydus-fuse、eStargz）：每次 path resolution 触发多次 LOOKUP 转发到 userspace daemon，context switch + data copy 开销大。
- Nydus-erofs + fscache：第一次访问要让 userspace daemon 下载 → 写盘 → 通知 kernel，长链路 + 同步 I/O，反而比 Nydus-fuse 还慢；fscache eviction 不可控导致性能波动。
- 在 kernel 实现完整 image parsing 和远程下载逻辑维护成本高。

核心矛盾：镜像 metadata 在 build 后就不再变（只读），但现有方案都把 lookup 当成动态 filesystem 操作处理。

## 核心方法

**MPHF for filesystem tree**：
- 用 Czech 等的 O(m) MPHF 算法在 image build 时构建：key = (parent inode number || filename)。MPHF 是 collision-free + space-optimal，给定 key 通过两层 hash 直接算出 dense array 的 unique index。
- 1M files 时只需 ~9.5 MB 存 {m, n, T1, T2, g}，构建时间 ~34s（相比 image build 几分钟可忽略）。
- Lookup：内核空间算 MPHF 值 → 索引 metadata array → 至多一次 I/O（page cache 命中则零 I/O）；filename 长度 >16B 才需读 tail extra metadata 区。

**Parallel path resolution**：
- 第二个 MPHF 以**完整路径**为 key，构造时强制和按 (parent inode, filename) 的 MPHF 输出相同 hash 值。
- 用 kprobe 挂在 `do_filp_open`，深度 >3 的路径丢给 workqueue，从尾向头并发构造 inode（kernel 自身是 top-down，CoFS 反向 bottom-up，互不冲突）。

**Image format**：基于 eStargz，把 inode 元数据抽成 cofs.inode.array 二进制文件（120 B/entry）。

**Fast data path**：
- cofs-snapshotter 下载远程数据后写入 mirror sparse file（以 inode number 命名，nominal size 与远程一致）。
- cofs-driver 用 vfs_lseek(SEEK_HOLE) 判断该 range 是否已落盘，命中则直接 vfs_read 走 host filesystem（kernel 内），miss 才走 FUSE 转发到 userspace。
- xfs/ext4/btrfs 的 inode lock 保证 lseek 与 write 互斥，正确性有 VFS 兜底。

## 关键结果

- 平均 lookup 时间比 fuse-loopback 低 73-86%；parallel lookup 在 elasticsearch 镜像上再加速 28%。
- 四个真实容器（mariadb、redis、tomcat、elasticsearch）cold startup 全面快于 Nydus-fuse/Nydus-erofs/eStargz。
- Image size 增加 <1%，build 时间增加约 5-10%。
- 已下载数据访问性能与 traditional/Nydus-erofs 持平（kernel-space 访问），优于 Nydus-fuse/eStargz。

## 相关

- **相关概念**：[[FUSE]]、Minimal Perfect Hash Function、Container Image、Lazy Pulling、Overlay Filesystem、Sparse File
- **同类系统**：Nydus-fuse、Nydus-erofs、eStargz、Overlaybd、erofs、fscache、ExtFUSE、RFUSE
- **同会议**：[[FAST-2026]]
