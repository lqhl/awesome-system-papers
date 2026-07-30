---
type: entity
kind: tool
aliases: [torch, PyTorch-Framework]
status: active
last_updated: 2026-07-18
tags: [machine-learning, training, compiler, runtime]
---

# PyTorch

> PyTorch 是执行与编程栈；本语料库中的许多论文借助它表达模型计算、分布式训练、扩展 kernel，以及接入调试或验证 hook。

## 是什么

在本 wiki 中，PyTorch 不是单一性能基准，而是模型代码、autograd、tensor storage、distributed collective、自定义算子及编译器/运行时后端的共同集成面。系统工作可能保留 PyTorch API 而替换下层实现，也可能揭示框架默认路径的边界。

这些论文使用了堆栈的不同部分：训练和分片系统依赖于分布式张量语义；内核系统扩展了算子执行；验证和调试工具观察或重放模型行为。因此，有关 PyTorch 的结果通常具有明确的版本、后端、设备和工作负载边界。

## 关键观察 / 隐含假设

- **观察**：框架兼容性往往是采用的边界。 [[veScale-FSDP-MLSys26]] 保留了 PyTorch `fully_shard` 风格的界面，同时更改了布局和缓冲区管理。
- **观察**：自定义编译器/运行时路径可以提高执行速度，但仍必须满足 PyTorch 张量、流和 autograd 语义。 [[Flashlight-MLSys26]] 和 [[TritorX-MLSys26]] 以不同的方式使用此边界。
- **假设**：PyTorch 级别的集成具有足够的可移植性，非常重要。 [[TrainCheck-OSDI25]] 和 [[FPRev-ATC25]] 表明相关的正确性和再现性表面还包括版本、运算符和数值行为。

## 演进时间线

- 2025 OSDI：[[TrainCheck-OSDI25]] — 将框架行为视为可重复训练诊断的一部分。
- 2026 MLSys：[[veScale-FSDP-MLSys26]] — extends distributed sharding while preserving familiar framework integration.
- 2026 MLSys：[[Flashlight-MLSys26]] — 检查主流框架堆栈旁边的专用执行路径。

## 相关概念

- [[FSDP]]、[[Tensor-Parallelism]]、[[CUDA]]、[[Triton]]

## 相关论文

- [[veScale-FSDP-MLSys26]] — PyTorch-compatible structured FSDP backend.
- [[TritorX-MLSys26]] — compilation/execution work at the tensor-program boundary.
- [[FPRev-ATC25]] — numerical reproducibility analysis involving framework execution.
- [[TrainCheck-OSDI25]] — training error diagnosis across framework behavior.
- [[PyLO-MLSys26]] — PyTorch-oriented learning-system integration.
