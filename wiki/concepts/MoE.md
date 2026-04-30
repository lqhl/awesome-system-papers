---
type: concept
aliases: [MoE, Mixture of Experts, Mixture-of-Experts, mixture of experts]
parent: "[[Transformer]]"
last_updated: 2026-04-24
tags: [llm-architecture, sparse-activation, scaling]
---

# MoE (Mixture of Experts)

> 用 router + 多个稀疏激活的 expert 子网络替代单个大 FFN，让模型参数量与每 token 计算量解耦——成为 2024 起 frontier LLM 的事实标配（DeepSeek-V3、Qwen3MoE、GLM-4.5、Kimi-K2 都是 MoE）。但 MoE 的负载均衡和通信效率是系统层最棘手的问题之一。

## 核心思想

经典 dense transformer：每层一个大 FFN，所有 token 走同样路径。
MoE：每层换成 N 个小 FFN（experts）+ 一个 router；每个 token 由 router 选 top-K（典型 K=2 或 8）个 expert，只在选中的 expert 上做计算。

效果：参数量 ×N 但 FLOPs 不变（因为只激活 K/N 子集），让模型能力可以快速 scale 到 trillion-parameter（DeepSeek-V3 671B、Kimi-K2 1T）但训推算力可控。

## 系统层挑战

MoE 让模型 capacity 上去了，但给系统层带来三类核心难题：

### 1. Expert load imbalance

不同 token 的 routing 分布不均匀，少数 hot expert 的 GPU 成为 straggler，决定整层延迟。modern MoE 模型为了 expert specialization 放弃了严格的 load-balancing loss，imbalance 反而恶化。

解决方向：
- Training time: auxiliary loss
- Inference time: expert replication（[[Libra-ICLR26|Libra]]、[[LatencyOptimal-MoELB-INET4AI25|LatencyOptimal-MoELB]]、EPLB、Lina、HarMoEny）
- Hot expert placement / dynamic reallocation

### 2. Expert parallelism 通信

[[Expert-Parallelism]] 把 expert 散到多 GPU，每层都要 all-to-all dispatch（router → expert）和 combine（expert → 下一层输入）。这是 MoE 系统的主要通信负载。

解决方向：
- Specialized P2P 通信（[[fabric-lib-MLSys26|fabric-lib]]、DeepEP、UCCL-EP、NVSHMEM）
- 算子融合 / overlap（与 attention 重叠）

### 3. Memory footprint

虽然只激活 K/N expert，但所有 expert 权重都要常驻内存（除非动态 swap）。这与 [[KV-Cache]] 一起挤压 HBM。

## 相关概念

- 上游：[[Transformer]]、[[FFN]]
- 子概念：[[Expert-Parallelism]]、[[Load-Balancing]]、[[Routing]]、[[Top-K-Gating]]
- 相关：[[Continuous-Batching]]、[[Speculative-Decoding]]
- 通信：[[RDMA]]、[[NVLink]]

## 引用本概念的论文

- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1.6T(49B 激活)与 284B(13B 激活)两个 DeepSeekMoE 模型;sigmoid→sqrt(softplus) affinity;前几层换 Hash routing;MegaMoE 融合 EP kernel 1.5-1.96× 加速
- [[Libra-ICLR26|Libra]] — Two-Stage Locality-Aware Execution + speculative gating prediction
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡和搬运代价
- [[fabric-lib-MLSys26|fabric-lib]] — MoE dispatch/combine over P2P RDMA
- [[AttnRes-arXiv26|Attention Residuals]] — 应用在 Kimi Linear MoE 模型（48B/3B-active）上做架构改进
- [[FluxMoE-arXiv26|FluxMoE]] — expert paging：把 expert 当虚存分页流式装载，2-layer sliding window + 压缩 GPU + CPU offload 腾 HBM 给 KV cache，Qwen3-Next-80B 上 3.0× over vLLM

## 代表 MoE 模型

- Switch Transformer (Fedus 2022)
- GShard (Lepikhin 2020)
- Mixtral (Jiang 2024)
- DeepSeek-V3 671B / DeepSeek-V2 / [[DeepSeek-V4-arXiv26|DeepSeek-V4]]-Pro 1.6T / Flash 284B
- Qwen3MoE 235B
- GLM-4.5 355B
- Kimi-K2 1T
- gpt-oss (OpenAI 2025)

## 已知局限 / 开放问题

- decode 阶段 + 多节点的 LB 仍是开放问题（Libra/INET4AI 都聚焦 prefill + 单节点）
- expert placement 在异构硬件（不同代 GPU 混布）下尚无成熟方案
- expert specialization 与 load-balancing loss 之间的 trade-off 没有理论指导
