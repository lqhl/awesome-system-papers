---
type: entity
kind: tool
aliases: [EXT4, Fourth-Extended-Filesystem]
status: active
last_updated: 2026-07-18
tags: [filesystem, linux, storage]
---

# Ext4

> Ext4 是广泛部署的 Linux 文件系统，也是本语料库中反复出现的兼容性/性能基准；它代表一个具体的实现，而不是所有本地文件系统的通用行为。

## 是什么

Ext4 通过元数据、分配、日志和页面缓存集成在块设备上提供 POSIX 文件系统语义。当系统更改数据路径、存储布局或安全属性，同时保留熟悉的 Linux 界面时，系统将与之进行比较。

## 关键观察 / 隐含假设

- **观察**：文件系统行为与内核I/O堆栈和设备耦合。 [[FS-PI-FAST26]] 在研究存储路径行为时使用 Ext4 上下文评估。
- **观察**：语义和规范比吞吐量更重要。 [[SysSpec-FAST26]] 和 [[CetoFS-FAST26]] 检查显式边界下的文件系统级属性。
- **假设**：Ext4 结果传输到另一个文件系统。分配、日志记录、缓存状态、安装选项和设备几何结构可能会使该推断无效。

## 演进时间线

- 2026 FAST：[[FS-PI-FAST26]] — storage-path evaluation with a filesystem boundary.
- 2026 FAST：[[SysSpec-FAST26]] — filesystem specification/behavior analysis.
- 2026 FAST：[[CetoFS-FAST26]] — filesystem system design and evaluation.

## 相关概念

- [[Buffered-IO]]、[[Direct-IO]]、[[Page-Cache]]、[[NVMe]]

## 相关论文

- [[FS-PI-FAST26]] — filesystem and storage-path evaluation.
- [[SysSpec-FAST26]] — specification and semantic analysis.
- [[CetoFS-FAST26]] — filesystem-system design.
