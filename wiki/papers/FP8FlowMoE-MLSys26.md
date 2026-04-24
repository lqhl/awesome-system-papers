---
type: paper
name: FP8FlowMoE
full_title: "FP8-Flow-MoE: A Casting-Free FP8 Recipe without Double Quantization Error"
authors: [Fengjuan Wang, Zhiyi Su, Xingzhu Hu, Cheng Wang, Mou Sun]
venue: MLSys
year: 2026
tags: [fp8, quantization, moe, training, mixed-precision]
source_pdf: "[[072b030ba126b2f4b2374f342be9ed44.pdf]]"
source_md: "[[072b030ba126b2f4b2374f342be9ed44]]"
---

# FP8-Flow-MoE: A Casting-Free FP8 Recipe without Double Quantization Error (MLSys 2026)

> **一句话总结**：提出 scaling-aware transpose 算子（仅操作 exponent bits，2–3× 快于 dequant→transpose→requant），把 [[MoE]] 训练流中的 FP8 cast 操作从 12 个压到 2 个，671B DeepSeek-V3 训练吞吐提升 21%、单卡显存降 16.5 GB 且不损精度。

## 问题

FP8 在 Hopper 上理论算力比 BF16 翻倍、通信减半，但现有 FP8 训练系统（TransformerEngine、DeepSeek-V3 的 DeepGEMM/DeepEP）仍以 BF16 为主干，每个 GEMM 边界要做 quantize/dequantize (Q/DQ)，实际吞吐远达不到理论值，甚至被 BF16 baseline 反超。

直接把 dataflow 全改成 FP8 会踩另一个坑——**double quantization error**：activation 沿 row-wise 量化（fprop/dgrad 用），weight-grad (wgrad) 需要 column-wise 量化。naive 做法是 dequant→transpose→requant，两次量化的 scaling factor 不同（per-128-tile 的 max 值不同），值被映射到两组不重合的离散格点，误差放大、训练失稳。

## 核心方法

**Scaling-aware Transpose（核心贡献）**：

证明若 row-wise 和 column-wise 的 scaling factor 都约束为 2 的幂（`s = 2^T`, `s' = 2^T'`），则两种量化域间的转换只需调整 FP8 encoding 的 exponent bits，**不需要 dequant+requant**。Algorithm 1：对每个 128×128 block，取该列最大的 row-wise scale 作新 column-wise scale（防溢出），逐元素把 exponent 减去 `k = log2(S_max / S_row_i)` 即可得到等价的 column-wise FP8 编码。

**Casting-free FP8 dataflow**：

整个 MoE 层（routing、dispatch all-to-all、permute、grouped GEMM、activation、第二层 grouped GEMM、unpermute、combine）全程保持 FP8，仅入口和出口各一次 cast，把 cast 操作从 **12 降到 2**。配套一套原生 FP8 算子套件（部分已合进 NVIDIA TransformerEngine 上游），plug-and-play 兼容 Megatron-LM。

## 关键结果

- Direct Transpose 自身 **2–3× 快于** naive dequant-transpose-quant
- 671B DeepSeek-V3 MoE 训练：**吞吐 +21%、单卡显存 -16.5 GB** vs BF16 基线和 naive FP8 基线
- naive FP8 kernel 替换只得 3% 提升、显存甚至更差——说明全流 FP8 + scaling 一致性是关键
- 16B DeepSeek-V2-lite × 200B tokens 验证收敛稳定
- 承诺开源，已部分进入 TransformerEngine 上游

## 相关

- **相关概念**：[[Quantization]]、[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：TransformerEngine、DeepGEMM、DeepEP、Megatron-LM、DeepSeek-V3 training
- **同会议**：[[MLSys-2026]]
