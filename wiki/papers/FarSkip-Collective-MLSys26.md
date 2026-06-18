---
type: paper
name: FarSkip-Collective
full_title: "FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models"
authors: [Yonatan Dukler, Guihong Li, Deval Shah, Vikram Appia, Emad Barsoum]
venue: MLSys
year: 2026
tags: [moe, expert-parallelism, communication-overlap, training, inference]
source_pdf: "[[698d51a19d8a121ce581499d7b701668.pdf]]"
source_md: "[[698d51a19d8a121ce581499d7b701668]]"
---

# FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models (MLSys 2026)

> **一句话总结**：FarSkip-Collective 修改 MoE 残差连接使 Dispatch/Combine 与下一子层计算重叠，FCSD 自蒸馏在 <10B tokens 内将 16B–109B 模型全层转换且平均精度 drop ≤2.5%，Llama 4 Scout 109B 平均 within 1%；Megatron 训练 EP 通信重叠 88.4%，[[vLLM]]/[[SGLang]] 推理 TTFT 加速 18.5%。

## 问题

[[MoE]] 在 Expert Parallelism 下 Dispatch/Combine all-to-all 为 **blocking communication**，造成 GPU 空闲。简单改连接可能损害大模型能力；此前工作多限于 dense TP 或小规模部分层修改。

## 核心方法

**FarSkip-Collective**：在 collective 进行时，用 **partial/outdated activation** $o^*_k$ 启动下一子层 $f_{k+1}$，将 communicated $o_k$ far-skip 加到更后层 residual。

- Attention 输入：$o^*_{attn} = o_{k-1} + shared\text{-}expert_{k-1}$（不含 routed expert，可 overlap Combine）
- MoE 输入：$o^*_{mlp} = o_{k-1}$（outdated，可 overlap Dispatch）

**FCSD (FarSkip-Collective Self-Distill)**：KL + 可选 hidden alignment，<10B tokens 恢复精度。

Megatron-LM / [[vLLM]] / [[SGLang]] PyTorch API 层异步 collective + 调度实现重叠。

## 关键结果

- DeepSeek-V2 Lite 16B、Qwen3-30B-A3B、Llama 4 Scout 109B：平均精度 drop **≤2.5%**（11 数据集）；Scout **within 1.0%** of instruction-tuned release
- 训练：EP all-to-all **88.4%** 计算-通信重叠（forward 87.6%，backward 89.0%）
- 推理：Llama-4 Scout modified model **TTFT +18.5%**；CUDA graph 下通信重叠最高 **97.6%**

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、communication overlap
- **同类系统**：Megatron-LM、[[vLLM]]、[[SGLang]]、DeepSeek-V2、Llama 4
- **同会议**：[[MLSys-2026]]