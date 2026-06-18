---
type: paper
name: BatchLLM
full_title: "BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching"
authors: [Zhen Zheng, Fanghao Zhou, Xin Ji, Chuanjie Liu, Taosong Fang, et al.]
venue: MLSys
year: 2026
tags: [llm-inference, batch-inference, prefix-sharing, kv-cache, throughput-optimization]
source_pdf: "[[a97da629b098b75c294dffdc3e463904.pdf]]"
source_md: "[[a97da629b098b75c294dffdc3e463904]]"
---

# BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching (MLSys 2026)

> **一句话总结**：微软提出面向大批量 offline LLM 推理（如 search snippet 生成）的优化系统，用全局前缀树 + DP 最大化一级前缀复用 + 内存中心 token batching + 水平融合 attention，比 [[vLLM]] / [[SGLang]] 快 1.3×–10.8×。

## 问题

信息处理类 LLM 任务（搜索引擎 snippet、广告、推荐）常以大 batch 或 offline 方式跑，指标是吞吐，且 prompt 间大量共享前缀（如同一网页文档）。现有推理引擎偏 streaming online，有三处短板：

1. **LRU-based implicit prefix cache**：全局大 batch 角度看会把快要复用的 [[KV-Cache]] 过早逐出。实测 vLLM 只达到 35.8% token saving，而理论上限 58.1%。
2. **Streaming 调度 + token batching 不适合**：按到达顺序调度，无法把 decode 比例高的请求提前与后续 prefill chunk 混合；token batch 只看 token 数/请求数阈值，decode-dominated 迭代出现"valleys"利用率低。
3. **前缀共享 Attention kernel** 里不同 KV chunk 在独立 kernel 执行，tail effect + launch overhead 大。

## 核心方法

核心 insight：**大 batch 的 prefill 特征是已知的**，可以全局 ahead-of-time 分析。

1. **Explicit Global KV Reuse Identification**：用 compact prefix tree（[[RadixAttention]] 类 radix tree）显式识别全局共享前缀。设计 DP 算法 `MaximizeReuse` 把多级前缀压缩成单级（savings ratio ~56%→~55% 仅损 1%），大幅简化 token batching 与 attention kernel。
2. **Prefix-Sharing Group Scheduling**：把共享同一前缀的请求打包成 group 一起调度，前缀 KV 生命周期缩到 group 完成即释放。
3. **Request Reordering + Memory-Centric Token Batching**：按 `decode_length / prompt_length` 比例降序排（decode 比例高的先跑），让后到的长 prefill chunk 与 decode 混合；batching 阈值从「token/request 数」改为 KV memory 使用率，消除 iteration token 数的 valley。
4. **Horizontal Fused Prefix-Shared Attention**：把不同 KV chunk 上的 partial attention + online softmax 合进同一 kernel，减 tail 和 launch 开销。

基于 vLLM v0.6.4 实现。

## 关键结果

- End-to-end：在微基准 + 一个 industry 生产 workload 上，NVIDIA 和 AMD GPU 下比 vLLM / SGLang 快 **1.3×–10.8×**。
- DP 前缀扩大算法将 token saving ratio 从 ~56%（多级）降到 ~55%（单级）仅损 1%，但大幅简化实现。
- DP 算法本身开销 < 0.01%。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、[[Flash-Attention]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]