---
type: paper
name: DynaFlow
full_title: "DynaFlow: Transparent and Flexible Intra-Device Parallelism via Programmable Operator Scheduling"
authors: [Yi Pan, Yile Gu, Jinbin Luo, Yibo Wu, Ziren Wang, "et al."]
venue: MLSys
year: 2026
tags: [intra-device-parallelism, operator-scheduling, torch-compile, overlap, fusion]
source_pdf: "[[f7177163c833dff4b38fc8d2872f1ec6.pdf]]"
source_md: "[[f7177163c833dff4b38fc8d2872f1ec6]]"
---

# DynaFlow: Transparent and Flexible Intra-Device Parallelism via Programmable Operator Scheduling (MLSys 2026)

> **一句话总结**：DynaFlow 用 `torch.compile` backend 把逻辑模型与物理执行 schedule 解耦：前端注解划分子图 + Python scheduler 定义 overlap/fusion/split 策略，后端异步管 control/data-flow 并保 CUDA Graph / TorchInductor 兼容，以极少代码把 4 类 intra-device parallelism 集成进 6 个 ML 系统，吞吐最高 **1.29×**。

## 问题

LLM 推理/训练由 compute-bound（GEMM）、memory-bound（decode attention）、network-bound（all-reduce / all-to-all）算子串行组成，资源常闲置。overlap、kernel fusion、batch splitting 等 intra-device parallelism 有效，但 [[vLLM]] / [[SGLang]] 等框架是静态顺序执行模型——集成 DBO 到 SGLang 曾需 **2 个月 + 1.3K 行**专码。更糟的是最优策略随 workload、硬件、模型而变，维护多套手写实现成本 prohibitive。

## 核心方法

**Frontend（可编程调度）**：
- 基于 TorchDynamo 图，用 `SplitModule` / `SplitFunc` / `dynaflow.mark` 划分子图（对齐 nn.Module 或 custom kernel 边界）
- 继承 `OpSchedulerBase`，在 `schedule()` 里用 `split()`、`get_ready_ops()`、`execute()`（支持 fusion `replace_func`）写 Python-native 策略
- 典型策略平均 **11 行** partition + **31 行** scheduler

**Backend（高效执行）**：
- 异步 callback 引擎管理依赖；静态分析预分配 merge buffer，**零拷贝** resharding
- 子图级 TorchInductor 编译 + 每 micro-batch 独立 CUDA Graph capture（复用 graph pool）

作为 torch.compile backend 插入，[[vLLM]] 集成仅 **75 LoC**。

## 关键结果

- **NanoFlow** on [[vLLM]]/[[SGLang]]：Llama-3-8B/70B、Qwen-2.5-72B 最高 **1.29×**；naive 固定 split 在轻负载可降至 **0.35×**
- **Dual-batch overlap** on DeepSeek-V2-Lite MoE：最高 **1.14×**，部分 workload **1.1×** 优于 vLLM 手写 DBO
- **Communication overlap** on HF/Megatron/xDiT/FastVideo：最高 **1.15×**
- **TokenWeave** fusion：vLLM/HF 最高 **1.21–1.22×**，动态 CTA 选择再 +12%
- Backend：CUDA Graph + Inductor 使 CPU launch 时间 **6.4×** 低于未优化版；sequential fallback **4.7ms** 接近 vLLM **4.4ms**

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[MoE]]、[[Chunked-Prefill]]、CUDA Graphs、Kernel Fusion
- **同类系统**：[[vLLM]]、[[SGLang]]、NanoFlow、TokenWeave、Megatron-LM、HuggingFace Transformers
- **同会议**：[[MLSys-2026]]