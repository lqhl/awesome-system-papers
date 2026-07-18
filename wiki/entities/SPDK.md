---
type: entity
kind: tool
aliases: [Storage-Performance-Development-Kit]
status: active
last_updated: 2026-07-18
tags: [storage, nvme, kernel-bypass, userspace-io]
---

# SPDK

> SPDK is a userspace storage stack commonly used as a kernel-bypass NVMe reference: it exposes polling, per-core queue pairs, and zero-copy-oriented paths while trading away parts of the conventional filesystem and kernel I/O interface.

## 是什么

In this corpus, SPDK is mainly a baseline or building block for high-performance local NVMe I/O. It makes the data path explicit and minimizes kernel crossings, so papers compare against it when they want to separate device throughput from page-cache, filesystem, or completion-path overhead.

It is not automatically the right deployment choice. Systems that retain POSIX filesystems, buffered I/O, or shared device access must either integrate only selected SPDK ideas or accept additional compatibility work.

## 关键观察 / 隐含假设

- **观察**：userspace polling and per-core queues can approach device capability, but CPU ownership and workload contention determine whether polling remains desirable. [[DPAS-FAST26]] contrasts polling, hybrid polling, and interrupts under contention.
- **观察**：filesystem compatibility can be as important as raw I/O. [[uCache-FAST26]] borrows SPDK-style NVMe ideas while retaining an ext4-assisted control path.
- **假设**：a benchmark close to SPDK isolates software-stack overhead. [[uCache-FAST26]] uses this comparison for its NVMe uStore, but its result is bounded by the specific random-read configurations.

## 演进时间线

- 2025 SOSP：[[Aeolia-SOSP25]] — uses userspace I/O context in a storage-system design.
- 2026 FAST：[[uCache-FAST26]] — combines SPDK-inspired data-path ideas with a unikernel cache and filesystem control path.
- 2026 FAST：[[DPAS-FAST26]] — analyzes completion-mode trade-offs relevant to polling-based paths.

## 相关概念

- [[NVMe]]、[[Direct-IO]]、[[Buffered-IO]]、[[io_uring]]

## 相关论文

- [[uCache-FAST26]] — compares uStore with SPDK while retaining filesystem compatibility.
- [[WSBuffer-FAST26]] — studies buffered versus direct high-bandwidth SSD paths.
- [[DPAS-FAST26]] — shows why completion mode depends on CPU contention and queue depth.
- [[RISTRETTO-FAST26]] — places kernel-bypass paths in a cloud-local-storage evolution.
