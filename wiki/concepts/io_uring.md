---
type: concept
aliases: [io-uring, Linux-io_uring]
last_updated: 2026-07-18
tags: [linux, io, asynchronous-io, kernel]
---

# io_uring

> io_uring is Linux's shared-ring asynchronous I/O interface: applications submit operations and consume completions through shared queues, reducing some syscall and context-switch overhead while making queueing, polling, and completion handling explicit.

## 核心思想

The interface separates submission and completion rings from the traditional one-syscall-per-operation path. It can support asynchronous file, network, and device operations, but it does not remove device latency, filesystem work, or kernel scheduling costs. How an application uses polling, batching, registered buffers, and queue depth determines the result.

## 为什么重要

In this corpus io_uring is a reference point for high-performance Linux I/O. It appears when systems compare kernel-bypass paths with kernel interfaces, build completion mechanisms, or investigate where a conventional I/O stack adds overhead.

## 关键观察 / 隐含假设

- **观察**：completion strategy is workload dependent. [[DPAS-FAST26]] compares polling, hybrid polling, and interrupts under device and CPU-contention boundaries.
- **观察**：an asynchronous API does not eliminate storage-stack semantics. [[Aeolia-SOSP25]] and [[UnICom-FAST26]] use I/O-path designs where filesystem, cache, or device behavior remains material.
- **假设**：lower submission overhead transfers to end-to-end throughput. [[OdinANN-FAST26]] and [[FS-PI-FAST26]] illustrate that index, data-layout, and storage-device work can dominate instead.

## 设计空间与取舍

- **Polling vs interrupts**：polling can reduce completion latency but consumes CPU and degrades under contention.
- **Batching vs tail latency**：larger batches amortize overhead but can delay individual requests.
- **Kernel API vs bypass**：io_uring retains kernel/filesystem integration; userspace bypass may reduce overhead but gives up compatibility or isolation.

## 引用本概念的论文

- [[DPAS-FAST26]] — adaptive SSD completion mode selection.
- [[Aeolia-SOSP25]] — storage-path system design using Linux I/O context.
- [[UnICom-FAST26]] — high-performance I/O/storage mechanisms.
- [[OdinANN-FAST26]] — storage-index execution with I/O-path considerations.
- [[KernelBypassTCP-ATC25]] — compares kernel and bypass communication-path trade-offs.

## 已知局限 / 开放问题

- Real gains depend on kernel version, device, queue depth, CPU isolation, and polling policy.
- API-level benchmarks should not be generalized to application SLOs without filesystem and workload measurements.
