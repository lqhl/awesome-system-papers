---
type: concept
aliases: [LLM inference, LLM serving, llm-inference, large language model inference, model serving]
parent: "[[LLM]]"
last_updated: 2026-07-30
tags: [llm-inference, serving, systems]
---

# LLM-Inference

> 大语言模型推理（LLM inference）把离线模型变成具有 TTFT、TPOT、吞吐、成本与可靠性目标的在线服务，核心是协调 prefill、decode、KV state、batch、parallelism 和数据移动。

## 核心思想

每个请求先用 prompt 做 compute-heavy prefill 并生成 KV cache，再进行逐 token、memory-bandwidth-heavy decode。scheduler 必须决定 admission、batch composition、prefill chunk、KV placement、parallel topology、speculation 和 output streaming。

LLM serving 不是单一 kernel：[[Continuous-Batching]] 管理动态请求集合，[[Disaggregation]] 分离阶段，[[Quantization]] 与 [[Sparse-Attention]] 减少计算/状态，[[Speculative-Decoding]] 减少串行 steps，tracing/diagnosis 则闭合生产反馈。

## 为什么重要

模型/上下文持续增长后，瓶颈在 HBM capacity、weight/KV bandwidth、network 和 queueing 间移动。只报告 tokens/s 会掩盖 TTFT/TPOT tail、SLO attainment、quality、replication cost 与 multi-tenant fairness；真实系统必须给出 workload distribution 和成本边界。

## 关键观察 / 隐含假设

- **prefill 与 decode 特性不同但 full disaggregation 不是总优**：[[EcoServe-OSDI26]] 发现 commodity network 上 KV transfer/load balance 可压倒计算，用 data-reduced cross-instance orchestration 在 NoDG/FuDG 之间折中。
- **生产瓶颈需要端到端 tracing**：[[StriaTrace-OSDI26]] 面向 online inference 收集细粒度 trace/diagnosis；开放问题是 concept drift、未知 root cause 与自动 mitigation 的误诊风险。
- **编译优化必须考虑动态 graph 与 framework**：[[GraCE-OSDI26]] 扩大 CUDA Graph coverage，[[MPK-OSDI26]] 做 SM-level mega-kernel specialization；两者都依赖 shape/configuration 稳定并需摊销 compile cost。
- **边缘/本地推理的瓶颈不同**：[[ADAngel-OSDI26]]、[[KAIROX-OSDI26]]、[[Sereno-OSDI26]] 分别处理 arbitrary precision、CPU–GPU migration 与 foreground memory-bandwidth interference。
- **真实 KV 行为决定系统设计**：[[KVCacheInTheWild-ATC25]]、[[DiffKV-SOSP25]]、[[PrefillOnly-SOSP25]] 表明 cache reuse、precision 和 workload specialization 不可由平均 context length替代。

## 设计空间与取舍

- **collocated serving**：无 KV network transfer，prefill/decode interference 高。
- **P/D disaggregation**：资源独立伸缩，增加 cache transport、scheduler 与 failure state。
- **continuous/chunked batching**：提升 occupancy，需在 TTFT、TPOT 与公平性间取舍。
- **compression/sparsity/speculation**：减少 bandwidth/steps，增加 quality、acceptance 或 kernel constraints。
- **compiler/persistent kernel**：降低 launch/data movement，specialization、debug 与 portability 成本更高。

## 引用本概念的论文

- [[EcoServe-OSDI26]] — 在 commodity GPU cluster 上比较 NoDG/FuDG 与 data-reduced orchestration。
- [[StriaTrace-OSDI26]] — 为 production LLM inference 提供 tracing 与 root-cause diagnosis。
- [[GraCE-OSDI26]] — 用 compiler support 自动扩大 CUDA Graph capture。
- [[ADAngel-OSDI26]] — 为 edge APQ LLM 自适应选择 mpGEMM kernel。
- [[KAIROX-OSDI26]] — 动态平衡 GPU/CPU neuron execution。
- [[Aegaeon-SOSP25]]、[[LithOS-SOSP25]]、[[HeteroInfer-SOSP25]] — 从 isolation、runtime 和异构硬件扩展 serving 设计空间。

## 已知局限 / 开放问题

- 统一以 p99 TTFT/TPOT、goodput、quality、energy 和 GPU-dollar 比较系统。
- 在 burst、cancellation、failure、扩缩容和 multi-tenancy 下维护 request/KV/output ownership。
- 自动识别 workload/hardware regime，在 collocation、disaggregation 与 hybrid 间切换。
- 构建可共享的 production trace 与 root-cause corpus，同时保护用户隐私。
