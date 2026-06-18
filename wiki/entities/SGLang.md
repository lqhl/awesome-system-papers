---
type: entity
kind: system
aliases: [SGLang]
status: active
last_updated: 2026-04-24
tags: [llm-inference, serving, scheduling]
---

# SGLang

> 主流 LLM serving 框架之一，以 RadixAttention（基于 radix tree 的 prefix sharing）和结构化生成 DSL 为标志，在 MoE / 长 prompt / agent 场景常被作为 vLLM 的替代或对照。

## 是什么

SGLang 由 LMSYS 团队开发（Zheng et al.，最初发表于 NeurIPS 2024 / OSDI 2025）。核心设计：

- **RadixAttention**：用 radix tree 表达 prefix tree，KV cache 自然按公共前缀复用
- **Structured generation DSL**：把多步生成（branching、parallelism、constrained decoding）抽象成 Python embedded DSL
- **Front-end + back-end 解耦**：编译复杂程序到 schedulable 的 backend 操作

## 演进时间线

- **2024 NeurIPS**：SGLang 原始论文
- **2025**：被多个 MoE 工作选为底层框架（如 [[Libra-ICLR26|Libra]] 实现于 SGLang v0.4.10、[[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 用 SGLang v0.4.7 评估 EPLB）
- **2026 MLSys**：[[GhostServe-MLSys26|GhostServe]] 以 SGLang 0.5.1 为后端实现 erasure-coded KV checkpointing；[[ContextPilot-MLSys26|ContextPilot]] 与 [[DriftBench-MLSys26|DriftBench]] 列为可集成 serving 框架；[[PRISM-MLSys26|PRISM]] 在 SGLang 完整集成 drafter；[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 实现 MoE 推理 EP 重叠；[[RaidServe-MLSys26|RaidServe]] 作为兼容 serving 栈；[[DynaFlow-MLSys26|DynaFlow]] NanoFlow 集成最高 1.19× 且避免 naive split 的 0.35× 退化；[[Matrix-MLSys26|Matrix]] 合成数据后端之一

## 相关概念

- [[RadixAttention]]
- [[KV-Cache]]
- [[Prefix-Caching]]
- [[MoE]]
- [[Continuous-Batching]]

## 对比

- [[vLLM-vs-SGLang]]（按需创建）

## 相关论文

- *SGLang 原始论文* — [[SGLang-NeurIPS24]]
- [[Libra-ICLR26|Libra]] — Libra 实现于 SGLang v0.4.10
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — 用 SGLang v0.4.7 评估 EPLB / heuristic
- [[CRAFT-MLSys26|CRAFT]] — 在 SGLang v0.4.8 上集成，替代 EPLB 做 per-layer expert replication，goodput 平均 1.14×
- [[EventTensor-MLSys26|EventTensor]] — ETC megakernel 对比 SGLang v0.5 baseline，Qwen3-30B-A3B batch=1 decode 快 1.20×
- [[GhostServe-MLSys26|GhostServe]] — fault-tolerant serving 插件，chunk 级 KV parity checkpoint
- [[ContextPilot-MLSys26|ContextPilot]] — context index 与 prefix-cache 协同的 long-context prefill 加速
- [[DriftBench-MLSys26|DriftBench]] — 105 配置 drift 测量中的 serving 框架维度
- [[OSWorld-Human-MLSys26|OSWorld-Human]] — Agent S2 grounding 模型用 SGLang serving
- [[PRISM-MLSys26|PRISM]] — speculative drafter 在 SGLang 上 system-level 验证，>2.6× 吞吐
- [[TriInfer-MLSys26|TriInfer]] — MLLM goodput 对比 baseline，最高 2.4×
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — MoE 分布式推理 EP 通信重叠实现
- [[WAVE-MLSys26|WAVE]] — LLM attention/GEMM/MoE kernel DSL，同类推理栈底层算子
- [[AgenticCache-MLSys26|AgenticCache]] — embodied agent 规划缓存，与 [[SGLang]]/[[vLLM]] serving 效率技术互补
- [[SHIP-MLSys26|SHIP]] — Groq SRAM pipeline serving 对比对象，Qwen3-235B 端到端吞吐与 TPOT 更稳
- [[ReSpec-MLSys26|ReSpec]] — VeRL+SGLang RL 生成阶段集成 adaptive speculative decoding
- [[TokenWeave-MLSys26|TokenWeave]] — 与 SGLang 同为未默认开启 TP compute-communication overlap 的 serving 栈对照
- [[LAPS-MLSys26|LAPS]] — 在 SGLang PD-disaggregation 上再做 prefill 内长短分离，prefill 延迟 -30%
- [[FlashAgents-MLSys26|FlashAgents]] — 扩展 SGLang 实现 inter-agent streaming prefill + intra-turn prefix cache，workflow 延迟最高 -40%
- [[Behdin-SemanticJobSearch-MLSys26|Behdin-SemanticJobSearch]] — LinkedIn 语义搜索 cross-encoder 在 SGLang 上做 prefill-only 高 RPS 优化，2000 items/s/GPU
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — ShareGPT 流量采集 kernel trace + `apply()` 动态替换算子实现
