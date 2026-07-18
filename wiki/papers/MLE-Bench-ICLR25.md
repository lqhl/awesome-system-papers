---
type: paper
name: MLE-Bench
full_title: "MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering"
authors: [Jun Shern Chan, Neil Chowdhury, Oliver Jaffe, James Aung, Dane Sherburn, Evan Mays, Giulio Starace, Kevin Liu, Leon Maksin, Tejal Patwardhan, Lilian Weng, Aleksander Madry]
venue: ICLR
year: 2025
tags: [benchmark, ml-engineering, kaggle, agent, evaluation]
source_pdf: "[[2410.07095v2.pdf]]"
source_md: "[[2410.07095v2]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering (ICLR 2025)

> **一句话总结**：OpenAI 假设「75 场人工精选 Kaggle 竞赛 + 与 private leaderboard 对齐的 medal 判定」能代表端到端 ML engineering 能力；在固定 24h/A10 沙箱下，最强 compound system（o1-preview + AIDE [[Agent-Scaffold]]）pass@1 仅 16.9% 得奖率（平均 7 枚金牌），pass@8 涨到 34.1%，但 agent 大量无效提交、几乎不会用第二张 GPU，且 scaffold 选择对分数的影响远大于 backbone 模型。

## 问题与动机

[[HumanEval]]、MBPP 等 coding benchmark 已饱和；[[SWE-Bench]] 把评测聚焦在「修真实 GitHub PR」，但仍缺一个**端到端自主 ML engineering** 标尺——训练模型、准备数据、跑实验、调试失败、产出可评分提交。这类能力直接关系到 AI R&D acceleration 风险建模（OpenAI Preparedness Framework、Anthropic RSP、Google DeepMind Frontier Safety 都需要可量化的 autonomy 指标）。

已有尝试各有缺口：[[MLAgentBench-ICML24]] 只有 13 个任务且 success 定义为「比 baseline 高 10%」；Weco AI 的 AIDE 自报在 Kaggle 上击败 >50% 人类但数据集不公开；DSBench 偏向 tabular data science 且自动化筛选会丢掉非标准格式竞赛。作者 claim：**MLE-bench 用 75 场人工移植的 Kaggle 竞赛 + 人类 medal 阈值，首次在难度、多样性和人类可比性上同时做到规模化**。

## 关键观察 / 隐含假设

- **观察 1**：Agent 在「问题清晰、数据干净、metric 固定」的 Kaggle 式任务上，medal 率与 human private leaderboard 可对齐，且能区分 scaffold 与模型差异。
  - **依赖假设**：手工重切的 train/test 分布与原始竞赛一致；private leaderboard 快照能代表当时人类水平；medal 阈值跨竞赛可比。
  - **可能失效场景**：竞赛格式高度非标、test 无法重建、或 agent 使用比当年参赛者更新的库/模型时，human 对比会失真。
- **观察 2**：**Scaffold 对最终 medal 率的影响远大于 backbone LM**——同为 GPT-4o，AIDE 8.7% vs [[OpenHands-ICLR25]] 4.4% vs MLAB 0.8%；AIDE 会在 24h 内持续 tree search 到 500 nodes 上限，而通用 scaffold 常几分钟就结束。
  - **依赖假设**：评测的是「model + scaffold」compound system，而非孤立模型能力；AIDE 的 Kaggle 专精启发式可迁移到其他竞赛。
  - **可能失效场景**：换到非 Kaggle 风格的 open-ended R&D（无清晰 metric、需自己定义数据集）时，AIDE 优势可能急剧缩小。
- **观察 3**：**多次尝试与时间预算可显著「买分」**——o1-preview pass@1 16.9% → pass@8 34.1%；GPT-4o 24h 8.7% → 100h 11.8%；但 **GPU 数量几乎不影响**（1×A10 8.7% vs 2×A10 10.2%，agent 基本不用第二张卡）。
  - **依赖假设**：当前瓶颈在推理、调试与实验规划，而非 raw training throughput；pass@k 外推对部署场景有意义。
  - **可能失效场景**：高复杂度竞赛若需要大规模分布式训练，固定单机 A10 设定会系统性低估「能调动集群的 agent」。
- **假设 1**：Pre-training contamination 未系统性抬高 GPT-4o 分数（familiarity 与 performance 无相关；obfuscate 描述后 8.5% vs 8.4%）。
  - **证据强度**：**中**——只测了 GPT-4o，且只能排除「死记讨论帖/竞赛名」式污染，无法排除高层策略记忆。

## 核心方法

**Benchmark 本体（75 + 7 dev）**：从 Meta Kaggle 5673 场筛到 586 场，经 ML 工程师双人 screening 后保留 75 场（22 Low / 38 Medium / 15 High 复杂度）+ 7 场 dev split。每场包含：竞赛描述、数据集（原 split 或手工重切）、本地 grading code、Kaggle **private** leaderboard 快照。复杂度按「有经验 ML 工程师不含训练时间需多久出 sensible solution」人工标注。

**Medal 作为 headline metric**：完全复用 Kaggle 按参赛队伍数动态调整的铜/银/金阈值（如 1000+ teams：bronze top 10%、silver top 5%、gold top 0.2%+10）。**Any Medal %** = 获得任意奖牌的竞赛占比——作者刻意选了一个 ceiling 极高的指标（历史上仅 9 人曾在 75 场不同竞赛都拿牌）。

**反作弊层**：submission 必须由独立 model 生成（禁止 agent 手写标签）；禁止在线查解法；GPT-4o mini 审 log 查 rule-breaking；Dolos 对比 Kaggle top-50 notebook，>60% 代码相似 disqualify。另提供本地 validation server（只验格式不给分数）。

**执行环境**：Ubuntu 20.04 Docker（sysbox），36 vCPU / 440GB RAM / 4095 GiB SSD / 1×24GB A10，每竞赛最多 24h，默认 3 seeds。评测三种开源 [[Agent-Scaffold]]：AIDE（Kaggle 专精 tree search）、MLAgentBench ResearchAgent（MLAB）、OpenHands CodeActAgent。

## 设计取舍

- **人工移植 vs 自动化生成**：75 场全部手工 port，换得多样性与 grading 可信度，但维护成本高、难持续更新。
- **Private leaderboard + 重切 test**：避免 public leaderboard overfit，但引入「分数与人类原始竞赛不完全可比」的 interpretability 成本。
- **Medal % 聚合 vs raw score**：跨竞赛可比、对人类直观，但丢失细粒度进步信号，且 pass@k / 长时运行会改变 metric 含义。
- **固定资源上限（24h, 1×A10）**：保证可复现与成本可控（单次全量 ≈ 1800 GPU-hours + 巨量 token），但与真实 Kaggle（数周、自选硬件、ensemble）差距大。
- **边界条件**：在「经典 supervised ML pipeline + CSV 提交」类竞赛上设计优雅；对需要外部数据下载、非 CSV 交付、或开放式研究问题的覆盖弱。

## 实验与结果

- **Scaffold（GPT-4o）**：AIDE 8.7% any medal > OpenHands 4.4% > MLAB 0.8%；valid submission 率 AIDE 54.9% 仍不高，大量 run 连格式正确提交都没产出。
- **Model（均用 AIDE）**：o1-preview **16.9%** > GPT-4o 8.7% > Claude-3.5-Sonnet 7.6% > Llama-3.1-405B 3.0%；o1-preview 平均 **7 枚金牌**（Kaggle Grandmaster 门槛 5 金），但竞赛集合与原始 Kaggle 不完全一致。
- **Pass@k**：o1-preview pass@8 **34.1%**（约为 pass@1 的 2×）；GPT-4o pass@6 17.0% ≈ o1-preview pass@1。
- **Compute scaling**：CPU-only 9.1% / 1×A10 8.7% / 2×A10 10.2%——agent 几乎不感知硬件差异。
- **Time scaling**：GPT-4o 100h 11.8% vs 24h 8.7%；前 2h 已拿到大部分奖牌，之后缓慢累积，且 AIDE 的「best attempt」选择不完美会导致奖牌数暂时下降。
- **Contamination**：GPT-4o familiarity 与归一化得分无相关；obfuscated 描述 8.4% vs 原版 8.5%；medal 提交无 Dolos 抄袭、无经人工确认的 rule-breaking。
- **成本**：o1-preview + AIDE 单 seed 跑 75 场平均 **127.5M input + 15.0M output tokens**。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| MLE-bench distinguishes the tested scaffolds | GPT-4o: AIDE any-medal 8.7%, OpenHands 4.4%, MLAB 0.8% (Table 2) | modified scaffolds, 75 tasks, 24h/1×A10 | high |
| o1-preview improves AIDE medal rate | 16.9±1.1% vs GPT-4o 8.7±0.5%, Claude 7.6±1.8%, Llama 3.0±1.0% (Table 2) | compound AIDE system; unequal seed counts | high |
| Repeat attempts raise estimated success | o1 AIDE pass@1 16.9%→pass@8 34.1% (Fig.3) | multi-seed pass@k estimate, not one deployment | high |
| Extra GPU gives no reliable measured gain | CPU 9.1±1.0%, 1×A10 8.7±0.5%, 2×A10 10.2±2.0% (Table 3) | GPT-4o+AIDE; CPU/2-GPU only 3 seeds | high |
| Contamination probe shows little difference for this model | original 8.5±0.6% vs obfuscated 8.4±1.0% (Table 4) | GPT-4o+AIDE, 10 seeds; not a general contamination proof | high |

## Critical Analysis

### 论证链条

作者从「缺 holistic ML engineering benchmark」→「Kaggle + human medal 可对齐」→「前沿 agent 已能拿牌」的链条基本闭合，但中间有两处跳步：(1) **16.9% medal 率是否意味着「接近人类 ML 工程师」**——实际上绝大多数竞赛仍未得奖，且 pass@k 与 100h 预算显著抬高分数；(2) **「o1-preview 平均 7 金 ≈ Grandmaster」**是 PR 式类比，论文自己也列出 modified dataset、更新工具链、时间预算不同等 caveat，不宜直接外推为 production-ready autonomy。

Scaffold 实验反而证明：**当前分数大量来自 engineering 层（AIDE 的持续搜索与 submission 追踪）**，不是 pure LM reasoning 的进步；这与 [[MLAgentBench-ICML24]] 中「prompt 结构决定幻觉率」的结论是同一类现象。

### 假设压力测试

- **Human 可比性**：重切 test、本地 reimplement grading、agent 可用 2024–2025 年更强的库和模型——三重因素都会让「超过当年 Kaggle 中位数」比看起来更容易或更难，论文只抽样验证了 sample/gold submission 一致性，**未系统量化整体 leaderboard 偏移**。
- **任务代表性**：筛选偏向「描述清晰、可本地评分、CSV 提交」的竞赛，**系统性排除**了真实 AI R&D 里「问题本身未定义、metric 需发明」的阶段；与 [[MLR-Bench-arXiv25]] 关注的 workshop 级研究任务也仅有部分重叠。
- **Scaffold 依赖**：换用未针对 Kaggle 调优的 scaffold，GPT-4o 可能从 8.7% 跌到 <1%（MLAB 已展示）；未来榜单若不固定 scaffold 报告规范，横向比较困难。
- **Contamination**：实验仅覆盖 GPT-4o；对 o1-preview 及后续更强模型，**高层策略记忆**仍无法被 familiarity/obfuscation 实验排除。

### 实验可信度

- **Benchmark 代表性**：75 场跨 NLP/CV/signal 等 15 类问题，奖金总额 $1.95M，比 [[MLAgentBench-ICML24]]/DSBench 更广，但仍是 **Kaggle 生态子集**，非工业界长周期 ML 项目。
- **Baseline 公平性**：三种 scaffold 都经作者 patch（Appendix A.6），且 AIDE 使用 GPT-4o 作 feedback model——**compound system 调优投入不均**；未与 Weco 原始 AIDE 数字直接同设定对比。
- **Ablation**：pass@k、time、hardware、obfuscation 实验支持「资源可换分、硬件不敏感、污染不显著」等 claim；但缺少「去掉 validation server / 去掉 plagiarism detector」对分数的影响消融。
- **Metric 覆盖**：主指标是 medal %，辅以 valid submission%、above median%；**未报告 tail latency、成本 per medal、或人工介入次数**。

### 系统性缺陷

- **工程可靠性**：最佳配置 valid submission 仅 82.8%，common failure 包括不用 validation server、OOM/disk 打满被 kill、不估算训练时长——说明 agent 离「稳健自主工程师」还差一个数量级。
- **资源隔离与可观测性**：Docker + sysbox 集群执行，但论文未讨论多租户隔离、失败恢复、或 trajectory 的可复现 replay 标准。
- **评测成本**：全量 benchmark 极贵，可能迫使社区只跑子集或 dev split，削弱「75 场 holistic」初衷。
- **运维与兼容性**：grading 逻辑手工维护，Kaggle 规则或数据 license 变更时的持续维护路径论文未讨论。

## 局限与 Future Work

- **局限 1**：公开 Kaggle 材料带来的 train-time contamination 无法完全消除；规则检测与 Dolos 挡不住「记住高层特征工程思路」。
- **局限 2**：任务覆盖 AI R&D 全流程中的一段——有清晰 problem statement 的 predictive modeling，不覆盖「定义问题、构建数据集、设计训练 infra」。
- **局限 3**：与原始 Kaggle 的 split/grading 差异使 human 对比只能近似；算法进步会让旧竞赛对现代 agent 变简单，复杂度标注需动态更新。
- **Future work 1**：定期加入新竞赛 + 私有 holdout，用 **ConStat 类 performance-based contamination detection** 监控分数是否随训练数据更新异常跳涨。
- **Future work 2**：在固定 scaffold 下分离「规划/调试/训练调度」子能力，测量 agent 对多 GPU、长训练 job、失败恢复的策略质量，而非只看最终 medal。
- **Future work 3**：与 [[MLR-Bench-arXiv25]] 互补——前者测 Kaggle 式 engineering，后者测 workshop 论文复现与科研诚信（如 fabricated results）。

## 相关

- **相关概念**：[[Agent-Scaffold]]、[[Pass@k]]、Contamination Detection、Kaggle Competitions
- **同类系统**：[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[SWE-Bench]]、DSBench、GAIA、AgentBench
- **相关 scaffold / 下游**：AIDE、[[AI-Scientist-v2-arXiv25]]（借鉴 AIDE 式 tree search）、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
