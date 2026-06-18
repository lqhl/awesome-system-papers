---
type: paper
name: WAVE
full_title: "WAVE: A Symbolic Python DSL and Compiler for High Performance Machine Learning"
authors: [Harsh Menon, Oleksandr Zinenko, Gaurav Verma, Stanley Winata, et al.]
venue: MLSys
year: 2026
tags: [kernel-dsl, gpu, amd, attention, gemm, compiler]
source_pdf: "[[68d30a9594728bc39aa24be94b319d21.pdf]]"
source_md: "[[68d30a9594728bc39aa24be94b319d21]]"
---

# WAVE: A Symbolic Python DSL and Compiler for High Performance Machine Learning (MLSys 2026)

> **一句话总结**：Wave 是 Python 嵌入的 wave-level kernel DSL，用 implicit indexing + symbolic mapping 把 matrix core 地址算术从 kernel 逻辑中剥离，在 AMD MI300/MI325/RX9070 上 attention 与 GEMM 性能匹配或超越 Triton 与手工调优库。

## 问题

Tensor/Matrix core 要求复杂的 per-thread 地址分布与 swizzling，传统 SIMT kernel 把计算与地址算术纠缠，难维护且跨硬件可移植性差。Triton/TileLang 等仍要求作者手写 tiling 与 offset 逻辑。

## 核心方法

**Wave** 两大原则：
- **Implicit Indexing**：compiler 从 Workgroup/Wave/Tiling/Hardware constraints 推导地址
- **Symbolic Mapping**：tile size、wave size、MMA type 等保持符号，late specialization

用户写 `@wave(constraints)` 函数 + `@iterate` 显式归约循环；constraints 声明 workgroup/wave/tiling/MMA 映射。Compiler 经 torch.fx 逐步 lower：type inference → index sequence 构造 → 分布式地址生成 → 优化（§4）。

支持 dynamic value remapping（MoE expert_id）、prefill/decode 同一源码不同 shape specialization。

## 关键结果

- AMD Instinct **MI300、MI325** 与 Radeon **RX9070RT** 上 LLM 相关 **attention、GEMM** 匹配或超越 Triton 与 hand-tuned libs
- 同一源码可生成 symbolic prefill 与 seq_len=1 decode kernel
- 覆盖 extend attention、persistent GEMM、[[MoE]] fused GEMM 等 transformer 关键 kernel

## 相关

- **相关概念**：[[Flash-Attention]]、[[MoE]]、kernel DSL、matrix core
- **同类系统**：Triton、TileLang、cuTile、[[SGLang]]、[[vLLM]]
- **同会议**：[[MLSys-2026]]