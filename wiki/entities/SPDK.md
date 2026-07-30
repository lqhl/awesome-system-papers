---
type: entity
kind: tool
aliases: [Storage-Performance-Development-Kit]
status: active
last_updated: 2026-07-18
tags: [storage, nvme, kernel-bypass, userspace-io]
---

# SPDK

> SPDK 是一个用户空间存储堆栈，通常用作内核旁路 NVMe 参考：它公开轮询、每核心队列对和面向零复制的路径，同时放弃部分传统文件系统和内核 I/O 接口。

## 是什么

在此语料库中，SPDK 主要是高性能本地 NVMe I/O 的基线或构建块。它使数据路径明确并最大限度地减少内核交叉，因此当论文想要将设备吞吐量与页面缓存、文件系统或完成路径开销分开时，可以将其与它进行比较。

它并不是自动正确的部署选择。保留 POSIX 文件系统、缓冲 I/O 或共享设备访问的系统必须仅集成选定的 SPDK 想法或接受额外的兼容性工作。

## 关键观察 / 隐含假设

- **观察**：用户空间轮询和每核心队列可以接近设备功能，但 CPU 所有权和工作负载争用决定轮询是否仍然可取。 [[DPAS-FAST26]] 对比轮询、混合轮询和争用中断。
- **观察**：文件系统兼容性与原始 I/O 一样重要。 [[uCache-FAST26]] 借鉴了 SPDK 风格的 NVMe 思想，同时保留了 ext4 辅助的控制路径。
- **假设**：接近 SPDK 的基准测试隔离了软件堆栈开销。 [[uCache-FAST26]] 对其 NVMe uStore 使用此比较，但其结果受特定随机读取配置的限制。

## 演进时间线

- 2025 SOSP：[[Aeolia-SOSP25]] — 在存储系统设计中使用用户空间 I/O 上下文。
- 2026 FAST：[[uCache-FAST26]] — 将 SPDK 启发的数据路径思想与 unikernel 缓存和文件系统控制路径相结合。
- 2026 FAST：[[DPAS-FAST26]] — analyzes completion-mode trade-offs relevant to polling-based paths.

## 相关概念

- [[NVMe]]、[[Direct-IO]]、[[Buffered-IO]]、[[io_uring]]

## 相关论文

- [[uCache-FAST26]] — compares uStore with SPDK while retaining filesystem compatibility.
- [[WSBuffer-FAST26]] — studies buffered versus direct high-bandwidth SSD paths.
- [[DPAS-FAST26]] — 说明为什么完成模式取决于 CPU 争用和队列深度。
- [[RISTRETTO-FAST26]] — places kernel-bypass paths in a cloud-local-storage evolution.
