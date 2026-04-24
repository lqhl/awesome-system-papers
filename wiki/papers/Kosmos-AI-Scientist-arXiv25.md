---
type: paper
name: Kosmos-AI-Scientist
full_title: "Kosmos: An AI Scientist for Autonomous Discovery"
authors: [Ludovico Mitchener, Angela Yiu, Benjamin Chang, Mathieu Bourdenx, Tyler Nadolski, et al.]
venue: arXiv
year: 2025
tags: [auto-research, ai-scientist, world-model, multi-agent, data-driven-discovery, long-horizon]
source_pdf: "[[2511.02824v1.pdf]]"
source_md: "[[2511.02824v1]]"
---

# Kosmos: An AI Scientist for Autonomous Discovery (arXiv 2025)

> **一句话总结**：Kosmos 用一个结构化 world model 协调数据分析 agent + 文献检索 agent 并行跑 **200+ rollouts**，单次 12 小时跑完相当于**人类专家 6.14 个月**的工作量，在代谢组、材料、连接组、统计遗传等 7 个领域产出真实 discovery，report 里 **79.4%** 语句经独立专家验证为正确且全部可 trace 到 code 或文献。

## 问题

已有 AI scientist（Sakana [[AI-Scientist-arXiv24]]、Robin、Virtual Lab、Google AI co-scientist）都受 context window 和 agent coherence 所限，能跑的动作数少，难以在**跨领域的数据驱动科研**里积累足够深度。具体瓶颈：
- 多 agent 之间缺乏共享 context，只能轻量同步。
- 长程迭代（几十轮）后 agent 会失焦，discovery 深度被动截断。
- Sakana 只能做 ML 研究；Robin 局限于 therapeutics；AI co-scientist 只提假设不跑数据；Virtual Lab 缺 exploratory analysis。

Kosmos 的目标：给定一个数据集 + 开放式研究目标，自主跑数小时级别的 literature search / data analysis / hypothesis generation 循环，最终产出 citation 完整、可复现的 scientific report。

## 核心方法

**系统结构**：
- 每个 cycle 并行最多 10 个任务，分派给两类 Edison Scientific agent——**data analysis agent**（基于 Finch）和 **literature search agent**（基于 PaperQA2）。
- Cycle 结束后由 LLM 把所有 task output summarize 更新到 **structured world model**——整个系统的共享 memory，压缩历史发现、当前假设、未解问题。
- 下一 cycle 用 world model 做 query 再产出新任务列表，如此迭代 20 个 cycle 左右（单次运行 ~12 小时）。
- 最终 LLM 基于 world model 合成 3-4 篇 scientific report，**每条 statement 强制 cite 一篇论文或一个 Jupyter notebook**，保证 traceability。

**Scale 数据（vs baseline）**：
- Kosmos 平均 42,500 行代码 + 读 1,500 篇全文论文/run；Robin 4,310 行 + 1,530 篇；Finch 301 行；PaperQA2 只读 33 篇 —— Kosmos 代码生成量比 Robin **高 9.8×**。
- 平均 166 个 data analysis rollout + 36 个 literature review rollout，比现有系统多 8×。

**评估方法**：
- 独立专家随机抽 102 条 statement 做 supported/refuted 判定，不给 code 和引文源。
- 让真实学术团队用 Kosmos 结果，估算对应的 expert-time，以及 novelty / reasoning depth。
- 7 个真实 case study：代谢组学（hypothermia 保护机制）、钙钛矿太阳能电池工艺参数、连接组学（log-normal 分布）、SOD2 → myocardial fibrosis、2 型糖尿病 GWAS 顺式调控、Alzheimer 病事件时序、以及内嗅皮层神经元老化的新临床机制。

## 关键结果

- **Accuracy**：全部 statement 79.4% supported；细分为数据分析 85.5%、文献综述 82.1%、synthesis（两者融合解释）57.9%——synthesis 是主要痛点，系统倾向把 statistically significant 混同于 scientifically valuable。
- **Expert-time scaling**：Cycle 20 的 Kosmos run 被学术合作者估算等价**人类 6.14 个月**研究（σ=2.49），且 valuable finding 数量与 cycle 数近似线性。
- **Discovery mix**（7 个 case）：3 个复现了未访问到的 preprint/未发表结果，2 个给已有发现补充新证据，1 个自创分析方法（Alzheimer 事件时序 breakpoint 模型），1 个**全新临床相关发现**（内嗅皮层神经元老化易感机制）。
- **Traceability**：每条 statement 绑定 Jupyter notebook 或引文，report 可被第三方直接 audit；这是现有 AI scientist 少见的严谨性承诺。
- **限制**：数据集 ≤5GB，不擅长处理 raw image/sequencing；不能访问外部数据做 orthogonal 验证；多 run 结果不一定收敛；研究方向对 prompt 措辞敏感；中间 cycle 不支持人类介入（但作者视 scientist-in-the-loop 为未来方向）。

## 相关

- **相关概念**：[[World-Model]]、[[Multi-Agent-System]]、[[LLM-Agent]]、[[Literature-Search]]、[[Hypothesis-Generation]]
- **同公司前作**：Robin（therapeutics-focused 前身系统）、PaperQA2、Finch
- **同类系统**：[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]
- **同主题**：[[Auto-Research]]
