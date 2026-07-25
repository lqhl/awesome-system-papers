---
type: concept
aliases: [CoT, Chain-of-Thought-Prompting]
last_updated: 2026-07-23
tags: [llm, reasoning, prompting, agents]
---

# Chain of Thought

> Chain-of-thought prompting elicits or represents intermediate reasoning traces before a final answer, giving an LLM workflow additional structure but not by itself a guarantee of correctness, faithfulness, or efficient execution.

## 核心思想

A prompt or agent workflow asks a model to decompose a task into intermediate steps, which can help planning, tool use, or verification. The resulting trace is model output: it may be useful for control and debugging, but it can be incomplete, post-hoc, or inconsistent with the final decision unless an external evaluator checks it.

## 为什么重要

Agent and automated-research systems use intermediate traces to coordinate planning and artifact production. The systems question is how to turn a trace into an auditable action: constrain it with tools, tests, code execution, or verifiers, and report its token/latency/cost impact.

## 关键观察 / 隐含假设

- **观察**：reasoning traces require external evaluation to become reliable system actions. [[AI-Scientist-arXiv24]] and [[Auto-Research-arXiv25]] use agent workflows with evaluator boundaries.
- **观察**：long reasoning can interact with memory and serving cost. [[SkipKV-MLSys26]] examines a systems path affected by such workloads.
- **假设**：a visible trace faithfully explains model behavior. [[Kosmos-AI-Scientist-arXiv25]] and [[RD-Agent-Quant-arXiv25]] illustrate why tool/verifier evidence is stronger than narrative trace alone.

## 设计空间与取舍

- **Free-form vs structured traces**：structure improves control but can constrain exploration.
- **Trace length vs cost/latency**：more steps consume context and serving resources.
- **Self-critique vs independent verification**：model-generated criticism is weaker than executable or external checks.

## 引用本概念的论文

- [[AI-Scientist-arXiv24]] — agent workflow with evaluation stages.
- [[Auto-Research-arXiv25]] — automated-research pipeline.
- [[SkipKV-MLSys26]] — serving/memory implications of reasoning workloads.
- [[RD-Agent-Quant-arXiv25]] — tool-oriented agent workflow.
- [[Kosmos-AI-Scientist-arXiv25]] — long-horizon agent/research context.
- [[InnovatorBench-ICLR26|InnovatorBench]] — 在开放式算法创新评测中考察 reasoning trace 能否转化为可执行、可评分的实现。
