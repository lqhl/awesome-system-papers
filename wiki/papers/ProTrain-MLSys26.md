---
type: paper
name: ProTrain
full_title: "ProTrain: Efficient LLM Training via Automatic Memory Management"
authors: [Hanmei Yang, Jin Zhou, Yao Fu, Xiaoqun Wang, Ramine Roane, Hui Guan, Tongping Liu]
venue: MLSys
year: 2026
tags: [llm-training, zero, gradient-checkpointing, offloading, auto-tuning]
source_pdf: "[[a0a080f42e6f13b3a2df133f073095dd.pdf]]"
source_md: "[[a0a080f42e6f13b3a2df133f073095dd]]"
---

# ProTrain: Efficient LLM Training via Automatic Memory Management (MLSys 2026)

> **一句话总结**：把 ZeRO sharding、activation swapping、gradient checkpointing 统一成少量可调参数，用 memory-aware profiler + cost model 自动搜索最优配置；GPT-2/OPT/Mistral/LLaMA 上吞吐比 DeepSpeed/Colossal-AI/FSDP **1.43–2.71×**，单卡 RTX3090 可训 **34B**。

## 问题

DeepSpeed 等暴露 18+ 耦合 knob（ZeRO stage3 max live params vs max reuse distance 冲突等），手动调参难且硬件一变就 OOM 或利用率低（10B GPT-2 默认只用 35.6% GPU memory、慢 1.18×）。

## 核心方法

- **Hierarchical chunk management**：persistent/non-persistent chunk 划分 ZeRO+offload，execution-order 排列消除 ping-pong
- **Interleaved block management**：每 transformer block 独立选 swap/checkpoint/none
- **Memory-aware profiler**：trace-based 捕获 transient allocation 与 unhookable ops（占 10B 峰值 ~17.2%）
- **Constrained optimization**：最小化 iteration time s.t. peak memory ≤ GPU capacity；runtime/memory 预测误差 <4%

## 关键结果

- 吞吐：RTX3090 avg **2090 tok/s**（**1.77–2.71×**），A100 **1.43–2.22×** vs baselines
- 最大可训模型：单卡 3090 **34B**、4×A100 **87B**（FSDP 单卡远小）
- 4×3090 扩展 **3.5×**；4×A100 34B LLaMA **2.49–3.58×** vs 单卡

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[LoRA]]
- **同类系统**：DeepSpeed、Colossal-AI、FSDP、ZeRO
- **同会议**：[[MLSys-2026]]