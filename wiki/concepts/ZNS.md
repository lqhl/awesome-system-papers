---
type: concept
aliases: [Zoned-Namespace, Zoned Namespaces, Zoned-Block-Device]
last_updated: 2026-07-18
tags: [storage, nvme, zoned-storage, garbage-collection]
---

# ZNS

> Zoned Namespaces (ZNS) expose storage as zones with sequential-write constraints, moving placement and garbage-collection decisions toward the host so that device mapping and reclamation can be made more predictable.

## 核心思想

ZNS divides writable capacity into zones. A host appends data in zone order and resets or reclaims zones when their contents become obsolete. The abstraction can reduce hidden device-side relocation and align log-structured storage with the device's physical management, but it also turns write ordering, open-zone limits, and reclamation scheduling into host-visible correctness and performance obligations.

The corpus treats ZNS as a design family rather than a guarantee of performance. [[ZUFS-FAST26]] adapts zoned semantics to mobile UFS, while storage papers use it as a reference point for how host software can manage placement and garbage collection explicitly.

## 为什么重要

Zoned storage offers a path to make write amplification and tail behavior more controllable on large flash devices. It is particularly relevant to log-structured filesystems, caches, and append-only services, where the host already knows data lifetime. Conversely, applications that require in-place updates, many concurrent writers, or opaque legacy I/O paths must pay for adaptation or retain conventional storage.

## 关键观察 / 隐含假设

- **观察**：zone-level mapping can reduce metadata pressure relative to page-level mapping. [[ZUFS-FAST26]] reports that its device's ZUFS mapping table is small enough to remain in SRAM, but this claim is specific to its zone geometry and phone platform.
- **观察**：the host-to-device path must preserve zone write order. [[ZUFS-FAST26]] identifies clock-gating requeue and block-layer corner cases that can violate the intended order even when the filesystem issues sequential writes.
- **假设**：large zones avoid device-side GC but can make host GC coarser. [[ZUFS-FAST26]] therefore adds proactive filesystem GC because a full section/zone can make foreground reclamation expensive.

## 设计空间与取舍

- **Host control vs compatibility**：explicit append/reset semantics enable placement-aware software, but force changes in filesystems, schedulers, and applications that assume overwrite-friendly block storage.
- **Large zones vs reclamation granularity**：larger zones reduce mapping state and can simplify sequential media management, while making each victim-selection and migration decision coarser.
- **Correctness vs power management**：device and kernel power-saving paths may need synchronization changes to preserve ordered writes.

## 引用本概念的论文

- [[ZUFS-FAST26]] — implements zoned UFS across the Android, filesystem, block-layer, driver, and device stack.
- [[DisCoGC-FAST26]] — contrasts discard and compaction trade-offs in a log-structured SSD service, illustrating the host-side reclamation problem that zoned designs seek to expose.
- [[WSBuffer-FAST26]] — studies how high-bandwidth SSD paths motivate separating buffered and direct data paths; zoned devices add ordering constraints to that decision.

## 已知局限 / 开放问题

- End-to-end behavior depends on filesystem policies, scheduler ordering, driver power management, and firmware geometry rather than the namespace abstraction alone.
- Open-zone limits, small writes, and foreground reclamation require workload-specific scheduling and remain hard to validate across devices.
