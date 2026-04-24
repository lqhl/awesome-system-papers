---
type: paper
name: AI-Scientist
full_title: "The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery"
authors: [Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, "et al."]
venue: arXiv
year: 2024
tags: [auto-research, agent, scientific-discovery, paper-generation, open-ended, llm-agent]
source_pdf: "[[2408.06292v2.pdf]]"
source_md: "[[2408.06292v2]]"
---

# The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (arXiv 2024)

> **一句话总结**：Sakana AI 的首个"端到端"自动化 ML 研究流水线——从 idea 生成、实验执行、LaTeX 写作到自动 peer review 一条龙跑完，**每篇论文成本约 \$15**；自动 reviewer 在 ICLR 2022 papers 上达到 65% balanced accuracy（人类 66%），并在 diffusion / 语言建模 / grokking 三个子领域跑出多篇被 LLM reviewer 判为"弱接收"的论文。

## 问题

前人把 LLM 用于科研的工作，大多只自动化科研流水线的**一个环节**：brainstorming idea（SciMON）、写代码（[[Aider]]、[[SWE-Bench]]）、帮写论文（Altmäe et al.）、或专注某个受限搜索空间的 AutoML / NAS / 算法搜索（[[FunSearch-Nature24]]、GNoME）。但"从 idea 到 peer review 全流程"还没被一个系统跑通——尤其缺少自动化的**论文写作和评审**这两步，使系统的发现既无法标准化评估也难以与人类科学社区对接。

本文目标是把**整条 research pipeline**——ideation、literature search、experiment planning、code change、execution、visualization、manuscript、peer review——都交给 LLM agent 自主完成，并让它能以 archive-driven 的 open-ended loop 持续迭代知识。

## 核心方法

系统三大阶段 + 一个外挂 reviewer（Figure 1）：

**1. Idea Generation（§3）**：给定一个 code template（如 NanoGPT 在 Shakespeare 上的 minimal run），让 LLM 用 chain-of-thought + [[Reflexion]] 风格 brainstorm 新方向；每个 idea 附带 description、实验计划、自评的 interestingness / novelty / feasibility 分数。用 Semantic Scholar API 做 novelty check，淘汰已有工作。archive 持续累积，新 idea 会以之前 idea + reviewer 分数为 conditioning——灵感来自 open-endedness 研究里的 "LLM as mutation operator"。

**2. Experiment Iteration（§3.2）**：用开源 coding agent [[Aider]] 执行实验。Aider 按计划改模板代码 → 跑实验 → 拿到错误或结果 → 最多 4 次 retry。每轮结束后 Aider 记"实验日志"，再据此 replan 下一步，总共最多 5 轮。最后让 Aider 改绘图脚本生成 figure，并为每张图写说明。

**3. Paper Write-up（§3.3）**：
- (a) Per-section text generation：Aider 按 intro → background → methods → experimental setup → results → conclusion 顺序填空白 LaTeX 模板，每节一轮 self-reflection。
- (b) Web search for references：开 20 轮 Semantic Scholar 检索补 related work 和其他章节的 citation，bibtex 自动追加。
- (c) Refinement：再一轮 self-reflection 去重、精炼。
- (d) Compilation：LaTeX linter 报错回灌 Aider 自动修复。

**4. Automated Reviewer（§4）**：用 PyMuPDF 把 PDF 转文本喂 GPT-4o，按 NeurIPS review guideline 打分（soundness / presentation / contribution / overall / confidence）。改进手段：5 轮 [[Reflexion]] self-reflection + 5 次 review ensembling + 1-shot example + meta-aggregation（Area Chair prompt）。在 500 篇 ICLR 2022 论文上评估。

**关键设计决策**：
- 不等 reviewer 结果就并行生成 idea，摊销 idea generation cost
- 用 text-only prompt + 小规模实验（8× H100 一周能跑几百篇）压低成本
- initial plotting / experiment 模板故意写得 minimal，给系统留足 creative 空间

## 关键结果

- **成本 \~\$15/paper**（约 \$250 跑完 50 个 idea 的 Sonnet 3.5 实验 + reviewer $0.25-0.50/次）；一个 8× H100 节点一周跑几百篇论文。
- **Automated reviewer vs 人类**（500 篇 ICLR 2022）：GPT-4o (1-shot) @6 达到 65% balanced accuracy（人类 66%）、F1 0.57（人类 0.49，AI 超人）、AUC 0.65（持平人类）；FNR 0.39 vs 人类 0.52（少误拒），FPR 0.31 vs 人类 0.17（多误收）。Claude Sonnet 3.5 有严重 over-optimism bias，需把阈值从 6 抬到 8。
- **3 个 domain × 4 个 base model 共跑 \~600 个 idea**：Sonnet 3.5 质量最高，GPT-4o 次之且经常写不好 LaTeX，DeepSeek Coder 最便宜（\~\$10）但常调不好 Aider，Llama-3.1 405B 最差。Diffusion 模板 Sonnet 3.5 跑 51 idea → 49 novel → 38 完成论文，mean score 3.82 / max 6.0。
- 案例研究 "**Adaptive Dual-Scale Denoising**"：系统自主提出 global/local 双分支 denoiser + 学习时间条件权重，KL 在 dinosaur 数据集降 12.8%，且自动画出权重随时间步演化的新图；另一个 "StyleFusion" 得分 5、"Unlocking Grokking" 得分 5。
- 失败模式：Aider 实现失败率高、LaTeX 编译错、图表超出页面、hallucinate ablation 表、数值大小比较错误、Sonnet 3.5 甚至**改代码延长自己的 time limit 或 relaunch 自己的进程**——突显 sandbox 必要性。
- 评审 API 花费 \$0.25–0.50/review；reviewer 和 human reviewer 分数相关性 0.18，高于两个 human reviewer 之间的 0.14。

## 相关

- **相关概念**：[[Aider]]、[[Reflexion]]、[[Chain-of-Thought]]、[[Open-Endedness]]、[[LLM-as-Judge]]、[[Semantic-Scholar-API]]
- **同类系统**：[[AI-Scientist-v2-arXiv25]]、[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
