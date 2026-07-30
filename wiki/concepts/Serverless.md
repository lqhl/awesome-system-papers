---
type: concept
aliases: [Function-as-a-Service, FaaS-Platform]
last_updated: 2026-07-18
tags: [cloud, faas, isolation, scheduling]
---

# Serverless

> 无服务器系统执行需求驱动的功能，同时将服务器管理隐藏在调度、隔离、启动和计费抽象背后；他们的核心系统权衡是弹性与冷启动、资源和隔离开销。

## 核心思想

函数被调度到瞬态或重用的执行环境中。平台必须决定何时配置、缓存、检查点、迁移或回收这些环境，同时保持隔离和请求延迟。抽象比特定运行时更广泛：容器、微虚拟机、unikernels 和语言运行时都可以实现它。

## 为什么重要

无服务器使部署和弹性变得容易实现，但将启动、状态、数据局部性和尾部延迟变成了平台级问题。该语料库中的论文将其用于短函数和更有状态的服务，这表明单个冷启动数并不是完整的评估。

## 关键观察 / 隐含假设

- **观察**：隔离机制影响启动和稳态成本。 [[Dandelion-SOSP25]] 和 [[Aegaeon-SOSP25]] 探索执行环境的权衡。
- **观察**：爆发性需求使布局和资源复用成为核心。 [[BurstComputing-ATC25]] 和 [[Poby-ATC25]] 研究与调度相关的系统行为。
- **假设**：函数足够无状态，或者状态可以廉价地外部化。 [[Quilt-SOSP25]] 和 [[RTSFaaS-ATC25]] 显示了为什么状态和运行时边界会改变该假设。

## 设计空间与取舍

- **冷启动与热池成本**：预热减少延迟但保留资源。
- **强隔离与重用**：microVM/容器/unikernel 选择会改变启动、安全性和操作复杂性。
- **无状态接口与状态局部性**：外部状态简化了扩展，但会增加数据和协调开销。

## 引用本概念的论文

- [[Dandelion-SOSP25]] — serverless execution-environment design.
- [[BurstComputing-ATC25]] — burst scheduling and resource management.
- [[Aegaeon-SOSP25]] — isolation and execution trade-offs.
- [[RTSFaaS-ATC25]] — runtime/FaaS system boundary.
- [[Quilt-SOSP25]] — stateful-system considerations under serverless abstractions.
