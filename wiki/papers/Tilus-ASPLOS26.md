---
type: paper
name: Tilus
full_title: "Tilus: A Tile-Level GPGPU Programming Language for Low-Precision Computation"
authors: [Yaoyao Ding, Bohan Hou, Xiao Zhang, Allan Lin, Tianqi Chen, Cody Yu Hao, Yida Wang, Gennady Pekhimenko]
venue: ASPLOS
year: 2026
tags: [gpu-dsl, low-precision, quantization, tensor-layout, llm-serving, area/ai-infra]
source_pdf: "[[asplos26-ding-tilus.pdf]]"
source_md: "[[asplos26-ding-tilus]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# Tilus：面向低精度计算的 Tile-Level GPGPU 语言（ASPLOS 2026）

> **原题**：Tilus: A Tile-Level GPGPU Programming Language for Low-Precision Computation

> **一句话总结**：Tilus 用 thread-block programming model、algebraic layout 和显式 memory hierarchy 支持任意 1–8 bit 类型；单一参数化 matmul 模板相对 Triton、Ladder、QuantLLM、Marlin 最高分别提高 1.75×、2.61×、1.29×、1.03×，并在三类 [[LLM|LLM]] prefill/decode 中保持端到端收益。

## 问题与动机

现有 GPU DSL 对非 2 次幂 bit-width、register layout 与 memory transformation 控制不足；专家 CUDA kernel 性能高但每种量化格式需重写。Tilus 试图在可编程性与任意低精度峰值性能间建立统一层（§1、§3）。

## 关键观察 / 隐含假设

- **观察 1**：decode 小 batch 的瓶颈是低 bit 权重搬运与 register layout conversion，而非纯 FLOPs（§9.2）。
  - **依赖假设**：weight-only quantization 和所测 GEMM shapes 代表目标 serving。
- **观察 2**：layout algebra 可把 bit packing、thread assignment 与 memory hierarchy组合成同一模板（§4–7）。
  - **可能失效场景**：irregular/sparse/data-dependent kernel 可能超出规则 tile abstraction。

## 核心方法

Tilus 定义 parameterized primitive layout 与 Kronecker composition，配合 thread-block instruction set、hierarchical memory 和 1–8 bit custom dtype lowering；auto-tuner 为同一程序模板搜索约 200 个配置（§4–8）。

## 设计取舍

- 显式 layout 获得性能，但比 Triton 更要求硬件知识。
- 任意 bit-width 提高覆盖，数值质量仍由上层 quantization 方法负责。
- 约一分钟/operator 的编译与 autotune 需由复用摊销。

## 实验与结果

- 相对 Triton/Ladder/QuantLLM/Marlin 最多 1.75×/2.61×/1.29×/1.03×（图 10）。
- 覆盖 uint1–8、int2–8 与 float3–8，同一 template 生成（图 11）。
- Gemma-2-9B、Qwen2.5-32B、Llama3.3-70B 的 prefill/decode 均优于 Ladder；A100/L40S/H100 case 显示较好 portability（图 12–14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 单一 DSL 覆盖任意低精度 | 图 10–11 | NVIDIA GPU、matmul 主导 | 强 |
| 带来端到端 LLM 收益 | 图 12–13 | 三模型、contiguous batching | 中到强 |
| 普遍优于专家 kernel | 最大收益有限且非全 shape | 选定 baseline | 中 |

## 批判性分析

### 论证链条

从 layout/control 缺口到统一模板再到 kernel+E2E 证据较完整；但贡献主要是表示与 codegen，不证明任意新量化格式的模型质量。

### 假设压力测试

大 batch prefill 重新 compute-bound 后，低 bit 搬运优势缩小；新 ISA 仍需 backend schedule。

### 实验可信度

跨三代 GPU、多个 baseline 与 E2E 较强；缺 compile-cache、开发人时、energy 和 AMD 结果。

### 系统性缺陷

layout/type/compiler stack 增加 trusted base，非法 bit packing 或 scale semantics 可能 silent corruption。

## 局限与后续工作

- **局限 1**：以 dense weight-only matmul 和 NVIDIA 为主。
- **后续工作 1**：覆盖 sparse/[[MoE|MoE]]、microscaling 与 AMD，并报告 compile amortization 和数值质量。

## 相关

- **相关概念**：[[Quantization]]、[[GPU-Kernels]]、[[Tensor-Compilation]]
- **相关工作**：[[Axe-arXiv26]]、[[FlashInfer-Bench-MLSys26]]

