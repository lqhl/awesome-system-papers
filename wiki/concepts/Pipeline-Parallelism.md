---
type: concept
aliases: [Pipeline Parallelism, Pipeline-Parallel, pipeline-parallel, PP, GPipe, PipeDream, 1F1B, interleaved 1F1B]
parent: "[[LLM-Inference]]"
introduced_by: GPipe (arXiv 2018)
last_updated: 2026-08-18
tags: [distributed-training, parallelism]
---

# Pipeline-Parallelism

> 流水线并行（pipeline parallelism，PP）把模型的层分成多个 stage，每个 stage 放在不同设备上；再把 batch 分成 microbatches，让不同 stage 同时处理不同 microbatch。它以 activation/gradient 边界通信换取超大模型容量和较低的跨设备通信频率。

## 核心思想

训练中，前向 activation 沿 stage 0 到 stage S-1 流动，反向 gradient 反向返回。如果一次只跑一个 batch，绝大多数 stage 会等待；分成 microbatches 后，已完成前一 stage 的 microbatch 可与后续 microbatch 重叠。

常见 schedule 包括：

- **GPipe**：先跑所有 forward，再跑所有 backward；简单，但 activation 存储和 warmup/cooldown bubble 较大。
- **1F1B**：warmup 后交替一个 forward 和一个 backward，降低峰值 activation。
- **interleaved 1F1B**：每个设备持有多个虚拟 stage，用更细交错减 bubble，但 schedule 和通信更复杂。
- **zero-bubble/延后 Wgrad**：将有 deadline slack 的 weight-gradient task 移到气泡中。

在推理中，PP 没有训练的 backward，但又有另一个动态问题：prefill 一次处理许多 token，decode 每轮只处理一个 token，请求长度与到达时间还不同。所以 serving PP 的 microbatch/chunk 必须随 TTFT、TPOT 与 batch 变化。

## 为什么重要

PP 的主要优势是跨 stage 只发 activation/gradient，而不是在每层频繁做大 collective。当模型单卡放不下、PCIe 或跨机链路不适合高频 [[Tensor-Parallelism]] 时，PP 很有价值。但系统吞吐由最慢 stage 和重叠后关键路径决定，不是简单将 layer FLOPs 均分。

OSDI 2026 给出了两个相反但互补的例子：

- [[Tessera-OSDI26]] 面向 4,096–12,288 张 Hopper 的超大 MoE 训练，先实测 layer-pair 内部的细粒度重叠，再选 stage partition。
- [[DCP-OSDI26]] 面向单机 4 张 A100 PCIe 的 LLM serving，不改 stage partition，只在线改 prefill chunk 和 decode 请求顺序。

前者处理长期稳定但层内异构的大训练，后者处理到达和 phase 不断变化的在线推理。它们不能共用一个“最佳 PP schedule”。

## 关键观察 / 隐含假设

- **stage balance 应按重叠后成本计算。** [[Tessera-OSDI26]] 发现异构 [[MoE]] 中，不同 layer pair 能隐藏的通信比例相差约 3 倍。如果先按串行 FLOPs 均分 stage，再给所有 stage 套同一 overlap，会在重叠后重新失衡。它的 20.0%–32.8% MFU 提升来自五个内部 Qwen3/Qwen3-Next 生产任务，不能外推到普通 dense 小集群。
- **可移动 task 有 deadline，不是可以任意延后。** Tessera 将 Wgrad 等 task 塞进 router 波动产生的气泡，但仍要在 optimizer/下一轮需要前完成，还要守住 activation/gradient memory budget。“zero bubble”是在依赖和内存约束下移动，不是气泡完全消失。
- **serving 中的最佳 chunk 会随模型和负载改变。** [[DCP-OSDI26]] 的 32B 主评测中，不同 trace 的最佳固定 chunk 是 256 或 512；14B Azure trace 又变成 1,024。这说明不能将 512 写成通用默认。
- **动态 chunk 的目标是用 slack 控制流水泡与尾延迟。** DCP 读取 TTFT slack、TPOT slack 和空闲 KV 比例，每隔一个 pipeline depth 调一次 chunk；delay scheduling 再把有余量的 decode 延后。在 Qwen2.5-32B、4 张 A100 PCIe 上，predictive 版本相对每条 trace 的最佳固定 chunk，Azure/CNN/ShareGPT 的 TPOT 降低 35%/42%/36%，E2E 降低 31%/36%/24%。主 SLO 是 P90 TTFT 2 秒、P90 TPOT 200 ms，没有跨节点、MoE 或异构 GPU 实验。
- **PP rank 的角色对称性可用来减少备机数量。** [[TrainMover-OSDI26]] 观察到 TP/DP/EP rank 大体对称，PP 常只有首段、中段、末段三类角色；一台 standby 分别 shadow-warm-up 这三类就可接替多个 rank。异构/多模态 stage、动态 layer 和数据依赖分支会打破这个假设。
- **动态异构需要运行时 reshard，不只是重切 stage。** [[Hetu-v2-OSDI26]] 用 HSPMD 在混合 GPU、故障后剩余 GPU 和 mixed-length data 上使用非对称 sharding，并在 graph 之间在线 reshard 参数/optimizer state。禁用 ZeRO-1 保留 DP redundancy 使正常 step 约增加 15%，表明弹性不是免费。
- **通信启动时机与 GPU 频率会反过来改变最佳 pipeline schedule。** [[Kareus-OSDI26]] 在 Megatron-LM 的 TP/PP/context parallel 训练上联合选通信启动位置、通信 SM 数和 DVFS。该方案假设分区重复且形状稳定；动态 MoE routing 或多租户干扰会让离线 Pareto 前沿漂移。
- **跨慢链路选 PP 还是 DP 有 crossover。** [[CrossPipe-ATC25]] 比较跨数据中心 PP/DP：PP 发 activation，DP 发 gradient/parameter collective，哪个更少取决于模型宽度、microbatch、带宽与可重叠比例，不能只用节点数决定。

## 设计空间与取舍

| 维度 | 选择 | 主要好处 | 主要代价 |
|---|---|---|---|
| stage partition | 按 FLOPs、内存、重叠后成本或异构硬件分 | 降低最慢 stage | profile/search 成本，路由漂移后失效 |
| microbatch 数 | 少到多 | 更多时 bubble 少 | activation memory、调度和同步开销上升 |
| schedule | GPipe、1F1B、interleaved、zero-bubble | 逐步降 bubble/内存 | dependency、weight version 和 recovery 更复杂 |
| serving chunk | 大 prefill chunk 到小 chunk | 大 chunk 利用计算，小 chunk 保 TPOT | TTFT/TPOT 互换，控制延迟 |
| parallel mix | PP 与 TP/DP/EP/CP 组合 | 适配模型与拓扑 | 搜索空间爆炸，collective 相互干扰 |
| 重配 | 静态长期 plan 或在线 reshard | 低开销或适应异构/故障 | state transfer、communicator 和一致性 |

## 引用本概念的论文

- [[GraphPipe-ASPLOS25]] — 将线性 stage chain 推广为 DAG，利用多分支 DNN 的独立 operator 并行；静态 profile/schedule 难适应 data-dependent graph。
- [[Tessera-OSDI26]] — 联合求异构 MoE 局部 schedule、stage partition 与可移动 task 填 bubble。
- [[DCP-OSDI26]] — 为 PP serving 动态选 prefill chunk，并用 decode slack 做 delay scheduling。
- [[TrainMover-OSDI26]] — 利用 PP 三类常见角色做通用 standby warm-up 和低中断接替。
- [[Hetu-v2-OSDI26]] — 在异构与故障后剩余设备上用非对称 graph 代替固定 SPMD layout。
- [[Kareus-OSDI26]] — 将通信时机、SM 配额和 GPU 频率放入 PP/TP 训练调度。
- [[RLinf-OSDI26]] — 把 RL 宏观 workflow 变换为 temporal/spatial/hybrid micro flows，组合 PP 与其他并行方式。
- [[DynaRL-OSDI26]] — 在 rollout/inference/trainer 资源移动时重建 TP/PP/DP 映射和 communicator。
- [[EcoServe-OSDI26]] — 说明推理 PP 还会受 prefill/decode 阶段切换、输入长度和 KV 传输影响。
- [[SDCHunter-OSDI26]] — 在 PP 通信边界记录 compact hash，先定位可疑 rank/group，再离线做昂贵的 layer-wise 比较。
- [[FlexTrain-MLSys26]] — 在弹性训练中调整 PP/DP 并考虑数值一致性。
- [[NEST-MLSys26]] — 将 planner 的组合并行计划落到 Megatron/NeMo runtime。
- [[CrossPipe-ATC25]] — 描绘跨数据中心慢链路上 PP 与 DP 的 crossover。
- [[FarSkip-Collective-MLSys26]] — 在 MoE 并行训练中改 forward/backward 顺序以隐藏 expert communication。
- [[ByteRobust-SOSP25]]、[[Mycroft-SOSP25]] — 从分布式训练故障与 hang 角度暴露 pipeline/collective 同步边界。
- [[PithTrain-arXiv26]] — 基于 DualPipeV 将 layer 拆为五阶段并重叠 EP all-to-all 与相邻 micro-batch forward/backward；吞吐对照支持固定配置下的效率，但没有测 stage failure、in-flight microbatch replay 或长期恢复。

## 已知局限 / 开放问题

- **缺少统一的重叠后 cost model。** compute、activation、collective、MoE routing、Wgrad deadline、memory 和 DVFS 相互影响；不同系统的 profile 粒度和硬件依赖很强。
- **在线动态 PP 的稳定性证据不足。** burst arrival、预测误差、fail-slow 和多租户可让 chunk/priority 控制振荡；应报 p99 SLO、公平性和切换频率。
- **weight version 与 in-flight microbatch 恢复尚未形成通用契约。** stage 迁移、重试或重新分片时，要明确哪些 activation/gradient 已消费，哪些可重放，哪些 optimizer update 已提交。
- **规划与执行仍高度绑定框架。** Tessera、TrainMover、FlexTrain 等都需要修改 Megatron/c10d/runtime；一个可移植的并行 plan IR 还不足以覆盖 kernel warm-up、communicator 和 failure semantics。
- **训练与推理不应共用一套完成度指标。** 训练应看 MFU、step time、收敛与恢复；serving 应看 TTFT、TPOT、goodput、KV 压力和公平性。
