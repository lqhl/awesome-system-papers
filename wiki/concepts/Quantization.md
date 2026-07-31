---
type: concept
aliases: [quantization, Quantization, quantized, INT8, FP8, INT4, W8A8, W4A16, PTQ, QAT, post-training quantization, quantization-aware training, mixed-precision]
parent: "[[LLM-Inference]]"
last_updated: 2026-07-30
tags: [model-compression, llm-inference, efficiency]
---

# Quantization

> 量化（quantization）用更少 bit 表示 weight、activation、KV cache 或 gradient，以降低容量与带宽、利用低精度算力；真正难点是质量、kernel 支持和 workload shape 共同决定的端到端收益。

## 核心思想

量化可按对象分为 weight-only、weight+activation、KV 与 training state；按时机分为 post-training quantization（PTQ）和 quantization-aware training（QAT）；按粒度从 per-tensor 到 per-channel/per-group/per-token。INT4、INT8、FP8、MXFP4 的 scale、zero point、outlier 与 accumulation precision 各不相同。

理论压缩比不等于 speedup。若硬件不原生支持 asymmetric bit-width，dequant、padding、partial product、shared-memory 或 sparse-index overhead 会抵消收益；不同 prefill/decode、batch 和 shape 还会改变最佳 kernel。

## 为什么重要

LLM inference 常受 weight/KV bandwidth 与 HBM capacity 限制，低 precision 可提升 batch 或让模型进入 edge/consumer GPU。训练则更关心误差累积、optimizer/master copy 和 collective precision。系统论文必须同时报告质量、memory、latency/throughput、energy 与特定硬件 ISA。

## 关键观察 / 隐含假设

- **任意精度需要自适应 kernel mapping**：[[ADAngel-OSDI26]] 发现 padding、bitwise、Split 的最优区间随 M/bit-width 改变，用离线 oracle map 获得 1.17–2.38 倍 TTFT 提升；代价是 specialization 与 896 MiB workspace。
- **稀疏与量化会交叉影响 break-even**：[[KAIROX-OSDI26]] 在 GPU–CPU hybrid decode 中利用 activation sparsity，但某些 speculative batch 下 dense baseline 反超；质量还依赖 predictor threshold。
- **MoE 的 expert placement 与 precision 必须联合**：[[LocalMoE-Hybrid-OSDI26]] 用 CPU/GPU 与低精度适配本地 MoE，仍需在 DDR/PCIe、top-k 和用户 SLO 下自动选策略。
- **新硬件 precision 改变 kernel design**：[[FlashAttention-3-NeurIPS24]]、[[FlashAttention-4-MLSys26]]、[[FP8FlowMoE-MLSys26]] 表明 FP8/MXFP 等只有在 scaling、layout 和 Tensor Core pipeline 匹配时兑现理论吞吐。

## 设计空间与取舍

- **weight-only PTQ**：部署简单、容量收益大，activation 保持高精度但算力利用可能不足。
- **W8A8/W4A8**：可用低精度 Tensor Core；[[ADAngel-OSDI26]] 显示 asymmetric operand 需要多策略 kernel。
- **KV quantization**：直接扩展 context/batch，但误差按生成长度累积并影响 attention quality。
- **FP8/低精度训练**：提高训练吞吐，需 scale history、master state 与跨 collective 数值控制。
- **mixed precision search**：提高质量—性能 Pareto，但 profile/search、版本和硬件绑定更强。

## 引用本概念的论文

- [[ADAngel-OSDI26]] — 为 W3/W4/W5A8 mpGEMM 选择 workload-adaptive DPR kernel。
- [[KAIROX-OSDI26]] — 联合 sparse neuron migration 与低精度 GPU–CPU inference。
- [[LocalMoE-Hybrid-OSDI26]] — 在本地 MoE serving 中权衡 precision、CPU/GPU 与 SLO。
- [[QFactory-ATC25]] — 自动生成/评估量化配置。
- [[DiffKV-SOSP25]] — 针对 KV cache 采用差异化 precision。
- [[FP8FlowMoE-MLSys26]] — 面向 MoE training 的 FP8 data/communication flow。

## 已知局限 / 开放问题

- 统一报告 task quality/perplexity，而非只报告 kernel speedup。
- 处理 dynamic batch、per-layer/per-group bits 与多租户 interference。
- 建立跨 GPU/NPU 的可迁移 cost model，减少每个模型 exhaustive profiling。
- 验证长 context、reasoning 和 RL training 中误差是否随阶段累积。
