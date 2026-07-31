---
type: entity
kind: tool
aliases: [EXT4, Fourth-Extended-Filesystem]
status: active
last_updated: 2026-07-30
tags: [filesystem, linux, storage]
---

# Ext4

> Ext4 是 Linux 成熟的 journaling 文件系统，也是新型缓存、写缓冲、内核旁路、解聚存储和形式化验证工作最常用的传统基线。

## 是什么

Ext4 以 extent、JBD2 journal、page cache 与 VFS 集成为核心，提供稳定 POSIX 语义和广泛工具生态。它的价值不仅是自身性能，更是作为“保留完整 Linux 文件系统服务”的参照：新系统绕过哪些 kernel 路径、牺牲哪些语义、节省多少 CPU，都可由与 Ext4 的比较具体化。

## 关键观察 / 隐含假设

- **观察**：高速 NVMe 下，传统 kernel write path 与 page cache 可能成为 CPU 瓶颈。[[WSBuffer-FAST26]] 重构 buffered write，[[Oxbow-OSDI26]] 则让 read 保留 kernel 服务、write 绕过 kernel，写吞吐最高为 Ext4 的 4.8 倍。
- **观察**：成熟的 page cache、readahead、sendfile 和 VFS interoperability 仍有高价值。[[Oxbow-OSDI26]] 的 Nginx 实验显示保留 kernel sendfile 可带来 3.3 倍吞吐，因此完全 userspace 化并非免费。
- **观察**：解聚和新型 cache 会暴露 inode lock、驱动栈与一致性成本。[[CetoFS-FAST26]]、[[uCache-FAST26]] 与 [[UnICom-FAST26]] 分别从远程存储和缓存路径重审 Ext4。
- **隐含假设**：block device 接口、集中式 metadata 与 journaling 成本仍可接受；在 computational storage、NVMe-oF 或极高核数环境中，该边界会移动。

## 演进时间线

- **长期基线**：Ext4 以 JBD2、extent 和 VFS 集成成为 Linux 通用文件系统默认选择之一。
- **2026 FAST**：[[WSBuffer-FAST26]]、[[uCache-FAST26]]、[[UnICom-FAST26]]、[[FS-PI-FAST26]] 和 [[CetoFS-FAST26]] 从写缓存、统一 I/O、接口与解聚角度测量或改造其路径。
- **2026 OSDI**：[[Oxbow-OSDI26]] 按操作属性拆分 kernel、userspace 与设备职责，既以 Ext4 为性能基线，也保留其 VFS 生态作为不可轻易丢弃的能力。

## 相关概念

- [[Journaling]]
- [[VFS]]
- [[Page-Cache]]
- [[Crash-Consistency]]
- [[Kernel-Bypass]]

## 相关论文

- [[Oxbow-OSDI26]] — 多组件文件系统，以 Ext4 为成熟 kernel baseline
- [[WSBuffer-FAST26]] — 高带宽 NVMe 的 buffered write 重构
- [[CetoFS-FAST26]] — NVMe-oF 上的内核文件系统瓶颈
- [[uCache-FAST26]] — 文件系统缓存路径
- [[UnICom-FAST26]] — 统一 I/O 与 Ext4 对照
- [[FS-PI-FAST26]] — 文件系统接口设计
- [[SysSpec-FAST26]] — 以 Ext4 级复杂系统为验证边界
