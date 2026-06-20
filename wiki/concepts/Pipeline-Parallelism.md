---
type: concept
aliases: [Pipeline Parallelism, pipeline-parallel, PP, GPipe, PipeDream, 1F1B, interleaved 1F1B]
parent: "[[LLM-Inference]]"
introduced_by: "[[GPipe-arXiv18]]"
last_updated: 2026-06-20
tags: [distributed-training, parallelism]
---

# Pipeline-Parallelism

> 把模型按 layer 切成多个 stage，每个 stage 放到一组 GPU；mini-batch 再切成 micro-batch 在不同 stage 间流水执行。核心痛点是首尾 pipeline bubble 和 activation 内存——GPipe / PipeDream / 1F1B / Interleaved 1F1B 是围绕降 bubble 的演进线。跨节点通信只在 stage 边界 send/recv activation，带宽要求远低于 [[Tensor-Parallelism|TP]]，因此 PP 是 3D 并行里跨机器的主力。

## 核心思想

模型 L 层切成 S 个 stage，每 stage L/S 层；batch 切成 M 个 micro-batch：

```
stage0: mb0 → mb1 → mb2 → mb3 → mb4 → ...
stage1:       mb0 → mb1 → mb2 → mb3 → ...
stage2:             mb0 → mb1 → mb2 → ...
stage3:                   mb0 → mb1 → ...
```

stage 间只传 activation（forward）和 gradient（backward），通信量 ∝ batch × hidden × seq_len。对比 TP：TP 每层 AllReduce，PP 每 L/S 层 send/recv，通信量大约缩小 1/(L/S) 倍但通信次数 × S 流水。

**Bubble**：warm-up（前 S-1 个 micro-batch 末 stage 空转）+ cool-down。bubble 占比 ≈ (S-1)/(M + S-1)，要求 M ≫ S。演进上：GPipe 先全部 forward 再 backward（activation O(M)）；PipeDream 1F1B 每 stage 做完 forward 立即 backward（activation O(S)）；Interleaved 1F1B 每卡放多个非相邻 stage，bubble 再降一半但通信翻倍；Zero-bubble PP（2023）手工调度 weight gradient 填 bubble；Chimera / DualPipe（DeepSeek-V3）双向 pipeline 同时跑。

activation 内存常与 activation checkpointing、[[ZeRO]]/[[FSDP]]、sequence parallelism 组合使用。

## 为什么重要

PP 是跨越 NVLink 域、把模型铺到多机多卡的基础切分维度。与 TP 的「每层通信」不同，PP 把通信频率降到 stage 边界，使 InfiniBand 带宽足以支撑大规模训练。这些论文共同假设：**bubble 占比与 microbatch 数、stage 数、调度策略三者绑定，是 PP 效率的第一性变量**。

在推理 serving 中，PP 近年出现非标准用法：Chunked Pipeline Parallelism（CPP）把长 prompt 分 chunk 沿 PP 流水（[[NVIDIA-Disagg-Study-MLSys26]]），紧 FTL 长上下文下优于宽 TP；[[SHIP-MLSys26]] 在 LPU 上用 TP+PP 异构分区 + dynamic chunked prefill 消除 bubble；[[FlexTrain-MLSys26]] 把 PP 作为弹性训练唯一可 bitwise 一致的扩缩维度。PP 还与 ZeRO 存在根本张力——[[Zorse-MLSys26]] 指出 ZeRO-2 省通信但 materialize 全 stage 参数，ZeRO-3 省显存但 gather 频率 × microbatch 数。

## 关键观察 / 隐含假设

- **观察 1：紧 FTL 长上下文下，prefill 侧 CPP（chunk 沿 PP 流水）一致优于宽 [[Tensor-Parallelism|TP]]。** [[NVIDIA-Disagg-Study-MLSys26]] 在 DeepSeek-R1 ISL=256K、64 GPU 上显示增大 PP 可同时压 FTL 又保吞吐；通信量 send/recv 相对 TP allreduce 小得多。
- **观察 2：PP 是弹性训练中唯一可保持 bitwise 确定性的扩缩维度。** [[FlexTrain-MLSys26]] 指出 DP 扩缩必然引入非确定性累加顺序，严格精度一致模式下仅 PP 可扩；代价是停训 + 全量 checkpoint，浅层模型加速上限低。
- **观察 3：PP 与 ZeRO 的冲突本质是参数 gather 频率 vs 驻留显存。** [[Zorse-MLSys26]] Table 1 对比 Zorse interleaved ministage PP + ZeRO 与 PP+ZeRO-2/3：ZeRO-2 省通信但 materialize 全 stage 参数；ZeRO-3 省显存但 gather 频率 × microbatch 数。
- **观察 4：LPU 异构 serving 中 PP bubble 可用极小 chunk prefill 消除。** [[SHIP-MLSys26]] 用 dynamic chunked prefill（1–2 token chunk 即可饱和 self-attention）+ fused context-batch 消除 pipeline bubble；但 LPUv1 peak FLOP/s 效率低于 GPU，C2C 带宽失配导致 exposed communication。

## 设计空间与取舍

- **路线 1：经典 1F1B（PipeDream）**：activation O(S)，bubble ≈ (S-1)/(M+S-1)；牺牲是 M 要足够大，小 batch 训练效率低。
- **路线 2：Interleaved 1F1B（Megatron 2021）**：每卡多个非相邻 stage，bubble 减半；牺牲是 stage 间通信翻倍、调度复杂度上升。
- **路线 3：Zero-bubble / DualPipe**：手工或双向调度填 bubble；牺牲是实现与调试成本，DeepSeek-V3 级工程投入。
- **路线 4：PP + ZeRO 组合（Zorse / FlexTrain）**：interleaved ministage + CPU offload 兼顾显存与通信；牺牲是 host memory 与 PCIe prefetch 依赖（[[Zorse-MLSys26]] 不支持 TP）。
- **路线 5：推理侧 CPP（Chunked Pipeline Parallelism）**：长 prompt 分 chunk 沿 PP 流水，适合 prefill-heavy disagg；牺牲是与 co-located [[Chunked-Prefill]] piggyback 的对比基线需公平（[[NVIDIA-Disagg-Study-MLSys26]] 局限 4）。
- **路线 6：非标准 PP 用法**：流式推理（[[StreamDiffusionV2-MLSys26]]）、layer 调度（[[LayeredPrefill-MLSys26]]）、geo-distributed partial sync（[[DreamDDP-MLSys26]]）；牺牲是通用框架支持不足。

## 引用本概念的论文

- [[GPipe-arXiv18|GPipe]] — 原始 pipeline parallel：micro-batch 流水，bubble 与 activation O(M) 问题
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 紧 FTL 下 prefill 侧 CPP 优于宽 TP；数十万 disagg 设计点扫描
- [[FlexTrain-MLSys26|FlexTrain]] — 弹性训练以 PP 为主扩缩维度保 bitwise 一致，在线 DAG profiling + Poisson 调度
- [[Zorse-MLSys26|Zorse]] — interleaved ministage PP + ZeRO 兼顾显存与通信，异构集群 planner
- [[SHIP-MLSys26|SHIP]] — QuadFour 拓扑 TP+PP 异构分区，dynamic chunked prefill 消除 bubble
- [[BEAM-MLSys26|BEAM]] — PP 下 chunk size 与 microbatch 作为能耗优化旋钮
- [[FaaScale-MLSys26|FaaScale]] — serverless scale-out 时动态拼 cross-node execution pipeline
- [[Chakra-MLSys26|Chakra]]、[[ProTrain-MLSys26|ProTrain]]、[[BOUTE-MLSys26|BOUTE]]、[[BOOST-MLSys26|BOOST]]、[[HexiScale-MLSys26|HexiScale]]、[[NEST-MLSys26|NEST]]、[[HetRL-MLSys26|HetRL]] — 训练 scheduler / planner
- [[AXLearn-MLSys26|AXLearn]]、[[ParallelKittens-MLSys26|ParallelKittens]]、[[DistCA-MLSys26|DistCA]]、[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 框架 + 分布式 attention + disagg 里的 PP
- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]]、[[AttnRes-arXiv26|AttnRes]]、[[LayeredPrefill-MLSys26|LayeredPrefill]] — 非 standard PP 用法
- [[DreamDDP-MLSys26|DreamDDP]] — geo-distributed Local SGD layer-wise partial sync，overlap 参数通信与 backward
- [[Optimus-ATC25|Optimus]]、[[ByteRobust-SOSP25|ByteRobust]]、[[TrainVerify-SOSP25|TrainVerify]]、[[FlexPipe-ATC25|FlexPipe]]、[[PPipe-ATC25|PPipe]] — MLLM / fault tolerance / pipeline 优化
- [[Charon-MLSys26|Charon]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]]、[[FP8FlowMoE-MLSys26|FP8FlowMoE]] — 仿真 / 通信 overlap / MoE 训练中的 PP

## 已知局限 / 开放问题

- bubble 占比在小 microbatch 或浅模型时仍高；[[FlexTrain-MLSys26]] 严格精度模式下仅 PP 可扩，加速上限受 batch 约束
- PP + ZeRO resharding 的 in-place 实现仍是开放问题（[[FlexTrain-MLSys26]]、[[Zorse-MLSys26]] 均需停训 checkpoint）
- 推理侧 CPP 与 co-located [[Chunked-Prefill]]、[[LayeredPrefill-MLSys26]] 等新一代调度的公平对比不足（[[NVIDIA-Disagg-Study-MLSys26]] 局限 4）
- 异构硬件（LPU+GPU，[[SHIP-MLSys26]]）上 PP 的 C2C 带宽失配与 exposed communication 未完全解决
- 动态集群（云环境节点弹性）上的 PP 重配置与 scale table 失效策略待验证（[[FlexTrain-MLSys26]] future work）