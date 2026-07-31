---
type: concept
aliases: [KV cache, KV Cache, kv-cache, KV-cache, key-value cache, KvCache]
parent: "[[Attention]]"
last_updated: 2026-07-30
tags: [memory, attention, llm-inference]
---

# KV-Cache

> KV cache 缓存 Transformer 每层历史 token 的 key/value，使自回归 decode 避免重复计算；它也是长上下文 LLM serving 的主导内存、带宽与迁移对象。

## 核心思想

prefill 生成 prompt 的 K/V，decode 每步追加新 token 并读取历史。容量与 batch、sequence length、layer/head dimension 和 precision 成正比。[[PagedAttention]] 用 fixed-size block 与 block table 消除连续预分配碎片，并支持 copy-on-write prefix sharing；代价是碎片化物理布局和更复杂 kernel/I/O。

KV management 已从 GPU allocator 扩展为 GPU/CPU/SSD/network 层级问题：cache admission、prefix reuse、compression/sparsity、prefill-decode transfer 与 weight competition 必须联合调度。

## 为什么重要

OSDI 2026 形成三条新路线。[[DirectKV-OSDI26]] 在 GH200/GB200 上让 attention 直接读 CPU-resident KV，省去 staging；[[ECHO-OSDI26]] 为 sparse attention 动态 offload，并 lossless prefetch 被选中的 KV；[[Strata-OSDI26]] 解耦 host/GPU layout，以大 I/O 和 ready-time-aware scheduler 在 SGLang 中把吞吐最高提升 5×。

[[Prism-OSDI26]] 把 weights 与 KV 视为同一 elastic balloon，[[LMetric-OSDI26]] 则用“新增 prefill token × 当前 batch”同时近似 locality 与 load，说明 KV 已成为 memory control plane 与 request scheduler 的共同状态。

## 关键观察 / 隐含假设

- **观察：cache hit 不等于及时可用。** [[Strata-OSDI26]] 的基线可让 prefill 74% 时间等待 KV transfer。
- **观察：物理 layout 决定 offload 是否能吃满链路。** [[DirectKV-OSDI26]]、[[SuperInfer-MLSys26]] 均指出碎片化小段和 staging 的损失。
- **观察：KV 与 weights 共享 HBM，不能分别管理。** [[Prism-OSDI26]]、[[FluxMoE-arXiv26]] 通过弹性回收/paging 处理竞争。
- **假设：prefix 或 attention selection 有复用/可预测性。** [[ECHO-OSDI26]]、[[SGLang-NeurIPS24]] 的收益依赖该性质。

## 设计空间与取舍

- **Paged / contiguous layout**：分页提高利用率与共享，连续布局提高 transfer/kernel locality。
- **GPU / CPU / SSD / remote tier**：容量逐级增大，latency 与 failure domain 也扩大。
- **Exact / compressed / sparse**：exact 保质量但占容量；压缩/稀疏需证明 accuracy 与召回。
- **Request-local / prefix-shared**：共享提高 hit rate，却引入 eviction、ownership 与 fairness。

## 引用本概念的论文

- [[vLLM-SOSP23]] — PagedAttention 与 block-level KV management。
- [[DirectKV-OSDI26]] — CPU-resident KV direct attention。
- [[ECHO-OSDI26]] — sparse attention 的动态 offload/prefetch。
- [[Strata-OSDI26]] — GPU/CPU/SSD hierarchical context cache。
- [[Prism-OSDI26]] — weights/KV 统一弹性共享。
- [[LMetric-OSDI26]] — locality/load 无参数路由指标。

## 已知局限 / 开放问题

- 需要统一 paged compute layout 与 storage/network transfer layout，而不复制多份 state。
- 多租户 KV security、fair eviction、failure recovery 与跨模型共享仍缺生产级语义。
- sparse/compressed KV 的 quality guarantee 和 SLO 应在同一评测中报告。
