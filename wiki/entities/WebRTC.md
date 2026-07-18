---
type: entity
kind: tool
aliases: [Web-Real-Time-Communication]
status: active
last_updated: 2026-07-18
tags: [networking, realtime, media, congestion-control]
---

# WebRTC

> WebRTC is a real-time communication stack used for interactive media and data delivery; its end-to-end behavior depends on codec, congestion control, transport, device, and application workload together.

## 是什么

WebRTC provides browser- and application-facing real-time communication building blocks, including media pipelines and network adaptation. In this corpus it is a deployment substrate and baseline for systems that change path selection, network adaptation, or execution placement.

## 关键观察 / 隐含假设

- **观察**：interactive quality is jointly determined by networking and media/runtime behavior. [[AnchorNet-ATC25]] studies a network-facing system path with this boundary.
- **观察**：application-level repair or adaptation must preserve real-time constraints. [[MARC-ATC25]] and [[Reparo-MLSys26]] use WebRTC-relevant workloads rather than treating packet throughput alone as success.
- **假设**：a controlled trace or testbed represents Internet variation. These papers' conclusions remain bounded by their measured network and endpoint configurations.

## 演进时间线

- 2025 ATC：[[AnchorNet-ATC25]] — network-aware system design involving WebRTC workloads.
- 2025 ATC：[[MARC-ATC25]] — real-time communication adaptation/repair context.
- 2026 MLSys：[[Reparo-MLSys26]] — runtime or learning-system behavior with real-time communication boundary.

## 相关概念

- [[Congestion-Control]]、[[QUIC]]、[[Tail-Latency]]

## 相关论文

- [[AnchorNet-ATC25]] — networking path and WebRTC workload.
- [[MARC-ATC25]] — real-time adaptation context.
- [[Reparo-MLSys26]] — WebRTC-relevant runtime behavior.
