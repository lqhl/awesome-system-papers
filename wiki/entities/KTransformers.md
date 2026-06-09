---
type: entity
kind: system
aliases: [KTransformers, ktransformers]
status: active
last_updated: 2026-06-09
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_url: "https://github.com/kvcache-ai/ktransformers"
---

# KTransformers

> CPU/GPU heterogeneous MoE inference engine from kvcache-ai, using AMX-optimized CPU expert execution, asynchronous CPU-GPU scheduling, and Expert Deferral to make very large sparse MoE models usable on limited GPU memory.

## 是什么

KTransformers 是 kvcache-ai 的开源推理系统，对应 SOSP 2025 论文 [[KTransformers-SOSP25]]。它把 [[MoE]] 模型里的 attention、shared experts 和 hot experts 放在 GPU，把多数 routed experts 放到 CPU DRAM 并用 Intel AMX/AVX-512 执行，从而让 DeepSeek-V3/R1 这类 671B 级模型可以在单 A100 + 双 Xeon 服务器上运行。

它的核心定位不是通用 GPU serving 框架，而是在 GPU 显存不足时，把 CPU 变成 MoE routed expert 的可用计算层级，同时尽量保持 attention 和 [[KV-Cache]] 在 GPU 上。

## 系统特点

- **AMX-aware expert kernel**：为 routed expert MLP 定制 AMX tiling、cache-line 对齐布局、Int4/Int8 block-wise 量化，并在低 arithmetic intensity 的 decode 小 batch 场景自动切回 AVX-512。
- **异步 CPU-GPU 调度**：通过 CUDA stream callback 和 [[CUDA-Graph]] 减少 decode token 路径里的 kernel launch 与同步开销。
- **NUMA-aware CPU execution**：把 expert 任务按 socket 和访存代价调度，避免跨 NUMA 访问把 CPU expert execution 的收益吃掉。
- **Expert Deferral**：把部分 expert 计算延后到下一层 attention 并发执行，提升 CPU/GPU overlap，在论文评估中进一步提高 decode 吞吐。
- **模型特化部署经验**：社区文档围绕 DeepSeek 系列给出本地/工作站部署 recipe，包括 GPU hot experts、CPU routed experts 和本地 NVMe 权重加载。

## 与本 wiki 的关系

KTransformers 是 MoE expert offloading 方向的重要生产化参照：它选择“CPU 执行 expert”而不是“expert 权重分页到 GPU 后再算”，因此和 [[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[DwarfStar]] 共同定义了个人机器/低显存服务器上 MoE inference 的几种设计点。

在 expert 与 [[KV-Cache]] 统一 offload 的研究问题里，KTransformers 的价值在于提供一个真实系统边界：attention/KV 通常留在 GPU，CPU 层级主要服务 routed experts。这个切分简单、可运行，但也暴露了下一步问题：当 CPU DRAM/NVMe 同时承载 expert weights、KV blocks 和 session state 时，是否还应维持这种对象级分工。

## 相关

- **论文页**：[[KTransformers-SOSP25]]
- **相关概念**：[[MoE]]、[[Expert-Offloading]]、[[KV-Cache]]、[[CUDA-Graph]]、[[NUMA]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[DwarfStar]]、[[MOE-INFINITY-arXiv24]]、[[FluxMoE-arXiv26]]
- **外部链接**：[kvcache-ai/ktransformers](https://github.com/kvcache-ai/ktransformers)
