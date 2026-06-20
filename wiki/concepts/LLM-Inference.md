---
type: concept
aliases: [LLM inference, LLM serving, llm-inference, large language model inference, model serving]
parent: "[[LLM]]"
last_updated: 2026-06-20
tags: [llm-inference, serving, systems]
---

# LLM-Inference

> 把 [[LLM]] 从离线模型变成在线服务的系统层：请求进入后要经历 prefill、decode、调度、缓存、并行、传输与 SLO 管理。它不是单一 kernel 优化，而是 [[KV-Cache]]、[[Continuous-Batching]]、[[PagedAttention]]、[[Disaggregation]]、[[Speculative-Decoding]]、[[Tensor-Parallelism]] 等机制的交汇点。

## 为什么重要

LLM inference 的核心矛盾是 **每个请求状态大、阶段异构、尾延迟敏感**。Prefill 更像大矩阵吞吐任务，decode 更像小 batch、逐 token、内存带宽敏感任务；长 context 又把 KV cache 变成主导内存对象。生产系统因此不能只优化 FLOPs，而要同时管理 queueing、cache hit、batch shape、GPU/host/网络带宽与多租户隔离。

这个概念页用于承接论文中频繁出现的「LLM serving / inference」共同语境；具体机制仍回到更窄的概念页：

- [[KV-Cache]] / [[PagedAttention]]：请求状态与显存管理
- [[Continuous-Batching]] / [[Chunked-Prefill]]：在线调度与 TTFT/TBT 取舍
- [[Disaggregation]] / [[RDMA]]：prefill-decode 分离与 KV 传输
- [[Speculative-Decoding]] / [[Sparse-Attention]] / [[Quantization]]：模型无损或近似加速
- [[Tensor-Parallelism]] / [[Pipeline-Parallelism]] / [[Expert-Parallelism]]：多 GPU / MoE 并行

## 典型边界

- **单机 benchmark 不等于生产 serving**：小 batch kernel speedup 可能被排队、cache miss、调度器开销或多租户隔离吃掉。
- **平均吞吐不等于 SLO**：TTFT、TBT、P95/P99 与 preemption 行为经常比 tokens/s 更能解释用户体验。
- **cache hit 不是免费收益**：prefix reuse、remote KV load、compression/offload 都要和 recompute 成本、隐私隔离、失效语义一起算。
- **模型演进会改变瓶颈但不消除系统问题**：GQA/MLA、MoE、reasoning long CoT、agent workflow 会重排 KV、expert、调度与网络的相对压力。

## 相关

- **核心系统**：[[vLLM]]、[[SGLang]]、[[TensorRT-LLM]]、[[Mooncake]]
- **相关概念**：[[LLM]]、[[KV-Cache]]、[[Continuous-Batching]]、[[Disaggregation]]、[[Speculative-Decoding]]、[[Prefix-Caching]]
