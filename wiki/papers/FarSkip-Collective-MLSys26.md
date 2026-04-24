---
type: paper
name: FarSkip-Collective
full_title: "FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models"
authors: [Yonatan Dukler, Guihong Li, Deval Shah, Vikram Appia, Emad Barsoum]
venue: MLSys
year: 2026
tags: [moe, communication-overlap, distillation, expert-parallelism, inference, training]
source_pdf: "[[698d51a19d8a121ce581499d7b701668.pdf]]"
source_md: "[[698d51a19d8a121ce581499d7b701668]]"
---

# FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models (MLSys 2026)

> **一句话总结**：改架构 skip 连接让下一 sub-block 用 outdated/partial activation 启动，从而把 [[MoE]] 的 all-to-all Dispatch/Combine 与计算重叠；用 FCSD self-distillation 把 DeepSeek-V2-Lite (16B)、Qwen-3-30B MoE、Llama-4-Scout (109B) 全层转换后与原模型差距平均 <2.5%，Llama-4-Scout <1%。

## 问题

[[MoE]] 模型用 [[Expert-Parallelism]] 时每层有两次 blocking all-to-all（Dispatch + Combine），[[Tensor-Parallelism]] 后又有 all-reduce，这些通信因为下一步计算必须等它们完成而暴露为 idle time，随模型稀疏化和硬件算力提升占比越来越大。先前工作多在小规模 dense 模型上研究 outdated/partial activation overlap，未在 100B+ MoE 上验证且常常只改部分层。

## 核心方法

**架构改造**：把 transformer 层写成 residual 累加，允许下一 sub-block 用不完整的 o_k^* 当输入，同时异步 collective 产生真正 o_k，然后把 o_k 的结果 "far-skip" 到下下层的 residual。

两种变体：
- **"Outdated"** (Eq 8a)：`o_k^* = o_{k-1}`，直接用前一层完整输出。
- **"Partial"** (Eq 8b)：`o_k^* = o_{k-1} + f_k^*(o_{k-1}^*)`，含当前层已经 ready 的独立部分。

对 MoE 采用混合策略：attention 入口用 partial（含 shared-expert 输出，不含要 Combine 的 routed experts），MoE 入口用 outdated（前一层最终输出）。

**FCSD (FarSkip-Collective Self-Distillation)**：模型参数 shape 完全不变，只改 connectivity；用原模型当 teacher 做 KL 知识蒸馏（< 10B tokens）恢复能力，用 MBPP+ 做早停 proxy 避免训练后期不稳定。

**实现**：
- **训练**（Megatron-LM）：async_op 发 Dispatch/Combine，用自定义 autograd function + stateful dict 暂存 backward handle、重排 autograd Sequence Number 优先级，让 backward 也能重叠 87.6-89% 通信。
- **推理**（vLLM & SGLang）：all-reduce 走 async mode、与 HIP/CUDA-graph 集成、直接 PyNCCL 绑定，97.6% 通信重叠。

## 关键结果

- 3 个全层转换模型（16B / 30B / 109B）在 11 个评测任务上：
  - DeepSeek-V2-Lite: avg 64.5 → 62.0（-2.5%）
  - Qwen-3-30B MoE: 75.9 → 73.7（-2.2%）
  - Llama-4-Scout: 76.0 → 75.1（**-0.9%**）
- 对比 SFT baseline 差距大得多（SFT: -9.5 / -16.4 / -10.4）。
- **训练 all-to-all 88.4% overlap**（DeepSeek-V2-Lite EP=8 单节点）。
- **推理 Llama-4-Scout TTFT 18.5% 加速**。
- 计划开源实现和 checkpoint。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Megatron-LM
- **同会议**：[[MLSys-2026]]
