---
type: entity
kind: system
aliases: [vLLM]
status: active
last_updated: 2026-07-30
tags: [llm-inference, serving, paged-attention]
---

# vLLM

> vLLM 是以 [[PagedAttention]] 为核心的开源 LLM serving engine；它既是主流部署栈，也是新调度、KV 管理与 kernel 论文最常用的强基线和集成宿主。

## 是什么

vLLM 将 [[KV-Cache]] 切成固定 block，以 block table 映射逻辑 token 与物理 HBM，避免按最大 sequence length 连续预分配，并支持 copy-on-write prefix sharing。continuous batching 在请求到达、prefill 和 decode 之间动态组织 batch。

它的边界是通用在线 generation runtime，而不是单一 kernel library。后续论文在其上替换 scheduler、offload、speculative decoding、MoE 或 disaggregation；比较时必须区分 upstream version、配置和论文 patch。

## 关键观察 / 隐含假设

- **观察：PagedAttention 解决容量碎片，却产生 transfer layout 债务。** [[Strata-OSDI26]] 通过 GPU-assisted I/O 重排层级 KV，[[SuperInfer-MLSys26]] 指出共享 block table 使双向 swap 难并发。
- **观察：vLLM 已成为“优化后基线”。** [[EcoServe-OSDI26]]、[[MPK-OSDI26]]、[[LMetric-OSDI26]] 均相对完整 serving stack 报告 SLO/吞吐，而非只比 PyTorch。
- **观察：scheduler 需要联合 locality 与 load。** [[LMetric-OSDI26]] 以新增 prefill token × batch size 避免人工调权。
- **假设：block-granularity 是通用折中。** token-level sparsity 和大块 I/O 分别会挑战这一粒度，见 [[OPKV-MLSys26]]、[[Strata-OSDI26]]。

## 演进时间线

- 2023 SOSP：[[vLLM-SOSP23]] — 提出 PagedAttention 与 memory-efficient continuous batching。
- 2025：[[BlitzScale-OSDI25]]、[[DiffKV-SOSP25]] — 将 vLLM 推向弹性 serving 与差异化 KV 管理。
- 2026 OSDI：[[EcoServe-OSDI26]] — 在普通 Ethernet 上以 PaDG 改善 vLLM goodput。
- 2026 OSDI：[[LMetric-OSDI26]] — 为 vLLM request routing 引入 locality/load 统一 metric。
- 2026 OSDI：[[MPK-OSDI26]] — 以 persistent mega-kernel 改善 vLLM/SGLang 执行。
- 2026 OSDI：[[Strata-OSDI26]] — 在 SGLang 集成层级 cache，并以 vLLM-LMCache 为强对照。

## 相关概念

- [[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Prefix-Caching]]、[[Disaggregation]]

## 相关论文

- [[vLLM-SOSP23]] — 原始系统论文。
- [[EcoServe-OSDI26]] — phase-disaggregated serving baseline/宿主。
- [[LMetric-OSDI26]] — production request routing 改进。
- [[Prism-OSDI26]] — 统一 weights/KV memory sharing，面向 vLLM 类 engine。
- [[Strata-OSDI26]] — 揭示分页 layout 在层级 I/O 上的代价。
