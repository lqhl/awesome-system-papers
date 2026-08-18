---
type: paper
name: AutoScientists
full_title: "AUTOSCIENTISTS: Self-Organizing Agent Teams for Long-Running Scientific Experimentation"
authors: [Shanghua Gao, Ada Fang, Marinka Zitnik]
venue: arXiv
year: 2026
tags: [auto-research, multi-agent, scientific-discovery, long-horizon-agent, llm-agent, ai4science, domain/auto-research, concern/long-horizon]
source_pdf: "[[arxiv26-gao-autoscientists.pdf]]"
source_md: "[[arxiv26-gao-autoscientists]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# AutoScientists：面向长时科学实验的自组织智能体团队（arXiv 2026）

> **原题**：AUTOSCIENTISTS: Self-Organizing Agent Teams for Long-Running Scientific Experimentation

> **一句话总结**：AutoScientists 把长时间运行的科学实验建模为**没有中心规划器的程序搜索**，依靠共享实验状态、同伴批评和动态团队重组，在固定实验算力预算下并行探索。它在 BioML-Bench 的 24 个任务上达到平均排行榜百分位 **74.40%**（比 Autoresearch-style 基线高 8.33 点）；GPT nanochat 达到 val_bpb≈0.978 只需 **34 次而非 65 次**实验；在 ProteinGym 的 217 项测定上，又把 Kermut 的平均 Spearman ρ 从 **0.657 提到 0.700**。

## 问题与动机

[[Auto-Research]] 方向的智能体已能生成假设、写代码、跑实验并根据反馈迭代，但多数系统仍沿**单一研究轨迹**推进，或依赖中心规划器在启动时固定地分解搜索空间。[[MLAgentBench-ICML24|MLAgentBench]]、AIDE、[[Auto-Research-arXiv25|Karpathy Autoresearch]] 等单智能体闭环在短程 ML 工程上有效，却在长时间运行的科学研究中遇到结构性瓶颈：有效方向会随证据变化；失败方向必须被记录，以免重复探索；新假设往往要在分析大量「接近成功但仍失败」的尝试后才浮现。

作者将问题形式化为**长期程序搜索**：给定任务描述、数据集 $D$、评估协议 $\ell_{\mathrm{eval}}$ 和可选初始程序 $p_0$，$n$ 个持久智能体不断提出代码变体，在 $D_{\mathrm{train}}$ 上训练并用 $\ell_{\mathrm{eval}}$ 评估，目标是找到尽可能好的程序 $p^\*$。这与 [[AlphaEvolve-arXiv25|AlphaEvolve]] 的评估器引导进化、[[AI-Scientist-v2-arXiv25|AI Scientist v2]] 的阶段管理树搜索不同——核心论断不是「变异算子更好」，而是**协作结构本身**：在实验预算固定时，如何让多个智能体维持彼此竞争的假设、在停滞后重组，并让失败知识跨团队传播。

## 关键观察 / 隐含假设

- **观察 1**：在长时间运行的实验中，搜索空间该怎样划分，在运行开始时通常并不知道，而且会随实验结果变化。单轨迹智能体容易在已经耗尽的方向上反复微调，错过从未被提出的轴；例如在 GPT 最优程序续跑实验中，Autoresearch 的 100 次尝试从未提出过 query-key normalization order。
  - **依赖假设**：不同研究 direction（architecture / schedule / optimizer / featurization 等）在固定实际时间内可**并行**推进，且并行带来的覆盖率增益大于 coordination overhead。
  - **可能失效场景**：实验强串行、方向间强耦合需顺序消融、或 GPU 预算只允许单实验时，team 并行优势消失（BioML-Bench 评测即被限制为每任务 1×H100 串行）。

- **观察 2**：在 GPU 训练/评估主导的成本结构下，**experimental 算力** 而非 LLM token 是稀缺资源；在消耗 GPU 前用 同伴批评 过滤弱提案，比事后分析失败实验更划算。
  - **依赖假设**：智能体的 critique 能识别明显重复、已登记 dead-end、或与 champion 机制矛盾的提案；forum 讨论不会系统性压制 bold but correct 的方向。
  - **可能失效场景**：critique 质量随 base LLM 波动；高维搜索空间中「看起来合理但实验无效」的提案仍可能漏过；论文未量化 critique 的 false reject rate。

- **观察 3**：stochastic 训练指标下，必须把「噪声带内的提升」与真实改进区分，否则 champion 被随机波动污染会级联误导后续搜索。
  - **依赖假设**：用历史实验估计噪声 σ，Δ > Mσ 直接 promote、0 < Δ ≤ Mσ 需第二 seed 确认，足以控制 false 宣传。
  - **可能失效场景**：σ 估计不准、任务指标非平稳、或 champion 切换改变后续实验的基线分布时，gate 可能过松或过严。论文未报告宣传 gate 的误接受/误拒绝率。

- **假设 1**：去中心化自组织（无 manager 智能体、roster 由 discussion 投票形成）在 long horizon 上优于固定 role 流水线或共识收敛式辩论。
  - **证据强度**：**中**——消融实验显示移除 self-organization 在 GPT optimization 上最伤（val_bpb 0.9777→0.9833），但四个组件在不同任务上各为主导因素，说明没有单一机制普适成立。

- **假设 2**：共享状态（champion、实验 log L、forum F、dead-end registry D_k、跨团队可读 queue）是避免重复探索的关键，而非更多智能体数量本身。
  - **证据强度**：**中偏强**——独立智能体消融实验在 Cell-Cell Communication 上 Odds Ratio 从 0.924 跌至 0.435，为最大比例降幅；但正确性依赖智能体遵守 markdown/JSON 协议，而非强类型运行时间保证。

## 核心方法

AutoScientists 部署 n 个长时间运行智能体（默认 **3 analyst + 6 实验**），由确定性 monitor 以 heartbeat 循环唤起；每个智能体读共享状态 S 后自主行动，**无中心 orchestrator 智能体**。系统在 **discussion phase** 与 **执行 phase** 间交替，全程由 S 协调而非规划器派单。

**讨论与自组织（Discussion & self-organization）**：冷启动时没有团队，也没有预设方向。每轮讨论中，智能体读取任务、$p^\*$ 和论坛，分别提出修改、批评竞争方案并识别搜索缺口；多数智能体提交 `[DISCUSS-DONE]` 后，最后一名分析智能体将提案汇总为团队表 $R=\{(T_k, axis_k, members_k)\}$ 并写入共享状态 $S$。停滞（如连续 10 次实验无改进）会触发重新讨论，团队可以创建、合并、拆分或退休，变更需得到受影响团队的同意。

**Execution & 角色分工**：每个 team 持续 propose-execute 闭环：
- **Analyst**：audit 未测参数、按历史效应量排序提案、维护 empirical axis priors，向 queue Q_k 投递实验；champion 更新后分析「什么特征带来增益」并 propose 同特征变体。
- **实验智能体**：从 Q_k 论断实验、对 p* 打 patch、训练、经 noise-aware gate 决定是否 promote、写回 L 和 F。所有结果（含失败）对全 team 可见；失败进入 dead-end registry D_k。

**共享状态四层**：(1) champion p* 含完整超参与复现说明；(2) 实验 log L；(3) shared forum F（提案 / 结果 / 机制分析）；(4) 团队局部但跨团队可读的 Q_k、D_k、假设 docs。输出包括最终 p*、模型 card 和研究发现报告。

**实现形态**（开源仓库）：它不是大型 Python 智能体框架，而是由 **Claude Code 子智能体、ClawInstitute 本地协作服务和 Markdown 运行手册/角色模板**组成。`launch.py` 创建运行目录并注册监控器、GPU 智能体和分析智能体；`runbook.md` 只负责循环调度，**不训练模型**；`HEARTBEAT.md` 驱动模式选择器。共享状态保存在工作区的 `champion.md`、`teams/roster.md`、`queue.md` 等文件中；ClawInstitute 用版本令牌和乐观锁拒绝过期写入，并原子地更新队列。相对 [[OpenHands-ICLR25|OpenHands]] 的事件流沙箱或 [[AI-Scientist-v2-arXiv25|AI Scientist v2]] 的内存树，AutoScientists 把协调契约外显为**可审计的文件协议**——这是系统最值得抽象的部分，也是其脆弱性来源。

## 设计取舍

- **取舍 1：优化 实验算力预算，不优化 LLM-call 效率**——多智能体 discussion、re-organization 和 cross-团队传播显著增加 token（表 S8 显示与 Autoresearch 同量级但更高）。收益是在相同 GPU 实验次数下更好覆盖率；代价是 dollar 成本可能更高，论文未报告总费用。
- **取舍 2：去中心化 forum 协调 vs 中心规划器**——收益是方向可随证据动态重组，避免启动时错误分解锁死；代价是 coordination 正确性依赖 LLM 遵守协议，且 alphabetically-last analyst consolidate roster 存在单点语义风险。
- **取舍 3：markdown/JSON 软协议 vs 强运行时间 enforcement**——收益是快速原型、人类可读轨迹、ClawInstitute revision 历史可 replay；代价是智能体若跳过 `result_latest.json`、直接写 `submission.csv` 或丢失 API trail，系统无硬隔离纠错。
- **取舍 4：同伴批评 前置 vs 先跑再议**——收益是减少无效 GPU 实验；代价是可能过滤掉 counter-intuitive 但正确的方向，论文未 ablate「无 critique、仅 shared log」的折中。
- **边界条件**：在**可脚本化 train/eval 闭环、指标可标量排序、实验单次成本可控**的 computational science（BioML、nanochat、ProteinGym）下最优雅；换到湿实验、需人类伦理审批、或指标需专家判读的领域会显著变脆。

## 实验与结果

- **BioML-Bench**：24 个 biomedical ML 任务、四域下，平均排行榜 percentile 为 74.40 (6.20)%，Autoresearch-style 基线为 66.07 (7.38)%，高 8.33 points，24/24 完成（§4.2，图 3，表 1；matched 每个领域 实验算力预算、每任务 1×H100 串行）。作者报告 drug-发现领域为最大增益；protein-工程为 96.97 (3.03)%。
- **GPT nanochat 训练 optimization**（5 min/H100 实验，val_bpb 越低越好）：(a) 从基线 0.998 出发，达 ≈0.978 需 **34 vs 65** 实验（**1.9×**），三 team 并行覆盖 architecture/schedule/optimizer；(b) 从 champion 0.9777 续跑，**7/93 accepted → 0.9730**，Autoresearch **0/100 accepted**，best 0.9783。
- **ProteinGym / Kermut 扩展**：ACE2–Spike 开发实验检测 Spearman ρ **0.747→0.840**（+12.5%）；冻结 方案 后 217 项实验检测 官方平均 ρ **0.657→0.700**（+0.043，+6.5%）。发现三-GP ensemble + expanded zero-shot features + diversity feature selection + quantile-warped targets；MSE 略升 0.006（rank-oriented 优化副作用）。
- **消融实验**（4 任务 × 4 组件）：完整系统全胜。No analyst 最伤 TDC-hERG（AUROC 0.867→0.738）；No 跨智能体反馈最伤 Plasma-Protein Binding（Pearson 0.8729→0.7144）；No self-organization 最伤 GPT（0.9777→0.9833）；独立智能体最伤 Cell-Cell Communication（OR 0.924→0.435）。
- **实现**：Claude Code + Claude Sonnet 4.6；与基线同 后端。默认 3+6 智能体 roster。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| BioML-Bench 平均百分位为 74.40%，比 Autoresearch 风格高 8.33 点 | §4.2，图 3，表 1 | 24 个任务、四个生物医学领域；实验算力匹配；单张 H100 串行执行 | 强 |
| GPT nanochat 达到约 0.978 只需 34 次实验，而对照需要 65 次 | §4.3，图 4a | 每次 5 分钟、单张 H100；同一代码库；按实验次数而非墙钟时间比较 | 强 |
| 从相同最佳方案继续时，系统接受 7 个改进，对照接受 0 个 | §4.3，图 4b | 相同 0.9777 最佳方案与失败方向登记表；93 次对 100 次实验 | 强 |
| 冻结后的 Kermut 配方在 217 个 ProteinGym 实验检测上提高平均 Spearman ρ | §4.4，表 2 | 在 ACE2–Spike 开发实验检测后冻结；主指标为排名；MSE 增加 0.006 | 强 |
| 四项协作机制的影响随代表任务而变化 | §4.5，表 3 | 四个代表任务；后端、接口、算力和起点固定；不是完整因子实验 | 强 |

## 批判性分析

### 论证链条

作者链条：**(观察) 单轨迹/固定分解无法支撑长时间运行搜索 → (设计) 去中心化 team + 共享状态 + critique + re-organization → (结果) 三域 SOTA-over-基线 under matched 实验预算 → (结论) coordination architecture 是瓶颈**。方法到主结果的整体逻辑闭合较好，尤其 GPT champion 续跑（0 accepted vs 7 accepted）直接支撑「不是更多算力，而是更广假设覆盖率」。

薄弱跳步在于：(1) BioML-Bench 的「Autoresearch」基线实为 **Autoresearch-style 单智能体编程闭环**，不是 Karpathy `autoresearch` 仓库直接跑 biomedical 任务——开源显示 BioML profile 需从零写 `train.py`，而 GPT 任务才 clone 原版仓库；表格命名易让读者误读。(2) 将 BioML percentile 增益外推为「普适优于一切单智能体科研智能体」时，未与 [[AI-Scientist-v2-arXiv25|AI Scientist v2]]、[[Kosmos-AI-Scientist-arXiv25|Kosmos]]、Biomni 等在**相同 编排-only 变量**下系统对照（Biomni 仅部分域可比）。(3) ProteinGym 的 217-实验检测提升来自**单实验检测开发后冻结**，泛化证据强于 repeated CV tuning，但仍非独立留出 test 协议意义上的 blind 发现。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 并行 team 提升实验效率 | GPT 34 vs 65；forum log 案例显示去重与 dead-end 退休 | 单 GPU 串行、强耦合实验、智能体数固定无法扩缩 |
| Peer critique 改善提案质量 | 定性 forum 案例；无 critique 消融实验独立成条 | critique 系统性保守；跨团队 信息过载 |
| 共享状态减冗余 | 独立智能体消融实验最大降幅 | 协议违规、queue 论断竞态、ClawInstitute 非强事务 |
| 匹配实验预算的公平性 | 同 后端、同任务接口、逐实验轨迹对比 | BioML 领域脚手架（approach menu、diversity 规则）是否对基线同等；LLM token 未匹配 |
| 冻结 方案 跨实验检测泛化 | 217 项实验检测 +6.5% ρ | 开发实验检测选择偏差；分位数变换 损害校准回归 |

**推断（非论文证明）**：若将 team 数、discussion 轮次、approach menu 等脚手架去掉，多智能体相对单智能体的增益可能显著缩水——当前结果混合了 **编排 + 领域提示词工程** 的贡献，二者未充分分解。

### 实验可信度

- **基准代表性**：BioML-Bench 覆盖 imaging/drug/protein/single-cell，比 [[MLE-Bench-ICLR25|MLE-Bench]] 更偏 biomedical、比 [[MLR-Bench-arXiv25|MLR-Bench]] 更偏端到端流水线；GPT nanochat 是 [[Auto-Research-arXiv25|Autoresearch]] 原题，外部有效性高；ProteinGym 是标准 protein ML 基准。三域组合支持「跨科学领域」论断，但不覆盖系统性能优化、分布式训练、理论证明类任务。
- **基线强度**：GPT 对比公平（同仓库、同 编排-only 变量）；BioML 对 Autoresearch-style 闭环而非完整 Biomni/STELLA 全矩阵；ProteinGym 对 Kermut SOTA 合理。缺少与 [[ASI-ARCH-arXiv25|ASI-ARCH]] 式固定流水线多智能体的 head-to-head。
- **消融实验**：四组件在四任务上互补，支持「非冗余」叙事；但每个消融实验只跑代表任务，未给出统计重复或置信区间。
- **指标覆盖**：主指标为排行榜 percentile / val_bpb / Spearman ρ；尾延迟、失败恢复时间、协议违规率、人类复现成本——**论文未讨论**。MSE 退化被承认但未纳入优化目标。

### 系统性缺陷

- **正确性与隔离**：依赖智能体自觉遵守 markdown heartbeat 规则；无 Docker 级沙箱隔离、无 deterministic replay of LLM decisions。ClawInstitute 本地模式 auth 弱（`X-Agent-Name` 识别），不适合 多租户 生产环境。
- **可观测性**：实验 log + forum 提供丰富轨迹，但缺少结构化指标仪表盘或自动化协议格式检查器；运维需人工读 workshop posts。
- **故障恢复**：`result_latest.json` + stale 论断 sweep（30 min）+ resume posting 机制可恢复部分失败，但训练中途崩溃、GPU OOM、ClawInstitute 409 冲突的处理仍靠 orchestrator 轮询启发式。
- **成本与复现**：需 Claude Code/Sonnet 4.6、H100、多小时运行、大量 Python/ML 依赖；BioML 全量多 seed 重复不可行（论文自述）。论文未讨论实际时间 vs 实验-count 的权衡在真实 lab 中的可接受性。
- **过拟合风险**：BioML 开发期反复局部 CV 选模，最终 private grader 评分；虽排除 `private/answers.csv`，多轮搜索仍可能过拟合验证反馈——与 [[MLE-Bench-ICLR25|MLE-Bench]] 式留出 test 相比证据更弱。

## 局限与后续工作

- **局限 1**：不以 LLM-call 效率为目标；多智能体讨论与重组带来更高 token 成本，总 dollar 成本可能高于单智能体，即使 GPU 实验数更少。
- **局限 2**：BioML-Bench 评测每任务 **1 GPU 串行**，未充分展示 parallel experimentation 的核心能力；多 GPU 规模扩展仍为后续工作。
- **局限 3**：智能体数量启动前固定（默认 9 worker + monitor）；动态扩缩 team 仅有附录 B.2 初步探索。
- **局限 4**：ProteinGym 优化 Spearman ρ 时 MSE 略升；多目标排行榜（含校准指标）未实现。
- **后续工作 1**：在 matched **token + GPU** 双预算下测量规模定律——team 数、GPU 数、discussion 频率对 percentile/val_bpb 的边际收益，回答「何时多智能体值得付费」。
- **后续工作 2**：将 markdown 协议收敛为**可验证运行时间约定**（typed queue、hard 宣传 gate、自动化协议 lint），并报告 violation rate 与对结果的影响——这是从 demo 走向研究 OS 的关键测量。
- **后续工作 3**：明确命名并开源 **Autoresearch-style 单智能体基线** 与 Karpathy GPT 仓库的区分，在 BioML 上补充与 Biomni/AIDE 的 编排-matched 对照。

## 相关

- **相关概念**：[[Auto-Research]]、长程智能体、多智能体 collaboration、共享状态、dead-end registry、noise-aware 验证
- **同类系统**：[[AI-Scientist-v2-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[OpenHands-ICLR25]]
- **评测基准**：[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]
- **对比**：AutoScientists 强调 **去中心化团队 + 实验状态协议**；[[AlphaEvolve-arXiv25]] 强调评估器引导 代码 evolution；[[AI-Scientist-v2-arXiv25]] 强调阶段管理器 tree 搜索 + 稿件流水线
