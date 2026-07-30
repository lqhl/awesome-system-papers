---
type: concept
aliases: [CoT, Chain-of-Thought-Prompting]
last_updated: 2026-07-23
tags: [llm, reasoning, prompting, agents]
---

# Chain of Thought

> 思维链（Chain of Thought, CoT）提示在最终答案前引出中间推理 trace，为 LLM 工作流增加结构，但本身不保证正确性、忠实性或执行效率。

## 核心思想

提示或智能体工作流要求模型把任务拆为中间步骤，可辅助规划、工具调用与验证。生成的 trace 仍只是模型输出；若没有外部 evaluator 检查，它可能不完整、属于事后解释，甚至与最终决策不一致。

## 为什么重要

智能体与自动科研系统用中间 trace 协调规划和产物生成。系统问题在于如何把 trace 变成可审计动作：用工具、测试、代码执行或 verifier 约束它，并报告 token、延迟与成本影响。

## 关键观察 / 隐含假设

- **观察**：推理痕迹需要外部评估才能成为可靠​​的系统动作。 [[AI-Scientist-arXiv24]] 和 [[Auto-Research-arXiv25]] 使用具有评估者边界的代理工作流。
- **观察**：长推理可以与记忆和服务成本相互作用。 [[SkipKV-MLSys26]] 检查受此类工作负载影响的系统路径。
- **假设**：可见的痕迹忠实地解释了模型的行为。 [[Kosmos-AI-Scientist-arXiv25]] 和 [[RD-Agent-Quant-arXiv25]] 说明了为什么工具/验证者证据比单独的叙述痕迹更强。

## 设计空间与取舍

- **自由形式与结构化痕迹**：结构改善了控制，但会限制探索。
- **跟踪长度与成本/延迟**：更多步骤消耗上下文和服务资源。
- **自我批评与独立验证**：模型生成的批评弱于可执行或外部检查。

## 引用本概念的论文

- [[AI-Scientist-arXiv24]] — agent workflow with evaluation stages.
- [[Auto-Research-arXiv25]] — automated-research pipeline.
- [[SkipKV-MLSys26]] — serving/memory implications of reasoning workloads.
- [[RD-Agent-Quant-arXiv25]] — tool-oriented agent workflow.
- [[Kosmos-AI-Scientist-arXiv25]] — long-horizon agent/research context.
- [[InnovatorBench-ICLR26|InnovatorBench]] — 在开放式算法创新评测中考察 reasoning trace 能否转化为可执行、可评分的实现。
