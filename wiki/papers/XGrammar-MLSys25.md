---
type: paper
name: XGrammar
full_title: "XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models"
authors: [Yixin Dong, Charlie F. Ruan, Yaxing Cai, Ruihang Lai, Ziyi Xu, Yilong Zhao, Tianqi Chen]
venue: MLSys
year: 2025
tags: [structured-generation, constrained-decoding, context-free-grammar, llm-serving, agents, area/ai-infra]
source_pdf: "[[mlsys25-dong-xgrammar.pdf]]"
source_md: "[[mlsys25-dong-xgrammar]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# XGrammar：灵活高效的 LLM 结构化生成引擎（MLSys 2025）

> **原题**：XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models

> **一句话总结**：XGrammar 将 vocabulary 分为可预检的 context-independent tokens 与 runtime 才解释的 dependent tokens，并用 grammar expansion、persistent stack 与 engine overlap 加速 CFG constrained decoding；grammar processing 最高比既有方案快 100×，端到端 structured generation 接近零开销。

## 问题与动机

agent code/function call 需要 JSON/CFG 合法输出；逐 token 对全 vocabulary 执行 parser stack transition 会产生显著 CPU/mask 开销，拖慢 GPU serving（§1–2）。

## 关键观察 / 隐含假设

- **观察 1：大部分 vocabulary token 的合法性与当前 parser context 无关，可提前判定。**
  - **依赖假设**：grammar 中 context-dependent token 集相对小。
- **观察 2：grammar CPU work 可与 GPU inference overlap。**
  - **可能失效场景**：极小模型/高并发时 parser thread 或 mask transfer重新成为瓶颈。

## 核心方法

系统预检 independent tokens，只对 dependent tokens runtime interpret；grammar context expansion进一步缩小后者，persistent stack 减少状态复制，并与 serving engine pipeline overlap（§3–4）。

## 设计取舍

- 预计算换 grammar compile/memory。
- CFG 灵活，但不验证生成内容语义。
- 静态 grammar 假设被后续 XGrammar-2 扩展。

## 实验与结果

- grammar execution/compilation 在所测 schema 上最高相对 prior solutions 100×（§5）。
- 与 LLM engine 集成后 structured generation overhead 接近零（§5）。
- correctness 覆盖 JSON schema/CFG 等结构，但非 tool execution correctness。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| token partition显著降 grammar cost | §5 最高100× | 选定 grammars/vocab | 强 |
| engine E2E开销接近零 | serving integration | 静态 grammar | 中到强 |
| 提升 agent可靠性 | 只保证 syntax | 不验证 semantics | 弱 |

## 批判性分析

### 论证链条

parser cost→token classification/persistent stack→micro与E2E证据闭合。其能力边界是 syntactic contract，不应外推为 tool-use correctness。

### 假设压力测试

动态 schema、请求内 protocol switch 与大量独特 grammar 会降低预计算/cache复用，正是 XGrammar-2 的问题来源。

### 实验可信度

有强 baseline 和 engine integration；缺生产 schema churn、P99、security 与多租户 cache isolation。

### 系统性缺陷

恶意 grammar complexity、parser DoS、cache version 与 invalid semantic arguments 未覆盖。

## 局限与后续工作

- **局限 1**：主要是请求开始前已知的静态结构。
- **后续工作 1**：支持动态 dispatch、subgrammar reuse 与 schema security audit。

## 相关

- **相关概念**：[[Structured-Generation]]、[[LLM-Inference]]
- **后续系统**：[[XGrammar2-CAIS26]]
