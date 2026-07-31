---
type: entity
kind: system
aliases: [SGLang]
status: active
last_updated: 2026-07-30
tags: [llm-inference, serving, scheduling]
---

# SGLang

> SGLang 是面向结构化 LM program 的 serving system，以 [[RadixAttention]]、cache-aware scheduling 与高性能 runtime 为核心，也是 agent、MoE、speculative decoding 和长上下文研究的常用集成平台。

## 是什么

SGLang frontend 暴露 `gen`、fork/join、select 与约束生成等程序结构；backend SRT 用 radix tree 映射 token prefix 到 [[KV-Cache]]，在跨请求、跨调用共享 prefix，并与 paged memory、CUDA graph 和 optimized kernel 组合。

与仅按独立 completion 调度相比，它更适合 few-shot、agent、RAG 和 benchmark 等 prefix 结构明确的 workload。低复用、长输出或 cache pressure 很高时，RadixAttention 收益会下降，scheduler 还需在 hit、batch 与 fairness 间取舍。

## 关键观察 / 隐含假设

- **观察：prefix locality 是可调度资源。** [[SGLang-NeurIPS24]] 的 cache-aware ordering 提高复用，但可能产生 starvation。
- **观察：SGLang 已成为 production-grade research substrate。** [[Strata-OSDI26]] 直接集成生产 SGLang，吞吐相对 TensorRT-LLM 最高提升 3.75×。
- **观察：framework abstraction 会限制 data movement。** [[SuperInfer-MLSys26]] 指出与 vLLM 共享的 paged block-table swap 路径难以双向并发。
- **假设：LM program/prefix structure 可提前或在线识别。** adversarial/low-reuse request 会使 radix metadata 只留下开销。

## 演进时间线

- 2024 NeurIPS：[[SGLang-NeurIPS24]] — 提出 RadixAttention、structured frontend 与 compressed FSM。
- 2025–2026：[[Libra-ICLR26]]、[[CRAFT-MLSys26]] — 成为 MoE load-balancing/replication 实验平台。
- 2026 MLSys：[[PRISM-MLSys26]]、[[ReSpec-MLSys26]] — 集成 speculative decoding 与 RL rollout。
- 2026 OSDI：[[DynamicPPServing-OSDI26]]、[[ECHO-OSDI26]] — 作为 PP serving 与 sparse-attention offload 基线。
- 2026 OSDI：[[Strata-OSDI26]] — 加入 GPU/CPU/SSD hierarchical context caching。

## 相关概念

- [[KV-Cache]]、[[RadixAttention]]、[[Prefix-Caching]]、[[Continuous-Batching]]、[[MoE]]

## 相关论文

- [[SGLang-NeurIPS24]] — 原始系统论文。
- [[Strata-OSDI26]] — production integration 的层级 KV cache。
- [[ECHO-OSDI26]] — SGLang 上的 sparse attention KV offload 对照。
- [[DynamicPPServing-OSDI26]] — PCIe GPU pipeline serving。
- [[DriftBench-MLSys26]] — SGLang/vLLM 迁移的 output drift。
