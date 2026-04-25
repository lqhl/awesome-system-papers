---
type: paper
name: Jenga
full_title: "Jenga: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity"
authors: [Tuowei Wang, Xingyu Chen, Kun Li, Ting Cao, Ju Ren, et al.]
venue: ATC
year: 2025
tags: [llm, fine-tuning, long-context, sparsity, memory-optimization]
source_pdf: "[[atc2025-wang-tuowei.pdf]]"
source_md: "[[atc2025-wang-tuowei]]"
---

# Jenga: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity (ATC 2025)

> **一句话总结**：JENGA 通过 token 级 contextual sparsity 直接剔除冗余 token，在长上下文 LLM 微调中实现 1.93× 显存节省与 1.36× 加速。

## 问题

长上下文 LLM 微调的内存瓶颈不在权重而在 activation——activation 与序列长度成正比。已有方法存在两个不足：

- PEFT 方法（如 [[LoRA]]）只省 optimizer 状态，activation 反而比 vanilla 更多（因低秩矩阵深嵌模型，反向传播路径几乎相同）
- 稀疏 attention（如 LongLoRA 的 shifted sparse attention）只在 hidden dimension 上稀疏，token 仍全部参与计算——作者称之为 **Shadowy Activation**：一个 token 哪怕只被少量使用，它的 activation 仍要保留

## 核心方法

JENGA 引入 **Contextual Token Sparsity**——长上下文中信息量高的 token embedding 在不同输入和不同层之间动态变化，可以直接把不重要的 token 整个剔除（不只是稀疏化它们的交互）。

三个关键技术：

1. **Information-driven Token Elimination**：定义 token 信息量 I(T_j) = Σ Q_i K_j（与所有其他 token 的交互之和）。在 [[Attention]] score 上做 block-wise aggregation，按 layer-specific threshold 剔除冗余 block。同时延伸到 MLP block（通过 ReLU/SiLU 后的中间激活评估）。
2. **Context-aware Pattern Prediction**：为每层部署一对小型 neural network predictor 预测 Q/K 的 informativeness，避免完整算 attention score。用 elastic size transformation 动态调整 predictor 参数规模。
3. **High-performance Kernel Optimization**：permutation-free 策略融合 token 选择/padding/residual add，避免全局内存拷贝；segment-based gradient computation 缓解长序列下 activation 内存峰值。

深度细节回 [[atc2025-wang-tuowei]]。

## 关键结果

- 端到端 fine-tuning 显存降低 **1.93×**（vs SOTA），speedup **1.36×**
- Llama2-7B / Llama3-8B / Mistral-7B / OPT-6.7B 上一致改进
- 验证跨 LLM 架构（Llama / Mistral / OPT）和 GPU 架构

## 相关

- **相关概念**：[[Attention]]、[[LoRA]]、[[KV-Cache]]
- **同会议**：[[ATC-2025]]
