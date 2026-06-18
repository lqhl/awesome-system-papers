---
type: concept
aliases: [Pipeline Parallelism, pipeline-parallel, PP, GPipe, PipeDream, 1F1B, interleaved 1F1B]
parent: "[[LLM-Inference]]"
introduced_by: "[[GPipe-arXiv18]]"
last_updated: 2026-04-24
tags: [distributed-training, parallelism]
---

# Pipeline-Parallelism

> 把模型按 layer 切成多个 stage，每个 stage 放到一组 GPU（一个 "pipeline stage"）。mini-batch 再切成若干 micro-batch，让不同 micro-batch 在不同 stage 同时流动，像工厂流水线一样。核心痛点是首尾的 "bubble"（pipeline 空转）和 activation 内存——GPipe / PipeDream / 1F1B / Interleaved 1F1B 是一条围绕降 bubble 的演进线。跨节点通信只发生在 stage 边界上（send/recv 激活），带宽要求远低于 [[Tensor-Parallelism|TP]]，所以 PP 是 3D 并行里跨机器的主力。

## 核心思想

模型 L 层，切成 S 个 stage 每 stage L/S 层；batch 切成 M 个 micro-batch：

```
stage0: mb0 → mb1 → mb2 → mb3 → mb4 → ...
stage1:       mb0 → mb1 → mb2 → mb3 → ...
stage2:             mb0 → mb1 → mb2 → ...
stage3:                   mb0 → mb1 → ...
```

- stage 间只传 activation（forward）和 gradient（backward），通信量 ∝ batch × hidden × seq_len
- 对比 TP：TP 每层 AllReduce，PP 每 L/S 层 send/recv，通信量大约 1/(L/S) 但通信次数 × S 流水

**Bubble**：warm-up (前 S-1 个 micro-batch stage S-1 还没开始工作) + cool-down。bubble 占比 ≈ (S-1)/(M + S-1)，M 要远大于 S。

## 演进

| 方案 | 特点 |
|---|---|
| **GPipe** (2018) | 所有 micro-batch forward 完再统一 backward，activation 占内存 O(M) |
| **PipeDream** (2019) | 1F1B：每 stage 做完 forward 立即做该 micro-batch 的 backward，activation O(S) |
| **Interleaved 1F1B** (Megatron 2021) | 每卡放多个非相邻 stage，bubble 再降一半，通信翻倍 |
| **Zero-bubble PP** (2023) | 手工调度 weight gradient 计算填进 bubble，bubble ~ 0 |
| **Chimera / DualPipe** (DeepSeek-V3) | 双向 pipeline 同时跑，通信与计算完全 overlap |

## Activation 内存问题

1F1B 下每 stage 需要缓存 M 个 activation（对应 in-flight micro-batch）。与：
- **Activation checkpointing / recomputation**：反向时重算前向，省内存换 33% 算力
- **[[ZeRO]] / [[FSDP]]**：把 optimizer / grad / param 再 shard 到 DP 维度
- **Sequence parallelism**：LayerNorm 的 activation 按 seq 切

## 与其他并行维度的组合

典型 3D 并行（Megatron-Turing NLG 530B、DeepSeek-V3）：
- **TP** 机内 8 卡（NVLink）
- **PP** 跨机器 + 跨 stage（IB）
- **DP** 跨 PP 副本（最外层）

对于 MoE：再加 **EP** 维度，通常 EP ⊆ DP 组。

## 引用本概念的论文

- [[Zorse-MLSys26|Zorse]] — Pipeline-Efficient ZeRO DP：interleaved ministage PP + ZeRO 兼顾显存与通信
- [[FaaScale-MLSys26|FaaScale]] — serverless scale-out 时动态拼 cross-node execution pipeline
- [[Chakra-MLSys26|Chakra]]、[[ProTrain-MLSys26|ProTrain]]、[[BOUTE-MLSys26|BOUTE]]、[[BOOST-MLSys26|BOOST]]、[[HexiScale-MLSys26|HexiScale]]、[[NEST-MLSys26|NEST]]、[[HetRL-MLSys26|HetRL]] — 训练 scheduler / planner
- [[FlexTrain-MLSys26|FlexTrain]] — 弹性训练以 PP 为主扩缩维度保 bitwise 一致，在线 DAG profiling + Poisson 调度吃潮汐 GPU，JCT 最多 1.73×
- [[AXLearn-MLSys26|AXLearn]]、[[ParallelKittens-MLSys26|ParallelKittens]]、[[DistCA-MLSys26|DistCA]]、[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 框架 + 分布式 attention + disagg 里的 PP
- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]]、[[AttnRes-arXiv26|AttnRes]]、[[LayeredPrefill-MLSys26|LayeredPrefill]] — 非 standard PP 用法（流式推理 / layer 调度）
- [[DreamDDP-MLSys26|DreamDDP]] — geo-distributed Local SGD 的 layer-wise partial sync，overlap 参数通信与 backward
- [[SHIP-MLSys26|SHIP]] — QuadFour 拓扑把数千 LPU pipeline/tensor 并行，dynamic chunked prefill 消除 bubble

## 相关概念

- 并行维度：[[Tensor-Parallelism]]、[[Data-Parallel]]、[[Expert-Parallelism]]、[[Context-Parallelism]]
- 内存：[[ZeRO]]、[[FSDP]]、Activation Checkpointing
- 实现：[[Megatron]]、[[DeepSpeed]]
- 通信：[[Collective-Communication]]
