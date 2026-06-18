---
type: paper
name: ApproxMLIR
full_title: "ApproxMLIR: An Accuracy-Aware Compiler for Compound ML Systems"
authors: [Hao Ren, Yi Mu, Sasa Misailovic]
venue: MLSys
year: 2026
tags: [compiler, mlir, approximate-computing, rag, llm-inference]
source_pdf: "[[a5771bce93e200c36f7cd9dfd0e5deaa.pdf]]"
source_md: "[[a5771bce93e200c36f7cd9dfd0e5deaa]]"
---

# ApproxMLIR: An Accuracy-Aware Compiler for Compound ML Systems (MLSys 2026)

> **一句话总结**：MLIR `approx` dialect 统一 ML（JAX/StableHLO）与非 ML（Polygeist/C++）组件的 accuracy knob，OpenTuner 搜 Pareto frontier + `approx-runtime` 动态决策；BM25 RAG 等 compound AI 在 6–9% QoS loss 下 **2.64–3.04×** speedup，优于 static approximation。

## 问题

Compound AI（LLM + retrieval/tool calling）各组件近似机会多，但 JAX/PyTorch 与 C++  toolchain 割裂，无法在端到端统一搜 accuracy-performance tradeoff。LLVM 级近似丢失高层语义；属性绑定易被 tiling 等 pass 丢弃。

## 核心方法

**approx dialect**：`approx.knob`（autotuner 接口）、`approx.decision_tree`（runtime 动态）、`approx.transform`（loop perforation、func substitution 等）。

**approx-opt** 降低到各 target dialect；**approx-runtime** 运行时按 state 选 configuration。C++/Python frontend 注解 knob。

## 关键结果

- LLM+RAG (kb)：6% QoS loss **2.64×**、9% QoS loss **3.04×** vs non-approximated
- 三个 compound AI + 五个 non-ML kernel：Pareto frontier 一致优于 static strategy
- Gemma 3 变体作 LLM backend

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[Flash-Attention]]
- **同类系统**：ApproxHPVM、ApproxTuner、OpenTuner、MLIR/Polygeist
- **同会议**：[[MLSys-2026]]