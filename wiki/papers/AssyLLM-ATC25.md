---
type: paper
name: AssyLLM
full_title: "AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks"
authors: [Shichen Zhan, Li Li, Chengzhong Xu]
venue: ATC
year: 2025
tags: [federated-learning, llm-fine-tuning, model-assembly, edge-computing, memory-optimization]
source_pdf: "[[atc2025-zhan.pdf]]"
source_md: "[[atc2025-zhan]]"
---

# AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks (ATC 2025)

> **一句话总结**：把多个预训练 LLM 拆成 transformer block，用客户端本地 inference + CKA/KL 兼容性打分挑出最适合下游任务的 block 组装成新模型，跳过 backpropagation；端侧内存降 92%、加速 30×、准确率比 FedLLM 基线高 18.26%。

## 问题

Federated Learning 微调 LLM（FedLLM）能保住边端数据隐私，但 Llama-7B 全量微调要 40+ GB、LoRA/Adapter 也要 15+ GB，普通边端设备只有 4–16 GB，导致 60–85% 客户端无法参与，数据多样性丢失、最终精度掉 14.7–19.1%。已有省内存方案各有问题：PEFT/QLoRA 准确率掉 5%+；BP-free（zero-order、forward gradient）训练不稳；recomputation/swapping 系统层省内存但训练时间翻 1.78–3.17×。

## 核心方法

把"微调"重新定义为"从预训练 block 池里挑+组装"，整个 fine-tuning 流程不做 backprop，每轮只做 inference：

- **Block Comparator**：用 CKA（Centered Kernel Alignment）+ COR（layer-wise KL divergence）双指标评估候选 block 与已组装模型的兼容性。客户端 forward 一遍本地 batch，计算两 block 输出激活的相似度；高 CKA 高 COR 才是好候选
- **Elastic Adapter**：解决跨预训练模型 block 拼接的三类不匹配——维度（线性投影）、语义（cross-attention 用一个 block 输出做 query、另一个做 K/V）、attention head 数（pool/expand）。多数情况只需简单 projection 矩阵，少数关键拼接点用 trainable adapter（仅 finetune adapter）
- **Block Quanter**：block-pool 总大小可达 40+ GB（多个 LLM 并存），用 block-wise 混合精度量化——分析 weight 对 block 输出 activation 的敏感度（random perturbation + masking），关键权重高精度、其他低精度
- **Block Swapper**：block 池仍可能超内存，按 block 之间的 correlation pre-load + pre-swap 流水化 block 在内存与外存间换入换出，掩盖 I/O 延迟

服务器端按 voting 聚合各客户端选出的 top-K block 形成下一轮候选模型，直到选到 terminating block 或达到深度上限。深度细节回 [[atc2025-zhan]]。

## 关键结果

- 比 FedLLM 基线（200 客户端、5 组内存 4–64 GB）准确率提升最多 18.26%
- 端到端训练加速最多 30.04×（vs recomputation/swapping 方案）
- 内存最多省 92%；4 GB 内存设备可参与，QLoRA 还要 15+ GB 才行
- 评估在 Llama-7B / OPT-6.7B / Vicuna-7B / BERT-base / RoBERTa-large block 池上，BoolQ + OBQA 任务

## 相关

- **相关概念**：[[Federated-Learning]]、[[LoRA]]、[[Quantization]]、[[CKA]]、[[Adapter-Tuning]]
- **同类系统**：[[FedAdapter]]、[[FwdLLM]]、[[QLoRA]]
- **同会议**：[[ATC-2025]]
