---
type: entity
kind: tool
aliases: [EXT4, Fourth-Extended-Filesystem]
status: active
last_updated: 2026-07-18
tags: [filesystem, linux, storage]
---

# Ext4

> Ext4 is a widely deployed Linux filesystem and a recurring compatibility/performance baseline in this corpus; it represents a concrete implementation, not the generic behavior of all local filesystems.

## 是什么

Ext4 supplies POSIX filesystem semantics over block devices with metadata, allocation, journaling, and page-cache integration. Systems compare against it when they change a data path, storage layout, or safety property while retaining a familiar Linux interface.

## 关键观察 / 隐含假设

- **观察**：filesystem behavior is coupled to the kernel I/O stack and device. [[FS-PI-FAST26]] uses Ext4-context evaluation when studying storage-path behavior.
- **观察**：semantics and specification matter beyond throughput. [[SysSpec-FAST26]] and [[CetoFS-FAST26]] examine filesystem-level properties under explicit boundaries.
- **假设**：an Ext4 result transfers to another filesystem. Allocation, journaling, cache state, mount options, and device geometry can invalidate that extrapolation.

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
