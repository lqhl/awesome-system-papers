---
type: paper
name: OSWorld-Human
full_title: "OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents"
authors: [Reyna Abhyankar, Qi Qi, Yiying Zhang]
venue: MLSys
year: 2026
tags: [agent, computer-use, benchmark, latency, gui-agent]
source_pdf: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01.pdf]]"
source_md: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01]]"
---

# OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents (MLSys 2026)

> **一句话总结**：首次对 computer-use agent 做延迟专项研究——planning + reflection 的 LLM call 占任务总延迟 75–94%，每轮比前一轮慢 3×；提出人类标注的 OSWorld-Human 369 任务金轨迹数据集和 Weighted Efficiency Score（WES）度量，发现最强 agent 也比人类多走 1.4–2.7× 步数。

## 问题

Computer-use agent（[[CUA]]，如 OpenAI Operator、Claude Computer Use、Agent S2、UI-TARS）在 OSWorld 等 benchmark 上比拼准确率，但忽视了**延迟**：一个人 30s 能完成的「调整两段行间距为 double」任务，agent 要花 12 分钟——实际不可用。

既没人测 agent 实际跑多慢、哪个阶段慢，也没有「人类最优步数」的对照基准。

## 核心方法

**1. 首个 CUA 延迟研究**

- 在 OSWorld 37 任务子集上测 Agent S2（用 GPT-4.1 planner/reflection、UI-TARS-7B grounding on SGLang）。
- **发现 1**：planning + reflection（都调大模型）占任务总时间 75–94%；retrieval 0.7–8.9%；grounding 因用小模型+[[SGLang]] 很轻。
- **发现 2**：agent 步数越多越慢，每 5 步一档——后期 step 的 LLM call 因 prompt 累积所有历史 screenshot+plan+reflection，latency 是早期 3×。
- **发现 3**：A11y tree 解析本身 3–26s，再加 tree token 膨胀 prompt，往往拖慢任务；Set-of-Marks 在视觉丰富应用更好。

**2. OSWorld-Human 金轨迹数据集**

- 对所有 369 OSWorld 任务手工标注 ground-truth 人类步骤，两人双盲标注 + 交叉验证 + VM 实跑验证。
- 提供 **single-action**（每个原子操作一步）和 **grouped-action**（能共用一次 observation 的连续操作合并成一步）两个版本。
- 发布为后续研究基线。

**3. Weighted Efficiency Score (WES)**

- 成功任务按 $t_{\text{exp}} / t_{\text{actual}}$ 打正分（步数少好），失败按 $-t_{\text{actual}}/S$ 打罚分（快速失败优于耗尽步数）。
- 比原始 success rate 更能反映 agent 的时间效率。

## 关键结果

- **延迟构成**：planning + reflection 占 75–94%；retrieval 3% 左右（仅任务开头一次）；grounding 3–6%。
- **后期 step 3× slowdown**：prompt 随历史累积导致。
- **Agent S2 最佳任务需 50 步**（max allowance），但人类 grouped-action 平均 3–9 步。
- **16 个主流 agent 对比**：OSWorld 最高成功率 42.5% 的 agent 在作者的 WES 严格指标上仅 17.4%；最领先 agent 仍比人类多 **1.4–2.7×** 步。

## 相关

- **相关概念**：[[CUA]]、[[GUI-Agent]]、[[Chain-of-Thought]]、[[ReAct]]
- **同类系统**：Agent S2、UI-TARS、OpenAI Operator、Anthropic Claude Computer Use、Jedi、InfantAgent、Aguvis、OmniParser
- **同会议**：[[MLSys-2026]]
