---
type: paper
name: KernelBypassTCP
full_title: "Opening Up Kernel-Bypass TCP Stacks"
authors: [Shinichi Awamoto, Michio Honda]
venue: ATC
year: 2025
tags: [networking, tcp, kernel-bypass, dpdk, benchmark]
source_pdf: "[[atc2025-awamoto.pdf]]"
source_md: "[[atc2025-awamoto]]"
---

# Opening Up Kernel-Bypass TCP Stacks (ATC 2025)

> **一句话总结**：在统一应用 nophttpd 上对 6 个 TCP stack（Linux/mTCP/F-Stack/IX/TAS/Demikernel）做横向评测，发现没有一个 stack 能在 bulk transfer + small RPC + 高并发连接 + 多核四类 workload 上同时表现良好——Linux 在 bulk 上比 IX 快 1.7×，IX 在 small message 上比 Linux 快 5.2×。

## 问题

学术界涌现大量 kernel-bypass TCP stack（[[RDMA]] 之外的 raw packet I/O 路线，基于 DPDK/netmap），但每篇论文只与 Linux + 1-2 个其他 stack 比较，且通常只针对一个 workload。运维者面对的问题是：到底要不要换 kernel-bypass、换哪个？现有文献回答不了，因为：

- 没有横向 benchmark：6 个代表性 stack 从未在同一应用、同一硬件、同一 workload 集合下被对比；
- 各 stack 编译/配置门槛极高，社区难以独立复现（Alibaba 报告说从头写一个 stack 比修旧的便宜）；
- 同一 stack 在不同 workload 下表现差异巨大，论文里报的优势可能在另一种 workload 下完全反转。

## 核心方法

作者写了 **nophttpd**——一个最小化的静态内存 HTTP server，针对每个 stack 的原生 API 单独实现一份（Linux 用 epoll、Demikernel 用 Rust async、IX/Demikernel 处理 packet-sized 分块、TAS 通过 LD_PRELOAD），避免用统一 wrapper 偏向某一 stack。在配对的 25GbE 直连机器上跑同一组 workload：

- **Bulk transfer**：单连接 2 MB 响应；
- **Small message latency**：单连接 64 B 请求、关闭中断聚合；
- **Concurrent connections**：4800 持久连接 + RPC；
- **Multicore scalability**：1-24 核，server 端 downclock 防 client bottleneck。

为公平测，禁用 TSO（mTCP/Demikernel 不支持），用一致的 wrk 客户端（修过多核 stat 聚合）。期间还要修 stack 本身的 bug：给 TAS 加 Window Scaling，调 mTCP 的 RSS 哈希种子，跳过 IX 上游不稳定版本改用 Reflex 里的 IX。

## 关键结果

- **Bulk transfer**：Linux 14.69 Gb/s 拿第一，F-Stack 13.66 Gb/s 第二；mTCP/TAS 10-12 Gb/s；IX/Demikernel 因 packet-level API 拖累最低。
- **Small message latency**：Demikernel 13 µs 最低；Linux busy-poll 也能做到 17 µs，与 kernel-bypass 同档。
- **Concurrent connections**：IX 在吞吐上吊打其他 30-684%；Linux/F-Stack 几乎一样烂，说明 syscall 不是瓶颈（FreeBSD TCP 用 DPDK 也救不回来）。
- **Multicore scalability**：IX 16 核内最强（比 TAS 高 16-384%、比 mTCP 高 456%），TAS 在 24 核展现最好的扩展斜率（67% 提升）；Demikernel 完全不支持多核 stack。
- **Linux vs IX**：Linux 在 bulk 上 1.7× IX，IX 在 small message 上 5.2× Linux——没有 one-size-fits-all。

## 相关

- **相关概念**：[[Kernel-Bypass]]、[[DPDK]]、[[RDMA]]
- **同会议**：[[ATC-2025]]
