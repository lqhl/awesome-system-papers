---
type: paper
name: PrefillOnly
full_title: "PrefillOnly: An Inference Engine for Prefill-only Workloads in Large Language Model Applications"
authors: [Kuntai Du, Bowen Wang, Chen Zhang, Yiming Cheng, Qing Lan, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, prefill-only, kv-cache, scheduling, vllm]
source_pdf: "[[3731569.3764834.pdf]]"
source_md: "[[3731569.3764834]]"
---

# PrefillOnly: An Inference Engine for Prefill-only Workloads in Large Language Model Applications (SOSP 2025)

> **一句话总结**:针对只需 1 个输出 token 的 prefill-only 工作负载(推荐、信用验证、embedding、P/D 分离的 prefill 节点),通过 hybrid prefilling 只保留单层 [[KV-Cache]] 并用 shortest-prefill-first 调度,相同 SLO 下 QPS 提升达 **4×**。

## 问题

LLM 除了生成型应用,越来越多在 discriminative 任务里替代传统 DL 模型——推荐、credit scoring、data labeling、文档 embedding。这些任务只需 LLM 输出**一个 token** 的概率分布(Yes/No)或最后层 hidden state,完全不需要 decoding。但现有引擎([[vLLM]])为可变输出长度设计:必须为所有层 cache KV、调度算法假设 JCT 不可预测。结果 MIL(max input length)受限,长上下文(如用户历史)被迫用 chunked prefill(降 14% 吞吐)或 tensor parallelism(跨 GPU all-reduce 吃掉算力)。

## 核心方法

PrefillOnly 完全拥抱 prefill-only 的两个特性:

1. **Hybrid prefilling**:普通 chunked prefilling 需要多次 forward pass、必须保留所有层 KV。PrefillOnly 观察到 GPU 内存主要被非 attention 层的临时 tensor 占据。于是**非 attention 层 chunk-by-chunk、attention 层不 chunk**,一次 forward pass 完成;只需保留**当前层**的 KV,后续层算完即丢。这让长请求不再需要跨 GPU 并行。
2. **Shortest-prefill-first + continuous prefill time estimation**:因为输出固定 1 token,JCT 可以预先算出——取决于输入长度和 prefix cache 命中情况。每次调度前重估所有 waiting 请求的 prefill time(prefix cache 状态时刻变化),从而准确地做 shortest-job-first。额外加 anti-starvation fairness 机制。

基于 [[vLLM]] 实现,通过 `torch.compile` 泛化到不同模型/硬件,无新 kernel。

## 关键结果

- **4×** 以上 QPS 提升,同时 **P99 和平均延迟更低**于 baseline。
- 在 4 种硬件(含 A100、H100)、3 个 LLM、2 条 trace 上评估。
- 不需新 kernel,可移植性强。
- 也适用于 P/D 分离架构的 prefill 节点、embedding 生成(Qwen3-Embedding 等)。

## 相关

- **相关概念**:[[KV-Cache]]、[[Prefix-Caching]]、[[Prefill-Decode-Disaggregation]]、[[Chunked-Prefill]]、[[Tensor-Parallelism]]、[[Shortest-Job-First]]
- **同类/依托系统**:[[vLLM]]、[[SGLang]]
- **同会议**:[[SOSP-2025]]
