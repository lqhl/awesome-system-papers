---
type: concept
aliases: [Pipeline Parallelism, Pipeline-Parallel, pipeline-parallel, PP, GPipe, PipeDream, 1F1B, interleaved 1F1B]
parent: "[[LLM-Inference]]"
introduced_by: GPipe (arXiv 2018)
last_updated: 2026-07-30
tags: [distributed-training, parallelism]
---

# Pipeline-Parallelism

> 流水线并行（pipeline parallelism, PP）按 layer/stage 切分模型，并让多个 micro-batches 在不同 stages 重叠执行，以容纳超大模型并跨较慢链路扩展。

## 核心思想

模型的连续 layers 被分配到 S 个 stages，activation/gradient 只在 stage boundary 传输。训练 schedule 从 GPipe 的 all-forward/all-backward 演进到 1F1B、interleaved 1F1B、zero-bubble 等；推理则要同时安排 prefill chunks 和 decode microbatches。

PP 的核心不是简单均分 FLOPs，而是最小化 post-overlap critical path：stage compute、activation communication、MoE AllToAll、Wgrad deadline、memory 和 warmup/cooldown 都会改变最佳 partition。

## 为什么重要

当模型单卡放不下或跨节点 collective 太贵时，PP 只在边界发送 activation，常比跨域 Data Parallelism 更节省带宽。但 bubble、最慢 stage、microbatch 数与 activation memory 会限制利用率；serving 中还要满足 per-request TTFT/TPOT 而非只看 steady-state throughput。

## 关键观察 / 隐含假设

- **stage balance 应基于 overlap 后成本**：[[Tessera-OSDI26]] 将 heterogeneous MoE compute/communication 建模为 task DAG，说明 serial layer cost 会选错边界。
- **serving PP 需要动态 chunk 与 slack 调度**：[[DynamicPPServing-OSDI26]] 根据 TTFT/TPOT slack 调整 prefill chunk，并延后有余量的 decode request；预测误差会造成 SLO 风险。
- **迁移的停顿主要来自 runtime/communicator state**：[[TrainMover-OSDI26]] 预热 joiner 并增量重配 collective，把 membership commit 缩成短暂停顿。
- **宏观 parallel plan 需要下沉到微观 flow**：[[RLinf-OSDI26]] 将 RL macro workflow 变换为可组合 micro flows；收益依赖 planner 对 rollout/training ratio 的估计。
- **跨慢链路 PP 有明确 crossover**：[[CrossPipe-ATC25]] 在跨数据中心训练中比较 PP 与 DP，结论依赖 activation/gradient volume 与带宽。

## 设计空间与取舍

- **GPipe**：schedule 简单，activation memory 和 bubble 大。
- **1F1B/interleaving**：降低峰值 activation/bubble，增加 schedule 和 weight-version 复杂度。
- **zero-bubble/deferred Wgrad**：用 deadline slack 填 bubble（[[Tessera-OSDI26]]），需精确 dependency 与 memory budget。
- **动态 serving PP**：[[DynamicPPServing-OSDI26]] 适应 arrival 与 SLO，控制稳定性和 fairness 更难。
- **异构 stage partition**：能匹配 GPU/network/MoE 差异，profiling 与重规划成本更高。

## 引用本概念的论文

- [[Tessera-OSDI26]] — 联合异构 MoE stage partition、overlap 与 bubble filling。
- [[DynamicPPServing-OSDI26]] — 为 LLM serving 动态调节 prefill/decode pipeline。
- [[TrainMover-OSDI26]] — 支持 PP/DP runtime 的低中断成员替换。
- [[RLinf-OSDI26]] — 将大规模 RL workflow 变换为细粒度并行 flows。
- [[CrossPipe-ATC25]] — 探索跨数据中心 PP 与 DP 的带宽边界。
- [[FlexTrain-MLSys26]] — 在弹性训练中调整 PP/DP 并讨论数值一致性。

## 已知局限 / 开放问题

- 联合 stage partition、schedule、activation memory、MoE routing 与网络 contention。
- 在 burst arrival、fail-slow 和动态 shape 下保证 p99 TTFT/TPOT 与公平性。
- 减少 profiling/solver 对硬件和版本的绑定，并安全在线重规划。
- 形式化 weight version、in-flight microbatch 与 failure recovery 的一致性。
