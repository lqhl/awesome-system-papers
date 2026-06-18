---
type: paper
name: IntAttention
full_title: "IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference"
authors: [Wanli Zhong, Haibo Feng, Zirui Zhou, Hanyang Peng, Shiqi Yu]
venue: MLSys
year: 2026
tags: [quantization, edge-inference, attention, int8, softmax]
source_pdf: "[[c20ad4d76fe97759aa27a0c99bff6710.pdf]]"
source_md: "[[c20ad4d76fe97759aa27a0c99bff6710]]"
---

# IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference (MLSys 2026)

> **一句话总结**：首个 plug-and-play 无需重训的纯整数 attention 流水线，用 IndexSoftmax（32 项 LUT + 整数 clipping + 整数归一化）消除 dequantize→softmax→requantize 路径，Armv8 CPU 上比 FP16 快 3.7×、比常规 INT8 pipeline 快 2.0×。

## 问题

把 Transformer 推到 edge 设备时，INT8 [[Quantization]] 能加速 QK^T 和 PV 两个 GEMM，但 softmax 因需浮点 exp + 行归一化 + 数据类型转换，在 INT8 pipeline 里占 attention 延迟 **57%–65%**，成为新瓶颈。

现有方案要么依赖专用硬件（Softermax、ConSmax），要么归一化仍走浮点（EXAQ、TurboAttention），要么需要 QAT/微调（I-BERT、I-ViT、I-LLM Shiftmax/DI-ClippedSoftmax）。没有同时满足"纯整数 + plug-and-play + 通用硬件"的方案。

## 核心方法

**IndexSoftmax** 三个紧耦合机制：

1. **Sparsity-aware 整数 clipping**：利用 softmax 稀疏性（大多数 logit 对归一化贡献可忽略），行 max-subtract 后用量化对齐阈值 c_int = round(c·√d / (s_Q·s_K)) 做 element-wise clip，整个过程不出整数域。
2. **32-entry LUT exp 近似**：在 clipped 整数范围内用 32 项 lookup table 代替浮点 exp，每元素仅需索引 + 乘加。
3. **整数归一化 + 直接 requantize**：行求和 + 除法全在整数域完成，输出 UINT8 的 P 直接喂给 INT32 积累的 PV GEMM。

**IntAttention pipeline** 端到端流程：INT32 logits from QK^T → IndexSoftmax → UINT8 P → INT32 PV GEMM；没有任何 dequant/requant 检索。只依赖 add / multiply / shift / indexed lookup，映射到 ARM NEON 等 SIMD-style 整数单元。

## 关键结果

- Armv8 CPU 相对 FP16 基线：最高 **3.7×** 加速、**61%** 能耗降低。
- 相对传统 INT8 attention pipeline：**2.0×** 加速。
- 多语言和视觉模型上精度高保真。
- 作为 drop-in replacement，无需量化感知训练或模型结构更改。

## 相关

- **相关概念**：[[Quantization]]、[[Attention]]、softmax
- **同类系统**：SageAttention、TurboAttention、I-BERT、I-ViT、I-LLM、EXAQ
- **同会议**：[[MLSys-2026]]