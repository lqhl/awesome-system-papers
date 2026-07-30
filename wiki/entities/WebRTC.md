---
type: entity
kind: tool
aliases: [Web-Real-Time-Communication]
status: active
last_updated: 2026-07-18
tags: [networking, realtime, media, congestion-control]
---

# WebRTC

> WebRTC是一个用于交互式媒体和数据传输的实时通信堆栈；它的端到端行为取决于编解码器、拥塞控制、传输、设备和应用程序工作负载。

## 是什么

WebRTC 提供面向浏览器和应用程序的实时通信构建块，包括媒体管道和网络适配。在此语料库中，它是更改路径选择、网络适应或执行放置的系统的部署基础和基线。

## 关键观察 / 隐含假设

- **观察**：交互质量由网络和媒体/运行时行为共同决定。 [[AnchorNet-ATC25]] 研究具有此边界的面向网络的系统路径。
- **观察**：应用程序级修复或适应必须保持实时约束。 [[MARC-ATC25]] 和 [[Reparo-MLSys26]] 使用与 WebRTC 相关的工作负载，而不是仅将数据包吞吐量视为成功。
- **假设**：受控跟踪或测试平台代表互联网变化。这些论文的结论仍然受到其测量的网络和端点配置的限制。

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
