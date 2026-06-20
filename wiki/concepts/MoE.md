---
type: concept
aliases: [MoE, Mixture of Experts, Mixture-of-Experts, mixture of experts]
parent: "[[Transformer]]"
last_updated: 2026-06-20
tags: [llm-architecture, sparse-activation, scaling]
---

# MoE (Mixture of Experts)

> 用 router + 多个稀疏激活的 expert 子网络替代单个大 FFN，让模型参数量与每 token 计算量解耦——2024 起 frontier LLM 的事实标配（DeepSeek-V3、Qwen3MoE、GLM-4.5、Kimi-K2）。但 expert load imbalance、all-to-all 通信与 HBM 争用是系统层最棘手的问题。

## 核心思想

经典 dense transformer：每层一个大 FFN，所有 token 走同样路径。MoE：每层 N 个小 FFN（experts）+ router；每个 token 由 router 选 top-K（典型 K=2 或 8）个 expert，只在选中 expert 上计算。

效果：参数量 ×N 但 FLOPs 近似不变（只激活 K/N 子集），让模型能力 scale 到 trillion-parameter（DeepSeek-V3 671B、Kimi-K2 1T）而训推算力可控。系统层代价是：**所有 expert 权重仍须常驻或可快速 materialize 的内存**，与 [[KV-Cache]] 争用 HBM；[[Expert-Parallelism]] 每层 all-to-all dispatch/combine 成为主通信负载。

## 为什么重要

[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 量化：同 per-token FLOP 对齐的 DenseFA 基线，MoE 实际慢 2–3×（云定价甚至 2.5–10×）。tax 在 prefill（padding/straggler/细粒度 expert）与 decode（weight amplification）形态相反——decode 上 routing skew 反而可能减少激活 expert 而加速，这与直觉相悖。

[[Libra-ICLR26|Libra]] 指出新一代 MoE 为 expert specialization 放松训练期 load-balancing loss 后，inference imbalance 从实现瑕疵变成架构必然（Qwen3MoE 层间 imbalance 可达 1.5–2.7×）。[[LayeredPrefill-MLSys26|LayeredPrefill]] 发现 [[Chunked-Prefill]] 在 MoE co-located serving 上引发 sparsity erosion——hybrid batch 激活几乎全部 expert 却达不到 GEMM ridge point。这些论文共同假设：**MoE 的系统优化不能沿用 dense 模型的 batching/parallel 直觉**。

## 关键观察 / 隐含假设

- **观察 1：现代大 MoE 的 expert load imbalance 与模型能力追求绑定。** [[Libra-ICLR26|Libra]] 比较 Qwen2MoE vs Qwen3MoE：新模型层间 imbalance 1.5–2.7，旧模型更接近 1.0；训练弱化 auxiliary loss 后 inference 偏斜加剧。
- **观察 2：相邻 Transformer block hidden state 演化慢，可提前预测下一层 expert 激活。** [[Libra-ICLR26|Libra]] lookahead predictor 在 Qwen3MoE 达 86.5–91.7% accuracy，远超 Lina lookup 的 37.5–47.3%。
- **观察 3：MoE tax 2–3× 且 phase 形态相反。** [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]]：prefill tax 随 batch 增大而降；decode 由 weight amplification 主导，但 skew routing 可能反直觉加速。
- **观察 4：chunked prefill 在 MoE 上触发 sparsity erosion。** [[LayeredPrefill-MLSys26|LayeredPrefill]]：SLO 合规 decode batch ≤32 时仅 ~55% expert 被加载；hybrid batch >256 激活几乎全部 expert，per-expert token 仍不足 ridge point。
- **观察 5：冷 expert 权重挤占热 KV cache。** [[FluxMoE-arXiv26|FluxMoE]]：decode 时层顺序执行，任一时刻只需当前层 expert，但 vLLM 式全量常驻使 KV budget 成为吞吐瓶颈。

## 设计空间与取舍

- **Training-time LB（auxiliary loss）**：简单但损害 expert specialization；新一代 frontier 模型倾向弱化。
- **Inference-time replication（[[Libra-ICLR26|Libra]]、[[CRAFT-MLSys26|CRAFT]]、EPLB）**：hot expert 复制到多 GPU；动态 workload 下静态 profiling 跟不上（[[Libra-ICLR26|Libra]] vs EPLB）。
- **Speculative gating（[[Libra-ICLR26|Libra]]）**：用当前层 hidden state 提前算下层 router——把 [[Speculative-Decoding]] 思想搬到 MoE 路由。
- **Expert paging / offload（[[FluxMoE-arXiv26|FluxMoE]]、[[MOE-INFINITY-arXiv24|MOE-INFINITY]]）**：把 expert 当虚存分页流式装载，腾 HBM 给 KV；低 batch 时 decompression overhead 可能反超（FluxMoE batch 32 仅 vLLM 63.9%）。
- **P2P 通信优化（[[fabric-lib-MLSys26|fabric-lib]]、DeepEP）**：scatter/barrier 封装 MoE dispatch/combine；EFA 与 ConnectX 碎片化是痛点。
- **Layer 维 prefill 调度（[[LayeredPrefill-MLSys26|LayeredPrefill]]）**：消除跨 chunk expert 重载，expert-load 降 39%；假设 co-located 而非 [[Disaggregation]]。
- **异构执行（[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]]、[[CoX-MoE-DAC26|CoX-MoE]]）**：hot expert 放 GPU、cold expert 在 NDP/CPU 执行。

## 引用本概念的论文

- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1.6T/284B DeepSeekMoE；MegaMoE 融合 EP kernel 1.5–1.96× 加速
- [[Libra-ICLR26|Libra]] — Two-Stage Locality-Aware Execution + speculative gating prediction
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡和搬运代价
- [[fabric-lib-MLSys26|fabric-lib]] — MoE dispatch/combine over P2P RDMA
- [[FluxMoE-arXiv26|FluxMoE]] — expert paging 腾 HBM 给 KV cache，3.0× over vLLM
- [[CRAFT-MLSys26|CRAFT]] — per-layer replication benefit 估计 + MCKP，比 EPLB 平均 1.14× goodput
- [[LayeredPrefill-MLSys26|LayeredPrefill]] — MoE 上 chunked prefill sparsity erosion 与 layer 维替代
- [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] — 分解 prefill/decode MoE tax，2–3× 慢于 DenseFA
- [[MoEBlaze-MLSys26|MoEBlaze]] — 训练侧 index 列表替代 routing buffer，H100 最高 6.2× 加速
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — casting-free FP8 MoE 训练流，671B 吞吐 +21%
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — 残差连接重叠 EP Dispatch/Combine
- [[NEST-MLSys26|NEST]] — device placement 原生支持 EP 与 ZeRO 联合搜索
- [[WAVE-MLSys26|WAVE]] — AMD GPU fused MoE GEMM kernel DSL
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 生产模拟器分析 MoE 对 prefill 延迟与吞吐影响
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — MoE expert routing 使 KVCache profiling 偏离 dense 规律
- [[SHIP-MLSys26|SHIP]] — MoE 小 batch 下 per-token expert 执行保 pipeline 平衡
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — 2G VRAM 上 235B MoE 仍 ≥5 TPS
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]] — personal-machine expert offloading，3.1–16.7× TPOT 改善
- [[OD-MoE-arXiv25|OD-MoE]] — cacheless edge-distributed MoE，99.94% expert activation recall
- [[AttnRes-arXiv26|Attention Residuals]] — Kimi Linear MoE 48B/3B-active 架构改进

## 已知局限 / 开放问题

- decode 阶段 + 多节点的 LB 仍是开放问题（[[Libra-ICLR26|Libra]] 聚焦 prefill + 单节点）
- expert placement 在异构硬件（不同代 GPU 混布）下尚无成熟方案
- expert specialization 与 load-balancing loss 之间的 trade-off 缺乏理论指导
- MoE tax 数字随实现栈（DeepEP/DeepGEMM）演进快速老化（[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]]）