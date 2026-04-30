---
type: concept
aliases: [Expert Parallelism, expert-parallel, EP, MoE Expert Parallelism]
parent: "[[MoE]]"
last_updated: 2026-04-24
tags: [moe, distributed-training, llm-inference, parallelism]
---

# Expert-Parallelism

> [[MoE]] 专用的并行切法：把每一层的 N 个 expert 分到 N/g 张 GPU 上，每张负责 g 个 expert。token 经过 router 选 top-k expert 后，按目标 GPU 重排（[[AllToAll]] dispatch）→ 在本地 expert 上算 FFN → 再 [[AllToAll]] combine 回原位置。通信模式由 AllReduce 变成 AllToAll，对网络拓扑和 LB 极度敏感。DeepSeek-V3 把 EP 推到 256 卡、[[DeepEP]] 给 H800 做了 custom NVLink/RDMA 协议，2025 年一整年 MoE 系统研究的主线都是 EP 调度。

## 为什么需要 EP

MoE 模型（671B DeepSeek、400B+ Qwen3）的参数 70% 以上在 expert FFN。如果走 [[Tensor-Parallelism|TP]]，每层要把整张巨大 FFN 都搬到所有卡，不划算。把 expert 切到不同 GPU 更自然：
- 每卡存 `N_expert / N_gpu` 个 expert 的权重
- token 稀疏激活：每 token 只经过 top-k（通常 2-8）个 expert
- 通信量 ∝ token 数 × hidden_dim × k，而非权重大小

## 通信模式

```
前向：
  attention → router 决定每 token 去哪些 expert
  AllToAll dispatch：按 expert 位置重排 token
  FFN（本地 expert）
  AllToAll combine：把结果送回 token 原位置
  continue
```

两次 AllToAll 是核心 overhead。DeepSeek 的 [[DeepEP]] 观察到 H800 节点内 NVLink 160 GB/s、跨节点 RDMA 50 GB/s，异构带宽让 naive AllToAll 严重倾斜，于是设计了 hierarchical 协议（节点内 + 跨节点分阶段）。

## 负载均衡（核心难点）

- **Token imbalance**：router 的 softmax 倾向于选少数"热"expert，导致部分 GPU 过载
- **Auxiliary load-balancing loss**：训练时加正则项压制倾斜，但伤模型质量
- **Expert bias / redundant experts**：DeepSeek-V3 改用 bias 调整 routing；[[NEST-MLSys26]] / [[MoEBlaze-MLSys26]] 等系统工作在 serving 时做动态 expert 复制或迁移

## EP 与其他并行维度的组合

- **TP + EP**：专家内部再 TP，处理单 expert 仍然大的情况
- **DP + EP**：attention 部分走 DP（每卡完整 attention 权重），FFN 走 EP
- **PP + EP**：跨 layer 的 PP 切分，每 PP stage 内再 EP
- **ZeRO + EP**：optimizer/grad 在 EP 组内 shard

## 推理时的特殊问题

- **[[Disaggregation]] + EP**：prefill 和 decode 的 expert 访问模式不同（prefill 是 dense batch、decode 是 sparse token），DeepSeek-V3 推理架构给两阶段配不同 EP 度数
- **Expert caching**：decode 阶段某些 expert 常年不触发，可以驱逐出 HBM（[[FluxMoE-arXiv26]]）
- **LB for tail latency**：一次 AllToAll 要等最慢的 GPU，[[LatencyOptimal-MoELB-INET4AI25]] 研究 LB 算法下界

## 引用本概念的论文

- [[FP8FlowMoE-MLSys26|FP8FlowMoE]]、[[NEST-MLSys26|NEST]]、[[MoEBlaze-MLSys26|MoEBlaze]]、[[CRAFT-MLSys26|CRAFT]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]] — EP 训练 / 推理 / 通信
- [[Libra-ICLR26|Libra]]、[[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — MoE LB 专项
- [[ParallelKittens-MLSys26|ParallelKittens]]、[[AXLearn-MLSys26|AXLearn]]、[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 框架 / 训练 / Disagg 里的 EP

## 相关概念

- 上游：[[MoE]]
- 并行维度：[[Tensor-Parallelism]]、[[Data-Parallel]]、[[Pipeline-Parallelism]]
- 通信：[[AllToAll]]、[[Collective-Communication]]、[[DeepEP]]、[[RDMA]]、[[NVLink]]
- Routing：[[Top-K-Gating]]、[[Routing]]、[[Load-Balancing]]
