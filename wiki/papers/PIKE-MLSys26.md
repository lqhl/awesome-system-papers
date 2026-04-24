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

> **一句话总结**：系统比较 LLM multi-agent kernel 优化的 explore/exploit 策略——发现「exploit-heavy + error-fixing agent + 粗粒度 step」最优，在 KernelBench 上 H100 平均 2.88× 加速，CUDA 和 Triton 双实现 SOTA。

## 问题

GPU kernel 优化对 LLM/ML workload 很重要，但现有方案各有局限：
- **Model compiler**（TorchInductor、TensorRT）需不断更新支持新 GPU，常落后手工 kernel（原版 FlashAttention 比 naive PyTorch 快 7.6×）。
- **DSL / Triton**：降低门槛但 peak performance 仍需大量专家时间。
- **LLM agent 方法**（KernelBench、METR 等）已显出潜力，但 **agent 角色、prompt 策略、solution library 设计的动力学从未被系统研究**——尤其 exploration vs exploitation 的 trade-off。

## 核心方法

**1. 统一逻辑框架**

把 LLM kernel 优化抽象成 5 stage：library → seed selection → prompt construction → evaluation → post-processing。5 种 agent 角色：
- **IBA (Initial Brainstorming Agent)**：从 PyTorch 模型出发生成 n 个优化 idea。
- **COA (Code Optimization Agent)**：给定 seed 和 idea 生成优化版 kernel。
- **EFA (Error Fixing Agent)**：编译/正确性失败时 iterative 修复。

参数空间：explore/exploit ratio、island 数、elite archive size、mutation vs crossover、long-term vs short-term library。

**2. 两种实现：PIKE-B / PIKE-O**

- **PIKE-B（Branching Search）**：每轮留 top-k 并行 mutate 成 n 个新 solution，没有 island、short-term memory，纯 exploit，mutation-only。
- **PIKE-O（基于 OpenEvolve）**：支持多 island、长/短期、crossover/mutation 切换，可调 explore/exploit ratio；作者改 OpenEvolve 加入 EFA（原版缺这个）。

关键发现：**exploit-heavy + EFA + 粗粒度 step** 稳赢。Parallel island 反而带来 explore 倾斜，伤害结果。

**3. 评测套件**

- 基于 METR refined KernelBench：**Level 3-pike**（30 任务，MLP/RNN/Attention/Mamba 组件，平均 85 LoC）+ **Level 5**（14 任务，DeepSeek-V3/Llama3/RWKV/SD3/Mamba-2 等前沿，平均 493 LoC）。
- 对比 PyTorch Eager、torch.compile（max autotuning）、TensorRT、METR solution。

## 关键结果

- **H100 平均 2.88× 加速**（refined KernelBench）。
- **exploit-heavy + EFA** 一致击败 explore-heavy。
- **粗粒度 step**（每次给 LLM 更大改动余地）好过小 step 逐步爬坡。
- 最佳方案 CUDA 和 Triton 双实现，超过 TorchInductor + TensorRT + METR。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同类系统**：KernelBench、METR、OpenEvolve、AlphaEvolve、Triton、CUTLASS、TorchInductor
- **同会议**：[[MLSys-2026]]
