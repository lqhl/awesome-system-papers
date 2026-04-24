---
type: paper
name: OptiKit
full_title: "Meeting SLOs, Slashing Hours: Automated Enterprise LLM Optimization with OptiKit"
authors: [Nicholas Santavas, Kareem Eissa, Patrycja Cieplicka, Piotr Florek, Matteo Nulli, "et al."]
venue: MLSys
year: 2026
tags: [llm-inference, auto-tuning, quantization, enterprise, slo]
source_pdf: "[[8613985ec49eb8f757ae6439e879bb2a.pdf]]"
source_md: "[[8613985ec49eb8f757ae6439e879bb2a]]"
---

# Meeting SLOs, Slashing Hours: Automated Enterprise LLM Optimization with OptiKit (MLSys 2026)

> **一句话总结**：eBay 开源的端到端分布式 LLM 优化框架，用 Ray actor 自动串起压缩 + 统计评估 + SLO 驱动基准 + Bayesian 运行时调参，生产环境实现 up to 2.8x GPU throughput 提升。

## 问题

企业部署 LLM 面临 GPU 容量瓶颈与手工优化依赖少数专家的矛盾：模型从 8B 到 70B+，跨异构硬件（H200/H100/A100）、跨后端（[[vLLM]]、[[SGLang]]、TensorRT-LLM）的压缩+serving 调优需要深厚系统专业知识，手动优化耗时难复现；现有工具如 TensorRT-Sweep、GuideLLM、SCOOT 各偏一隅，缺 end-to-end、数据主权、生产级集成。

企业场景下需要「automation + standardization + deep enterprise integration」三位一体，让普通应用团队也能拿到专家级优化结果。

## 核心方法

**四个子系统流水线**：

1. **Optimizer**：backend-agnostic 的压缩引擎，以 recipe 形式封装压缩策略（`int w8a8`=GPTQ+SmoothQuant、`int w4a16`、`fp8 dynamic`=RTN），模块化的校准数据采样（uniform / length-weighted / token-statistics stratified）。
2. **StatEval**：跨 vLLM / OpenAI-style endpoint 的统计评估库，内置 GSM8K、IFEval、Do-Not-Answer，加 eBay 内部电商 benchmark。
3. **Benchmarker**：SLO 驱动的性能扫描；用线性回归斜率 β≈1 做 steady-state detection（|β-1| ≤ τ_β，τ_β 取 0.02-0.05），用 exponential search 逼近 SLO 临界的最大可持续请求率。
4. **Tuner**：基于 Ray Tune 的 Bayesian 超参优化，objective `fitness(c) = throughput(c) / tensor_parallel_size(c) + λ·slo_penalty(c)`，搜索 parallelism / batch size / context window 等运行时参数。

**架构分三层**：Actor-Based Execution（Ray actor 细粒度 GPU/CPU 分配）、Flow Composition（declarative flow + 故障重试 + Docker 版本隔离）、Submission Engine（Pydantic schema 校验 + 打包 + 企业调度器对接）。

## 关键结果

- 生产环境中 [[Quantization]] + 调优后 GPU 吞吐 2x+ 提升，最高 2.8x。
- 相比手工优化可节约数百小时工程师时间，覆盖三个模型家族。
- 已开源，支持 HDFS / MMS / EMS 企业数据源，集成 Grafana/logs/tracing 观测链路。

## 相关

- **相关概念**：[[Quantization]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
