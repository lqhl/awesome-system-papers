---
type: paper
name: DriftBench
full_title: "DriftBench: Measuring and Predicting Infrastructure Drift in LLM Serving Systems"
authors: [Gianluigi Vitale]
venue: MLSys
year: 2026
tags: [llm-serving, monitoring, infrastructure-drift, safety, quantization]
source_pdf: "[[4c56ff4ce4aaf9573aa5dff913df997a.pdf]]"
source_md: "[[4c56ff4ce4aaf9573aa5dff913df997a]]"
---

# DriftBench: Measuring and Predicting Infrastructure Drift in LLM Serving Systems (MLSys 2026)

> **一句话总结**：DriftBench 测 236,985 对 prompt-response、105 配置，用 PRI 预测 infrastructure drift：未见硬件 R²=**0.909**、未见精度 R²=**0.763**；生产案例拦截 23.85% safety flip 的高风险升级。

## 问题

LLM 部署常换 GPU、精度（FP16→FP8）、框架（[[vLLM]]→TensorRT-LLM 或 [[SGLang]]），假设同权重同输入应功能等价，实则输出 flip。Evidently/WhyLabs 等监控 data/concept drift，无法检测计算路径变化导致的 functional flip；单 workload benchmark 可漏 **99%** safety 风险（workload 间 flip 差 **88×**）。

## 核心方法

**Infrastructure drift 定义**：serving stack（硬件/精度/框架）变化致输出 functional correctness 改变，权重与输入不变。

**Flip rate 指标**：correct↔incorrect 双向计为 flip；分 code/math/safety/chat/long-context 五类 workload 评测。

**PRI（Portability Risk Index）**：gradient boosting 从配置元数据回归 drift rate；held-out dimension 评估真外推。

**Systematic vs idiosyncratic**：硬件/精度可 predict-once；framework/model 需重新实测（R²<0.48）。

## 关键结果

- **236,985** 对 × **105** 配置 × **5** 模型 × **4** GPU × **3** 框架 × **3** 精度
- PRI held-out：hardware R²=**0.909**，precision R²=**0.763**；framework/model R²<**0.48**
- Llama-3.1-8B H100/FP16→B200/FP8：safety flip **23.85%**（520 AdvBench prompts）
- vs Evidently：H100→FP8 上 DriftBench 检 3% functional flip，Evidently 0 failure flagged

## 相关

- **相关概念**：[[Quantization]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、Evidently AI
- **同会议**：[[MLSys-2026]]