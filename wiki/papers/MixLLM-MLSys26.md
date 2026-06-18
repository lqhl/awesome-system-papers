---
type: paper
name: MixLLM
full_title: "MixLLM: LLM Quantization with Global Mixed-precision between Output-features and Highly-efficient System Design"
authors: [Zhen Zheng, Xiaonan Song, Chuanjie Liu]
venue: MLSys
year: 2026
tags: [quantization, llm-inference, mixed-precision, gpu-kernel, w4a8]
source_pdf: "[[2723d092b63885e0d7c260cc007e8b9d.pdf]]"
source_md: "[[2723d092b63885e0d7c260cc007e8b9d]]"
---

# MixLLM: LLM Quantization with Global Mixed-precision between Output-features and Highly-efficient System Design (MLSys 2026)

> **一句话总结**：W4.4A8 按全局显著性给 ~10% 输出通道 8-bit、其余 4-bit，two-step dequantization + fast I2F 走 int8 Tensor Core，Llama 3.1 70B PPL 增量从 SOTA ~0.5 降到 <0.2，大 batch 下还比 W4A16 更快。

## 问题

[[Quantization]] 要同时满足精度、显存、系统效率三角，但 weight-only（GPTQ/AWQ）4-bit 精度仍不够、大 batch 还被 dequant 拖慢；weight-activation（SmoothQuant/QoQ）激活更难量化；Atom 等 mixed-precision 在 **层内局部** 挑 outlier，忽略层间重要性差异，且 input-feature 混合精度对 kernel 不友好。

## 核心方法

**MixLLM** 算法-系统协同：

1. **全局输出通道混合精度**：对所有 linear 层的输出 channel 用 Taylor 一阶+二阶（Fisher 近似 Hessian）估算量化对最终 loss 的贡献，全局排序；top ~10% 走 8-bit symmetric，其余 4-bit asymmetric（group size 128）。输出特征天然 disjoint，利于 kernel 切分。
2. **量化配置**：激活固定 **8-bit 对称 group-wise**（4-bit 激活精度损失大、对大 MatMul 算力收益仅 ~6%）；权重 4-bit 非对称。
3. **Two-step dequantization**：先在 int8 域算 `(W_q-z)·A_q`，再乘 per-group scale；I2F 用 bias 技巧变成一次 float 减法并 fuse 进 mma accumulator（A100 上 512×4096×4096 省 **>20 TOPS**）。
4. **软件流水**：重叠 HBM load、dequant、Tensor Core MatMul；高/低 bit 子问题 CUDA Graph 并行写回同一输出 tensor。

## 关键结果

- **W4.4A8**（仅 10% 通道 8-bit）：Llama 3.1 70B PPL 增量 **<0.2**（SOTA ~0.5）；三模型 MMLU-Pro 平均 **+0.93**。
- 精度优于 GPTQ/AWQ/SmoothQuant/QoQ/QuaRot 等 4-bit 方案；W8A8 近无损。
- 系统：相对 float16 平均 **1.90–2.75×**（视 8-bit 比例）；大 batch 超过 TRT-LLM W4A16（后者仅 float16 的 83% @ bs=512）。

## 相关

- **相关概念**：[[Quantization]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、[[Tensor-Parallelism]]
- **同类系统**：Atom、QoQ、GPTQ、AWQ、SmoothQuant、QuaRot
- **同会议**：[[MLSys-2026]]