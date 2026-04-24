---
type: entity
kind: system
aliases: [vLLM]
status: active
last_updated: 2026-04-24
tags: [llm-inference, serving]
---

# vLLM

> UC Berkeley 提出的高吞吐 LLM serving 框架，PagedAttention 的起源，是当前 open-source LLM inference 事实标准之一。

## 是什么

vLLM 由 UC Berkeley Sky Lab（Kwon, Stoica 等）于 2023 年 SOSP 提出。核心 contribution 是 [[PagedAttention]]——把 KV cache 当 OS 虚存分页管理，消除内外部碎片，让单 GPU 吞吐相比 FasterTransformer 提升 2-4×。

vLLM 之后快速演化为社区生态：支持 continuous batching、tensor parallelism、speculative decoding、prefix caching、FP8、LoRA、guided decoding 等几乎所有主流 LLM serving feature。它也是大量后续 system 工作的 baseline 或集成目标。

## 演进时间线

- **2023 SOSP**：原始论文（Kwon et al.），引入 [[PagedAttention]] 和 [[Continuous-Batching]] 联合调度
- **2024**：FP8 / MQA / GQA 支持；PagedAttention V2；prefix sharing
- **2025**：disaggregated inference 集成；speculative decoding；多种推理优化
- **2026**：作为 baseline 出现在大量论文里：[[TransferEngine-arXiv25|pplx-garden TransferEngine]] 提到 vLLM 是 P2P 通信集成对象之一

## 相关概念

- [[PagedAttention]]（vLLM 引入的核心机制）
- [[KV-Cache]]
- [[Continuous-Batching]]
- [[Prefix-Caching]]
- [[Speculative-Decoding]]

## 对比

- [[vLLM-vs-SGLang]]（按需创建）

## 相关论文

- *vLLM 原始论文*（SOSP 2023, Kwon et al.）— 待生成 paper wiki 页：`[[vLLM-SOSP23]]`
- [[TransferEngine-arXiv25|TransferEngine (Perplexity, arXiv 2025)]] — 把 P2P RDMA 集成进 vLLM 等推理框架
- [[FluxMoE-arXiv26|FluxMoE]] — 基于 vLLM v0.10.2，用 PagedTensor 把 MoE expert 转为 streaming resource（仅 20 LoC 侵入），Qwen3-Next-80B 上 3.0× 吞吐

## 开放问题

- vLLM 在 disaggregated inference 场景下的 KV transfer 仍是显式协调，缺乏 cross-vendor RDMA 抽象（[[TransferEngine-arXiv25|pplx-garden]] 是一个补充）
- MoE-aware 的 vLLM 调度仍在演进（[[Libra-arXiv26|Libra]] 在 [[SGLang]] 上做了，vLLM 路径尚未跟进）
