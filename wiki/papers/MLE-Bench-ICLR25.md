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
last_reviewed: 2026-07-27
---

# MLE-bench：评测机器学习智能体的工程能力（ICLR 2025）

> **原题**：MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering

> **一句话总结**：OpenAI 假设「75 场人工精选 Kaggle 竞赛 + 与 private 排行榜对齐的 medal 判定」能代表端到端 ML 工程能力；在固定 24h/A10 沙箱下，最强 compound 系统（o1-preview + AIDE [[Agent-Scaffold]]）pass@1 仅 16.9% 得奖率（平均 7 枚金牌），pass@8 涨到 34.1%，但智能体大量无效提交、几乎不会用第二张 GPU，且脚手架选择对分数的影响远大于 backbone 模型。

## 问题与动机

[[HumanEval]]、MBPP 等编程基准已饱和；[[SWE-Bench]] 把评测聚焦在「修真实 GitHub PR」，但仍缺一个**端到端自主 ML 工程** 标尺——训练模型、准备数据、跑实验、调试失败、产出可评分提交。这类能力直接关系到 AI R&D acceleration 风险建模（OpenAI Preparedness 框架、Anthropic RSP、Google DeepMind 前沿 Safety 都需要可量化的 autonomy 指标）。

已有尝试各有缺口：[[MLAgentBench-ICML24]] 只有 13 个任务且成功定义为「比基线高 10%」；Weco AI 的 AIDE 自报在 Kaggle 上击败 >50% 人类但数据集不公开；DSBench 偏向 tabular 数据 science 且自动化筛选会丢掉非标准格式竞赛。作者论断：**MLE-bench 用 75 场人工移植的 Kaggle 竞赛 + 人类 medal 阈值，首次在难度、多样性和人类可比性上同时做到规模化**。

## 关键观察 / 隐含假设

- **观察 1**：智能体在「问题清晰、数据干净、指标固定」的 Kaggle 式任务上，medal 率与人类 private 排行榜可对齐，且能区分脚手架与模型差异。
  - **依赖假设**：手工重切的训练/测试分布与原始竞赛一致；private 排行榜快照能代表当时人类水平；medal 阈值跨竞赛可比。
  - **可能失效场景**：竞赛格式高度非标、test 无法重建、或智能体使用比当年参赛者更新的库/模型时，人类对比会失真。
- **观察 2**：**脚手架对最终 medal 率的影响远大于 backbone LM**——同为 GPT-4o，AIDE 8.7% vs [[OpenHands-ICLR25]] 4.4% vs MLAB 0.8%；AIDE 会在 24h 内持续 tree 搜索到 500 nodes 上限，而通用脚手架常几分钟就结束。
  - **依赖假设**：评测的是「模型 + 脚手架」compound 系统，而非孤立模型能力；AIDE 的 Kaggle 专精启发式可迁移到其他竞赛。
  - **可能失效场景**：换到非 Kaggle 风格的开放式 R&D（无清晰指标、需自己定义数据集）时，AIDE 优势可能急剧缩小。
- **观察 3**：**多次尝试与时间预算可显著「买分」**——o1-preview pass@1 16.9% → pass@8 34.1%；GPT-4o 24h 8.7% → 100h 11.8%；但 **GPU 数量几乎不影响**（1×A10 8.7% vs 2×A10 10.2%，智能体基本不用第二张卡）。
  - **依赖假设**：当前瓶颈在推理、调试与实验规划，而非原始训练吞吐；pass@k 外推对部署场景有意义。
  - **可能失效场景**：高复杂度竞赛若需要大规模分布式训练，固定单机 A10 设定会系统性低估「能调动集群的智能体」。
- **假设 1**：预训练污染未系统性抬高 GPT-4o 分数（familiarity 与性能无相关；obfuscate 描述后 8.5% vs 8.4%）。
  - **证据强度**：**中**——只测了 GPT-4o，且只能排除「死记讨论帖/竞赛名」式污染，无法排除高层策略记忆。

## 核心方法

**基准本体（75 + 7 dev）**：从 Meta Kaggle 5673 场筛到 586 场，经 ML 工程师双人 screening 后保留 75 场（22 Low / 38 Medium / 15 High 复杂度）+ 7 场 dev split。每场包含：竞赛描述、数据集（原 split 或手工重切）、本地 grading 代码、Kaggle **private** 排行榜快照。复杂度按「有经验 ML 工程师不含训练时间需多久出 sensible solution」人工标注。

**Medal 作为 headline 指标**：完全复用 Kaggle 按参赛队伍数动态调整的铜/银/金阈值（如 1000+ teams：bronze top 10%、silver top 5%、gold top 0.2%+10）。**Any Medal %** = 获得任意奖牌的竞赛占比——作者刻意选了一个 ceiling 极高的指标（历史上仅 9 人曾在 75 场不同竞赛都拿牌）。

**反作弊层**：submission 必须由独立模型生成（禁止智能体手写标签）；禁止在线查解法；GPT-4o mini 审 log 查 rule-breaking；Dolos 对比 Kaggle top-50 notebook，>60% 代码相似 disqualify。另提供本地验证 server（只验格式不给分数）。

**执行环境**：Ubuntu 20.04 Docker（sysbox），36 vCPU / 440GB RAM / 4095 GiB SSD / 1×24GB A10，每竞赛最多 24h，默认 3 seeds。评测三种开源 [[Agent-Scaffold]]：AIDE（Kaggle 专精 tree 搜索）、MLAgentBench ResearchAgent（MLAB）、OpenHands CodeActAgent。

## 设计取舍

- **人工移植 vs 自动化生成**：75 场全部手工 port，换得多样性与 grading 可信度，但维护成本高、难持续更新。
- **Private 排行榜 + 重切 test**：避免 public 排行榜过拟合，但引入「分数与人类原始竞赛不完全可比」的可解释性成本。
- **Medal % 聚合 vs 原始分数**：跨竞赛可比、对人类直观，但丢失细粒度进步信号，且 pass@k / 长时运行会改变指标含义。
- **固定资源上限（24h, 1×A10）**：保证可复现与成本可控（单次全量 ≈ 1800 GPU-hours + 巨量 token），但与真实 Kaggle（数周、自选硬件、ensemble）差距大。
- **边界条件**：在「经典 supervised ML 流水线 + CSV 提交」类竞赛上设计优雅；对需要外部数据下载、非 CSV 交付、或开放式研究问题的覆盖弱。

## 实验与结果

- **脚手架（GPT-4o）**：AIDE 8.7% any medal > OpenHands 4.4% > MLAB 0.8%；valid submission 率 AIDE 54.9% 仍不高，大量运行连格式正确提交都没产出。
- **模型（均用 AIDE）**：o1-preview **16.9%** > GPT-4o 8.7% > Claude-3.5-Sonnet 7.6% > Llama-3.1-405B 3.0%；o1-preview 平均 **7 枚金牌**（Kaggle Grandmaster 门槛 5 金），但竞赛集合与原始 Kaggle 不完全一致。
- **Pass@k**：o1-preview pass@8 **34.1%**（约为 pass@1 的 2×）；GPT-4o pass@6 17.0% ≈ o1-preview pass@1。
- **算力规模扩展**：CPU-only 9.1% / 1×A10 8.7% / 2×A10 10.2%——智能体几乎不感知硬件差异。
- **Time 规模扩展**：GPT-4o 100h 11.8% vs 24h 8.7%；前 2h 已拿到大部分奖牌，之后缓慢累积，且 AIDE 的「best attempt」选择不完美会导致奖牌数暂时下降。
- **Contamination**：GPT-4o familiarity 与归一化得分无相关；obfuscated 描述 8.4% vs 原版 8.5%；medal 提交无 Dolos 抄袭、无经人工确认的 rule-breaking。
- **成本**：o1-preview + AIDE 单 seed 跑 75 场平均 **127.5M input + 15.0M 输出 tokens**。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| MLE-bench 能区分被测脚手架的能力 | GPT-4o 下 AIDE 任意奖牌率 8.7%、OpenHands 4.4%、MLAB 0.8%（表 2） | 修改后的脚手架；75 个任务；24 小时、单张 A10 | 强 |
| o1-preview 提高 AIDE 的奖牌率 | 16.9±1.1%，GPT-4o 为 8.7±0.5%、Claude 为 7.6±1.8%、Llama 为 3.0±1.0%（表 2） | 复合 AIDE 系统；各模型种子数不相等 | 强 |
| 重复尝试能提高估计成功率 | o1+AIDE 的 pass@1 为 16.9%，pass@8 为 34.1%（图 3） | 多种子 pass@k 估计，不代表一次部署 | 强 |
| 增加 GPU 没有带来可靠的实测收益 | CPU 为 9.1±1.0%，单张 A10 为 8.7±0.5%，两张 A10 为 10.2±2.0%（表 3） | GPT-4o+AIDE；CPU 和双 GPU 配置仅 3 个种子 | 强 |
| 污染探针在 GPT-4o 上没有显示明显差异 | 原始描述 8.5±0.6%，混淆描述 8.4±1.0%（表 4） | GPT-4o+AIDE、10 个种子；不能普遍证明不存在污染 | 强 |

## 批判性分析

### 论证链条

作者从「缺 holistic ML 工程基准」→「Kaggle + 人类 medal 可对齐」→「前沿智能体已能拿牌」的链条基本闭合，但中间有两处跳步：(1) **16.9% medal 率是否意味着「接近人类 ML 工程师」**——实际上绝大多数竞赛仍未得奖，且 pass@k 与 100h 预算显著抬高分数；(2) **「o1-preview 平均 7 金 ≈ Grandmaster」**是 PR 式类比，论文自己也列出 modified 数据集、更新工具链、时间预算不同等 caveat，不宜直接外推为生产环境-ready autonomy。

脚手架实验反而证明：**当前分数大量来自工程层（AIDE 的持续搜索与 submission 追踪）**，不是 pure LM 推理的进步；这与 [[MLAgentBench-ICML24]] 中「提示词结构决定幻觉率」的结论是同一类现象。

### 假设压力测试

- **人类可比性**：重切 test、本地 reimplement grading、智能体可用 2024–2025 年更强的库和模型——三重因素都会让「超过当年 Kaggle 中位数」比看起来更容易或更难，论文只抽样验证了样本/gold submission 一致性，**未系统量化整体排行榜偏移**。
- **任务代表性**：筛选偏向「描述清晰、可本地评分、CSV 提交」的竞赛，**系统性排除**了真实 AI R&D 里「问题本身未定义、指标需发明」的阶段；与 [[MLR-Bench-arXiv25]] 关注的 workshop 级研究任务也仅有部分重叠。
- **脚手架依赖**：换用未针对 Kaggle 调优的脚手架，GPT-4o 可能从 8.7% 跌到 <1%（MLAB 已展示）；未来榜单若不固定脚手架报告规范，横向比较困难。
- **Contamination**：实验仅覆盖 GPT-4o；对 o1-preview 及后续更强模型，**高层策略记忆**仍无法被 familiarity/obfuscation 实验排除。

### 实验可信度

- **基准代表性**：75 场跨 NLP/CV/信号等 15 类问题，奖金总额 $1.95M，比 [[MLAgentBench-ICML24]]/DSBench 更广，但仍是 **Kaggle 生态子集**，非工业界长周期 ML 项目。
- **基线公平性**：三种脚手架都经作者 patch（附录 A.6），且 AIDE 使用 GPT-4o 作反馈模型——**compound 系统调优投入不均**；未与 Weco 原始 AIDE 数字直接同设定对比。
- **消融实验**：pass@k、time、hardware、obfuscation 实验支持「资源可换分、硬件不敏感、污染不显著」等论断；但缺少「去掉验证 server / 去掉 plagiarism 检测器」对分数的影响消融。
- **指标覆盖**：主指标是 medal %，辅以 valid submission%、above median%；**未报告尾延迟、成本 per medal、或人工介入次数**。

### 系统性缺陷

- **工程可靠性**：最佳配置 valid submission 仅 82.8%，common 失败包括不用验证 server、OOM/disk 打满被 kill、不估算训练时长——说明智能体离「稳健自主工程师」还差一个数量级。
- **资源隔离与可观测性**：Docker + sysbox 集群执行，但论文未讨论多租户隔离、失败恢复、或轨迹的可复现 replay 标准。
- **评测成本**：全量基准极贵，可能迫使社区只跑子集或 dev split，削弱「75 场 holistic」初衷。
- **运维与兼容性**：grading 逻辑手工维护，Kaggle 规则或数据 license 变更时的持续维护路径论文未讨论。

## 局限与后续工作

- **局限 1**：公开 Kaggle 材料带来的 train-time 污染无法完全消除；规则检测与 Dolos 挡不住「记住高层特征工程思路」。
- **局限 2**：任务覆盖 AI R&D 全流程中的一段——有清晰问题论断的 predictive modeling，不覆盖「定义问题、构建数据集、设计训练 infra」。
- **局限 3**：与原始 Kaggle 的 split/grading 差异使人类对比只能近似；算法进步会让旧竞赛对现代智能体变简单，复杂度标注需动态更新。
- **后续工作 1**：定期加入新竞赛 + 私有留出集，用 **ConStat 类基于性能的污染 detection** 监控分数是否随训练数据更新异常跳涨。
- **后续工作 2**：在固定脚手架下分离「规划/调试/训练调度」子能力，测量智能体对多 GPU、长训练 job、失败恢复的策略质量，而非只看最终 medal。
- **后续工作 3**：与 [[MLR-Bench-arXiv25]] 互补——前者测 Kaggle 式工程，后者测 workshop 论文复现与科研诚信（如编造结果）。

## 相关

- **相关概念**：[[Agent-Scaffold]]、[[Pass@k]]、Contamination Detection、Kaggle Competitions
- **同类系统**：[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[SWE-Bench]]、DSBench、GAIA、AgentBench
- **相关脚手架 / 下游**：AIDE、[[AI-Scientist-v2-arXiv25]]（借鉴 AIDE 式 tree 搜索）、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
