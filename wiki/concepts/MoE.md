---
type: concept
aliases: [MoE, Mixture of Experts, Mixture-of-Experts, mixture of experts]
last_updated: 2026-07-30
tags: [llm-architecture, sparse-activation, scaling]
---

# MoE

> 混合专家模型（Mixture of Experts，MoE）由 router 为每个 token 选择少量 expert，在保持近似计算量的同时扩大参数容量；代价是 token dispatch、负载不均与 expert memory placement。

## 核心思想

MoE 通常以 top-k routing 将 token 重排到 expert，执行 FFN 后 combine。训练/服务会叠加 [[Expert-Parallelism]]、[[Tensor-Parallelism]] 与 data parallel；all-to-all、padding、straggler 和 HBM 中 expert weight/KV 竞争决定实际性能。

## 为什么重要

OSDI 2026 将 MoE 带到不同硬件边界。[[LocalMoE-Hybrid-OSDI26]] 用 dual consumer GPU、CPU AVX-512 和 stream loading 运行完整 DeepSeek-V3；[[RollArt-OSDI26]] 在 3000+ GPU MoE agentic RL 中按 task domain 做异构 placement；[[UCCL-Tran-OSDI26]] 以可演化 transport 处理 all-to-all collision；[[BatchGen-OSDI26]] 和 [[DynamicPPServing-OSDI26]] 则处理 serving batch/phase 波动。

## 关键观察 / 隐含假设

- **观察：稀疏 FLOPs 不等于稀疏系统成本。** token dispatch、padding 与 cold expert load 可主导 latency，见 [[MoE-Serving-Tax-MLSys26]]。
- **观察：expert 与 KV 争用 HBM。** [[FluxMoE-arXiv26]] 通过 paging cold expert 释放 KV budget。
- **假设：routing/hotness 具有局部稳定性。** [[PopFetcher-ATC25]]、[[KAIROX-OSDI26]] 的预测迁移依赖这一点。

## 设计空间与取舍

- **Replication / migration / paging**：复制降通信但占 HBM；迁移适应热点却有 stall；paging 扩容量但受链路限制。
- **Token / expert / node granularity**：越细平衡越好，dispatch metadata 与 synchronization 越重。
- **Static / online balance**：静态 plan 稳定，在线 plan 能适应 routing drift。

## 引用本概念的论文

- [[LocalMoE-Hybrid-OSDI26]] — commodity hardware 上的完整 MoE 推理。
- [[RollArt-OSDI26]] — 生产规模 agentic MoE RL。
- [[UCCL-Tran-OSDI26]] — MoE all-to-all transport extensibility。
- [[FarSkip-Collective-MLSys26]] — expert-parallel communication overlap。
- [[CRAFT-MLSys26]] — cost-aware expert replication。

## 已知局限 / 开放问题

- router quality、system balance 与 model quality 仍多被分开优化。
- fault tolerance、heterogeneous expert precision 与跨域 MoE serving 缺少统一 abstraction。
