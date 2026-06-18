---
type: paper
name: AttributionSparseActivation
full_title: "Attribution-Based Sparse Activation in Large Language Models"
authors: [Jifeng Song, Xiangyu Yin, Boyuan Yang, Kai Huang, Weichen Liu, Wei Gao]
venue: MLSys
year: 2026
tags: [sparse-activation, llm-inference, attribution, runtime-adaptation, pruning]
source_pdf: "[[c9e1074f5b3f9fc8ea15d152add07294.pdf]]"
source_md: "[[c9e1074f5b3f9fc8ea15d152add07294]]"
---

# Attribution-Based Sparse Activation in Large Language Models (MLSys 2026)

> **一句话总结**：用 Corrected GxO 归因度量做 lossy 运行时稀疏激活，在 Llama-3/Phi-2/Gemma 上达 70% 神经元稀疏且精度损失 <5%，推理延迟降 35%、GPU 内存降 40%，无需重训练。

## 问题

LLM 推理算力/内存成本高，但 pruning、[[Quantization]]、distillation 等多需离线重训练，难按输入动态适配。Sparse activation 可在运行时按输入关掉不重要神经元，但 lossless 方案（零输出 magnitude）对 Llama-3、Phi-2、Gemma 等高效模型几乎无效——GeLU/SiLU 下几乎没有零输出神经元。强行按 magnitude 稀疏会在生成任务上严重掉精度。

## 核心方法

提出 **attribution-based sparse activation**：用 gradient-based attribution 评估神经元对输出的贡献，关掉低分神经元。

- 基线 **GxO**（Gradient × Output）是高效的一阶近似，但层间 interdependency 会导致归因排名错误。
- 论文量化 inter-layer 归因误差上下界，给 GxO 加 **corrective term**（期望约为 `½·|x_i|·√Σ(∂F/∂x_k)²`），一次 forward+backward 即可算完全部神经元归因。
- 流程：每 token forward 收集输出 → 算 Corrected GxO → 按层阈值选 top fraction 激活 → 未激活列权重置零转 sparse format，走 sparse matmul。

与 [[Quantization]]、[[LoRA]]、speculative decoding、[[KV-Cache]] 压缩正交可叠加。

## 关键结果

- 70% 神经元稀疏，QA/摘要等生成任务精度损失 <5%。
- 推理延迟降 **35%**，GPU 内存降 **40%**。
- 70% 稀疏下，Corrected GxO 比 baseline 稀疏方案精度高至少 **30%**。
- 覆盖 Llama-3、Phi-2、Gemma、MobiLlama 多模型多 benchmark。

## 相关

- **相关概念**：[[Sparse-Attention]]、[[Quantization]]、[[LoRA]]、[[KV-Cache]]、model pruning
- **同类工作**：OPT ReLU 零激活稀疏、SNIP、Integrated Gradients
- **同会议**：[[MLSys-2026]]