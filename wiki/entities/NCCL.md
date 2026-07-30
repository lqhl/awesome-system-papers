---
type: entity
kind: tool
aliases: [NVIDIA-Collective-Communications-Library]
status: active
last_updated: 2026-07-18
tags: [distributed-training, collective-communication, gpu-networking]
---

# NCCL

> NCCL 是 NVIDIA 的 GPU 集体通信库，也是该语料库中数据并行、张量并行和专家并行系统的循环执行基础。

## 是什么

NCCL 通过 GPU 互连提供 AllReduce、AllGather 和 ReduceScatter 等集合。在纸质页面中，它通常是实现底层而不是贡献本身：系统要么围绕其集合进行调度，诊断其故障，更改缓冲区/布局行为，要么将新的传输路径与标准堆栈的假设进行比较。

NCCL 吞吐量和故障行为取决于拓扑、GPU 生成、驱动程序/运行时版本、消息大小、并发流量和集体算法选择。因此，使用 NCCL 测量的结果不应推广到没有平台边界的抽象网络声明。

## 关键观察 / 隐含假设

- **观察**：集体行为与工作负载和拓扑耦合。 [[fabric-lib-MLSys26]] 和 [[veScale-FSDP-MLSys26]] 将缓冲区布局和通信调度视为一流的性能约束。
- **观察**：通信故障和落后者是操作问题，而不仅仅是性能噪音。 [[Guard-MLSys26]] 和 [[Greyhound-ATC25]] 研究相关的可靠性/诊断边界。
- **假设**：标准集体 API 足以进行优化。 [[Obscura-ATC25]] 和 [[Mercury-SOSP25]] 表明部署约束可能需要额外的传输、调度或可观察性机制。

## 演进时间线

- 2025 ATC：[[Greyhound-ATC25]] — investigates distributed execution behavior involving collective communication.
- 2025 SOSP：[[Mercury-SOSP25]] — places communication/runtime behavior in a system-management context.
- 2026 MLSys：[[fabric-lib-MLSys26]] — 将集体实施和调度视为性能工程的一部分。

## 相关概念

- [[FSDP]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[RDMA]]

## 相关论文

- [[fabric-lib-MLSys26]] — collective communication implementation and scheduling.
- [[veScale-FSDP-MLSys26]] — planned collective buffers for FSDP.
- [[Guard-MLSys26]] — reliability and diagnosis around distributed execution.
- [[Greyhound-ATC25]] — communication-related distributed-system behavior.
- [[Obscura-ATC25]] — deployment constraints around communication paths.
