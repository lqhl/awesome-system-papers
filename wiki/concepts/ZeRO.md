---
type: concept
aliases: [Zero-Redundancy-Optimizer, ZeRO-1, ZeRO-2, ZeRO-3]
last_updated: 2026-07-18
tags: [distributed-training, sharding, memory-management]
---

# ZeRO

> ZeRO 是一系列数据并行分片策略，可删除重复的优化器状态、梯度以及最终跨等级的参数，以使更大的模型适合聚合加速器内存。

## 核心思想

这些阶段逐步对优化器状态、梯度和参数进行分片。内存优势与集体通信相结合：参数具体化和梯度减少发生在计算周围，因此有用的比较始终针对规定的模型、批次、拓扑和实现。

在这个语料库中，ZeRO 既是基线也是合成点。内存管理系统围绕它调整策略；隐私、量化和结构化优化器工作增加了简单统一分片可能违反的语义约束。

## 为什么重要

ZeRO/FSDP式分片改变了模型训练的可行性边界。它还使集体缓冲区布局、检查点、卸载和优化器语义成为一流的系统关注点，而不是本地实现细节。

## 关键观察 / 隐含假设

- **观察**：更积极的阶段会减少驻留状态，但会增加沟通和物化工作。 [[DP-ZeRO-MLSys26]] 在指定的 A100 配置下衡量这种与差异隐私簿记的权衡。
- **观察**：统一分片可能与结构化状态发生冲突。当量化块或矩阵优化器无法跨越分片边界时，[[veScale-FSDP-MLSys26]] 主张不规则的放置。
- **假设**：内存策略可以围绕固定的训练行为进行优化。 [[ProTrain-MLSys26]] 搜索 ZeRO、卸载和检查点选项，但其结论受到分析模型和序列的限制。

## 设计空间与取舍

- **阶段深度与通信**：分片更多状态会降低内存，但会增加集体依赖性。
- **卸载与加速器驻留**：卸载可以扩展容量，同时引入主机设备带宽和调度约束。
- **统一与语义分片**：简单的放置简化了实现；结构化运算符可能需要填充或更丰富的放置元数据。

## 引用本概念的论文

- [[DP-ZeRO-MLSys26]] — composes ZeRO stages with differential privacy.
- [[veScale-FSDP-MLSys26]] — changes FSDP/ZeRO-style placement for structured training.
- [[ProTrain-MLSys26]] — searches memory strategies including ZeRO and offload.
- [[FSDP]] — related fully-sharded data-parallel abstraction.

## 已知局限 / 开放问题

- 一旦解决了基本的内存问题，通信拓扑、故障恢复以及与 TP/EP/CP 的可组合性就可以占据主导地位。
- 全面训练的效用和收敛性必须与可行性或微基准吞吐量分开衡量。
