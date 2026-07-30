---
type: concept
aliases: [Non-Uniform-Memory-Access]
last_updated: 2026-07-18
tags: [hardware, memory, scheduling, placement]
---

# NUMA

> 非一致内存访问 (NUMA) 系统暴露了与位置相关的内存和 I/O 成本：处理器访问本地内存和设备的方式与附加到另一个套接字或节点的资源不同。

## 核心思想

NUMA 拓扑使布局成为性能正确性的一部分。线程、页面、队列、加速器和存储设备应该根据套接字和互连局部性的知识进行映射；否则，远程流量、缓存一致性工作和带宽争用可能会主导名义计算或设备能力。

## 为什么重要

该语料库中的许多高核心数和多设备结果取决于固定、分配策略和 I/O 布局。忽略拓扑的基准测试可能无法重现，或者错误地将局部性效应归因于算法。

## 关键观察 / 隐含假设

- **观察**：内存/交换或I/O资源分区与核心局部性相互作用。 [[ScaleSwap-FAST26]] 和 [[MAIO-FAST26]] 评估具有此类约束的系统路径。
- **观察**：加速器/设备放置可能会暴露跨节点流量。 [[DSA-2LM-ATC25]] 和 [[Catur-MLSys26]] 使用硬件感知执行上下文。
- **假设**：固定一次就足够了。动态调度、页面迁移、共享数据和多租户放置可能会使静态映射失效。

## 设计空间与取舍

- **局部性与负载平衡**：严格的局部性会导致容量浪费；平衡可以增加远程流量。
- **首次接触、绑定或迁移**：分配策略会改变稳态带宽和适应成本。
- **CPU、内存和设备拓扑**：仅优化一层可以将争用转移到另一层。

## 引用本概念的论文

- [[ScaleSwap-FAST26]] — core-centric swap-resource management.
- [[MAIO-FAST26]] — memory/I/O placement context.
- [[DSA-2LM-ATC25]] — hardware-aware acceleration path.
- [[Catur-MLSys26]] — device/runtime placement boundary.
- [[SoarAlto-OSDI25]] — system scheduling/locality context.
