---
type: paper
name: MLAgentBench
full_title: "MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation"
authors: [Qian Huang, Jian Vora, Percy Liang, Jure Leskovec]
venue: ICML
year: 2024
tags: [auto-research, agent, benchmark, ml-experimentation, react]
source_pdf: "[[2310.03302v2.pdf]]"
source_md: "[[2310.03302v2]]"
---

# MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation (ICML 2024)

> **一句话总结**：首个评估 LLM agent 端到端跑 ML 实验的 benchmark，覆盖 CIFAR-10 / Kaggle / BabyLM 等 13 个任务；Claude v3 Opus 基于 ReAct-style agent 拿下最高 37.5% 平均 success rate，但成功率在老数据集到最新 Kaggle 之间从 100% 跌到 0%，显露长程规划和幻觉是主要瓶颈。

## 问题

机器学习研究的核心是**实验迭代**：给定任务，研究者设计方法、写代码、跑实验、读结果、再改进。这一过程需要大量先验知识、能写出可跑代码、能诊断失败原因——门槛很高。传统 [[AutoML]] 和 NAS 把搜索空间限定在超参和架构内，很难覆盖完整实验流程。

随着 LLM 在代码和推理上进步，一个自然问题是：**能不能让 LLM agent 像研究员一样端到端做 ML 实验？** 已有的 AutoGPT、[[ReAct]]、[[Reflexion]] 等 agent 框架尚未在 ML 实验这类需要**多轮代码编辑 + 执行 + 诊断**的长程任务上被系统评估过；AgentBench、WebArena 等测 agent 的环境也不涉及真实 ML 研究。这篇论文填补了这一缺口。

## 核心方法

**Benchmark 框架（§2）**：每个任务由三样东西定义——任务描述（目标 + 提交格式）、starter files（数据 + 基线代码 + 数据说明）、evaluator（给最终提交打分）。Agent 在一个 file-system workspace 里反复动作，直到提交 `submission.csv` 或超时。

**动作集（Table 1）**：两类动作——
- **Primitive**：List / Read / Write / Append / Copy / Inspect Script Lines / Undo Edit / Execute Script / Final Answer
- **Compound**（含独立 LM call）：Understand File（按 query 读文件 + LM 摘要）、Edit Script / Edit Script Segment（按指令改代码）

**13 个任务（Table 2）**：分四类——
- Canonical：CIFAR-10、IMDb、ogbn-arxiv
- Classic Kaggle：house-price、spaceship-titanic
- Recent Kaggle（2022-08 后发布，潜在 OOD）：parkinsons-disease、fathomnet、feedback、identify-contrails
- Recent Research：CLRS、BabyLM
- Code Improvement：llama-inference、vectorization

**Agent 设计（§3）**：基于 [[ReAct]] 增强的 prompting agent。每步 prompt 包含所有动作说明、任务描述、最近 3 步 $(r, a, o)$ 历史。LM 按固定格式输出五块：**Reflection**（反思上一步，借鉴 [[Reflexion]]）、**Research Plan and Status**（高层规划 + 当前进度）、**Fact Check**（核对 Plan 里的 claim 是被执行验证的还是被幻觉出来的）、**Thought**、**Action + Action Input**（JSON）。Fact Check 是关键——作者发现 preliminary 里 LM 常在没跑代码的情况下就声称性能提升，Fact Check 要求 agent 显式区分 confirmed vs guessed。

**评估维度**：
- **Competence**：是否在 8 次 trial 里把性能 metric 比 baseline 提高 ≥10%（success rate）
- **Average improvement**：所有有效提交的平均提升百分比
- **Efficiency**：总 token 数 + wall-clock 时间

## 关键结果

- **Claude v3 Opus 最强，平均 success rate 37.5%**（8 run × 13 task），明显好于 GPT-4（19.2%）、GPT-4-turbo（26.0%）、Gemini Pro（18.3%）、Mixtral（3.8%）。
- **task 间差异极大**：house-price / spaceship-titanic 100%，但 parkinsons-disease、fathomnet、BabyLM、vectorization 全部 0%——越新越难的任务越挫败，提示训练数据污染在老任务上起作用。
- GPT-4 **平均 metric 提升 41.3% 比 Claude v3 Opus 的 26.1% 更高**，但靠 identify-contrails 一个 task 把均值拉起来；整体 Claude v3 Opus 更稳定。
- 与 **AutoGPT / LangChain ReAct 对比**：本文 agent 在 GPT-4-turbo 上 26.0% vs AutoGPT 2.9% vs LangChain 1.0%；Claude v3 Opus 上 37.5% vs 13.5% vs 33.7%——Research Plan + Fact Check 两个槽位显著降低幻觉。
- **Cost**：GPT-4-turbo 全 benchmark 约 600 万 token ≈ $60；但 26% 成功率意味着期望每次成功需 $231，**可靠性仍是落地瓶颈**。
- CIFAR-10 错误模式分析：Bad Plan、Hallucination、Response Format Error、Submission Format Error、Small Improvement 各占一部分；GPT-4 比 Claude v3 Opus 更易幻觉和坏规划。

## 相关

- **相关概念**：[[ReAct]]、[[Reflexion]]、[[AutoGPT]]、[[Agent-Scaffold]]、[[AutoML]]
- **同类系统**：[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
