---
type: concept
aliases: [CUDA-Graphs]
last_updated: 2026-07-18
tags: [gpu, runtime, scheduling, kernel-launch]
---

# CUDA Graph

> CUDA Graph 捕获 GPU 工作图，以更低的 CPU launch 开销和更明确的依赖调度重放重复执行；当执行结构足够稳定、足以摊销捕获与更新成本时最有效。

## 核心思想

图记录 kernel、内存操作及其依赖，供后续实例化与重放。它能降低逐算子 dispatch 开销并支持运行时调度优化，但动态 shape、控制流、内存地址或 batch 组成变化可能要求重建图或走 fallback 路径。

## 为什么重要

GPU 服务与训练系统在小 kernel 或高请求率下常受 CPU launch 与同步限制。CUDA Graph 是常用机制，但只看图执行 microbenchmark 不足以证明端到端收益，还需给出捕获、更新、并发及 workload mix 的边界。

## 关键观察 / 隐含假设

- **观察**：启动开销对于重复性细粒度工作最为重要。 [[EventTensor-MLSys26]] 和 [[DynaFlow-MLSys26]] 使用具有此边界的 GPU 运行时上下文。
- **观察**：抢占和动态调度可能与固定捕获的图发生冲突。 [[GPreempt-ATC25]] 和 [[Torpor-ATC25]] 检查运行时控制问题。
- **假设**：图形形状仍然可重复使用。 [[LAPS-MLSys26]] 说明了为什么更改执行条件需要显式回退或更新评估。

## 设计空间与取舍

- **捕获/重放与动态执行**：重放降低了开销，但限制了变化。
- **CPU开销与内存/更新成本**：图管理本身会消耗资源和同步。
- **单流与并发请求**：好处可以随着批处理和多租户调度而改变。

## 引用本概念的论文

- [[EventTensor-MLSys26]] — GPU runtime/execution context.
- [[DynaFlow-MLSys26]] — dynamic execution and scheduling context.
- [[GPreempt-ATC25]] — GPU preemption boundary.
- [[Torpor-ATC25]] — runtime scheduling context.
- [[LAPS-MLSys26]] — dynamic workload conditions.
