---
type: paper
name: mTuner
full_title: "mTuner: Accelerating Parameter-Efficient Fine-Tuning on Multi-GPU Servers with Elastic Tensor"
authors: [Kezhao Huang, Siqi Zhu, Mingshu Zhai, Liyan Zheng, Kinman Lei, et al.]
venue: ATC
year: 2025
tags: [peft, fine-tuning, memory-management, llm-training, elastic-tensor]
source_pdf: "[[atc2025-huang-kezhao.pdf]]"
source_md: "[[atc2025-huang-kezhao]]"
---

# mTuner: Accelerating Parameter-Efficient Fine-Tuning with Elastic Tensor (ATC 2025)

> **一句话总结**：提出 elastic tensor 抽象动态调节 tensor 在显存中的份额，把 PEFT 的内存波谷利用率拉满，PCIe/NVLink 服务器上分别提升 28.3% / 14.5% 平均吞吐。

## 问题

PEFT（[[LoRA]] 等）只更新少量参数、绝大多数权重 frozen，留下两个机会和三个挑战：

1) 时间维度内存利用率低——activations 的 first-in-last-out 模式造成峰谷，谷期大量空闲显存浪费；
2) 通信被数据依赖卡死——activation 的 [[Tensor-Parallelism]] 通信只能在生成后启动，前面计算阶段通信资源闲置；
3) 累积策略僵化——所有阶段统一累积导致峰值过高。

现有方案（DeepSpeed ZeRO、Megatron、Flux）静态调度，无法适配 PEFT 的动态特性。

## 核心方法

提出 **elastic tensor** 抽象：所有 tensor（参数、激活）视为可动态调节存储比例的实体，定义四个核心动作 + 可调比例：

- **Gather**：跨设备 all-gather 把比例从 $\frac{1}{D}$ 提到 100%
- **Discard**：丢弃已 gather 的部分降低比例（无开销）
- **Execute**：执行计算生成 runtime tensor，比例为输入 batch 的处理份额
- **Checkpoint**：保存生成的 runtime tensor 用于反向

基于 elastic tensor 实现三类优化：

- **Temporal memory adjustment**：在内存谷期渐进式（progressive）缓存更多 frozen weights（如 12.5% → 25% → 50% → 100%），峰前再渐进 discard。利用 PEFT 大量 frozen 权重特性减少 forward 时的 all-gather 通信。
- **Dependence-relaxed communication**：在 attention 计算时提前 gather MLP 的部分 weights（25% 或 50%），减少后续 activation 的 all-gather/reduce-scatter 范围（8 GPU → 4 GPU），让 TP 通信更小、矩阵乘 reduction 维度更大。
- **Adaptive data accumulation**：对接近 loss 的深层 layer，按 batch 维度切分（如 4 样本切成 2 组）优先做 backward，降低 activation 峰值高度 $H_{new} = \frac{l}{L}\frac{b}{B}H + (1-\frac{l}{L})H$。

调度器用双重内存（峰值 + 谷值）DP 算法在 profile 数据上搜索最优 schedule。基于 PyTorch FSDP 实现，hook 形式接入。深度细节回 [[atc2025-huang-kezhao]]。

## 关键结果

- 7B-70B Llama 2 模型，PCIe 服务器（8×A100-40G）上比最强基线 DeepSpeed 提升 28.3%（最高 51.2%），4×NVLink H100 服务器上比 Flux 提升 14.5%（最高 24.8%）
- 比 Torch-FSDP 平均加速 4.15×
- 长序列（≥4096）下平均 34% 加速
- 渐进填谷把 80.2% workload 提升到 25% elastic tensor 比例，整体通信时间减少 41%
- Schedule 搜索 70B 模型仅 147.9s，相对 23h 训练可忽略
- 开源：https://github.com/xxcclong/mTuner

## 相关

- **相关概念**：[[LoRA]]、PEFT、[[Tensor-Parallelism]]、FSDP、[[Activation-Checkpointing]]
- **同类系统**：DeepSpeed ZeRO、Megatron、Flux
- **同会议**：[[ATC-2025]]
