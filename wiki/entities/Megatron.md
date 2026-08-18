---
type: entity
kind: system
aliases: [Megatron-LM, Megatron-Core, Megatron]
status: active
last_updated: 2026-08-18
tags: [llm-training, distributed-training, tensor-parallel, pipeline-parallel, expert-parallel]
---

# Megatron

> Megatron-LM/Megatron-Core 是 NVIDIA 主导的大模型分布式训练栈。在本 wiki 的论文中，它既是常见基线，也是新调度、通信、容错和数据系统真正落地时的执行底座。

## 是什么

Megatron 把大 Transformer 拆成多个并行维度：层内使用 [[Tensor-Parallelism]]，层之间使用 [[Pipeline-Parallelism]]，再叠加 [[Data-Parallelism]]、optimizer sharding 与 MoE 的 [[Expert-Parallelism]]。它同时管理 model construction、pipeline schedule、collective group、distributed optimizer 和 checkpoint 等状态。

页面中的“Megatron”不能当成一个固定 binary：论文可能使用 Megatron-LM、Megatron-Core、NeMo 集成，或者一个改了数千行代码的内部 fork。因此，“相对 Megatron 快多少”必须与版本、并行布局、kernel、collective 和硬件一起阅读。

## 关键观察 / 隐含假设

- **Megatron 提供成熟执行语义，但大多数新机制仍需深度修改。** [[Tessera-OSDI26]] 集成到内部 Megatron-LM，用约 11 KLoC Python+2 KLoC C++ 建立可移动 task 的运行时；[[TrainMover-OSDI26]] 的原型约 12 KLoC，还同时修改 PyTorch c10d 和 NCCL。这些证据不支持“只写一个外部 scheduler 就能完成”。
- **固定的并行布局同时是优势和约束。** 对长期稳定训练，TP/PP/DP/EP 布局可被充分调优。[[TrainMover-OSDI26]] 正是保留这个布局，让新机器一对一接替旧 rank；1,024 GPU 上计划迁移和意外恢复的 runtime 停机分别是 16.6 秒和 21.1 秒，但不包含故障检测时间。
- **非对称集群会打破默认 SPMD 假设。** [[Hetu-v2-OSDI26]] 在 H800+H20 混合集群、故障后剩余 GPU 和变长数据上使用非对称 HSPMD；其 32B Llama 实验中 Megatron 每步 10.45 秒，HSPMD 计划为 6.05 秒。这是特定 planner 和 16 H800+32 H20 上的结果，不是 Megatron 在所有同构集群都会慢 1.7 倍。
- **MoE 的最佳 stage 不能只按串行 FLOPs 均分。** [[Tessera-OSDI26]] 发现不同 layer pair 能隐藏的通信比例相差约 3 倍，因此先实测局部细粒度 schedule，再选 pipeline partition。该系统在 4,096–12,288 张 Hopper 的五个生产任务上报告 MFU 相对提升 20.0%–32.8%；这些数字包含内部 runtime 和特定 MoE 结构。
- **通信时机、SM 数和频率会联合变化。** [[Kareus-OSDI26]] 在 16 张 A100 上将这三者一起搜索；相对 Megatron 的最大时间降幅 14.9%、最大能耗降幅 22.1% 来自不同配置，不应相加成一个结果。
- **框架还是数据和故障语义的边界。** [[Chen-LLMDataPipelines-OSDI26]] 的生产样本同时覆盖 FSDP、FSDP2 和 Megatron，说明训练数据 I/O 不能只按单一 runtime 推导；[[OpGuard-OSDI26]] 则需固定 Megatron/PyTorch/NCCL 的随机数与 collective 顺序，才能逐位比较两次训练。

## 设计空间与取舍

| 问题 | 保留 Megatron 默认做法 | 扩展路线 | 代价 |
|---|---|---|---|
| 集群异构 | 启动前固定对称 layout | HSPMD/动态 reshard | planner、多份 graph 和切换一致性 |
| MoE 重叠 | 固定 EP/PP schedule | 实测局部 schedule、移动 Wgrad | 更大搜索空间与 runtime 改造 |
| 故障恢复 | checkpoint/restart | standby+shadow iteration+增量 collective | 备用 GPU、记录数据与 NCCL/c10d 修改 |
| 能耗 | 固定频率与默认 collective | 联合搜索通信时机、SM、DVFS | 离线 profile 会随 shape/干扰漂移 |

共同隐含假设是：训练 graph、tensor shape、角色和通信顺序在一段时间内可预测。agentic RL、动态 MoE routing、多模态分支和弹性资源都会让这个假设变弱。

## 演进时间线

- **早期**：Megatron-LM 将 TP+PP+DP 组成大模型 3D parallel 训练方案。
- **2025**：[[Greyhound-ATC25]]、[[Optimus-ATC25]]、[[PopFetcher-ATC25]] 分别在 fail-slow、多模态 bubble 和 MoE expert prefetch 上扩展其执行面。
- **2026**：[[FlexTrain-MLSys26]]、[[NEST-MLSys26]]、[[AITurbo-FAST26]] 把弹性并行、计划执行和 checkpoint 加速接到 Megatron 生态。
- **2026·agent-native 对照**：[[PithTrain-arXiv26]] 固定 Claude Code 与训练系统任务，对比 Megatron-LM 的 registry、runtime spec 和 native extension 路径；结果说明这些生产抽象会增加局部 feature integration 成本，但没有覆盖跨模型共享修改可能获得的复用收益。
- **2026·OSDI**：[[Hetu-v2-OSDI26]]、[[Tessera-OSDI26]]、[[TrainMover-OSDI26]]、[[Kareus-OSDI26]] 分别改写了非对称并行、MoE 流水计划、成员迁移和时间—能耗调度边界。

## 相关概念

- [[Tensor-Parallelism]]
- [[Pipeline-Parallelism]]
- [[Data-Parallelism]]
- [[Expert-Parallelism]]
- [[MoE]]

## 相关论文

- [[TrainMover-OSDI26]] — 保留既有 parallel layout 的 rank 接替和增量 communicator 切换。
- [[Tessera-OSDI26]] — 从实测局部 schedule 联合求 MoE pipeline partition。
- [[Hetu-v2-OSDI26]] — 对非对称设备与运行时重分片的补充路线。
- [[Kareus-OSDI26]] — 在 Megatron-LM 上联合调整通信与 GPU 频率。
- [[OpGuard-OSDI26]] — 把 Megatron 训练执行变成可对齐的故障诊断对象。
- [[Chen-LLMDataPipelines-OSDI26]] — 用包括 Megatron 在内的生产任务刻画大模型数据管道。
- [[Seer-OSDI26]]、[[RLinf-OSDI26]]、[[DynaRL-OSDI26]]、[[RollArt-OSDI26]] — 将 Megatron 作为 RL trainer backend，再分别重写 rollout 调度、资源编排或跨域权重同步；它们的端到端收益不能归因于 Megatron 本身。
