---
type: entity
kind: system
aliases: [Megatron-LM, Megatron-Core, Megatron]
status: active
last_updated: 2026-06-20
tags: [llm-training, distributed-training, tensor-parallel, pipeline-parallel, expert-parallel]
---

# Megatron

> NVIDIA 主导的大规模 LLM 分布式训练框架（Megatron-LM / Megatron-Core），以 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]] 与 [[3D-Parallelism]] 为核心抽象，是当前论文中最常被当作 baseline、插件宿主与执行栈的 industrial training runtime 之一。

## 是什么

Megatron 是 NVIDIA 为大规模 Transformer 预训练设计的分布式训练栈，社区与论文中常称 **Megatron-LM**（经典实现）或 **Megatron-Core**（模块化核心库）。其核心能力是把模型按层与算子维度切分到多 GPU：[[Tensor-Parallelism]] 在 attention/MLP 内切分参数与激活；[[Pipeline-Parallelism]] 用 1F1B、interleaved 1F1B、zero-bubble 等 schedule 沿层维流水；[[Data-Parallelism]] 与 ZeRO 族 optimizer sharding 组合成工业界常说的 **3D parallel**；MoE 场景下再叠加 [[Expert-Parallelism]] 与 token dispatch/combine collective。

这些论文共同把 Megatron 视为「hand-tuned hybrid parallelism + NCCL collective + 可插拔训练模块」的事实标准，而非通用 auto-parallel compiler。它的边界也很清楚：论文反复指出 Megatron 假设 dense 或标准 MoE Transformer、同步训练语义、以及按固定 parallel plan 启动的长跑 job；对 MLLM 异构结构、变长 iteration、跨 DC 网络、或弹性扩缩，朴素 Megatron 配置往往留下可观 bubble 或工程摩擦，需要专门系统（[[Optimus-ATC25]]、[[FlexPipe-ATC25]]、[[CrossPipe-ATC25]] 等）在其之上改造。

与 [[DeepSpeed]]、[[FSDP]]、Alpa 等相比，Megatron 在 wiki 图谱中的角色更偏 **生产级执行面**：[[NEST-MLSys26]] 输出 placement plan 后交给 Megatron/NeMo 执行；[[PopFetcher-ATC25]]、[[Greyhound-ATC25]]、[[FlexTrain-MLSys26]] 直接以 Megatron-LM 为集成目标；[[FarSkip-Collective-MLSys26]] 在 Megatron MoE recipe 上实现 EP 通信重叠。与此同时，Megatron 也常作为 **强 baseline** 出现——[[Optimus-ATC25]] 在 3072 GPU 上对比 Megatron-LM balanced；[[CrossPipe-ATC25]] 在 GH200 集群上对比 1F1B/ZBV 等 Megatron 风格 schedule；[[BOOST-MLSys26]] 指出 vanilla Megatron TP 对低秩 bottleneck 架构通信暴涨。

## 关键观察 / 隐含假设

- **观察 1：Megatron 是「可改造训练壳」，但深度优化往往意味着非 trivial fork 或插件。** [[Greyhound-ATC25]] 的 DETECT 可与 Megatron 解耦（只 hook [[NCCL]]），但 MITIGATE 需 **1.5k LOC Megatron-LM plugin** 改 micro-batch 与 topology；[[PopFetcher-ATC25]] 是 **8000+ LOC PyTorch 插件**接 Megatron EP；[[FlexTrain-MLSys26]] 基于 Megatron-LM 扩展 **9000+ LOC** 弹性 PP。这些论文共同假设：引用 Megatron 数字时必须区分 vanilla upstream 与论文自定义 patch。
- **观察 2：Megatron 的 pipeline / collective 语义是后续调度创新的隐含前提。** [[CrossPipe-ATC25]] 指出 Megatron-LM 风格 **grouped send/recv** 在跨 DC delay 下会引入额外同步等待，并在 Megatron 内加入 CrossPipe module；[[Obscura-ATC25]] 把 Megatron-LM 列为同类 PP 系统，强调 1F1B bubble 形态决定 recomputation 能否被隐藏；[[Optimus-ATC25]] 假设生产 MLLM 已跑在 Megatron/MegaScale 式 3D stack 上，**~48% GPU cycle idle** 来自 DP/PP/TP 通信而非 encoder 算力本身。
- **观察 3：Megatron checkpoint 与通信初始化成本被下游系统反复当作优化靶点。** [[AITurbo-FAST26]] 测得 Megatron 约 **1/4 codebase（2228 LoC）** 在做 checkpoint 优化仍次优，且 **NCCL group init 可达数分钟**；集成 AITurbo 后仅需 **286 LoC**，并对齐 Megatron DCP / PyTorch DCP 的 tensor-native 文件思路。论文暗示：Megatron 训练栈的 I/O 与 init 路径与计算内核同样值得系统层关注。
- **观察 4：Megatron 作为并行基线，其「朴素切分」在异构 workload 上会成为攻击面。** [[Optimus-ATC25]] 称 Megatron-LM 把 **所有 encoder 放第一 PP stage**，多 encoder 时异构 imbalance 更严重（最高 **1.27×** gap）；[[BOOST-MLSys26]] 称低秩架构下 vanilla Megatron TP 在 4 GPU 上通信占比 **>20% 并爆炸**；[[FlexPipe-ATC25]] 虽未直接改 Megatron，但指出静态 PP 按 max sequence length 配置在变长 mixture 训练中长期 under-utilize——工业 Megatron 作业常沿此静态假设运行。
- **观察 5：Megatron 是 planning 与 runtime 之间的「落地缝隙」承载者。** [[NEST-MLSys26]] 输出 plan 可在 Megatron-LM/NeMo 执行，但 **不保证 EP dispatch、ZeRO offload 等实现细节零摩擦**；plan→runtime glue code 工程风险被论文列为系统性缺陷。类似地，[[FarSkip-Collective-MLSys26]] 需改 Megatron MoE forward/backward 顺序与 autograd 才能兑现 **88.4% EP overlap**，说明 Megatron 抽象并不自动包含最新通信重叠语义。

## 演进时间线

- **经典 Megatron-LM 时代**：确立 TP + PP + DP 3D 并行、1F1B pipeline、分布式 checkpoint 等工业训练范式；[[Obscura-ATC25]]、[[CrossPipe-ATC25]] 等仍以 Megatron-LM schedule 与通信布局为讨论起点。
- **2025 ATC 集群**：训练栈开始围绕 Megatron **填 bubble、治 straggler、加速 MoE**——[[Optimus-ATC25]] 利用 MLLM 双组件结构塞满 Megatron bubble；[[Greyhound-ATC25]] 在生产 fail-slow 场景用 Megatron plugin 做 mitigation；[[PopFetcher-ATC25]] 在 Megatron EP 上叠加 expert prefetch；[[CrossPipe-ATC25]] 在 Megatron 内实现跨 DC delay-aware PP；[[FlexPipe-ATC25]] 将 Megatron-LM 列为 variable-length PP 同类系统。
- **2026 MLSys / FAST 周边**：Megatron 从「被对比的 baseline」转为「被扩展的 platform + 被优化的外围」——[[FlexTrain-MLSys26]] 以 Megatron-LM 为弹性 PP 宿主；[[NEST-MLSys26]] 将 Megatron 作为 plan 执行目标；[[FarSkip-Collective-MLSys26]] 在 Megatron 上实现 MoE EP 架构级重叠；[[BOOST-MLSys26]] 针对 Megatron TP 与低秩架构的不匹配提出 BTP；[[AITurbo-FAST26]] 把 Megatron checkpoint 路径从框架内重度优化改为存储层透明加速。

## 相关概念

- [[Tensor-Parallelism]]（Megatron 最核心的切分维度）
- [[Pipeline-Parallelism]]、[[1F1B]]、[[Pipeline-Bubble]]、[[Zero-Bubble-Pipeline]]
- [[Data-Parallelism]]、[[3D-Parallelism]]
- [[Expert-Parallelism]]、[[MoE]]、[[All-to-All]]
- [[Checkpoint]]、[[NCCL]]

## 相关论文

- [[Optimus-ATC25]] — 以 Megatron-LM/MegaScale 3D stack 为强 baseline，揭示 MLLM 训练 ~48% idle bubble 并用 encoder kernel 级调度填充
- [[Greyhound-ATC25]] — DETECT 框架无关，MITIGATE 为 Megatron-LM plugin，做 fail-slow 四级缓解
- [[CrossPipe-ATC25]] — 在 Megatron-LM 内实现跨 DC delay-aware pipeline schedule 与 NCCL 执行引擎
- [[PopFetcher-ATC25]] — 可接 Megatron-LM 的 MoE expert prefetch 插件，重叠 EP All-to-All 与 Attention 计算
- [[FlexTrain-MLSys26]] — 基于 Megatron-LM 实现弹性 PP、在线 DAG profiling 与 Poisson 调度
- [[NEST-MLSys26]] — 纯 planning 系统，输出并行配置供 Megatron-LM/NeMo 执行
- [[FarSkip-Collective-MLSys26]] — 在 Megatron MoE recipe 上实现 partial/outdated activation 与 **88.4%** EP 通信重叠
- [[Obscura-ATC25]] — 1F1B pipeline recomputation 调度，将 Megatron-LM 列为同类 PP 训练系统
- [[FlexPipe-ATC25]] — 变长输入动态 PP 重配，与 Megatron-LM 静态 PP 假设形成对比
- [[BOOST-MLSys26]] — 指出 vanilla Megatron TP 对低秩 bottleneck 架构通信不友好，提出 BTP 协同设计
- [[AITurbo-FAST26]] — 相对 Megatron 重度 checkpoint 代码，用 grouped I/O API 透明加速训练 checkpoint 读写