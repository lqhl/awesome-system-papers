---
type: paper
name: Charon
full_title: "Charon: A Unified and Fine-Grained Simulator for Large-Scale LLM Training and Inference"
authors: [Mengtian Yang, Zhekun Zhang, Mingheng Wu, Jianwen Yan, Hanshi Sun, Li-wen Chang]
venue: MLSys
year: 2026
tags: [simulator, llm-training, llm-inference, design-space-exploration, operator-level]
source_pdf: "[[c9f0f895fb98ab9159f51fd0297e236d.pdf]]"
source_md: "[[c9f0f895fb98ab9159f51fd0297e236d]]"
---

# Charon: A Unified and Fine-Grained Simulator for Large-Scale LLM Training and Inference (MLSys 2026)

> **一句话总结**：Charon 用 compiler-style pass 把 HuggingFace/vLLM 原生 PyTorch 模型转成算子图，混合 profiling/analytical/prediction 后端模拟训练与推理，端到端误差 <5.35%（大规模训练 <3.74%），大集群 profiling 成本降 30k×。

## 问题

LLM 训练/推理的最优配置空间（DP/PP/TP/EP/SP、batch、fusion、overlap）可达数千组合，全集群实测单次探索需数百 GPU-hour，总成本可达 10⁶ GPU-hour。现有 simulator 碎片化：多数只覆盖训练或推理，需手工建 mock 模型或预处理 trace，缺算子级粒度与灵活优化 pass。

## 核心方法

Charon 把 simulation 视为 compiler-style 变换流水线：

1. **Graph-based Frontend**：`torch.fx` / `torch.compile` 追踪原生 PyTorch 模型（HuggingFace、[[vLLM]]、自定义），自动生成 forward/backward 联合图；pass 注入 TP/PP/DP/FSDP/ZeRO/EP/SP 通信算子，支持 operator fusion/rewrite、activation checkpointing、disaggregated prefill/decode 分图。
2. **Multi-engine Backend**：profiling（最准）、prediction（RF 预测未见 shape）、analytical（roofline + 分层 link-centric 通信模型）三引擎 + fused fallback；支持 FP32/BF16/FP16/FP8/INT8。
3. **Overlap Processor**：ratio-based 与 bandwidth-aware 通信-计算/通信-通信重叠模型。
4. **Design Space Explorer**：内置搜索 + 规则剪枝，两分钟级完成 Llama-3 70B 推理 cost-latency Pareto 探索。

## 关键结果

- LLaMA3-8B、Qwen3-8B、Qwen3-30B-A3B 端到端误差 consistently <**5.35%**；近万 GPU 大规模训练 <**3.74%**。
- 大集群实验相比实测 profiling 成本降 **>30k×**。
- Llama-3 70B 推理 case study：自动发现优于人工调优 baseline 的部署配置；放松 TPS/user 约束可获最高 **7×** TPS/GPU。
- Dynamic sequence parallelism 规划平均降 attention block 延迟 **15%**。
- [[MoE]] 训练 8-GPU 峰值内存预测误差 +0.39%。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[KV-Cache]]、roofline
- **同类系统**：ASTRA-Sim、SimAI、Vidur、LLMServingSim、Lumos、Echo
- **同会议**：[[MLSys-2026]]