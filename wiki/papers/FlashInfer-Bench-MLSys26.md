---
type: paper
name: FlashInfer-Bench
full_title: "FlashInfer-Bench: Building the Virtuous Cycle for AI-Driven LLM Systems"
authors: [Shanli Xing, Yiyan Zhai, Alexander Jiang, Yixin Dong, Yong Wu, "et al."]
venue: MLSys
year: 2026
tags: [benchmark, llm-inference, gpu-kernels, ai-code-generation, flashinfer]
source_pdf: "[[c8ffe9a587b126f152ed3d89a146b445.pdf]]"
source_md: "[[c8ffe9a587b126f152ed3d89a146b445]]"
---

# FlashInfer-Bench: Building the Virtuous Cycle for AI-Driven LLM Systems (MLSys 2026)

> **一句话总结**：面向 AI-generated GPU kernel 的闭环框架：FlashInfer Trace 统一 schema + 真实 serving workload 数据集 + 抗 reward-hacking 的 benchmark + `apply()` 动态注入最佳 kernel 进 [[vLLM]]/[[SGLang]]，实现 zero-code 部署。

## 问题

LLM agent 已能生成复杂 GPU kernel，但集成进生产推理系统有三道坎：(1) kernel 依赖（ragged 分布、精度、memory layout）难精确传达给 agent；(2) 真实 serving 流量与 uniform/random 设置差异大；(3) 生成 promising kernel 后仍需手工改引擎代码。

## 核心方法

四个组件形成 virtuous cycle：

1. **FlashInfer Trace**：JSON schema 四元组 Definition × Workload × Solution × Evaluation，支持 static/dynamic shape 与 ragged tensor（page table + 索引指针）。
2. **FlashInfer-Bench Dataset**：服 DeepSeek-V3、Llama-3.1-8B、Qwen3-30B-A3B 于 ShareGPT 真实流量，覆盖 GEMM、Attention、Normalization、Sampling、[[MoE]] 等，每 Definition ~50 workload。
3. **Robust Kernel Benchmark**：确定性/低精度/随机 kernel 分别用 elementwise、matched-ratio、TVD 验证；subprocess isolation 防 reward hacking；Hungarian 调度多 GPU benchmark。
4. **flashinfer_bench.apply()**：AOT 索引 + O(1) dispatch 动态替换 kernel，`FIB_ENABLE_APPLY=1` 零代码接入 [[vLLM]] / [[SGLang]]。

## 关键结果

- Fast-0.95 top：gemini-2.5-pro、gpt-o3、gpt-5-2025-08-07；正确率 top：gpt-5 (83.9%)、gpt-o3 (71.3%)、gemini-2.5-pro (48.8%)。
- 大多正确性错误来自编译失败；模型难利用架构 intrinsic；Triton 多数任务更好，CUDA 专门优化潜力更大。
- Apply() 在 CUDA graph + warmup 下 dispatch 开销可忽略。

## 相关

- **相关概念**：[[MoE]]、[[Flash-Attention]]、[[KV-Cache]]、KernelBench
- **同类系统**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、FlashInfer
- **同会议**：[[MLSys-2026]]