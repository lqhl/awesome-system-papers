---
type: concept
aliases: [CC, Congestion-Control-Algorithm]
last_updated: 2026-07-18
tags: [networking, transport, latency, feedback-control]
---

# Congestion Control

> Congestion control adjusts sending behavior from feedback about loss, delay, delivery rate, or explicit signals to share network capacity while limiting queue growth and instability.

## 核心思想

Transport endpoints infer available capacity from delayed and noisy observations. A controller therefore chooses how aggressively to probe, how to react to congestion signals, and which objective—throughput, latency, fairness, or application quality—to prioritize. Its behavior is inseparable from path topology, competing flows, buffers, and the transport/runtime implementation.

## 为什么重要

Many networking and real-time systems claims reduce to a congestion-control choice. A throughput improvement can harm queueing delay or fairness; a low-latency policy can leave capacity unused. Evaluations need workload, RTT/loss variation, competing-flow, and endpoint boundaries.

## 关键观察 / 隐含假设

- **观察**：one control loop may not fit every traffic class. [[MARC-ATC25]] and [[AnchorNet-ATC25]] treat real-time/application constraints as part of the objective.
- **观察**：datacenter or hardware feedback paths have different signals and timescales. [[Barre-ATC25]] and [[SwCC-ATC25]] examine such system-specific boundaries.
- **假设**：a testbed controller result generalizes to Internet or production traffic. [[SplitConn-ATC25]] and [[STORM-ATC25]] show why path and workload composition must be explicit.

## 设计空间与取舍

- **Loss, delay, rate, or explicit feedback**：signals differ in responsiveness and noise sensitivity.
- **Throughput vs tail latency/fairness**：more aggressive probing can improve one flow while harming queues or peers.
- **End-host vs network-assisted control**：network feedback can improve observability but adds deployment requirements.

## 引用本概念的论文

- [[AnchorNet-ATC25]] — application-aware networking path.
- [[MARC-ATC25]] — real-time adaptation context.
- [[Barre-ATC25]] — network feedback/control system boundary.
- [[SwCC-ATC25]] — congestion-control design/evaluation.
- [[SplitConn-ATC25]] — transport-path system trade-offs.
