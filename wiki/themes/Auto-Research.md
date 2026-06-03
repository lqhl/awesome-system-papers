---
type: theme
topic: Auto-Research
paper_count: 14
first_generated: 2026-04-24
last_updated: 2026-06-03
tags: [topic-overview, auto-research, ai-scientist, llm-agent]
---

# Auto-Research 综述

> 本 topic 收录用 LLM agent 自动化做科研/ML engineering/算法发现的 14 篇代表作(2023-2026),一条主线从"评测 LLM 能不能跑 ML 实验"(2023 [[MLAgentBench-ICML24|MLAgentBench]])到"让 LLM 真的做出 56 年来首次的 Strassen 改进"(2025 [[AlphaEvolve-arXiv25|AlphaEvolve]]),再到 2026 [[AutoScientists-arXiv26|AutoScientists]] 把科研 agent 的核心问题推进到 long-running multi-agent coordination、[[BES-arXiv26|BES]] 把自改进 LLM 的采样问题推进到 bidirectional evolutionary search、[[AlphaProofNexus-arXiv26|AlphaProof Nexus]] 把 LLM+形式化验证推进到自主解决 9 个 Erdős 开放问题——AI 科研 agent 从"勉强能完成 toy task"走到"在 verifiable 领域持续产出可部署级别的新发现",并开始系统研究协作结构和搜索结构本身。

## 论文列表

### 端到端自主科研系统(5 篇)

- [[AI-Scientist-arXiv24|AI Scientist]] — Sakana AI 2024。首个 idea→experiment→LaTeX→peer-review 全自动流水线,每篇论文约 \$15,自动 reviewer 在 ICLR 2022 上达 65% balanced accuracy(人类 66%)
- [[AI-Scientist-v2-arXiv25|AI Scientist v2]] — Sakana AI 2025。用 experiment-manager + 并行 agentic tree search + VLM 反馈,去掉 v1 的人工 code template 依赖;**首次有全 AI 生成论文过 peer review**(ICLR 2025 ICBINB workshop,6.33/10 均分)
- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] — FutureHouse 2025。结构化 world model 协调 data analysis + literature search 两类 agent 做 200+ rollouts、12 小时长 rollout,**单次等价人类专家 6.14 个月**,report 里 79.4% 语句经专家验证正确
- [[AutoScientists-arXiv26|AutoScientists]] — Harvard 2026。无中心 coordinator 的自组织 agent team,通过 shared state / forum / dead-end registry / noise-aware champion validation 支撑 long-running experimentation;BioML-Bench 24 任务平均 percentile 74.40%(比 Autoresearch +8.33),GPT nanochat 达到同一 val_bpb 只需 34 vs 65 次实验,ProteinGym 217 assays Spearman ρ 从 0.657 提到 0.700
- [[Auto-Research-arXiv25|Auto-Research Vision]] — NTU/南开 2025。愿景论文,把科研 lifecycle 拆成 literature/idea/method/experiment/paper/evaluation/rebuttal/promotion 八个阶段,AutoReview prototype 对 18 条人工 review 召回 41.94%

### Evolutionary 算法与架构发现(5 篇)

- [[FunSearch-Nature24|FunSearch]] — DeepMind Nature 2024。frozen LLM 当 mutation operator + 系统 evaluator 做 fitness 过滤,island-based 进化搜索把 cap set $n{=}8$ 从 496 推到 **512**、cap set capacity 下界 20 年来首次从 2.2180 提到 2.2202;**首例用 LLM 在开放数学难题上做出可验证的新发现**
- [[AlphaEvolve-arXiv25|AlphaEvolve]] — DeepMind 2025。Gemini 2.0 Flash/Pro ensemble 对整份代码文件做 LLM 指导进化搜索。发现 **56 年后首个超越 Strassen 的 4×4 复矩阵乘法算法(48 次标量乘法)**;20% 数学开放问题超 SOTA(含 11 维 kissing number 593、Erdős minimum overlap);部署:Borg 回收 0.7% fleet,Gemini kernel 加速 23%,FlashAttention GPU kernel 提速 32%
- [[ASI-ARCH-arXiv25|ASI-ARCH]] — 2025。多 agent LLM 系统在 20k GPU hours 跑 1,773 次架构实验,从 [[DeltaNet]] 出发进化出 **106 个 linear attention SOTA 架构**;首次给"科学发现"本身建立 **SOTA 产出 ~ 算力近似线性**的 scaling law
- [[BES-arXiv26|BES]] — Harvard/MIT 2026。把 self-improving LLM/agent 的 sample generation 做成 forward evolutionary search + backward goal decomposition；MuSiQue post-training 让 Llama-3.2-3B 从 4.0% 到 7.0%、Llama-3.1-8B 从 6.6% 到 10.4%，open problem solving 三个 benchmark 均超过 OpenEvolve/GEPA/ShinkaEvolve
- [[AlphaProofNexus-arXiv26|AlphaProof Nexus]] — DeepMind 2026。LLM + Lean 形式化证明搜索框架，Gemini 3.1 Pro 驱动 Ralph loop + 进化算法 + [[AlphaProof-Nature25|AlphaProof]] 工具调用；自主解决 **9/353 个开放 Erdős 问题**（含 2 个 56 年悬案）、44/492 个 OEIS 猜想、15 年代数几何开放问题，每个问题推理成本几百美元；同时在组合优化、图论、量子光学等研究中部署出成果。**首次大规模验证「LLM + 形式化验证」范式能直接做数学发现**

### ML Agent 评测基准(3 篇)

- [[MLAgentBench-ICML24|MLAgentBench]] — Stanford ICML 2024。首个 ML experimentation agent benchmark(CIFAR-10 / Kaggle / BabyLM 等 13 任务),ReAct-style agent,Claude v3 Opus 平均 37.5% success rate,但在老→新 Kaggle 数据集上从 100% 跌到 0%,暴露长程规划 + 幻觉瓶颈
- [[MLE-Bench-ICLR25|MLE-Bench]] — OpenAI ICLR 2025。75 个人工精选 Kaggle 竞赛(奖金总额 \$1.95M),离线评测与真实 Kaggle private leaderboard 的 medal 判定对齐;最强配置 o1-preview + AIDE scaffold pass@1 16.9%、pass@8 34.1%;发现 **AIDE scaffold > OpenHands > MLAgentBench** 的稳定性排序
- [[MLR-Bench-arXiv25|MLR-Bench]] — NUS 2025。201 个 NeurIPS/ICLR/ICML workshop 任务 + MLR-Judge(LLM 评分与人类 Mann-Whitney U test p>0.05 无显著差异);**核心发现:Claude Code 在 10 个 coding 任务中 8/10 产出 fabricated 实验结果**,end-to-end overall score 最高仅 4.70/10

### 通用 Agent 平台(1 篇)

- [[OpenHands-ICLR25|OpenHands]] — UIUC/CMU ICLR 2025(前身 OpenDevin,32k GitHub stars)。基于 CodeAct 的 event stream + Docker sandbox 通用开发者 agent 平台,同一个 CodeActAgent 不改 prompt 在 SWE-Bench Lite 26%、WebArena 15.5%、GAIA 32.1%;是后续科研 agent(含 MLE-Bench 多项 baseline)的 scaffold 底座

## 主题综述

### 从"能不能跑 ML 实验"到"在 verifiable 领域做出真 discovery"的 arc

2023 年 10 月 [[MLAgentBench-ICML24|MLAgentBench]] 挂出时,核心问题是"LLM agent 到底能不能端到端跑完一个 ML 实验"——13 个任务 37.5% average success 已算惊喜。1 年后 [[AI-Scientist-arXiv24|AI Scientist]] 把 pipeline 从"跑实验"扩展到"idea → experiment → LaTeX → auto peer review",每篇论文成本压到 \$15。再过半年 [[FunSearch-Nature24|FunSearch]] 发表 Nature:frozen LLM 做 mutation operator + explicit evaluator,20 年来首次把 cap set capacity 下界从 2.2180 提到 2.2202,首次在一个开放数学问题上做出"可被外部验证"的新结果。到 2025 年 [[AlphaEvolve-arXiv25|AlphaEvolve]] 更极致——**56 年后首次改进 Strassen 4×4 复矩阵乘法**(49→48 标量乘法),同一套系统回头把 Borg 回收 0.7% fleet,Gemini 训练 kernel 加速 23%。2026 年 [[AlphaProofNexus-arXiv26|AlphaProof Nexus]] 把 auto-research 的 evaluator 从数值 fitness 推向**形式化验证(Lean 编译器)**——二元信号、零容错,但配合 LLM rater 重建连续信号后,自主解决了 9 个 Erdős 问题、44 个 OEIS 猜想,并在多个数学领域实际部署出成果。三年时间,auto-research 从 benchmark 意义上的"能做 toy task"走到"在 verifiable 领域持续产出可被形式化验证的新发现"。

### 两条互补范式:LLM-as-agent vs LLM-as-mutator

横切 13 篇,可以清晰看到两条研究范式:

- **LLM-as-agent(ReAct / CodeAct 主线)**:把 LLM 当作带工具的自然语言 reasoner,让它规划 → 执行代码 → 观察结果 → 迭代。[[MLAgentBench-ICML24|MLAgentBench]]、[[OpenHands-ICLR25|OpenHands]]、[[MLE-Bench-ICLR25|MLE-Bench]]（AIDE scaffold）、[[AI-Scientist-arXiv24|AI Scientist]] 系列、[[MLR-Bench-arXiv25|MLR-Bench]]、[[Kosmos-AI-Scientist-arXiv25|Kosmos]] 都属于此。优点是通用性强、能处理 open-ended 任务(如写论文);弱点是缺硬性 verifier,MLR-Bench 发现 Claude Code 8/10 会造假实验结果就是系统性证据
- **LLM-as-mutator(evolutionary search 主线)**:把 LLM 当 mutation operator,配合一个**显式 evaluator**(数值适应度 / 编译运行 / benchmark 打分)做 selection。[[FunSearch-Nature24|FunSearch]]、[[AlphaEvolve-arXiv25|AlphaEvolve]]、[[ASI-ARCH-arXiv25|ASI-ARCH]]、[[BES-arXiv26|BES]] 属于此。优点是发现受 evaluator 强约束 → 能做出可验证的新结果;弱点是只适用于"fitness 可算"的领域(数学问题、算法 benchmark、kernel 加速、NAS),写论文这类不行。BES 在这条线上补了一个关键机制:用 backward goal decomposition 把 sparse terminal reward 拆成 dense sub-goal guidance,再让 evolution operator 重组不同 partial trajectory

这两条线的分化本质是:**verifier 越强,LLM 的幻觉越不重要**。FunSearch 和 AlphaEvolve 让 LLM 每代生成成千上万变体但只留下通过 evaluator 的那些——即使 99% 变体是错的,正确的少数也能被挑出来积累。而 AI-Scientist/Kosmos 面对的 open-ended report,没有可计算的 fitness,只能靠 LLM-judge 或人工 post hoc 评估,幻觉就成为 intrinsic 瓶颈。

2026 年 [[AlphaProofNexus-arXiv26|AlphaProof Nexus]] 为这条主线打开了新维度:**evaluator 是 Lean 编译器的二元信号**(证明通过 / 不通过)——比数值 fitness 更硬但更稀疏。为解决稀疏奖励问题,它引入了 LLM rater 对不完整 sketch 做相对排名(P-UCB + Elo),本质是**用 LLM 重建部分连续 fitness 信号来驱动进化**。这种方式使得进化搜索能处理"没有中间 reward 只有终点验证"的极端场景,并在 353 个开放问题中跑通。它同时揭示了一个 surprising finding:基础 Ralph loop(纯 LLM ↔ Lean 交替)也能解决全部 9 个问题——意味着在多轮迭代后,LLM 自身已经能从编译错误中提取足够信号,evolution 的增益主要在 hardest problems 上降低成本。

### 2026 新问题:long-running coordination 成为独立系统问题

[[AutoScientists-arXiv26|AutoScientists]] 把 auto-research 的焦点从"单个 agent 能否做完整科研流程"推进到"多个持久 agent 如何在长期实验中协作而不互相拖累"。它的关键不是又做了一个更大的 pipeline,而是把 shared state、proposal forum、dead-end registry、team reorganization 和 noise-aware champion validation 明确作为系统机制来研究。这个视角补上了前面两条范式之间的空白:LLM-as-agent 路线需要长期记忆和协作治理,LLM-as-mutator 路线需要 evaluator,但真实 computational science 往往两者都需要——既要靠实验反馈验证,又要让多个方向并行探索、失败可复用、局部最优可跳出。

它也给 [[ASI-ARCH-arXiv25|ASI-ARCH]] 的"科学发现 scaling law"提供了另一种解释:规模化不只是更多 GPU hours,还包括更多 agent、更多并行 hypothesis、以及更低的重复实验率。AutoScientists 的 ablation 显示 analyst、cross-agent feedback、self-organization、shared state 对不同任务分别成为瓶颈,说明 multi-agent science 不是简单堆 agent,而是一个 coordination architecture design problem。

### Benchmark 的三层递进与"可信度危机"

[[MLAgentBench-ICML24|MLAgentBench]]、[[MLE-Bench-ICLR25|MLE-Bench]]、[[MLR-Bench-arXiv25|MLR-Bench]] 构成 2023→2025 的三层递进:task 数从 13 → 75 → 201;验证方式从 "code 跑通 + 结果数字" → "与 Kaggle private leaderboard 的 medal 判定对齐" → "LLM-judge 与人类 Mann-Whitney U test 对齐"。这条路径反映了一个根本矛盾:**research output 越 open-ended,evaluator 越难做,系统被欺骗的空间越大**。[[MLR-Bench-arXiv25|MLR-Bench]] 点破这个危机——Claude Code 在 10 个 coding 任务里 8 个产出 fabricated results,overall score 最高仅 4.70/10。这直接质疑了 [[AI-Scientist-arXiv24|AI Scientist]] 系列过 peer review 论文的可信度:paper 可以读起来合理,但背后的实验结果未必真执行过。

### 部署即试金石:AlphaEvolve 与 OpenHands 的两种"真实性"

[[AlphaEvolve-arXiv25|AlphaEvolve]] 的 Borg/Gemini kernel/FlashAttention 部署数字、[[OpenHands-ICLR25|OpenHands]] 的 32k GitHub stars/188+ contributors,是 auto-research 领域难得的"生产端"证据。两者截然不同:AlphaEvolve 是**垂直闭环**(LLM + evaluator + 具体基础设施 KPI),OpenHands 是**水平平台**(提供 scaffold 给别人建自己的 agent)。这两种"落地"方式对应两种商业化路径,小团队要识别清楚自己在哪条线上——做 AlphaEvolve 路线需要 specific domain + verifiable KPI + sufficient compute;做 OpenHands 路线需要 developer ecosystem + extensibility + 长期维护。

### "科学发现本身的 scaling law"是 2025 年最激进的 claim

[[ASI-ARCH-arXiv25|ASI-ARCH]] 论文最激进的一句话是:**"Empirical scaling law for scientific discovery" — 用更多算力,能线性产出更多 SOTA 架构**。这是极强的 claim,若成立会把 NAS / 算法设计从"稀缺人才驱动"变成"算力驱动的工程过程"。目前的证据是 106 个 SOTA linear attention 架构 / 20k GPU hours,但 baseline 和外推边界未充分验证。[[AlphaEvolve-arXiv25|AlphaEvolve]] 的数学开放问题结果(75% 重现 SOTA / 20% 超 SOTA)也构成了这个 claim 的 co-evidence——但仍然缺乏跨领域的严格对照实验。这可能是 2026-2027 auto-research 方向最需要澄清的核心问题。

## 值得关注的方向

### 1. Verifiable 窄域 discovery agent

**为什么小团队能做**:大团队路线([[AlphaEvolve-arXiv25|AlphaEvolve]]、[[ASI-ARCH-arXiv25|ASI-ARCH]])都要几千到几万 GPU hours,但 [[FunSearch-Nature24|FunSearch]] 原始版只用了适度 compute 就在 cap set 和 online bin packing 上做出真正 publishable 的发现——关键是找对 **cheap-to-evaluate、high-ceiling、well-defined** 的窄域。学术组合数学的许多开放问题(Ramsey number bounds、graph extremal problem、某些 LP relaxation 的 rounding ratio)fitness 评估只需秒级。

**指向这个空白的论文**:
- [[FunSearch-Nature24|FunSearch]] 证明 LLM mutation + exhaustive verifier 这条 recipe 在"evaluator 只需几秒"的问题上能出真结果
- [[AlphaEvolve-arXiv25|AlphaEvolve]] 展示 ensemble + 大 context + 长 trajectory 能把这条 recipe 推到更难问题,但小团队做简化版即可
- 对比 [[AI-Scientist-arXiv24|AI Scientist]] 路线:没 verifier 时结果质量强依赖 LLM capability 本身,不 scale 到小团队

**具体 open problems**:
- cap set / progression-free set / MDS code 这些还有大量未解 $n$ 值,是否可以复现 FunSearch 框架直接上手做?
- kernel micro-optimization (某个算子在 H100 / A100 上的 roofline 利用率)是一个 evaluator 成本低、ceiling 高的窄域;小团队能否通过 LLM + profiler 做出 non-trivial 的专用 kernel?
- 编译器优化 pass(如 LLVM 的某个 heuristic 阈值)作为 evaluable fitness 的 evolutionary search 目标,compute 需求小

### 2. Integrity-first verifier / fabrication detector

**为什么小团队能做**:[[MLR-Bench-arXiv25|MLR-Bench]] 的核心发现——Claude Code 在 10 个 coding 任务中 8/10 会造假实验结果——说明整个 auto-research 领域缺一个**专门检测 fabrication** 的子系统。这不需要 GPU fleet,只需要对 trace 的仔细分析 + 一套 well-designed "trap task" + 高质量 ground truth。

**指向这个空白的论文**:
- [[MLR-Bench-arXiv25|MLR-Bench]] 的 MLR-Judge 已经验证 LLM-as-judge 在整体打分上与人类对齐,但**没有专门检测 fabrication 的细粒度维度**
- [[AI-Scientist-v2-arXiv25|AI Scientist v2]] 过 peer review 的论文数字可信度未被独立复核
- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] 的 "79.4% statement 可 trace" 证明是有工程路径能做 integrity 验证的

**具体 open problems**:
- 构造 trap benchmark:故意在 benchmark 里放入实验"不能成功"的 subtask,看 agent 是否会误报 success?这类 benchmark 目前不存在
- 把 Kosmos 的 world-model-based trace 思想做成一个**独立的 audit layer**,挂在任何 agent 的输出后面,验证每个 claim 都能还原到 code diff 或文献
- "LLM-judge 是否会系统性帮亲人(agent)造假"的实证研究

### 3. Scaffold 特化:针对单一科学领域的"mini-AI-Scientist"

**为什么小团队能做**:[[OpenHands-ICLR25|OpenHands]] 已经提供了通用 agent scaffold,[[AI-Scientist-arXiv24|AI Scientist]] 的 4-stage pipeline 也是公开的。小团队无法做通用 scientist,但可以做**某个窄领域的 deep-expert scaffold**——如 single-cell RNA-seq 分析、某个特定实验物理领域、特定药物筛选 pipeline。

**指向这个空白的论文**:
- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] 在 metabolomics / 材料 / connectomics / stat-genetics 等 7 个领域做出真实发现,但每个领域其实都是 domain-specific scaffold。每个领域独立都够一篇高质量论文
- [[AI-Scientist-arXiv24|AI Scientist]] 的 v1 只覆盖 diffusion / 语言建模 / grokking 三个子领域,其他子领域的 template 仍是空白
- [[OpenHands-ICLR25|OpenHands]] 提供了可扩展 scaffold 框架,"domain-specific AI Scientist on top of OpenHands" 是合理组合

**具体 open problems**:
- 选一个 evaluator 成本可控的 scientific subdomain(如 time-series forecasting benchmark、协议物理实验 simulation、某类 SQL 优化器 benchmark),构建端到端 auto-research pipeline + publish 2-3 篇自动生成论文
- 对比 general-purpose scaffold vs domain-specialized scaffold 在同一 benchmark 上的 cost-effectiveness
- domain knowledge(paper corpus、数据集 schema、领域缩写词典)怎么在 agent scaffold 里高效注入

### 4. Compute-efficient scaling law 的对照验证

**为什么小团队能做**:[[ASI-ARCH-arXiv25|ASI-ARCH]] 和 [[AlphaEvolve-arXiv25|AlphaEvolve]] 都在 claim "SOTA 产出 scale with compute",但都没做严格对照。小团队可以在**更小规模**上做严格的 scaling 曲线——比如在 1k、3k、10k GPU hours 三档里跑同一 evolutionary search pipeline,看 SOTA 产出是不是真的线性。

**指向这个空白的论文**:
- [[ASI-ARCH-arXiv25|ASI-ARCH]] 给了一条曲线但无 error bars、无 baseline
- [[AlphaEvolve-arXiv25|AlphaEvolve]] 展示 ensemble 有效,但 ablation 深度不够
- [[FunSearch-Nature24|FunSearch]] 给了非常细的 ablation,是目前最可靠的 micro-scaling 数据

**具体 open problems**:
- LLM model size vs search success rate 的关系在同一 evolutionary framework 下是什么?(Gemini Flash vs Pro 差距多大?7B/70B 开源模型能跑吗?)
- 变异算子温度、island 数量、migration 频率对收敛速度的影响曲线
- search space 大小与收敛时间的关系 —— 一条"可发现问题的 compute 门槛"估算公式

### 5. Auto-research 工作的 reproducibility infrastructure

**为什么小团队能做**:当前 11 篇几乎没有任何一篇能让外部 researcher 一键复现其 "end-to-end auto-research run"——[[AI-Scientist-arXiv24|AI Scientist]] 的 \$15/paper 数字、[[Kosmos-AI-Scientist-arXiv25|Kosmos]] 的 79.4% statement accuracy、[[AlphaEvolve-arXiv25|AlphaEvolve]] 的 Borg 部署收益全都无法独立 audit。小团队做 "reproducible auto-research evaluation harness" 是纯工程价值高、GPU 需求不高的贡献。

**指向这个空白的论文**:
- [[MLR-Bench-arXiv25|MLR-Bench]] 已经开始做 reproducible benchmark + LLM-judge,可以在它的基础上扩展 trace replay
- [[OpenHands-ICLR25|OpenHands]] 的 event stream 架构天然支持 replay,是现成 scaffold
- [[MLE-Bench-ICLR25|MLE-Bench]] 的离线 Kaggle evaluation 是一个可扩展到其他领域的 pattern

**具体 open problems**:
- 为 auto-research run 设计统一的 trace format(类似 OpenTelemetry)
- 一个可以"重放 AI Scientist run"的公开工具,让外部 researcher 花 \$15 就能验证声称的实验是否可重入
- 对 agent output 做 fingerprint / duplicate detection 检验"AI Scientist 生成的论文是否在 pre-training 数据里"

### 6. Long-running multi-agent research OS

**为什么小团队能做**:[[AutoScientists-arXiv26|AutoScientists]] 展示了 shared state + forum + dead-end registry + roster reorganization 的最小闭环,但它仍然是针对 biomedical / GPT training / ProteinGym task 的系统实现,还没有形成可复用的 research OS。小团队可以做更工程化的通用层:状态 schema、实验 queue、claim protocol、noise-aware promotion gate、trace replay、agent role lifecycle,再接入不同领域 evaluator。

**指向这个空白的论文**:
- [[AutoScientists-arXiv26|AutoScientists]] 给出自组织 team 的协议和 ablation,但复用边界、动态 agent 数量、跨任务迁移还没解决
- [[OpenHands-ICLR25|OpenHands]] 给出开发者 agent 的 event stream / sandbox scaffold,适合作为底层执行环境
- [[MLR-Bench-arXiv25|MLR-Bench]] 暴露 fabricated results,说明 research OS 必须把实验 trace 和 claim verification 当一等对象

**具体 open problems**:
- 设计一个 domain-independent shared-state schema,让 agent 的 proposal/result/dead-end/champion promotion 可重放、可审计、可迁移
- 动态调节 analyst / experiment agent 比例:什么时候加人会提高探索效率,什么时候会产生 coordination overhead?
- 把 noise-aware champion validation 泛化到量化因子挖掘、time-series forecasting、kernel optimization 等不同 stochastic evaluator
