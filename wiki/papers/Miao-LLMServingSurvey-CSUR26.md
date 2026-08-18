---
type: paper
name: Miao-LLMServingSurvey
full_title: "Towards Efficient Generative Large Language Model Serving: A Survey from Algorithms to Systems"
authors: [Xupeng Miao, Gabriele Oliaro, Zhihao Zhang, Xinhao Cheng, Hongyi Jin, Tianqi Chen, Zhihao Jia]
venue: CSUR
year: 2026
tags: [survey, llm-serving, inference, systems, algorithms, area/ai-infra]
source_pdf: "[[csur26-miao-llm-serving-survey.pdf]]"
source_md: "[[csur26-miao-llm-serving-survey]]"
review_status: complete
evidence_level: full-text
empirical_evidence: none
last_reviewed: 2026-08-18
---

# 高效生成式 LLM Serving：从算法到系统的综述（CSUR 2026）

> **原题**：Towards Efficient Generative Large Language Model Serving: A Survey from Algorithms to Systems

> **一句话总结**：该综述以 prefill/decode 与 memory/compute/communication 瓶颈为轴，系统整理模型压缩、快速解码、并行、调度、KV 管理和 distributed serving；价值是建立算法—系统联合 taxonomy，而非提出或实验证明一个新系统。

## 问题与动机

LLM serving 优化分散在模型、kernel、runtime 与集群层，单看某一速度倍数容易忽略质量、SLO 和硬件边界。综述尝试用端到端生成过程串起这些层次（§1–2）。

## 关键观察 / 隐含假设

- **观察 1：prefill 与 decode 的资源形态不同，必须分别优化再联合调度。** 前者更 compute-bound，后者常受 memory/KV 限制。
  - **依赖假设**：经典 autoregressive Transformer serving仍是主要对象。
- **观察 2：算法优化只有进入 runtime/serving policy 才能形成端到端收益。**
  - **可能失效场景**：agentic、多模态、diffusion LM 与新硬件会使 taxonomy快速老化。

## 核心方法

论文按模型/算法、单机执行、并行与分布式系统整理技术，并比较 latency、throughput、memory、quality 与 deployment tradeoff；不提供新实现或统一复现实验。

## 设计取舍

- 广覆盖便于导航，但不同论文 metric/hardware 不可直接横比。
- taxonomy 提供结构，会受快速演化的模型和 serving stack 影响。

## 实验与结果

- 原文为 survey，无新的数值实验；证据来自所引论文的公开结果与分类（§3–后续各节）。
- 覆盖压缩、speculative decoding、KV/cache、batch/scheduling、parallel/disaggregation 等主线；不能把引用工作的最大倍数视为本综述复现。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| serving需算法—系统协同 | 多类技术交叉taxonomy | 截至收稿文献 | 中到强 |
| prefill/decode瓶颈不同 | 汇总大量系统论文 | 模型/硬件依赖 | 强 |
| 某路线普遍最优 | 无统一复现实验 | 跨论文异构设置 | 弱 |

## 批判性分析

### 论证链条

分类与术语统一有价值，但属于 secondary synthesis；任何性能选择仍需回原论文核对模型、硬件、arrival 和 SLO。

### 假设压力测试

thinking model、dynamic tool calls、multimodal generation 与 agent program scheduling 会弱化传统 request-level taxonomy。

### 实验可信度

没有自有实验；引用覆盖广，但存在发表偏差与版本快速过期。

### 系统性缺陷

survey 无法解决实现可用性、artifact reproducibility 和 production trace缺口。

## 局限与后续工作

- **局限 1**：文献截止时间早于 2026 年大量 agent/megakernel 工作。
- **后续工作 1**：维护版本化 taxonomy，并用统一 workload matrix 对关键路线复测。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[Speculative-Decoding]]、[[Disaggregation]]
- **相关系统**：[[vLLM]]、[[SGLang]]
