---
type: concept
aliases: [FL, Federated-Learning-System]
last_updated: 2026-07-18
tags: [machine-learning, distributed-systems, privacy, edge]
---

# Federated Learning

> 联邦学习协调来自分布式客户端的模型更新，无需集中原始数据；它将优化与设备异构性、通信、隐私、参与和故障行为结合起来。

## 核心思想

服务器选择客户端、分发模型、聚合返回的更新并重复。抽象本身并不保证隐私或鲁棒性：安全聚合、差异隐私、参与者选择和系统调度在规定的威胁和可用性模型下提供单独的属性。

## 为什么重要

真正的跨设备部署面临间歇性连接、非 IID 数据、有限的上行链路、丢失和资源受限的客户端。协议加速或学习结果必须说明它是时序模型、模拟还是部署测量，以及它涵盖哪些服务器/客户端对手。

## 关键观察 / 隐含假设

- **观察**：聚合开销和隐私要求可以主导这一轮。 [[DISAGG-MLSys26]] 在参数化时序和仿真边界下评估基于委员会的安全聚合设计。
- **观察**：客户异质性和参与影响系统策略。 [[PLayer-FL-MLSys26]] 和 [[FLoRIST-MLSys26]] 研究联邦系统设计环境。
- **假设**：尽管数据和可用性存在差异，但本地培训和聚合可以改善共同目标。 [[AssyLLM-ATC25]] 和 [[SONAR-MLSys26]] 公开工作负载/系统特定的边界。

## 设计空间与取舍

- **隐私与通信/计算**：安全聚合和隐私机制增加了协议和端点成本。
- **同步与异步参与**：异步减少了等待，但改变了陈旧性和正确性假设。
- **统计效用与系统可行性**：模型收敛性、数据异构性、设备可用性需要联合评估。

## 引用本概念的论文

- [[DISAGG-MLSys26]] — secure aggregation under a federated threat model.
- [[PLayer-FL-MLSys26]] — federated system design.
- [[FLoRIST-MLSys26]] — federated learning/runtime context.
- [[AssyLLM-ATC25]] — asynchronous/distributed learning boundary.
- [[SONAR-MLSys26]] — federated-system behavior.
