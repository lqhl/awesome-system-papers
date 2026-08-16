---
type: concept
aliases: [CoT, Chain-of-Thought-Prompting]
last_updated: 2026-08-14
tags: [llm, reasoning, prompting, agents]
---

# Chain of Thought

> 思维链（Chain of Thought，CoT）让模型在给出答案前生成中间推理步骤；它可以帮助分解复杂任务，但这些步骤既不是正确性证明，也不一定忠实反映模型真正使用的依据。

## 核心思想

CoT 把一次直接回答改成一段多 token 的推理轨迹。轨迹可以由 prompt 触发，也可以通过监督学习或强化学习形成；在 agent 中，它还会和检索、代码执行、工具调用交替出现。系统因而可以观察中间步骤，并据此做调度、缓存、审查或失败恢复。

要分清三件事：最终答案是否正确、推理文字是否合理、推理文字是否忠实。一个模型可能写出很顺的解释却得到错误答案，也可能答案正确但理由不可验证。因此，CoT 最适合被当作“可利用但不可信的运行轨迹”，不能直接充当 verifier。

## 为什么重要

长推理模型会生成数千到数万 token。CoT 因而不只是 prompting 技巧，也是一种系统工作负载：它扩大 [[KV-Cache]]，拉长 decode 时间，并产生很重的长度长尾。[[Seer-OSDI26]] 的生产工作负载中，rollout 占一次强化学习迭代的 63%–87%；系统正是利用同一 prompt 组内 response 的相关性来缓解最后一批长请求。

在自动科研和代码优化中，可读的步骤也不等于可靠结果。[[AI-Scientist-arXiv24]]、[[Auto-Research-arXiv25]] 和 [[Kosmos-AI-Scientist-arXiv25]] 都用中间计划组织长流程，但仍依赖真实实验、检索记录或外部评审。[[ECO-OSDI26]] 更直接：CoT 往往生成更多修改，同时也产生更多错误，生产系统最终靠 build、test、code owner 和 rollout 过滤结果。

## 关键观察 / 隐含假设

- **同一 prompt 产生的多条 CoT 往往相关，但不是完全相同。** [[Seer-OSDI26]] 用一个已生成 response 估计同组其余 response 的长度，并共享 suffix context；高采样温度、异常长答案或任务难度突变都会削弱这种相关性。
- **推理越长，未必越好。** [[SkipKV-MLSys26]] 发现 reasoning 中存在句子级冗余，并通过压缩 KV 和 steering 缩短生成；但它的收益只在所测 DeepSeek-R1 distilled 模型和任务上成立，不能推出任意 CoT 都能安全裁剪。
- **CoT 适合提出候选，不适合单独作判定。** [[ECO-OSDI26]] 的生产结果表明，zero-shot、ReAct 与 CoT 没有一个在所有修改上最好；模型生成之后仍要经过独立验证。
- **长程 agent 需要压缩状态。** [[Kosmos-AI-Scientist-arXiv25]] 用结构化世界模型汇总大量运行轨迹和文献，而不是把全部 CoT 原样塞回 context；这里假设压缩不会丢掉决定后续实验的关键信息。
- **自动评审会继承评审器自身的偏差。** [[AI-Scientist-arXiv24]] 与 [[Auto-Research-arXiv25]] 都使用模型评审中间或最终产物；有限 benchmark 上的相关性不能证明它能识别真正的新颖性、可复现性和科研价值。
- **更长的预算会暴露新的失败模式。** [[InnovatorBench-ICLR26]] 中 agent 运行超过 11 小时才接近峰值，但仍会过早终止训练、遗忘后台任务和生成模板化推理；增加 token 或时间并不能自动解决状态管理。

## 设计空间与取舍

- **显式 CoT prompt**：接入简单、无需改模型；输出格式、长度和忠实性不稳定。
- **训练得到的 reasoning**：可以塑造长程行为；训练与 rollout 成本更高，长度长尾也更严重。
- **压缩、隐藏或裁剪轨迹**：减少 token、KV 和泄露风险；可能删掉真正影响答案的步骤，也降低人工可审计性。
- **按轨迹做系统调度**：可预测长度、迁移未完成请求或复用 context（[[Seer-OSDI26]]）；预测错误会造成负载失衡或对困难样本产生偏置。
- **工具和 verifier 约束**：用编译、测试、定理检查器或真实实验验证动作；可靠性更高，但系统成本和失败处理更复杂。

## 引用本概念的论文

- [[Seer-OSDI26]] — 把长 CoT rollout 当作可预测、可迁移的系统工作负载。
- [[SkipKV-MLSys26]] — 从句子级冗余出发减少 reasoning KV 占用和生成长度。
- [[ECO-OSDI26]] — 量化 CoT 在生产代码优化中的收益与错误率，并用多层验证收口。
- [[AI-Scientist-arXiv24]] — 用 CoT 和反思生成研究想法、实验和论文，但最终质量依赖外部评审。
- [[Auto-Research-arXiv25]] — 用 CoT 拆解研究任务并做方法规划，端到端闭环证据仍有限。
- [[Kosmos-AI-Scientist-arXiv25]] — 用结构化记忆支撑长时间、多轨迹科研探索。
- [[RD-Agent-Quant-arXiv25]] — 将 CoT 作为金融代码生成基线，显示累积知识与结构化执行同样重要。
- [[InnovatorBench-ICLR26]] — 展示长时科研 agent 中的遗忘、急躁和模板化推理问题。

## 已知局限 / 开放问题

- 需要区分“解释看起来合理”和“解释忠实”，并建立不依赖同源模型自评的指标。
- 应同时报告任务质量、生成 token、KV 占用、P99 延迟和验证成本，而不只报告答案准确率。
- 裁剪或压缩 CoT 时，要测量对困难样本、长尾样本和不同模型的选择性伤害。
- verifier 也可能受 prompt injection、共同训练数据或同类推理错误影响；多模型投票并不等于独立证据。
