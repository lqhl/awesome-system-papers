---
type: paper
name: OptiKit
full_title: "Meeting SLOs, Slashing Hours: Automated Enterprise LLM Optimization with OptiKit"
authors: [Nicholas Santavas, Kareem Eissa, Patrycja Cieplicka, Piotr Florek, Matteo Nulli, Stefan Vasilev, Seyyed Hadi Hashemi, Antonios Gasteratos, Shahram Khadivi]
venue: MLSys
year: 2026
tags: [quantization, enterprise-ml, ray, llm-serving, automation]
source_pdf: "[[8613985ec49eb8f757ae6439e879bb2a.pdf]]"
source_md: "[[8613985ec49eb8f757ae6439e879bb2a]]"
---

# Meeting SLOs, Slashing Hours: Automated Enterprise LLM Optimization with OptiKit (MLSys 2026)

> **一句话总结**：eBay 的 Ray 分布式 pipeline 自动跑 compression（GPTQ/SmoothQuant/FP8 recipe）→ StatEval → SLO-aware Benchmarker → Bayesian Tuner，三模型族 GPU 吞吐 >2×、人工优化工时大幅削减，INT8/FP8 统计精度恢复 >99%。

## 问题

企业多团队抢有限 GPU；手工 quantization + [[vLLM]]/TensorRT 调参依赖稀缺专家，缺端到端、可复现、接 registry 的 production pipeline。

## 核心方法

**Ray actors + flows**：Fetch → Optimizer（backend-agnostic recipe：int w8a8/w4a16、fp8 dynamic）→ StatEval（GSM8K/IFEval/Do-Not-Answer + 内部 benchmark）→ Benchmarker（steady-state regression β≈1 + exponential rate search）→ Tuner（Optuna TPE 搜 TP/max_seqs/batch tokens）。

**SLO objective**：\(J = \text{TPS/GPU} + \lambda \cdot \mathbb{1}[\text{SLO fail}]\)。

## 关键结果

- 生产：**>2×** GPU throughput（Qwen 7B / Mistral 24B / Llama 70B 族，Fig.1）
- FP8 & INT W8A8：平均统计恢复 **>99%**；INT W4A16 更敏感
- Mistral 24B 全 pipeline 数小时级（Fig.5）；开源发布

## 相关

- **相关概念**：[[Quantization]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、TensorRT-Sweep、Neural Magic
- **同会议**：[[MLSys-2026]]