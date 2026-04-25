---
type: paper
name: UCP
full_title: "Universal Checkpointing: A Flexible and Efficient Distributed Checkpointing System for Large-Scale DNN Training with Reconfigurable Parallelism"
authors: [Xinyu Lian, Sam Ade Jacobs, Lev Kurilenko, Masahiro Tanaka, Stas Bekman, et al.]
venue: ATC
year: 2025
tags: [llm-training, checkpointing, parallelism, deepspeed, reconfiguration]
source_pdf: "[[atc2025-lian.pdf]]"
source_md: "[[atc2025-lian]]"
---

# Universal Checkpointing: A Flexible and Efficient Distributed Checkpointing System for Large-Scale DNN Training with Reconfigurable Parallelism (ATC 2025)

> **一句话总结**：用 atomic checkpoint + pattern-based 重配置流水线把 DP/TP/PP/SP/ZeRO/3D 并行 checkpoint 解耦，1T 模型重配置 < 3 分钟（占总训练时间 < 0.001%），比串行脚本快 14–257×。

## 问题

LLM 训练动辄数月（GPT-4 90–100 天，LLaMA 3.1 平均每 3 小时一次故障）。现有 checkpoint（PyTorch DCP、Megatron MCP、CheckFreq、Gemini）都和具体并行策略绑定：DP 各 rank 各存自己分片，重配 ZeRO-3 → 3D parallel 需手写转换脚本；DCP 只支持改 DP 度，MCP 只覆盖 PP/TP。MoE、GQA 等异构架构重配更难。

## 核心方法

UCP 在 [[DeepSpeed]] 中实现，核心三件事：

- **Atomic Checkpoint**：每个 tensor operator 的 weight/Adam-m/Adam-v 各一个 fp32 文件，去掉 rank id、padding、partition info，只与参数名挂钩，与并行策略和硬件配置完全解耦。
- **Pattern-Based Reconfiguration Pipeline**：定义 6 种 pattern——Unique（PP 私有）、Replicate（LayerNorm）、Partial（异步累积）、Shard-V（列切）、Shard-H（行切）、Shard-Hy / Shard-NC（多维或非连续切，用于 [[MoE]] 融合权重和 [[GQA]] 不等大小 QKV）。配合 Extract / Union / StripPad / UcpInfo / Save / Load 6 个原语自动转换。
- **Efficient Reconfiguration**：把转换抽象成 MapReduce（mapper 读 ckpt，shuffler 按参数名分发，reducer 按 pattern 合并），node 间按 numel 平衡 + node 内多核并行；redundancy-bypassing loading 让同 DP group 各 rank 只读自己的 atomic 文件再用 all-gather；layer-by-layer 加载控内存峰值；lazy 调用避免影响正常训练。

深度细节见 [[atc2025-lian]]。

## 关键结果

- 7B–1T 参数模型，nested-parallel 重配比串行脚本快 14–257×，1T 模型 < 3 min（< 0.001% 训练时间）。
- 在 BLOOM 176B、Phi-3.5-MoE 42B、SmileyLlama 8B、YuLan-Mini 4.2B 真实生产训练中已用。
- 任意 ZeRO-1/3 + PP + TP + SP 与 3D 并行间互转都不损失训练 loss 曲线（实测 GPT 350M、7B、176B 与 Mixtral-7×8B 42B）。
- 384×A100-80GB 集群 5 GB/s 存储带宽下做出全部实验。

## 相关

- **相关概念**：[[Checkpointing]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[ZeRO]]、[[MoE]]、[[Mixed-Precision-Training]]
- **同类系统**：CheckFreq、Gemini、PyTorch DCP、Megatron MCP
- **同会议**：[[ATC-2025]]
