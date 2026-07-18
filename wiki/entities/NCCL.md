---
type: entity
kind: tool
aliases: [NVIDIA-Collective-Communications-Library]
status: active
last_updated: 2026-07-18
tags: [distributed-training, collective-communication, gpu-networking]
---

# NCCL

> NCCL is NVIDIA's GPU collective-communication library and a recurring execution substrate for data-parallel, tensor-parallel, and expert-parallel systems in this corpus.

## 是什么

NCCL provides collectives such as AllReduce, AllGather, and ReduceScatter over GPU interconnects. In paper pages it is usually an implementation substrate rather than the contribution itself: a system either schedules around its collectives, diagnoses their failures, changes buffer/layout behavior, or compares a new transport path against the assumptions of the standard stack.

NCCL throughput and failure behavior depend on topology, GPU generation, driver/runtime version, message size, concurrent traffic, and collective algorithm selection. A result measured with NCCL therefore should not be generalized to an abstract network claim without its platform boundary.

## 关键观察 / 隐含假设

- **观察**：collective behavior is coupled to workload and topology. [[fabric-lib-MLSys26]] and [[veScale-FSDP-MLSys26]] treat buffer layout and communication scheduling as first-class performance constraints.
- **观察**：communication failures and stragglers are operational concerns, not only performance noise. [[Guard-MLSys26]] and [[Greyhound-ATC25]] study related reliability/diagnostic boundaries.
- **假设**：the standard collective API is sufficient for an optimization. [[Obscura-ATC25]] and [[Mercury-SOSP25]] show that deployment constraints can require additional transport, scheduling, or observability mechanisms.

## 演进时间线

- 2025 ATC：[[Greyhound-ATC25]] — investigates distributed execution behavior involving collective communication.
- 2025 SOSP：[[Mercury-SOSP25]] — places communication/runtime behavior in a system-management context.
- 2026 MLSys：[[fabric-lib-MLSys26]] — treats collective implementation and scheduling as part of performance engineering.

## 相关概念

- [[FSDP]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[RDMA]]

## 相关论文

- [[fabric-lib-MLSys26]] — collective communication implementation and scheduling.
- [[veScale-FSDP-MLSys26]] — planned collective buffers for FSDP.
- [[Guard-MLSys26]] — reliability and diagnosis around distributed execution.
- [[Greyhound-ATC25]] — communication-related distributed-system behavior.
- [[Obscura-ATC25]] — deployment constraints around communication paths.
