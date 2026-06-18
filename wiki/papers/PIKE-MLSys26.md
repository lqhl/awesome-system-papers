---
type: paper
name: PIKE
full_title: "Optimizing PyTorch Inference with LLM-based Multi-Agent Systems"
authors: [Kirill Nagaitsev, Luka Grbcic, Samuel Williams, Costin Iancu]
venue: MLSys
year: 2026
tags: [agent, llm, kernel-optimization, kernelbench, gpu, ai4s]
source_pdf: "[[54229abfcfa5649e7003b83dd4755294.pdf]]"
source_md: "[[54229abfcfa5649e7003b83dd4755294]]"
---

# Optimizing PyTorch Inference with LLM-based Multi-Agent Systems (MLSys 2026)

> **一句话总结**：提出 PIKE 逻辑框架比较 LLM multi-agent PyTorch kernel 优化策略，发现 exploit-heavy + Error Fixing Agent + 粗粒度 step 最优，在 refined KernelBench 上 H100 平均 2.88× 加速（$25/task 时 2.51×），稳定超过 torch.compile 与 METR。

## 问题

GPU kernel 优化是 ML 推理性能的关键瓶颈。Model compiler（TorchInductor、TensorRT）需持续适配新 GPU 且常落后手工 kernel；Triton 等 DSL 降低门槛但 peak tuning 仍昂贵。近期 LLM agent 在 KernelBench 上已显出潜力，但 **multi-agent 系统的 explore/exploit 动力学、agent 角色与 library 设计从未被系统研究**。

## 核心方法

**PyTorch Inference Kernel Evolution (PIKE)** 把 kernel 搜索抽象为五阶段循环：library → seed selection → prompt construction → evaluation → post-processing。三类 agent：
- **IBA**：从 PyTorch 模型 brainstorm n 个优化 idea
- **COA**：基于 seed 生成优化 kernel
- **EFA**：编译/正确性失败时 iterative 修复

关键参数：explore/exploit ratio、island 数、elite archive、mutation vs crossover、长/短期 library。

**PIKE-B**：每轮取 top-k 并行 mutate，100% exploit、mutation-only、short-term memory，无 island。

**PIKE-O**：基于 OpenEvolve，支持 island/crossover/可调 explore ratio；作者补上原版缺失的 EFA。通过 ablation 可把 PIKE-O 逐步调成接近 PIKE-B。

评测用 METR refined KernelBench（Level 3-pike 30 任务 + Level 5 14 任务），300 query/task 预算，Gemini 2.5 Pro（EFA 可用 Flash）。

## 关键结果

- **Level 3-pike**：PIKE-B + EFA 达 **2.88×** geomean speedup vs PyTorch Eager；PIKE-O 调 exploit 后 **2.81×**
- **按成本**：cheap EFA 在 $25/task 达 **2.51×**，ROI 最优
- **Level 5**：PIKE-B **2.57×**（query）/ **2.44×**（$50/task）
- exploit-heavy + EFA 一致击败 explore-heavy；性能与 step 粒度正相关（粗 step 更好）
- 最佳解 CUDA + Triton 双实现，超过 torch.compile、TensorRT、METR

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同类系统**：KernelBench、METR、OpenEvolve、AlphaEvolve、Triton、TorchInductor
- **同会议**：[[MLSys-2026]]