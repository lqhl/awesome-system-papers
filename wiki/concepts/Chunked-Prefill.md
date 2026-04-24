---
type: concept
aliases: [chunked prefill, Chunked Prefill, chunked-prefill, prefill chunking, split prefill, piggyback prefill]
parent: "[[Continuous-Batching]]"
introduced_by: "[[SARATHI-arXiv23]]"
last_updated: 2026-04-24
tags: [llm-inference, scheduling, batching]
---

# Chunked-Prefill

> [[Continuous-Batching]] 的一个具体调度技术：把长 prompt 的 prefill 切成固定 token 数的小 chunk（如 512 token/chunk），每个 iteration 算一个 chunk，同 iteration 里"捎带"（piggyback）一批 decode 请求，让 prefill 与 decode 在同一个 kernel call 里混跑。目的是同时治住两个 SLO——TTFT（首 token 延迟）被 naïve prefill 一步算完时挤爆，TBT（token-to-token）被长 prefill 抢走后严重抖动。SARATHI (2023) 提出，Sarathi-Serve (OSDI 24) 落地，后续 vLLM、SGLang 都已默认开启。

## 问题背景

朴素 continuous batching 有两种失败模式：

1. **纯分阶段调度**：prefill 独占一个 iteration → decode 请求在这 iteration 内完全 stall，TBT 抖动
2. **允许 prefill + decode 混跑**：一个长 prompt 的 prefill kernel call 可能跑几百毫秒，decode 全部 block，同样抖

根因：prefill 的计算量 ∝ prompt_len²（attention）+ prompt_len（FFN），而 decode 每步只加 1 个 token。两类请求的单 iteration 耗时差距可达 1000×。

## Chunked prefill 的思路

**把 prefill 切成固定算力预算的 chunk**：每 chunk 算 `chunk_size` 个 token 的 prefill（如 512）。每 iteration 的工作预算固定：

```
iteration i:
  执行 1 个 prefill chunk (<= chunk_size tokens)   ← 可能是某个长 prompt 的第 k 块
  + 搭载 B 个 decode 请求（各 1 步）               ← 填满剩余算力
```

- chunk_size 控制 TTFT 与 TBT 之间的 trade-off：小 chunk → TBT 稳但 TTFT 长；大 chunk → TTFT 好但 TBT 抖
- prefill chunk 之间通过 [[KV-Cache]] 续算，不用从头重算；FA 的 variable-length 支持天然兼容
- 实际工程里 chunk_size 常动态调整：队列压力大时减小，保 decode；队列闲时增大，保 TTFT

## 效果

Sarathi-Serve 报 Llama-2 13B 上：
- TBT P99 降低 ~2×
- TTFT 持平或略降
- 整体吞吐提高 ~1.3-2×（prefill/decode 混跑填满算力）

## 与其他方案的关系

- **vs [[Disaggregation]]**：chunked prefill 是"软方案"——同一组 GPU 上调度；disaggregation 是"硬方案"——物理拆两组 GPU，二者互为替代，大规模 serving 往往 disagg，中等规模 chunked prefill 够用
- **vs priority scheduling**：chunked prefill 降低 prefill block 的时长，priority 决定谁先执行，互补
- **vs speculative decoding**：speculative 是 decode-side 加速，与 prefill 路径无关

## 引用本概念的论文

- [[LayeredPrefill-MLSys26|LayeredPrefill]]、[[LAPS-MLSys26|LAPS]]、[[BatchLLM-MLSys26|BatchLLM]]、[[MixLLM-MLSys26|MixLLM]]、[[Stream2LLM-MLSys26|Stream2LLM]]、[[SuperInfer-MLSys26|SuperInfer]] — 进阶 prefill 调度
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]、[[SparseSpec-MLSys26|SparseSpec]]、[[SpecDecodeBench-MLSys26|SpecDecodeBench]]、[[SpanQueries-MLSys26|SpanQueries]] — 对照 disagg / 结合 spec decoding

## 相关概念

- 上游：[[Continuous-Batching]]、[[LLM-Inference]]
- 替代：[[Disaggregation]]
- 互补：[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]
- 实现：[[vLLM]]、[[SGLang]]
