---
type: paper
name: BatchGen
full_title: "BatchGen: An Architecture for Scalable and Efficient Batch Inference"
authors: [Tairan Xu, Leyang Xue, Zhan Lu, Jinfu Deng, Hongyang Xiao, et al.]
venue: OSDI
year: 2026
tags: [llm-inference, batch-inference, coroutine, mixture-of-experts, scheduling]
source_pdf: "[[osdi26-xu-tairan.pdf]]"
source_md: "[[osdi26-xu-tairan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 可扩展高效批推理架构（OSDI 2026）

> **原题**：BatchGen: An Architecture for Scalable and Efficient Batch Inference

> **一句话总结**：BatchGen把sequence表示为可在module boundary暂停、合并与迁移的event-driven coroutine，摆脱interactive serving的固定GPU/atomic forward；128 GPUs上batch completion最多快2.3×，memory-constrained accelerator相对offload baseline最高9.6×。

## 问题与动机

batch inference关注整批completion/throughput而非单request latency；[[MoE|MoE]] per-expert batch太小，reasoning output heavy-tail让固定placement出现straggler与idle GPU。

## 关键观察 / 隐含假设

- neural module boundary是自然yield point，sequence state/KV可迁移。
- 跨sequence重组可放大expert batches并把long-tail工作迁走。
- batch任务容忍单sequence latency变化。

## 核心方法

sequence coroutine暴露pause/resume/combine/partition/migrate primitives；cluster runtime按expert readiness、device load和memory动态编排events，重组expert batches并redistribute stragglers；state manager支持成本较低的KV迁移/offload。

## 实验与结果

- **设置**：8–128 H20/H200 GPUs、DeepSeek等batch workloads，对比SGLang-Optimized/offloading baseline，以BCT和throughput为指标（§6）。
- 128 GPU BCT最高改善2.3×；memory constrained最高9.6×。
- 16×H20/8×H200多配置相对SGLang 1.25×–1.66×。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| coroutine model改善batch completion | §6、表 4 | batch非interactive | 强 |
| 支持弱/小显存GPU | constrained实验 | 所测offload | 强 |

## 批判性分析

### 论证链条

抽象直接针对batch与interactive objective错配，scale/弱GPU结果都支持动态重组。

### 假设压力测试

frequent KV migration、跨节点网络或短sequence会使coroutine scheduling overhead占优。

### 实验可信度

规模达128 GPUs且baseline强；quality、failure和production cost仍需长期验证。

## 局限与后续工作

- fault recovery、multi-tenant fairness与energy/cost。
- 联合RL rollout producer/consumer scheduling。

## 相关

- **相关概念**：[[Batch-Inference]]、[[Coroutine]]、[[Mixture-of-Experts]]、[[Straggler]]
- **相关系统**：[[SGLang]]、[[vLLM]]
- **同会议**：[[OSDI-2026]]
