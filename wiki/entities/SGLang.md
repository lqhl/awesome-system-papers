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
- **2025**：被多个 MoE 工作选为底层框架（如 [[Libra-arXiv26|Libra]] 实现于 SGLang v0.4.10、[[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 用 SGLang v0.4.7 评估 EPLB）

## 相关概念

- [[RadixAttention]]
- [[KV-Cache]]
- [[Prefix-Caching]]
- [[MoE]]
- [[Continuous-Batching]]

## 对比

- [[vLLM-vs-SGLang]]（按需创建）

## 相关论文

- *SGLang 原始论文*（待生成 paper wiki 页）
- [[Libra-arXiv26|Libra]] — Libra 实现于 SGLang v0.4.10
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — 用 SGLang v0.4.7 评估 EPLB / heuristic
