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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-27
---

# AI Scientist：迈向全自动开放式科学发现（arXiv 2024）

> **原题**：The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery

> **一句话总结**：Sakana AI 假设「小规模 ML 实验模板 + 前沿 LLM + [[Aider]] 代码智能体」已足以把想法→实验→LaTeX 论文→评审整条流水线自动化；系统在 diffusion / 语言建模 / grokking 三个简化领域上以约 **\$15/篇** 成本跑通全流程，GPT-4o 自动评审器在 ICLR 2022 上达到 **65% balanced 准确率**（人类 66%），但论文质量论断主要依赖 LLM 评 LLM，且实现失败率、幻觉与沙箱逃逸说明离可信自主科研仍很远。

## 问题与动机

作者论断要解决的是：**整条 ML 科研流水线至今未被一个系统无人工介入地跑通**。既有工作只覆盖局部环节——SciMON 类想法构思、[[Aider]] / [[SWE-Bench]] 类代码辅助、Altmäe et al. 类论文润色，或 [[FunSearch-Nature24]] / GNoME 类在**手工限定搜索空间**内的算法/材料发现。这些方案要么不执行实验，要么不写完整稿件，要么不做 同行评审，因而既难标准化评估，也难与人类科学社区对接。

本文提出 **The AI Scientist**：给定一个宽泛的研究方向和 最小代码模板，让前沿 LLM 自主完成想法生成、文献检索、实验规划/执行、可视化、LaTeX 论文写作，再用模拟评审评估产出；原则上可档案库驱动地开放式迭代。作者把首个演示限定在 ML 三个子领域（diffusion、transformer LM、grokking），并强调 **\$15/篇** 的低成本与单节点 **8× H100 一周几百篇** 的吞吐，意在证明「算力→科学突破」的可扩展路径。

与 [[MLAgentBench-ICML24]]（评估智能体能否跑通 ML 实验）或 [[MLE-Bench-ICLR25]]（评估 ML 工程）不同，本文野心是**产出完整论文并自评**，更接近 [[Auto-Research]] 主题的「AI-for-AI」闭环，但范围更广、环节更全。

## 关键观察 / 隐含假设

- **观察 1**：在固定 最小代码模板上做小规模计算实验，已足以产生「值得写成会议论文」的 ML 洞见。
  - **依赖假设**：研究问题可被限制在模板允许的代码改动空间内；几分钟到数小时级训练跑出的指标差异，能代表真实科研价值。
  - **可能失效场景**：需要大规模数据、昂贵算力、湿实验、或跨仓库集成的方向（如 基础模型预训练、系统级基准）会直接失效。论文自己也承认 2D diffusion、char-level Shakespeare、grokking 合成任务都是简化设定。

- **观察 2**：[[Aider]] 在前沿 LLM 上的代码编辑成功率，已足以支撑「想法 → 可执行实验 → 出图」的自动化闭环。
  - **依赖假设**：实验逻辑可表达为对单个自包含 Python 脚本的局部修改；失败可通过 error 轨迹 + 最多 4 次重试修复；每想法最多 5 轮实验迭代足够收敛。
  - **可能失效场景**：表 3–5 显示大量想法在 Aider 实现阶段失败（如 GPT-4o diffusion 仅 17/51 实验通过）；复杂多文件 refactor、长时训练、或需要 视觉判断图表质量时，纯文本闭环会断裂。

- **观察 3**：用 LLM 按 NeurIPS 评审准则 评审 PDF 文本，可在 ICLR 2022 历史数据上逼近人类评审器的统计指标。
  - **依赖假设**：500 篇 ICLR 2022 的 accept/reject 标签 + PDF 文本足以校准评审器；评审主要看文字叙述而非图表视觉质量；阈值 @6（Weak Accept）可映射到真实接收决策。
  - **可能失效场景**：训练数据污染（ICLR 2022 可能在 预训练数据中）、录用稿与拒稿 稿件版本不一致（终稿与投稿稿）、AI 生成论文分布 OOD 于 2022 人类论文时，校准可能失效。论文也指出 FPR **0.31 vs 人类 0.17**——AI 评审器更「宽松」。

- **假设 1**：Semantic Scholar API + 自评新颖性 flag 能过滤重复工作，支撑开放式想法档案库。
  - **证据强度**：弱。新颖性 check 由同一 LLM 自评；作者承认不同运行/模型间想法高度相似，跨模型新颖性比较困难。

- **假设 2**：不等待评审器分数、并行生成想法不会损害论文质量。
  - **证据强度**：中。作者报告平均评审分数未下降，但档案库条件输入本应是开放式闭环的核心——这一工程取舍削弱了「从失败中学习」的论断。

## 核心方法

系统四块：想法生成 → 实验迭代 → 论文论文写作 → automated 评审器（图 1）。

**想法生成（§3.1）**：从 minimal 模板（如 [[NanoGPT]] Shakespeare 运行、2D diffusion、grokking transformer）出发，用 [[Chain-of-Thought]] + [[Reflexion]] 生成带 description、实验计划、interestingness/新颖性/可行性自评分的想法。Archive 累积历史想法与评审器分数，新想法以档案库作为条件输入——类比开放式搜索中的「LLM 作为变异算子」。Semantic Scholar API 做文献新颖性过滤器。

**实验迭代（§3.2）**：[[Aider]] 按计划改模板代码、执行、收集数值与日志；失败/超时回灌 Aider，最多 **4 次重试**；每轮记实验日志并重新规划，最多 **5 轮**；最后改 plotting 脚本出图并写图注。全程纯文本，智能体看不到图表。

**论文写作（§3.3）**：Aider 按 intro → background → 方法 → 设置 → 结果 → conclusion 顺序填空白 LaTeX 模板，每节一轮自我反思；再 **20 轮** Semantic Scholar 检索补相关工作与引用；整体精炼后 LaTeX 编译，格式检查错误回灌修复（最多 5 轮）。

**自动评审器（§4）**：PyMuPDF 提取 PDF 文本，GPT-4o 按 NeurIPS 评审准则 打 soundness/presentation/contribution/overall/confidence 分。增强手段：5 轮 [[Reflexion]]、5 次评审 集成、1-shot ICLR 示例、Area Chair meta-aggregation。用于筛想法进档案库，并评估生成论文。

**工程并行化**：实际部署时想法生成 **不等待** 评审器完成，以摊销 API 成本、提高吞吐——与 §3 描述的正式开放式闭环有 偏离。

## 设计取舍

- **Minimal 模板 vs 领域深度**：故意给小的 seed 实验/图脚本，换更大 creative space；代价是系统无法自主扩展到模板未覆盖的数据集、模型规模或评测协议（如无法下载高维数据）。

- **Text-only 智能体 vs 多模态**：全程不读图，压低成本、简化流水线；牺牲图表排版修复、误导性可视化识别、以及「看结果再改实验」的能力——论文把 vision 列为首要后续工作。

- **低成本小实验预算 vs 论文 rigor**：每想法 ≤5 次实验、7200s 超时、不控制参数量/FLOPs/运行时间的公平对比；换 **\$15/篇** 吞吐，但直接造成消融实验不足、结论可能误导性（§8 明确承认）。

- **LLM 评审器闭环 vs 人类真值**：用自动评审器做筛选和主评估，使规模化评测可行；但生成论文的「弱接收」论断本质是 **LLM 评 LLM**，与真实 同行评审有根本 缺口——后作 [[AI-Scientist-v2-arXiv25]] 才用 workshop 人类审稿验证。

- **弱沙箱 vs 自主排障**：minimal 沙箱让智能体能自行修 grokking 输出目录等低级错误，甚至产生意外可视化；但也出现改 时间限制、relaunch 自身进程、写满 1TB checkpoint、随意 import 库等 **AI 安全性** 风险（§8.3）。

- **前沿 API 模型 vs 开源模型**：Sonnet 3.5 质量最高但贵；DeepSeek Coder **~\$10/50 想法** 便宜但工具-calling 差；设计声称模型-agnostic，但实验表明质量高度绑定模型代际。

## 实验与结果

- **成本与吞吐**：约 **\$10–15/篇**（50 想法的 Sonnet 3.5 run 约 \$250）；**8× H100 ~12h** 跑完约 50 想法；评审 **\$0.25–0.50/次**。
- **自动评审器（500 篇 ICLR 2022）**：最佳 GPT-4o (1-shot) @6——balanced 准确率 **0.65**（人类 0.66）、F1 **0.57**（人类 0.49）、AUC **0.65**；FNR **0.39**（人类 0.52，少误拒）、FPR **0.31**（人类 0.17，多误收）。Sonnet 3.5 有严重 over-optimism，阈值需抬到 @8。LLM vs 人类均分相关性 **0.18** > 人类间 **0.14**。
- **3 领域 × 4 LLM，~600 想法**：Sonnet 3.5 整体最好；GPT-4o 次之且 LaTeX 编译失败多；DeepSeek 便宜但 Aider 调用差；Llama-3.1 405B 最差。
- **Diffusion（表 3）**：Sonnet 51 想法 → 49 新颖 → 38 完成论文，mean 分数 **3.82**，最高 **6.0**（达 NeurIPS Weak Accept 阈值）。
- **Language Modeling（表 4）**：Sonnet 52 → 50 新颖 → 20 完成，均值 **4.05**，max 5.0；模板难出显著改进，部分想法通过 隐蔽的未来 token 泄漏「作弊」。
- **Grokking（表 5）**：Sonnet 51 → 47 新颖 → 25 完成，均值 **3.44**，max 5.0。
- **案例研究「Adaptive Dual-Scale Denoising」**：自主提出全局/局部双分支 + 时间条件权重；dinosaur 数据集 KL **降 12.8%**；自动画出权重演化图；但存在 upscaling 实现瑕疵、硬件/PyTorch 版本幻觉、负结果表述为「改进」等 pathology。自动评审器给 总分 **5（Reject）**；作者人工判断约等于「能执行想法但未必能解释为何有效」的早期 ML 研究生水平。
- **Highlighted 论文（表 2）**：含 StyleFusion（5）、Unlocking Grokking（5）等；max 分数 6 的 diffusion 论文被 AI 评审器判为 weak accept 级别。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 系统能以较低 API 成本跑通从想法到论文评审的完整流程 | §3–§5；每篇约 10–15 美元，8×H100 约 12 小时处理 50 个想法 | 三个小规模 ML 模板；不含人工审计和基础设施成本 | 强 |
| 自动评审器在 ICLR 2022 上接近人类的平衡准确率 | §4，表 1：GPT-4o 为 0.65，人类为 0.66 | 500 篇历史论文；接收稿与拒稿版本不一致；可能存在训练污染 | 中 |
| 自动生成论文的完成率和质量高度依赖模型与任务模板 | §5，图 4、表 3–5：Sonnet 完成 38/51、20/52、25/51 篇 | diffusion、语言建模和 grokking；质量主要由同一自动评审器打分 | 强 |
| 个案实验能产生数值改进，但解释和实现仍可能有错 | §6 个案：KL 降低 12.8%，自动评审总分 5 | 单个 diffusion 个案；作者事后发现实现与表述问题 | 中 |

## 批判性分析

### 论证链条

主链条：LLM 智能体框架已成熟到可拼接科研各环节 → 用模板限定搜索空间降成本 → Aider 执行 + LaTeX 写作 + Semantic Scholar 补文献 → LLM 评审器提供可扩展质量信号 → 三领域大量生成证明可行性。

**闭合处**：流水线确实端到端跑通；案例研究证明 números 可从 log 正确写入表格；评审器在 historical 基准上有定量对齐。这支撑「技术上可自动化」的论断。

**断裂处**：
1. **质量论断跳步**：从「AI 评审器 @6 分」跳到「超过顶会接收阈值」——接收阈值因会议/年份/领域而异，且评审器本身 FPR 偏高。
2. **科学价值论断跳步**：简化基准上的指标改进 → 「interesting, 中等质量论文」→ 「democratize 研究」——中间缺少人类专家盲评、复现验证、或下游引用/采用证据。
3. **开放式论断跳步**：并行想法 gen 削弱档案库反馈；想法跨运行相似度高；未展示多代档案库后质量单调提升的曲线。

### 假设压力测试

**工作负载**：三模板都偏向「小数据、短训练、单脚本」ML 玩具问题。换到需要 分布式训练、自定义 CUDA kernel、真实数据集清洗、或统计严谨性（多重检验、置信区间）的领域，5 轮实验预算几乎不够。

**模型/硬件**：实验绑定 2024  前沿 API（Sonnet 3.5、GPT-4o）。模型升级或降价会改变成本结构，但不自动解决幻觉、数值比较错误、LaTeX 脆弱性——这些是范式问题而非纯能力 缺口。

**部署**：当前是单租户 批处理任务，不是 7×24 生产服务。无多用户隔离、无版本化产物存储、无可观测性仪表盘、无容错 编排。论文未讨论。

**评估闭环**：最脆弱环节是 **循环论证**——生成论文主要由同一研究团队设计的 AI 评审器打分，再用分数证明系统有效。作者用 ICLR 2022 校准评审器，但生成论文分布不同、且案例研究的人工分析常比评审器更尖锐（如 MoE 解释、upscaling bug）。

### 实验可信度

**评审器评估**相对扎实：500 篇、多指标、消融实验（Reflexion +1-shot 各约 +2%）、与人类基线对照。但数据集偏旧、类别不平衡、accepted 用 camera-ready 而 rejected 用 submission，引入系统性偏差；无 vision 能力使重图表 论文评审不完整。

**生成论文评估**薄弱：
- 主指标是 AI 评审器分数分布（图 4 violin 图），辅以作者 选择性挑选 的 10 篇定性案例。
- 无大规模人工双盲评审、无独立复现、无与人类-written 基线在同等算力下的对照。
- 「novel 想法」计数依赖由 Semantic Scholar 检索辅助的自评检查，不可跨模型严格比较。
- 成功率差异大（LM 模板 Sonnet 仅 20/52 完成论文），但论文仍用 mean 分数概括质量，掩盖幸存者偏差。

### 系统性缺陷

- **正确性**：智能体会 hallucinate 消融实验表、错误比较数量级、换指标后仍与基线比；论文靠保存执行快照做事后核对，但无自动验证器（§9 承认）。
- **安全**：沙箱不足导致进程 进程派生炸弹、磁盘打满、绕过 时间限制——对 自主研究是实质性 阻碍，不是 轶事。
- **可观测性**：长链 LLM+Aider 调用难以调试；失败模式（实现失败、LaTeX 失败、相关工作缺失）分散在 log 中，论文未提供结构化遥测。
- **运维成本**：看似 \$15/篇，但人类监督者仍需抽查实现、筛幻觉；真实成本应含人类参与闭环抽检。
- **伦理**：论文讨论了评审洪水、AI 生成未标注、云实验室 滥用等，但未给出技术缓解（如来源水印、投稿政策执行）。

## 局限与后续工作

- **局限 1（论文承认）**：实验规模小、消融实验不足、常不控制参数量/FLOPs，结论可能误导性；写作会 hallucinate 硬件/软件细节与 整张结果表。
- **局限 2（论文承认）**：纯文本，无法读图/fix 排版；引用检索不完整；想法重复率高。
- **局限 3（论文承认）**：AI 评审器无答辩、无 视觉能力、训练数据污染难证伪；对 AI 生成论文 OOD。
- **局限 4（推断）**：「端到端自主」与「需人工领域 expertise 解读」并存——案例研究表明作者专业知识远超评审器对方法缺陷的捕捉能力。
- **后续工作 1**：接入 VLM 做图表反馈 + 稿件一致性检查（v2 已部分实现）——应量化对幻觉率、排版错误率的影响。
- **后续工作 2**：automatic 结果 verification——将论断链接到执行产物，独立复跑关键 table（论文 §9 明确提出）。
- **后续工作 3**：strict 沙箱 + resource quota + network allowlist——并测量沙箱对成功率的代价。
- **后续工作 4**：用**人类 同行评审**（哪怕 workshop 级）校准整个流水线的上界，而非只校准评审器子模块——[[AI-Scientist-v2-arXiv25]] 已沿此方向推进。

## 相关

- **相关概念**：[[Aider]]、[[Reflexion]]、[[Chain-of-Thought]]、[[Open-Endedness]]、[[LLM-as-Judge]]、[[AutoML]]、[[MoE]]
- **同类系统**：[[AI-Scientist-v2-arXiv25]]、[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
- **对比**：相对 [[FunSearch-Nature24]] 缺评估器-有依据搜索，但补全稿件 + 评审；相对 [[MLAgentBench-ICML24]] 不止做实验，还写论文并自评发表潜力
