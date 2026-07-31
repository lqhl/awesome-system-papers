---
type: entity
kind: system
aliases: [Megatron-LM, Megatron-Core, Megatron]
status: active
last_updated: 2026-07-30
tags: [llm-training, distributed-training, tensor-parallel, pipeline-parallel, expert-parallel]
---

# Megatron

> Megatron-LM/Megatron-Core 是 NVIDIA 主导的大模型分布式训练栈，以 [[Tensor-Parallelism]]、pipeline/data/expert parallel 的组合为核心，是论文中常见的工业执行面与强基线。

## 是什么

Megatron 在 Transformer layer 内做 TP，沿 layer 做 PP，并叠加 DP、optimizer sharding 与 MoE EP。它提供成熟 collective、pipeline schedule、distributed checkpoint 和 model recipe，但通常采用启动前固定的 parallel plan。

论文中的“Megatron”可能是 upstream、NeMo/Megatron-Core，或数千行 patch 的 fork；因此性能数字必须连同版本、plugin 和 parallel configuration 阅读。

## 关键观察 / 隐含假设

- **观察：Megatron 是可扩展执行壳，但深度优化需要侵入式集成。** [[Greyhound-ATC25]]、[[FlexTrain-MLSys26]]、[[PopFetcher-ATC25]] 都加入大量 plugin/code。
- **观察：固定 parallel layout 可被保留，同时迁移其角色。** [[TrainMover-OSDI26]] 将故障节点 role 搬到 standby，1024 GPU downtime 约 20 s。
- **观察：MoE collective 顺序仍有优化空间。** [[FarSkip-Collective-MLSys26]] 修改 forward/backward 与 autograd 才实现 88.4% EP overlap。
- **假设：标准 Transformer 与同步长跑 job 占主流。** agentic RL、elastic cluster、MLLM 异构 component 会挑战这一边界。

## 演进时间线

- 早期：Megatron-LM 确立 TP + PP + DP 的大模型 3D parallel execution。
- 2025 ATC：[[Optimus-ATC25]]、[[Greyhound-ATC25]]、[[PopFetcher-ATC25]] — 分别填 MLLM bubble、处理 fail-slow、prefetch MoE expert。
- 2026 MLSys/FAST：[[FlexTrain-MLSys26]]、[[NEST-MLSys26]]、[[AITurbo-FAST26]] — 弹性 PP、plan execution 与 checkpoint 加速。
- 2026 OSDI：[[TrainMover-OSDI26]] — 不改变已调优 layout 的故障迁移。
- 2026 OSDI：[[Tessera-OSDI26]]、[[RobustRL-OSDI26]]、[[UEP-OSDI26]] — 在训练规划、RL recovery 和 MoE network path 中引用/扩展 Megatron 语义。

## 相关概念

- [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[Expert-Parallelism]]、[[Checkpointing]]

## 相关论文

- [[TrainMover-OSDI26]] — role-preserving live migration。
- [[RobustRL-OSDI26]] — RL role/phase-aware recovery。
- [[Tessera-OSDI26]] — 大规模并行计划与执行。
- [[NEST-MLSys26]] — planner 输出到 Megatron/NeMo runtime。
- [[AITurbo-FAST26]] — 透明加速 Megatron checkpoint。
