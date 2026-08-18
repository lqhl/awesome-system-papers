---
type: paper
name: FlashInfer
full_title: "FlashInfer: Efficient and Customizable Attention Engine for LLM Inference Serving"
authors: [Zihao Ye, Lequn Chen, Ruihang Lai, Wuwei Lin, Yineng Zhang, et al.]
venue: MLSys
year: 2025
tags: [llm-inference, attention, gpu-kernels, kv-cache, jit, area/ai-infra]
source_pdf: "[[mlsys25-ye-flashinfer.pdf]]"
source_md: "[[mlsys25-ye-flashinfer]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# FlashInfer：可定制的高效 LLM Attention Engine（MLSys 2025）

> **原题**：FlashInfer: Efficient and Customizable Attention Engine for LLM Inference Serving

> **一句话总结**：FlashInfer 以 block-sparse/composable KV format、JIT attention template 和兼容 CUDA Graph 的 load-balanced scheduling 统一多样 serving attention；相对 compiler backend inter-token latency 降 29%–69%，长上下文 latency 降 28%–30%，parallel generation 提速 13%–17%。

## 问题与动机

LLM attention 随 paged/ragged KV、GQA、prefix sharing、sampling 与 batch 变化，固定 kernel 或通用 compiler 难同时获得覆盖与峰值性能。FlashInfer 提供 serving engine 可组合的 attention/kernel interface（§1–3）。

## 关键观察 / 隐含假设

- **观察 1：KV storage heterogeneity 应成为 kernel template 的显式输入。** block-sparse 与 composable format 避免为每个 serving case 重写算子。
  - **依赖假设**：主流 workload 可归约到所支持的 [[Attention|attention]] template。
- **观察 2：动态 load balance 与 CUDA Graph static constraint 必须协同。**
  - **可能失效场景**：新 attention semantics、跨 GPU communication 或极端 raggedness。

## 核心方法

系统组合可定制 JIT template、paged/ragged KV layout、调度与 CUDA Graph integration，并作为 SGLang、vLLM、MLC-Engine 的底层组件（§3–4）。

## 设计取舍

- template coverage 换维护矩阵。
- JIT customization 换 cold-start/compile cache。
- library interface 易集成，但端到端收益受上层 scheduler 限制。

## 实验与结果

- 相对 compiler backend inter-token latency 降 29%–69%（§5）。
- long-context inference latency 降 28%–30%；parallel generation 加速 13%–17%（§5）。
- kernel 与 serving engine case 覆盖不同 KV/layout/dynamic batch，但结论绑定所测 GPU/模型版本。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| FlashInfer 提供高性能 attention | §5 三类 latency improvement | 选定 GPU/serving workloads | 强 |
| template 可覆盖多样 KV | 多 format/case | 非所有 attention variant | 中到强 |
| kernel speedup全传到生产 SLO | 有 E2E但无长期 trace/P99 | 实验流量 | 中 |

## 批判性分析

### 论证链条

workload heterogeneity→template/layout/scheduler→kernel与E2E证据闭合，且已有多引擎采用。不同 baseline 是否启用同等级手工 kernel 需按具体表读取。

### 假设压力测试

新 GPU ISA、[[Quantization|quantization]]、[[Sparse-Attention|sparse attention]] 与多 GPU disaggregation 会扩大 specialization surface。

### 实验可信度

覆盖真实 engine integration 是优势；缺 production arrival、tail latency、compile amortization 和回归事故。

### 系统性缺陷

JIT binary cache、版本 ABI、错误 kernel rollback 与多租户隔离需上层承担。

## 局限与后续工作

- **局限 1**：主要是单 GPU attention/kernel layer。
- **后续工作 1**：以真实 trace 测多 GPU、P99、cold JIT 与版本升级。

## 相关

- **相关概念**：[[Flash-Attention]]、[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]
- **相关系统**：[[vLLM]]、[[SGLang]]、[[FlashInfer-Bench-MLSys26]]
