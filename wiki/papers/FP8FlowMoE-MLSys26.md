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

> **一句话总结**：scaling-aware transpose 仅改 FP8 exponent 即在 row/column-wise 布局间转换（2–3× 快于 dequant→transpose→requant），把 [[MoE]] 训练流 cast 从 12 降到 2，671B DeepSeek-V3 吞吐 +21%、单卡显存 -16.5 GB，16B 模型 200B tokens 收敛与 BF16 一致。

## 问题

FP8 在 Hopper 理论算力翻倍、通信减半，但 TransformerEngine / DeepSeek-V3 等仍以 BF16 为主干，GEMM 边界频繁 Q/DQ，实测吞吐常低于优化 BF16。全 FP8 流又会引入 **double quantization error**：fprop/dgrad 用 row-wise scale，wgrad 需 column-wise；naive dequant→transpose→requant 两次映射到不同离散格点，误差放大、训练失稳。

## 核心方法

**Scaling-aware Transpose**：约束 per-128-tile scale 为 2 的幂时，row→column 转换只需调整 FP8 exponent（Algorithm 1：块内对齐到最大 scale 防溢出），无需 dequant+requant。

**Casting-free FP8 dataflow（FP8-Flow-MoE）**：
- MoE 全路径（routing、dispatch all-to-all、permute、grouped GEMM、SwiGLU、combine）保持 FP8
- 仅两处保留 BF16：第一层 grouped linear 与 activation 之间、第二层 grouped linear 与 backward combine 之间（防 overflow/非线性放大误差）
- cast 数 **12→2**；配套 fused permute+padding、fused SwiGLU+quant 等原生 FP8 kernel（部分已进 TransformerEngine 上游）

## 关键结果

- Direct Transpose：**2–3×** 快于 naive 三路转换
- 671B DeepSeek-V3（32-node Hopper，EP/PP 8/32–32/8）：吞吐 **+6–21%** vs BF16；AC=sel 时 peak mem **-8 GB vs BF16、-16.5 GB vs Blockwise**；EP=32 时仅 FP8-Flow 不 OOM
- naive FP8 kernel 替换仅 +3% 吞吐、显存无收益
- DeepSeek-V2-lite 16B × 200B tokens：loss 曲线与 BF16 几乎重合
- 兼容 Megatron-LM + TransformerEngine，承诺开源

## 相关

- **相关概念**：[[Quantization]]、[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：TransformerEngine、DeepGEMM、DeepEP、Megatron-LM
- **同会议**：[[MLSys-2026]]