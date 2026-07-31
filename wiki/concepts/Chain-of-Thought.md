---
type: concept
aliases: [CoT, Chain-of-Thought-Prompting]
last_updated: 2026-07-30
tags: [llm, reasoning, prompting, agents]
---

# Chain of Thought

> 思维链（Chain of Thought, CoT）让模型在答案前生成中间推理轨迹；它提高复杂任务的可分解性，却不自动保证轨迹正确、忠实或执行高效。

## 核心思想

CoT 将一次性映射改成多 token 的中间步骤，可由 prompt 引导、模型训练产生，或在 agent workflow 中与工具调用交替。系统可以利用轨迹做长度预测、verifier 检查、speculative execution 与调度，但不能把自然语言解释本身当作证明。

在 OSDI 2026 语料中，CoT 已从 prompting 技巧变成系统 workload：长且 heavy-tailed 的 reasoning response 主导 RL rollout，代码优化 agent 的 reasoning 必须通过测试/人审，shell agent 的步骤需要 capability boundary。

## 为什么重要

CoT 增加 token、KV cache、decode latency 与输出方差。对训练系统，它造成 rollout straggler 与显存膨胀；对 agent 系统，它形成可观测计划，却也扩大 prompt injection、幻觉动作和成本。可靠系统必须把 trace 与可执行效果、外部验证和明确 SLO 分开。

## 关键观察 / 隐含假设

- **组内 CoT 具有可利用的统计结构**：[[Seer-OSDI26]] 假设同 prompt group 的长度和 token pattern 相关，并用 probe response 调度剩余 rollout；高温度或异常样本会破坏预测。
- **推理轨迹不是 correctness oracle**：[[ECO-OSDI26]] 的 LLM self-review 之后仍需 build/test、code owner 与上线监控；[[SMARTTalk-OSDI26]] 也用 protocol/static check 约束模型生成的系统代码。
- **长 CoT 是资源 workload 而非免费质量增益**：[[SPEX-OSDI26]]、[[SkipKV-MLSys26]] 从执行与 KV 角度削减 reasoning cost；这些近似必须重新验证任务质量。
- **agentic research 需要外部 evaluator**：[[AI-Scientist-arXiv24]]、[[Auto-Research-arXiv25]] 与 [[InnovatorBench-ICLR26]] 共同表明可读 trace 不等于可复现实验或真正创新。

## 设计空间与取舍

- **显式 prompting**：无需训练即可使用，但轨迹格式、长度和忠实性不稳定。
- **训练期 reasoning/RL**：可塑造长程行为，却产生 heavy-tail rollout 和更高训练成本（[[Seer-OSDI26]]）。
- **隐藏或压缩轨迹**：降低 token/KV 开销和泄露风险，但削弱可审计性。
- **工具/验证器约束**：提高动作可靠性（[[ECO-OSDI26]]、[[SMARTTalk-OSDI26]]），代价是测试、sandbox 与人工 review 成本。

## 引用本概念的论文

- [[Seer-OSDI26]] — 利用 prompt-group CoT context 预测长度并加速同步 RL rollout。
- [[SPEX-OSDI26]] — 处理长 reasoning execution 的系统成本。
- [[SMARTTalk-OSDI26]] — 用受约束生成与验证把模型 reasoning 转成系统实现。
- [[ECO-OSDI26]] — 将 LLM reasoning/edit 纳入多层生产验证流水线。
- [[SkipKV-MLSys26]] — 针对 reasoning workload 的 KV/cache 冗余做优化。
- [[AI-Scientist-arXiv24]] — 在自动科研 workflow 中使用中间计划与评审轨迹。

## 已知局限 / 开放问题

- 如何测量 faithfulness，而不是只看 final-answer accuracy。
- 如何同时优化 reasoning quality、token/KV 成本、p99 latency 与隐私泄露。
- 如何防止 verifier 也被同源模型错误或 prompt injection 欺骗。
- 如何在调度中利用 CoT 统计相关性而不对长/困难样本产生 selection bias。
