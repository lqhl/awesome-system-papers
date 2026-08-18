---
type: paper
name: Multiverse
full_title: "Multiverse: Your Language Models Secretly Decide How to Parallelize and Merge Generation"
authors: [Xinyu Yang, Yuwei An, Hongyi Liu, Tianqi Chen, Beidi Chen]
venue: NeurIPS
year: 2025
tags: [parallel-generation, reasoning, non-autoregressive, llm-inference, model-system-codesign, area/ai-infra]
source_pdf: "[[neurips25-yang-multiverse.pdf]]"
source_md: "[[neurips25-yang-multiverse]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# Multiverse：由模型决定并行与合并的生成系统（NeurIPS 2025）

> **原题**：Multiverse: Your Language Models Secretly Decide How to Parallelize and Merge Generation

> **一句话总结**：Multiverse 将 MapReduce 内化进模型输出协议，由模型自适应拆任务、并行生成子结果并无损合并；32B 模型用 1K examples 微调约 3 小时，在 AIME24/25 达 54%/46%，同 context budget 平均高 1.87 points，并行 engine 最高加速约 2×。

## 问题与动机

自回归模型常在文本中隐式列出可并行子任务，却仍串行生成。外部 workflow 需要预定义 DAG，难随问题改变。Multiverse 让模型直接产生 Map/Process/Reduce control token，并由 runtime interpreter 执行（§1–3）。

## 关键观察 / 隐含假设

- **观察 1：reasoning trace 中存在可学习的隐式并行结构。** curator 将顺序 trace 转为结构化训练样本。
  - **依赖假设**：分解后的子任务独立，reduce 能无损整合。
- **观察 2：模型应决定 sequential/parallel switching。** runtime 只解释协议，不另做 planner。
  - **可能失效场景**：强依赖链、共享中间状态或错误分解会放大并行浪费。

## 核心方法

Multiverse Curator 自动构造 1K structured examples；Multiverse [[Attention|Attention]] 隔离并行 reasoning branches，又保持 causal-compatible training；Engine interpreter 按模型 token 动态切换并行与顺序 generation（§3–4）。

## 设计取舍

- model-controlled parallelism 自适应，但调度正确性难外部保证。
- parallel branches 降 wall-clock，增加总 token/显存和 reduce failure。
- 只需小规模微调，效果依赖强 base model 已有分解能力。

## 实验与结果

- 32B 模型约 3h/1K examples 微调，AIME24/25 54%/46%（§5）。
- 同 context length 相对 AR-LLM 平均提高 1.87 points；不同 batch 下最高约 2× speedup（§5）。
- 开源 data/model/engine/recipes，但主要证据集中数学 reasoning。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 模型可学会并行生成协议 | AIME与trajectory analysis | 32B、数学任务 | 中到强 |
| 并行可改善 wall-clock | 最高约2× | 所测 engine/batch | 中 |
| reduce 无损且普适 | 任务分数基本保持 | 有限 domain | 中偏弱 |

## 批判性分析

### 论证链条

隐式分解→structured data/attention/runtime→质量与速度证据完整；“natively parallel”仍依赖外部 interpreter 和特定协议，不是任意语言输出自然并行。

### 假设压力测试

software engineering、tool side effect 和长程研究中的 branch 共享状态会破坏独立性，错误 reduce 也可能隐藏局部分支失败。

### 实验可信度

公开 artifact 与 budget control 是优点；缺跨 domain、生产 scheduler contention、总 compute/energy 与错误归因。

### 系统性缺陷

branch cancellation、priority、KV duplication、failure isolation 和 deterministic replay 未充分覆盖。

## 局限与后续工作

- **局限 1**：主要验证数学 reasoning 与单一规模。
- **后续工作 1**：在 tool-using DAG、代码和跨文档任务上测 dependency violation、总 token、P99 和恢复。

## 相关

- **相关概念**：[[LLM]]、[[Parallel-Decoding]]、[[Speculative-Decoding]]
- **相关系统**：[[Agentix-NSDI26]]

