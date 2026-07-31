---
type: concept
aliases: [Tensor Parallelism, Tensor-Parallel, tensor-parallel, TP, Megatron-style parallelism, intra-layer parallelism]
parent: "[[LLM-Inference]]"
last_updated: 2026-07-30
tags: [distributed-training, llm-inference, parallelism]
---

# Tensor-Parallelism

> 张量并行（tensor parallelism，TP）在单层内部切分矩阵或 tensor，由多个 GPU 计算 partial result 并通过 collective 合并；它用通信换取模型容量与算力聚合。

## 核心思想

Megatron-style TP 对 FFN/attention 采用 column-parallel 与 row-parallel matmul，使每个 Transformer block 只在必要边界 AllReduce。TP 常限制在 NVLink domain，跨节点再组合 [[Pipeline-Parallelism]]、data parallel 与 [[Expert-Parallelism]]。

## 为什么重要

OSDI 2026 强化了 TP 的 phase/hardware specificity。[[DynamicPPServing-OSDI26]] 指出 PCIe GPU 上 TP 高频 AllReduce 使 PP 更具优势；[[Prism-OSDI26]] 在多模型服务中让 weights/KV 弹性共享，而 TP layout 仍约束可回收粒度；[[TrainMover-OSDI26]] 保持训练 parallel layout 不变，只迁移故障角色以缩短中断。

[[Tessera-OSDI26]]、[[EcoServe-OSDI26]] 表明 TP 必须与 serving phase、network 和 batch 联合选择，而不是固定“卡越多越快”。

## 关键观察 / 隐含假设

- **观察：prefill/decode 的最优 TP 度不同。** compute-bound prefill 更能利用宽 TP，memory-bound decode 更易被 collective 支配。
- **观察：互连拓扑决定 TP 上限。** [[DynamicPPServing-OSDI26]] 在 PCIe A100 上以 PP 避免频繁 AllReduce。
- **假设：layer shape 与 batch 足够均匀。** MoE、变长序列和异构 component 会产生 imbalance。

## 设计空间与取舍

- **TP degree**：扩大可降单卡计算/容量，却增加 collective 与小 GEMM inefficiency。
- **TP / PP / DP / EP composition**：组合可匹配拓扑，但计划空间和重配置成本快速膨胀。
- **Static / phase-specific plan**：动态 plan 提高利用率，需 state redistribution 与 SLO-safe switching。

## 引用本概念的论文

- [[DynamicPPServing-OSDI26]] — PCIe GPU 上 PP 与 TP 的对照。
- [[TrainMover-OSDI26]] — 保持 parallel layout 的故障迁移。
- [[Tessera-OSDI26]] — 大模型训练并行规划。
- [[BOOST-MLSys26]] — 低秩架构的 bottleneck TP。
- [[Megatron]] — TP 的主流训练执行栈。

## 已知局限 / 开放问题

- 弹性 TP 的低开销 state resharding 与 collective reconfiguration 尚未成熟。
- 自动 planner 需同时建模 kernel shape、network contention 与 application SLO。
