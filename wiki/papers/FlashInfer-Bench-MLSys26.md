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

LLM agent 已能生成复杂 GPU kernel（KernelBench、Kevin 等），但集成进生产推理系统有三道坎：
1. kernel 依赖（ragged 分布、数据精度、memory layout）难精确传达给 agent；
2. 真实 serving 流量与论文 uniform/random 设置差异大，难追踪真实性能；
3. 生成完 promising kernel 仍需手工改引擎代码，集成 gap 大。

## 核心方法

四个组件形成 virtuous cycle：

1. **FlashInfer Trace**：自包含的 JSON schema，4 个部分 Definition（I/O 张量、dtype、static/dynamic 轴、PyTorch 参考实现）× Workload（具体输入，可为 safetensors dump / 随机 / 标量）× Solution（实现代码 + entry + 兼容 metadata）× Evaluation（正确性 + 性能 + 环境快照）。支持 ragged tensor 通过 full-page tensor + 索引指针。

2. **FlashInfer-Bench Dataset**：服 DeepSeek-V3、Llama-3.1-8B、Qwen3-30B-A3B 于 ShareGPT 真实流量，采集 GEMM、Attention、Normalization、Sampling、[[MoE]] 等算子，每 Definition 保留 ~50 workload；deduplicate 时按 batch size 等性能敏感轴和张量统计保多样性。

3. **Robust Kernel Benchmark**：
   - 确定性 kernel 按 `|y_sol - y_ref| ≤ ε_abs + ε_rel·|y_ref|` 逐元素比，拒 NaN/Inf。
   - 低精度 kernel 用 matched-ratio ρ=0.95 的 tight 阈值。
   - 随机 kernel（sampling）用 total variation distance (TVD) 与 mask violation 双检。
   - Isolation：每 solution 独立 subprocess + CUDA context teardown；persistent 模式 + 备用 worker pool 加速大扫描。
   - System support：Hungarian 算法在 cost matrix 上分配 micro-batch，EMA 在线更新 cost。

4. **flashinfer_bench.apply()**：AOT 索引 + O(1) dispatch 动态替换 kernel，zero code change 接入 vLLM / SGLang（`FIB_ENABLE_APPLY=1`）。支持 decorator + imperative API，未命中或全局关闭时透明 fallback。

## 关键结果

- 公开 leaderboard 追踪 frontier LLM 在真实 workload 上的 GPU 编程能力。
- 关键发现：（1）大多正确性错误来自编译失败；（2）模型不会利用架构细节和 intrinsic；（3）高层语言（Triton）多数任务表现更好，CUDA 在专门优化上潜力更大。
- Fast-0.95 top performer: gemini-2.5-pro、gpt-o3、gpt-5-2025-08-07；正确率 top：gpt-5 (83.9%)、gpt-o3 (71.3%)、gemini-2.5-pro (48.8%)。
- Apply() 在 CUDA graph + warmup 下 dispatch 开销可忽略。

## 相关

- **相关概念**：[[MoE]]、[[Flash-Attention]]、[[KV-Cache]]、Kernel Bench
- **同类系统**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、FlashInfer
- **同会议**：[[MLSys-2026]]
