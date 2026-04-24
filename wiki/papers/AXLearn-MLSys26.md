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

> **一句话总结**：Apple 的开源训练框架，用严格封装的 JAX/XLA 模块化配置树实现 O(1) LoC-Complexity 加新特性（RoPE/MoE 10 行代码配置 1000+ 实验 vs. DeepSpeed 需要 4000+ LoC），同时在 H100/TPU v5p/Trainium2 上与 Megatron/MaxText 性能持平甚至更好。

## 问题

Apple 训练 LLM 的两个硬约束不是单纯性能：
1. **Modularity**：让数百名工程师能用最少代码试验多种架构（FFN → MoE、普通 attention → RoPE 等）。现有框架（DeepSpeed、Megatron-LM、TorchTitan、MaxText）依赖 subtyping，引入新 layer 往往要修改整条继承链，DeepSpeed 从 QwenV2 改到 QwenV2-MoE 用了 >200 LoC，生产环境放大到数十/数百 variants 就是几千行。
2. **Hardware-Agnostic**：不能绑定单一厂商，需要同时支持 GPU、TPU、AWS Trainium；AWS、GCP、Azure、自有机房都要能用。Megatron-LM 对 Nvidia 优化，Haiku/Flax/Pax/MaxText 偏 TPU，都不满足。

## 核心方法

**1. 严格封装 + 组合优于继承**：
- 每个模块有 Config object，child config 通过 `set()` 从 parent 注入 `input_dim`。换 FFN 为 MoE 只需写 `replace_config(cfg, target=FeedForwardLayer, new_cfg=MoELayer.default_config())`——10 行代码改 1000+ experiment。
- 提出 **LoC-Complexity** 作为系统扩展性量化指标：衡量添加新 feature 引入的 asymptotic LoC 变化。AXLearn 是 O(1)，其他系统多是 O(NM) 或 O(N)（N 是模块数，M 是 feature variants 数）。
- RoPE/MoE 实际 LoC 改动估计（生产代码 20 model variants × 10 attention variants）：Megatron-LM MoE 20 LoC，DeepSpeed MoE 4000 LoC，AXLearn 0 LoC。

**2. Config-Modifier + Mesh Rules（hardware-agnostic 优化）**：
- 所有 layer 原生支持 FSDP、pipeline、expert、sequence、tensor parallelism，用户用配置选择而非改代码。
- **Mesh rule** = 加速器类型到 config modifier 的映射，TPU v5e 用 FSDP within slice + DP across slices + INT8 + activation offload，全部 10 行配置。
- [[Flash-Attention]] 作为 drop-in layer，在 GPU 上走 cuDNN/Pallas，在 Trainium 上走 AWS NKI kernel，在 TPU 上走 SplashAttention。
- 原生支持 JAX AOT 编译，在单 host 就能检查 OOM、MFU，避免大规模 run 浪费。

**3. InvocationContext（状态穿越 JAX 的纯函数边界）**：
- JAX 要求 pure functional，但训练本身有状态（params、PRNG、summaries）。AXLearn 引入 InvocationContext stack：parent 调用 child 时自动 push context，split PRNG key，建 summary store；return 时 pop 回收。
- Context 里引用 module 但 module 不引用 context，使得第三方库（如 optax）和 custom_vjp 路径都能访问。

**4. Unified Training + Inference**：
- 意外发现 AXLearn 组件可复用为推理 engine，在 TPU 上推理性能超过 vLLM。KV cache 是 encapsulated component，可直接切换为 [[PagedAttention]]、[[Continuous-Batching]]、[[Disaggregation]]（prefill/decode 分离）等 inference-friendly 布局而不用改 attention layer。

**5. Runtime 能力**：
- 异步多云 checkpoint（S3/GCS），watchdog 检测 hang/低利用率，slice-level hot-swap + 备机跑低优先级任务，persistent compilation cache 避免重启编译。

## 关键结果

- **Modularity**：AXLearn 的 LoC-Complexity(RoPE) = O(1), LoC-Complexity(MoE) = O(1)；其他系统多在 O(NM)。生产估算 AXLearn 改 0 行，DeepSpeed 改 4000 行。
- **性能**（iteration time / MFU / throughput）：
  - Llama2-7B on 32×H100-8：AXLearn 1.4s / 54.2% MFU，追平 MaxText，显著优于 PyTorch FSDP（29.9%）和 Megatron-LM（44.9%）。
  - Llama2-7B on TPU v5p-512：AXLearn 66.2% MFU > MaxText 61.6%。
  - Llama2-70B on TPU v5p-1024：AXLearn 68% MFU > MaxText 64.4%（PyTorch XLA FSDP OOM）。
  - Trainium2-16：首个大规模支持，Llama2-7B 3.5M tokens/s。
- Apple 内部已部署多年，上千 model × 上百工程师，Apache 2.0 开源于 github.com/apple/axlearn。

## 相关

- **相关概念**：[[MoE]]、[[RoPE]]、[[Flash-Attention]]、[[FSDP]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Continuous-Batching]]、[[PagedAttention]]、[[Disaggregation]]
- **对比系统**：Megatron-LM、DeepSpeed、MaxText、TorchTitan、Flax、Praxis/Pax、[[vLLM]]
- **同会议**：[[MLSys-2026]]
