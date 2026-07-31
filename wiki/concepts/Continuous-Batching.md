---
type: concept
aliases: [continuous batching, Continuous Batching, iteration-level scheduling, in-flight batching, dynamic batching, Orca-style batching]
parent: "[[LLM-Inference]]"
introduced_by: Orca (OSDI 2022)
last_updated: 2026-07-30
tags: [llm-inference, scheduling, batching]
---

# Continuous-Batching

> 连续批处理（continuous batching）在每个 decode iteration 重新组织 active requests，让完成者退出、新请求加入，以避免静态 batch 被最长输出拖住。

## 核心思想

LLM output length 高度变化。request-level batch 必须等全部请求结束；iteration-level scheduler 每 token step 更新 running set，并结合 paged KV 管理不同长度 state。现代实现还把 prefill 切 chunks、处理 priority、speculation 和 distributed workers。

batch 越大通常 GPU throughput 越高，但 queueing、TPOT、KV capacity 与 interference 也增加。scheduler 的目标应是 SLO-constrained goodput，而非总是填满 GPU。

## 为什么重要

continuous batching 是 vLLM/SGLang 等 serving runtime 的基本调度抽象，也是其他优化的承载层。quantized/sparse kernel、speculative verification、P/D disaggregation 和 prefix cache 都会改变一次 iteration 的 shape/cost，静态 cost model 很快失准。

## 关键观察 / 隐含假设

- **prefill/decode 异构会破坏统一 batch**：[[EcoServe-OSDI26]] 用 phase switching 与 TPOT slack 减少 interference；[[DynamicPPServing-OSDI26]] 在 PP 中动态调整 chunk。
- **kernel 最优点随 M/batch 变化**：[[ADAngel-OSDI26]] 说明 arbitrary-precision mpGEMM 在小 decode batch、短/长 prefill 间需切换 Bitwise/Split/Padding。
- **operator-level scheduling仍过粗**：[[MPK-OSDI26]] 将 active tensor fragments 下沉为 SM tasks，以 persistent mega-kernel 消除 host launch；其评估仍需 production arrivals/p99。
- **KV state 是 admission 的硬约束**：[[vLLM-SOSP23]] 用 paged allocation支持动态 batch，[[KVCacheInTheWild-ATC25]] 表明真实 cache reuse/residency 应进入 routing。
- **speculation 使 request progress 不再一 token 同步**：[[Seer-OSDI26]] 的 grouped SD 需要按 acceptance/draft length 自适应调度。

## 设计空间与取舍

- **iteration-level decode**：简单通用，频繁 scheduler/launch overhead。
- **chunked prefill**：保护 decode TPOT，可能拉长单请求 TTFT。
- **priority/deadline aware**：提高 SLO attainment，可能降低 aggregate throughput 或公平性。
- **persistent/mega-kernel batching**：减少 launch、细化 dependency，specialization/debug 成本高。
- **distributed batching**：跨 workers 提高规模，KV migration 与 stale load information 增加。

## 引用本概念的论文

- [[vLLM-SOSP23]] — 将 paged KV 与 iteration-level scheduling 结合为主流实现。
- [[ADAngel-OSDI26]] — 展示 dynamic batch/shape 对量化 kernel selection 的影响。
- [[MPK-OSDI26]] — 将 batching 与 tensor dependency 下沉到 GPU SM-level runtime。
- [[EcoServe-OSDI26]] — 用 phase/slack orchestration处理 prefill-decode interference。
- [[SGLang-NeurIPS24]] — 将 continuous batching 与 structured generation/cache runtime 结合。
- [[NanoFlow-OSDI25]] — 在 serving pipeline 内跨算子重叠和调度请求流。

## 已知局限 / 开放问题

- 在 burst、priority、cancellation 和 heterogeneous length 下保证 p99 与公平性。
- 联合 admission、KV allocation、prefill chunks、speculation 与 parallel topology。
- 建立随 model/kernel/hardware drift 在线校准的 iteration cost model。
- 报告 scheduler CPU、launch、energy 与 low-load latency，而不只 peak throughput。
