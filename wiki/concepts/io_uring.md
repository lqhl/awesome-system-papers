---
type: concept
aliases: [io-uring, Linux-io_uring]
last_updated: 2026-07-18
tags: [linux, io, asynchronous-io, kernel]
---

# io_uring

> io_uring 是 Linux 的共享环异步 I/O 接口：应用程序通过共享队列提交操作并使用完成，减少一些系统调用和上下文切换开销，同时使排队、轮询和完成处理显式化。

## 核心思想

该接口将提交环和完成环与传统的每个操作一个系统调用的路径分开。它可以支持异步文件、网络和设备操作，但它不会消除设备延迟、文件系统工作或内核调度成本。应用程序如何使用轮询、批处理、注册缓冲区和队列深度决定了结果。

## 为什么重要

在此语料库中，io_uring 是高性能 Linux I/O 的参考点。当系统将内核旁路路径与内核接口进行比较、构建完成机制或调查传统 I/O 堆栈在何处增加开销时，就会出现这种情况。

## 关键观察 / 隐含假设

- **观察**：完成策略取决于工作负载。 [[DPAS-FAST26]] 比较设备和 CPU 争用边界下的轮询、混合轮询和中断。
- **观察**：异步API并没有消除存储堆栈语义。 [[Aeolia-SOSP25]] 和 [[UnICom-FAST26]] 使用 I/O 路径设计，其中文件系统、缓存或设备行为仍然重要。
- **假设**：较低的提交开销转移到端到端吞吐量。 [[OdinANN-FAST26]] 和 [[FS-PI-FAST26]] 说明索引、数据布局和存储设备工作可以占据主导地位。

## 设计空间与取舍

- **轮询与中断**：轮询可以减少完成延迟，但会消耗 CPU 并在争用情况下性能下降。
- **批处理与尾部延迟**：较大的批次可以分摊开销，但可能会延迟单个请求。
- **内核 API 与绕过**：io_uring 保留内核/文件系统集成；用户空间旁路可能会减少开销，但会放弃兼容性或隔离性。

## 引用本概念的论文

- [[DPAS-FAST26]] — adaptive SSD completion mode selection.
- [[Aeolia-SOSP25]] — storage-path system design using Linux I/O context.
- [[UnICom-FAST26]] — high-performance I/O/storage mechanisms.
- [[OdinANN-FAST26]] — storage-index execution with I/O-path considerations.
- [[KernelBypassTCP-ATC25]] — compares kernel and bypass communication-path trade-offs.

## 已知局限 / 开放问题

- 实际收益取决于内核版本、设备、队列深度、CPU 隔离和轮询策略。
- 在没有文件系统和工作负载测量的情况下，API 级基准测试不应推广到应用程序 SLO。
