---
type: paper
name: MLE-Bench
full_title: "MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering"
authors: [Jun Shern Chan, Neil Chowdhury, Oliver Jaffe, James Aung, Dane Sherburn, "et al."]
venue: ICLR
year: 2025
tags: [benchmark, ml-engineering, kaggle, agent, evaluation]
source_pdf: "[[2410.07095v2.pdf]]"
source_md: "[[2410.07095v2]]"
---

# MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering (ICLR 2025)

> **一句话总结**：OpenAI 推出的自主 ML engineering benchmark，75 个人工精选的 Kaggle 竞赛（总奖金 $1.95M）+ 离线评测 + 与真实 Kaggle private leaderboard 对齐的铜银金奖判定；最强配置 o1-preview + AIDE scaffold 在 pass@1 拿到 16.9% 得奖率（相当于平均 7 枚金牌），pass@8 涨到 34.1%。

## 问题

代码 benchmark（HumanEval、MBPP）已饱和，SWE-Bench 聚焦 bug fix，但缺一个**端到端自主 ML engineering** 评测——这正是 AI R&D acceleration 风险模型的核心能力（OpenAI Preparedness Framework、Anthropic RSP、Google DeepMind Frontier Safety 都需要衡量这个维度）。已有尝试（MLAgentBench 13 题、AIDE/Weco 自报、DSBench）要么覆盖少、要么只挑 tabular 任务、要么无法直接对比人类水平。

## 核心方法

**数据集构建**：从 Meta Kaggle 5673 场竞赛筛到 586 场做人工 screening，最终选 75 场（22 Low / 38 Medium / 15 High 复杂度）+ 7 场 dev split。每场包含：

- 爬取的 Overview / Data 描述
- 数据集（能用原 split 就用，不能则手动重切 train/test 并确保分布相近）
- 本地 grading code
- Kaggle private leaderboard 快照（public 容易被 overfit）

**Medal 判定**：完全复用 Kaggle 规则——按参赛队伍数动态定铜/银/金阈值（如 1000+ teams：bronze top 10%、silver top 5%、gold top 0.2%+10），保证不同竞赛的奖牌可比。**Headline metric = 拿到任何奖牌的百分比**。

**反作弊机制**：
- **Rule-breaking detection**：GPT-4o 审 agent log，查是否手写预测、是否调外部 LLM API
- **Plagiarism detection**：Dolos 代码相似度工具对比 Kaggle 前 50 notebooks，>60% 相似直接 disqualify
- **Submission 必须由独立 model 产生**，agent 不能靠记忆直接写答案文件
- **Contamination 实验**：测 base model 对竞赛讨论帖的 token familiarity 与得分的相关性 → 无显著相关；手工 obfuscate 描述去掉 Kaggle 痕迹 → 得分无变化（8.5% vs 8.4%）

**执行环境**：Ubuntu 20.04 Docker，36 vCPU / 440GB RAM / 4095 GiB SSD / 1× A10 GPU，24h / competition，3 seeds，75 场合计 1800 GPU-hours。

**Scaffold 对比**：AIDE（Kaggle 专精，tree search over code）、MLAgentBench (MLAB)、OpenHands CodeActAgent 三家都跑 GPT-4o。

## 关键结果

- **Scaffold 对比（GPT-4o）**：AIDE 8.7% > [[OpenHands-ICLR25|OpenHands]] 4.4% > MLAB 0.8%。AIDE 胜在会在整 24h 里持续 prompt 模型改进到 500 nodes 上限；MLAB / OpenHands 常提早结束、加载几千行文件把 context 打爆
- **Model 对比（都用 AIDE）**：o1-preview 16.9% > GPT-4o 8.7% > Claude-3.5-Sonnet 7.6% > Llama-3.1-405B 3.0%。o1-preview 平均拿 7 枚金牌（Kaggle Grandmaster 门槛是 5 枚），但竞赛不完全可比
- **Pass@k**：GPT-4o pass@6 = 17.0% ≈ o1-preview pass@1 16.9%；两者 pass@6 都约为 pass@1 的 2×
- **Compute scaling**：CPU-only 9.1% / 1×A10 8.7% / 2×A10 10.2%，agent 几乎不用第二张 GPU
- **Time scaling**：GPT-4o + AIDE 从 24h 8.7% → 100h 11.8%
- 共同失败模式：不用 validation server、OOM 被 kill、不会估算训练时间
- 开源 [github.com/openai/mle-bench](https://github.com/openai/mle-bench)，后续被 [[AI-Scientist-v2-arXiv25]]、AIDE 等工作广泛引用为 ML agent 标尺

## 相关

- **相关概念**：Kaggle Competitions、Pass@k、Contamination Detection、Agent Scaffold
- **相关 benchmark**：SWE-Bench、MLAgentBench、DSBench、GAIA、AgentBench
- **相关 scaffold**：AIDE、MLAB、[[OpenHands-ICLR25]]
- **下游引用**：[[AI-Scientist-v2-arXiv25]]（用 AIDE 作为 inspiration 做 agentic tree search）
- **同主题**：[[Auto-Research]]
