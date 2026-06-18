---
type: paper
name: AXLearn
full_title: "AXLearn: Modular, Hardware-Agnostic Large Model Training"
authors: [Mark Lee, Chang Lan, Tom Gunter, John Peebles, Hanzhi Zhou, et al.]
venue: MLSys
year: 2026
tags: [training-framework, modularity, jax, xla, hardware-agnostic, apple]
source_pdf: "[[28dd2c7955ce926456240b2ff0100bde.pdf]]"
source_md: "[[28dd2c7955ce926456240b2ff0100bde]]"
---

# AXLearn: Modular, Hardware-Agnostic Large Model Training (MLSys 2026)

> **一句话总结**：Apple 开源 JAX/XLA 训练框架，严格封装模块化配置实现 RoPE/[[MoE]] 等特性 O(1) LoC-Complexity（10 行配置 1000+ 实验），在 H100/TPU v5p/Trainium2 上与 Megatron/MaxText 性能持平，弱扩展 256→4096 chip MFU 仍 52–63%。

## 问题

Apple 训练 LLM 的两个硬约束不是单纯性能：
1. **Modularity**：数百名工程师需用最少代码试验多种架构（FFN→[[MoE]]、attention→RoPE）。DeepSpeed、Megatron-LM、TorchTitan、MaxText 依赖 subtyping，QwenV2→QwenV2-MoE 需 >200 LoC，生产环境数十 variants 放大到数千行。
2. **Hardware-Agnostic**：需同时支持 GPU、TPU、AWS Trainium，覆盖 AWS/GCP/Azure/自有机房。Megatron 偏 Nvidia，Haiku/Flax/Pax/MaxText 偏 TPU。

## 核心方法

**严格封装 + 组合优于继承**：
- 层次化 Config tree + `replace_config()` config modifier；换 FFN 为 [[MoE]] 约 10 行，内部用于 1000+ 实验。
- **LoC-Complexity** 量化扩展性：AXLearn 对 RoPE/[[MoE]] 为 O(1)，Megatron/DeepSpeed 等多为 O(N) 或 O(NM)。

**AXLearn Composer + Runtime**（基于 XLA/GSPMD）：
- 并行（FSDP、TP、PP、[[Expert-Parallelism|expert-parallel]]、sequence parallel）与 remat、量化均通过 config 指定，无需改 layer 代码。
- **Mesh rules**：按 accelerator 类型自动应用 [[Flash-Attention|FlashAttention]] 等 custom kernel 与 remat 策略。
- **InvocationContext**：在 JAX 函数式约束下透明管理 state/PRNG/summary，模块互不感知。
- Runtime：异步 checkpoint（S3/GCS）、watchdog、slice-level hot-swap 故障恢复（21 min 总 downtime 含 restore）。

训练与推理统一：复用 attention/KV 封装，可接 [[Continuous-Batching]]、[[Disaggregation|disaggregated prefill-decode]]、[[PagedAttention]] 式 paged KV。

## 关键结果

- 同硬件对比：TPU 上 SOTA（优于 MaxText）；H100 上优于 PyTorch FSDP；Megatron 在 H100 略快（PyTorch 调度细于 XLA 的 trade-off）
- 弱扩展：70B 模型 256→4096 chip MFU 63.0%→52.4%；150B 8192→32768 chip 40.6%→37.6%
- TPU 推理 vs [[vLLM]]：Llama2-7B/70B 吞吐 2.8×/1.6×（vLLM TPU 支持仍实验性）
- 生产：>10,000 并发实验、数百工程师、十亿级用户产品；开源 Apache 2.0

## 相关

- **相关概念**：[[MoE]]、[[Flash-Attention]]、[[Expert-Parallelism]]、[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]
- **同类系统**：Megatron-LM、DeepSpeed、TorchTitan、MaxText、Flax、[[vLLM]]
- **同会议**：[[MLSys-2026]]