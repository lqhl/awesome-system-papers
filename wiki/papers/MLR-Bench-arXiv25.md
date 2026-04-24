---
type: paper
name: MLR-Bench
full_title: "MLR-Bench: Evaluating AI Agents on Open-Ended Machine Learning Research"
authors: [Hui Chen, Miao Xiong, Yujie Lu, Wei Han, Ailin Deng, et al.]
venue: arXiv
year: 2025
tags: [auto-research, benchmark, llm-judge, research-agent, evaluation]
source_pdf: "[[2505.19955v1.pdf]]"
source_md: "[[2505.19955v1]]"
---

# MLR-Bench: Evaluating AI Agents on Open-Ended Machine Learning Research (arXiv 2025)

> **一句话总结**:NUS 团队提出的开放式 ML research agent 基准,包含 201 个 NeurIPS/ICLR/ICML workshop 任务、MLR-Judge(LLM 评分与人类评审 Mann-Whitney U test p>0.05 无显著差异)、MLR-Agent 四阶段 scaffold;主要发现是 Claude Code 在 10 个 coding 任务中 8/10 产出 fabricated 实验结果,end-to-end overall score 最高仅 4.70/10。

## 问题

此前 research agent 评估基准各有局限:[[MLE-Bench-ICLR25]] 聚焦 Kaggle 工程、[[MLAgentBench-ICML24]] 聚焦实验执行、PaperBench 聚焦论文复现、RE-Bench 测 R&D 能力,缺少覆盖完整 idea→proposal→experiment→writing pipeline 的 open-ended 研究任务基准。同时评估仍高度依赖人类专家评审,无法规模化。更关键的问题是没有系统性方法去诊断 AI research agent 的 failure mode——特别是 fabricated result、novelty 不足等科学可靠性问题。

## 核心方法

三件套组成:

- **Tasks**:从近三年 NeurIPS/ICLR/ICML workshops 人工筛选 **201 个 open-ended research tasks**,覆盖 9 个 ML topic(LLM/VLM、AI for Science、ML Theory、Trustworthy AI、CV、ML Systems、Multimodality、RL、Others)。Task 就是 workshop overview + topics,不带固定 ground truth。
- **MLR-Judge**:rubric-based LLM judge。定义 9 个 review dimension(Consistency、Clarity、Novelty、Feasibility、Completeness、Soundness、Insightfulness、Significance、Overall),对每个阶段用不同子集;用 Gemini-2.5-Pro-Preview + Claude-3.7-Sonnet 双 judge 平均打分。Coding 阶段 judge 可读 execution log 与 source code,比只看 paper 的人类更能抓 hallucination。
- **MLR-Agent**:简单的四阶段 scaffold(Idea Generation → Proposal Generation → Experimentation → Paper Writing),刻意避免重 prompt engineering 以检验模型本身能力。中间插入 GPT-4o-Search-Preview 做 literature review 补给。支持 stepwise(每步独立测单个模型)和 end-to-end(同一 backbone 全程跑)两种模式。Experimentation 阶段用 [[OpenHands-ICLR25]] 式的 coding agent(具体用 Claude Code)。

评估 6 个 frontier 模型(o4-mini-high、Claude-3.7-Sonnet、DeepSeek-R1、Ministral-8B、Qwen3-235B-A22B、Gemini-2.5-Pro-Preview)+ Claude Code。Human validation:招募 10 位 NeurIPS/ICLR/ICML 有评审经验的 ML 专家,每篇 paper 分配两位独立打分,用 Mann-Whitney U test 比较 human-human 与 human-LLM 的评分差异分布。

与已有工作的差异:同期 [[Auto-Research-arXiv25]] 是 vision paper,不提供可量化的 benchmark;[[AI-Scientist-v2-arXiv25]] 是 agent 系统不是 benchmark。MLR-Bench 首次把 201 个真实 workshop topic 作为 open-ended 任务,配套 human-validated LLM judge。

## 关键结果

- **Idea/Proposal Generation**:6 个模型在 201 task 上 Consistency/Significance 普遍 >8.5/10,但 Novelty/Feasibility 普遍 <7.5,说明生成"创新且可实现"的想法仍是难点;Ministral-8B 在 Feasibility 上与大模型接近,model size 不是唯一决定因素。
- **Experimentation (Claude Code)**:10 task overall 分均低于 7.0,Soundness/Insightfulness/Significance 尤其低;**10 task 中有 8 个报告的是 fabricated/placeholder 结果**,即使显式指令"不准造数据"也会在执行失败后 shortcut 生成"合理数字"。
- **Paper Writing**:Gemini-2.5-Pro-Preview 最强(overall 6.60),因其擅长公式/算法写作;但没有模型 overall >7.0,因前一步实验本身质量不过关。
- **End-to-End**:Claude-3.7-Sonnet overall 4.70(成本 $2.40/task)、o4-mini-high 3.95(成本 $1.15)、Gemini-2.5-Pro-Preview 3.75(成本 $1.24);Soundness 最低(3.35-4.05),研究自动化离"真正可靠"还差很远。
- **MLR-Judge vs human**:5 个维度 Mann-Whitney U test p 值均 >0.05,LLM-human 差异不显著大于 human-human 差异,可作为规模化评估代理。
- **两大 failure mode**:(1) Experiment hallucination——coding agent 遇错不报错反而造数;(2) Lack of novelty——idea 多是 "trivial combination" 缺 motivation。

## 相关

- **相关概念**:LLM-as-a-judge、rubric-based evaluation、open-ended research、hallucination detection、agent scaffold
- **同类系统**:[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[AI-Scientist-v2-arXiv25]]、[[OpenHands-ICLR25]]、[[Auto-Research-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]
- **同主题**:[[Auto-Research]]
