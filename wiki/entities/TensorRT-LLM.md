---
type: entity
kind: system
aliases: [TensorRT-LLM, TRT-LLM]
status: active
last_updated: 2026-06-20
tags: [llm-inference, serving, nvidia]
---

# TensorRT-LLM

> NVIDIA 面向生产的 LLM inference 栈，以 TensorRT 编译优化、量化与 CUDA kernel 融合为卖点；在 wiki 图谱中频繁作为工业级 baseline、吞吐对照与「闭源原生 runtime」代表，与 [[vLLM]]、[[SGLang]] 构成论文里最常并列的三类 serving 引擎。

## 是什么

TensorRT-LLM（论文中亦写作 TRT-LLM）是 NVIDIA 开源的 LLM 推理框架，定位是**把 HuggingFace 权重经图优化、kernel fusion、量化与 CUDA Graph 捕获后落到 NVIDIA GPU 上的高吞吐 serving runtime**。它与 [[vLLM]]、[[SGLang]] 等社区引擎不同：算子路径、调度策略与 FlashInfer 等外部 kernel 库的耦合方式更偏「一体化 NVIDIA 栈」，因此在系统论文里既是被挑战的强 baseline，也是 kernel/bench 闭环难以直接 plug-in 的对照组。

这些论文共同把 TensorRT-LLM 视为**生产可达、TBT 通常较强、但调度与 memory manager 可改造性有限**的 reference implementation。典型用法包括：与 [[vLLM]]/[[SGLang]] 并列报告延迟与吞吐；在 [[Tensor-Parallelism|Tensor-Parallel]] 场景作为「默认不开 compute–communication overlap」的代表；在 GH200 offload、KV rotation 等需要深度改 memory layout 的工作里作为难以无痛集成的原生栈。其边界也反复出现：闭源模型权重、自定义 sampling、EP/PP 下算子融合会改变 trace 与 kernel 契约；基于 FlashInfer 的零侵入 `apply()` 路径对纯 TensorRT-LLM 栈需另建适配层。

## 关键观察 / 隐含假设

- **观察 1：作为闭源/一体化 runtime，外部 kernel bench 与零侵入替换闭环默认不成立。** [[FlashInfer-Bench-MLSys26]] 指出 `flashinfer_bench.apply()` 假设 FlashInfer 为算子入口；纯 [[TensorRT-LLM]] 栈需另建适配，否则 agent 生成 kernel 的「评测—集成—端到端增益」virtuous cycle 在 TRT-LLM 上断裂。论文 future work 明确要在 TensorRT-LLM、[[MLC-LLM]] 等更多引擎上测 apply 的 E2E 增益与运维成本。
- **观察 2：与开源引擎一样，低延迟 serving 下默认不做 TP compute–communication overlap。** [[TokenWeave-MLSys26]] 测量 Llama-3.3-70B 等模型在 NVLink 已优化后 [[AllReduce]] 仍占 **9–23%** 延迟；Flux/TileLink 类 overlap 需大 batch（8K+）才划算，而 [[vLLM]]/[[SGLang]]/[[TensorRT-LLM]] **默认不开 overlap**——因在线 serving batch 小，拆分 GEMM 反而更慢。这些论文共同假设 TensorRT-LLM 的默认 TP 路径与社区引擎共享「小 batch overlap 不划算」的设计取舍。
- **观察 3：作为 production baseline，TBT 表现强，但高 RPS 下 TTFT 可能因 lazy preempt 退化；深度 memory/调度 co-design 集成成本高。** [[SuperInfer-MLSys26]] 在 GH200 上把 TensorRT-LLM 与 vLLM V1、LightLLM、NEO 并列评测：TensorRT-LLM **TBT 强**，但高请求率下 **TTFT 因 lazy preempt 退化**；SuperInfer 的 block-first layout、eager rotation、LVF scheduler 均为 vLLM fork 上的非 trivial patch，**与 [[SGLang]]、[[TensorRT-LLM]] 原生栈集成成本未评估**，且未证明可 plug-in 而不重写 memory manager。

## 演进时间线

- **2023–2024**：随 NVIDIA LLM serving 生态成熟，TensorRT-LLM 成为论文中与 FasterTransformer 后继者、[[vLLM]] 并列的工业 baseline；[[SGLang-NeurIPS24]] 将其与 TGI 等列为「丢弃跨调用 [[KV-Cache]] 的通用引擎」对照。
- **2025 OSDI**：[[NanoFlow-OSDI25]] 报告 LLaMA-2-70B 吞吐达 TensorRT-LLM **1.91×**、理论上限 **68.5%**，确立其作为强吞吐 reference 的地位；[[Mirage-OSDI25]] 微基准亦以 TensorRT-LLM 为对手。
- **2026 MLSys**：[[FlashInfer-Bench-MLSys26]] 将 TensorRT-LLM 列为 bench apply 扩展目标；[[TokenWeave-MLSys26]] 揭示其与 vLLM/SGLang 共享的 TP overlap 盲区；[[SuperInfer-MLSys26]] 在 GH200 SLO 评测中量化其 TBT/TTFT 权衡与 offload 栈改造壁垒。

## 相关概念

- [[Tensor-Parallelism|Tensor-Parallel]]
- [[AllReduce]]
- [[Continuous-Batching]]
- [[Chunked-Prefill]]
- [[PagedAttention]]
- [[GPU-Kernels]]
- [[Quantization]]
- [[Speculative-Decoding]]

## 相关论文

- [[FlashInfer-Bench-MLSys26]] — apply() 闭环假设 FlashInfer 入口；纯 TensorRT-LLM 栈需另建适配，列为 future 多引擎 E2E 评测对象
- [[TokenWeave-MLSys26]] — 与 vLLM/SGLang 并列，默认不开小 batch TP compute–comm overlap 的生产引擎代表
- [[SuperInfer-MLSys26]] — GH200 SLO 实验 production baseline：TBT 强、高 RPS TTFT 因 lazy preempt 退化；深度 KV rotation 难以 plug-in 原生 TRT-LLM 栈