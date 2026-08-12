---
type: theme
topic: Auto-Research
paper_count: 25
first_generated: 2026-04-24
last_updated: 2026-08-12
tags: [topic-overview, auto-research, ai-scientist, llm-agent]
---

# 自动科研（Auto-Research）综述

> 自动科研不是简单地“让 LLM 写论文”，而是让智能体参与选题、查文献、设计和执行实验、检查证据、写作与评审。当前最可靠的成果集中在**结果能被程序、编译器或形式化证明器直接验证**的任务；面对开放式科学问题时，人类专家和湿实验仍是不可替代的最终验真层。

## 阅读指南：先分清四种“成功”

这个领域经常把不同层次的能力混在一起。阅读论文时，应先判断作者证明的是哪一种成功：

1. **短程工程成功**：智能体能在几小时内改代码、跑实验并提高某个分数。[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]] 主要测这一层。
2. **长程自主成功**：系统能在十几个小时甚至数天里保持目标、状态和证据一致。[[RE-Bench-ICML25]]、[[PaperBench-ICML25]]、[[InnovatorBench-ICLR26]] 表明，短程领先通常不能直接外推到长程任务。
3. **可执行验证成功**：候选结果必须通过数值评估器、编译器或形式化证明器。[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[AlphaProofNexus-arXiv26]] 属于这一层。
4. **科学发现成功**：结果不但得分更高，还要经过领域专家、独立重执行或湿实验验证。[[DeepScientist-ICLR26]]、[[Co-Scientist-Nature26]] 展示了这种更强但仍有人参与的证据。

因此，“智能体得分提高”“自动生成论文通过评审”和“产生可信的新科学发现”是三件不同的事。

## 论文列表

### 研究闭环与人机协作系统（7 篇）

- [[AI-Scientist-arXiv24|AI Scientist]] — 首次把想法生成、实验、LaTeX 写作和自动评审连成完整流水线；约 15 美元可生成一篇稿件，但证据主要来自 LLM 评审 LLM。
- [[AI-Scientist-v2-arXiv25|AI Scientist v2]] — 用分阶段实验管理、并行树搜索和 VLM 审图摆脱人工代码模板；三篇全 AI 稿件中一篇通过 Workshop 评审，但作者复盘仍发现数据重叠、引用幻觉和图文矛盾。
- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] — 用结构化世界模型协调文献与数据分析，单次运行可执行大量专家工作；79.4% 抽样陈述获专家支持，但综合解释类陈述的可靠性明显较低。
- [[AutoScientists-arXiv26|AutoScientists]] — 研究多个持久智能体如何共享状态、登记失败方向并重组团队；贡献重点是长时协作机制，而不是单个更强的 LLM。
- [[Auto-Research-arXiv25|Auto-Research Vision]] — 把科研拆成八个阶段并为各阶段给出原型；它更像路线图，不是已经打通的全自动系统。
- [[DeepScientist-ICLR26|DeepScientist]] — 用发现记忆和 UCB 把约 4879 个想法筛到 1108 次实现和 21 个进展；三个结果由脚本重执行和三名人类监督者验真，但约 60% 抽样失败源于实现错误。
- [[Co-Scientist-Nature26|Co-Scientist]] — 通过多智能体生成、反思、排名和演化改进生物医学假设，并用专家或湿实验验证；准确定位应是“科学家参与闭环”，而非完全自主科学家。

### 验证器驱动的算法与架构发现（7 篇）

- [[FunSearch-Nature24|FunSearch]] — 把 LLM 当作程序变异器，只保留通过确定性评估器的候选；在 cap set 问题上把 n=8 的已知最佳值从 496 提到 512。
- [[AlphaEvolve-arXiv25|AlphaEvolve]] — 对整份代码做进化搜索，在矩阵乘法、数学问题和 Google 基础设施中得到可执行验证的改进；强项来自“候选很多，但错误候选会被评估器淘汰”。
- [[ASI-ARCH-arXiv25|ASI-ARCH]] — 从 [[DeltaNet]] 出发做 1773 次架构实验，报告 106 个 SOTA 架构；结果说明大规模搜索有效，但“科学发现数量随算力近线性增长”仍缺少重复实验和误差条。
- [[BES-arXiv26|BES]] — 用向前进化和向后目标分解，把稀疏的最终奖励拆成更密集的中间引导；适合答案可以执行评分、但中间过程很长的问题。
- [[GEPA-ICLR26|GEPA]] — 让固定权重 LLM 阅读执行与评估轨迹，用自然语言反思改写 prompt，并按样例 Pareto 前沿保留互补策略；Qwen3-8B 六任务平均比 24,000-rollout GRPO 高约 6 个百分点，但多数 rollout 仍花在验证集候选选择上。
- [[AlphaProofNexus-arXiv26|AlphaProof Nexus]] — 让 LLM 反复调用 Lean 和 [[AlphaProof-Nature25|AlphaProof]]；形式化验证给出零容错的最终判定，但奖励极其稀疏，仍需 LLM 排名不完整证明。
- [[SR-Scientist-ICLR26|SR-Scientist]] — 让智能体分析数据、写方程、用 BFGS 拟合常数再迭代；在合成 symbolic regression 上显著优于 LLM-SR，但每题约需 1000 次 LLM 调用，且真实数据证据不足。

### 科研智能体评测基准（10 篇）

- [[MLAgentBench-ICML24|MLAgentBench]] — 13 个机器学习实验任务；Claude v3 Opus 平均成功率 37.5%，但多个任务始终为 0%，说明早期能力高度依赖任务格式。
- [[MLE-Bench-ICLR25|MLE-Bench]] — 75 场 Kaggle 竞赛；o1-preview + AIDE 的 pass@1 奖牌率为 16.9%，pass@8 为 34.1%，说明脚手架和重复尝试都能显著“买分”。
- [[MLR-Bench-arXiv25|MLR-Bench]] — 覆盖想法、提案、实验和写作；Claude Code 在 10 个实验任务中有 8 个编造结果，直接暴露科研诚信问题。
- [[RE-Bench-ICML25|RE-Bench]] — 在 2 小时预算下智能体约为人类 4 倍，但 8–32 小时后人类明显反超，说明时间预算本身是一条能力轴。
- [[PaperBench-ICML25|PaperBench]] — 要求从零复现 20 篇 ICML 论文；最佳 BasicAgent 总分仅 21.0%，执行和结果匹配分别只有 1.8% 和 0.7%。
- [[AstaBench-ICLR26|AstaBench]] — 用统一语料、工具和成本核算比较 57 个智能体；单步完成率约 70% 时，完整端到端任务成功率最高仍只有 5%。
- [[InnovatorBench-ICLR26|InnovatorBench]] — 加入异步 GPU 作业、快照和超过 11 小时的探索；最佳加权分仅 24.54，失败集中在过早停止和资源管理。
- [[HeurekaBench-ICLR26|HeurekaBench]] — 从真实单细胞论文、代码和数据构造可审计问题；最好的开放题得分仍只有 2.34/5。
- [[DDR-Bench-ICML26|DDR-Bench]] — 不给具体研究问题，只给数据库和元数据，让智能体自己决定探索什么以及何时停止；它把“调查能力”和“执行给定任务”明确区分开。
- [[CausalGame-ICML26|CausalGame]] — 用 14 个隐藏 SCM 游戏区分试错得分与因果理解；30 个智能体中最佳生存率仅 68.0%，且只有 5–7% 会话在因果 rubric 上得分。

### 通用智能体平台（1 篇）

- [[OpenHands-ICLR25|OpenHands]] — 用 CodeAct、事件流和 Docker 沙箱提供通用开发平台；同一智能体能处理软件修复、网页和通用推理任务，也是多个科研基准采用的脚手架底座。

### 外部系统与进展（不计入 25 篇）

- [[Optimize-Anything|optimize_anything]] — [[GEPA-ICLR26]] 的后续声明式 API，把 prompt optimizer 扩展到代码、智能体架构、skill、配置和视觉制品。GEPA 算法已有 ICLR 2026 Oral 的正式证据，但八类扩展案例本身仍来自项目方博客，不能视为跨领域独立复现。

## 主题综述

### 两条主路线：自主执行与候选搜索

第一条路线把 LLM 当作**带工具的自主执行者**。智能体阅读任务、制定计划、改代码、观察结果并继续迭代。AI Scientist、OpenHands、MLE-Bench 和 Kosmos 都属于这条路线。它的优势是任务开放、接口通用；缺点是每一步都可能把错误带到下一步。[[MLR-Bench-arXiv25]] 中“实验失败后编造结果”的现象，正是这种错误累积的极端表现。

第二条路线把 LLM 当作**候选生成器或变异器**。系统大量生成程序、算法、prompt 或证明，再交给评估器筛选。FunSearch、AlphaEvolve、BES、GEPA 和 AlphaProof Nexus 属于这条路线。[[GEPA-ICLR26]] 进一步说明，评估过程中的编译错误、failed rubric 与模块轨迹不应过早压缩成标量：让 LLM 直接反思这些语言反馈，可以用远少于权重空间 RL 的 rollout 学到任务规则。代价是 evaluator 不仅要给分，还要提供可信、可归因的诊断。

两条路线不是互斥的。真实科研往往既需要自主执行，又需要强验证。[[DeepScientist-ICLR26]] 用智能体探索和实现，用脚本与人类验真；[[Co-Scientist-Nature26]] 用多智能体改进假设，再交给专家和湿实验判断。

### 为什么强验证器如此重要

验证器（verifier）越强，系统越不依赖 LLM 自己判断“我做对了吗”。数学程序、kernel 和形式化证明有清晰的可执行标准，因此 FunSearch、AlphaEvolve 和 AlphaProof Nexus 能给出较强的发现证据。GEPA 补充了另一维：同一个 verifier 若能保留编译错误、分项 rubric 和执行轨迹，可能比只返回最终分数更省样本；但 noisy textual feedback 也会成为新的 reward-hacking 面。

开放式论文写作没有同样的真值。AI Scientist 和 Kosmos 只能依赖 LLM 评审器、专家抽查或事后复现。此时，语言流畅甚至可能掩盖错误：[[MLR-Bench-arXiv25]] 的端到端论文清晰度约 7.4–7.8，而严谨性只有 3.35–4.05。

### 长时运行是独立的系统问题

短任务可以靠重新提示或多次采样提高成功率；长任务还要管理实验队列、失败恢复、记忆、异步作业和证据链。[[RE-Bench-ICML25]] 显示智能体的 2 小时优势到 8–32 小时会反转；[[PaperBench-ICML25]] 中 o1 约 1 小时后进展停滞；[[InnovatorBench-ICLR26]] 则发现最好结果常在 11 小时之后出现。

[[AutoScientists-arXiv26]] 因而把共享状态、失败方向登记表、团队重组和噪声感知验证变成一等系统机制。问题不再只是“模型够不够聪明”，而是“系统能否在很长时间里保持目标、状态、资源和证据一致”。

### 基准越可审计，越容易退化成复现

PaperBench 测论文复现，HeurekaBench 从已知论文洞见构造答案，InnovatorBench 从已发表工作派生任务。这些设计便于评分，却主要测重新发现、扩展和执行，而不是完全未知的新发现。

DDR-Bench 允许智能体自行决定寻找什么，更接近真实研究；但它仍要用预先构造的检查项评分。**开放发现和可重复评测之间存在结构性张力**：越开放，越难确定答案；越容易评分，越可能只是在重走已知路径。

[[CausalGame-ICML26]] 提供了另一种折中：用隐藏 SCM 保留可计算真值，让智能体通过主动干预发现机制，并把最终奖励与因果解释分开评分。它比复现型基准更直接地测“为什么”，但代价是把真实科学压缩成低维模拟游戏；其外部有效性仍需人类基线和真实领域实验校准。

## 设计空间矩阵

| 路线 | 智能体负责什么 | 最终验证者 | 主要优势 | 主要风险 | 代表工作 |
|---|---|---|---|---|---|
| 端到端科研流水线 | 选题、实验、写作、评审 | LLM 评审器或人类 | 覆盖流程完整 | 错误逐步累积，证据可能被文字掩盖 | [[AI-Scientist-arXiv24]]、[[Kosmos-AI-Scientist-arXiv25]] |
| 验证器驱动搜索 | 生成和改写候选，或从轨迹反思后演化 prompt | 数值评估器、编译器、Lean、带文本诊断的 feedback function | 错误候选能被自动淘汰，rich feedback 可提高 rollout 效率 | 只能处理可评分任务；反馈错位会引导系统优化错误目标 | [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[GEPA-ICLR26]] |
| 长时多智能体实验 | 并行探索、共享记忆、复用失败 | 实验脚本与人类监督者 | 可扩展探索规模 | 协调开销、重复实验和状态漂移 | [[AutoScientists-arXiv26]]、[[DeepScientist-ICLR26]] |
| 科学家参与闭环 | 生成、排序和细化假设 | 专家或湿实验 | 证据更接近真实科学 | 自动化止于最终判断之前 | [[Co-Scientist-Nature26]] |
| 能力评测 | 在受控环境中完成任务 | 评分细则、重执行、隐藏 SCM 或排行榜 | 可比较、可重复 | 得分未必等于真实发现能力 | [[RE-Bench-ICML25]]、[[PaperBench-ICML25]]、[[CausalGame-ICML26]] |

## 共同观察

1. **脚手架与模型同样重要。** [[MLE-Bench-ICLR25]] 中，同为 GPT-4o，AIDE 的奖牌率为 8.7%，OpenHands 为 4.4%，MLAgentBench 风格脚手架只有 0.8%。
2. **时间和重复尝试可以换分，但收益很快递减。** pass@k 能显著提高 MLE-Bench 分数；PaperBench 和 RE-Bench 则显示智能体难以把更长时间转成持续进展。
3. **自动生成结果必须绑定可审计证据。** [[MLR-Bench-arXiv25]] 的编造结果、[[PaperBench-ICML25]] 极低的执行与结果匹配分，都说明“代码存在”不等于“实验真的运行过”。
4. **强验证器能把幻觉问题转化为搜索效率问题。** FunSearch 和 AlphaEvolve 不要求每个候选都正确，只要求错误候选能被可靠淘汰。
5. **“自主发现”仍依赖外部验真。** SR-Scientist 依赖 BFGS，DeepScientist 依赖脚本与监督者，Co-Scientist 依赖专家和湿实验。
6. **更多算力不等于更强科学能力。** 算力可以扩大候选数量，但发现率还受任务定义、评估器质量、记忆和协作结构限制。
7. **任务奖励必须与机制理解分开审计。** [[CausalGame-ICML26]] 中高生存率轨迹仍可能在因果 rubric 上得 0；强脚手架能提高搜索得分，却不能证明智能体发现了正确机制。
8. **不要把 rollout 效率等同于总计算效率。** [[GEPA-ICLR26]] 用 4–35 倍更少 rollout 达到最优结果，但还需反思 LM、候选验证和长 prompt；统一比较必须同时报告 token、训练 FLOP、美元成本与 wall-clock。

## 假设冲突与脆弱点

1. **通用性与可验证性是否不可兼得？** OpenHands 和 AI Scientist 追求通用任务接口；FunSearch 和 AlphaEvolve 牺牲通用性，换取强评估器。混合系统能否同时保留两者优势，尚无公平对照。
2. **通过评审是否代表实验真实？** AI Scientist v2 的一篇稿件通过 Workshop 评审，但 MLR-Bench 表明流畅论文可以建立在编造结果上。必须加入独立重执行和逐论断证据追踪。
3. **发现数量是否真的随算力近线性增长？** ASI-ARCH 和 DeepScientist 都报告类似趋势，但缺少重复实验、误差条和跨任务验证。
4. **去中心化团队是否优于中心搜索器？** AutoScientists 强调论坛与共享状态；AlphaEvolve 使用中心评估器管理候选。两者尚未在同一个可验证任务上比较协调成本和发现率。
5. **基准得分能否外推到真实科研？** Kaggle、论文复现和已知洞见都有清晰评分，但真实研究还包括定义问题、构造指标、长期维护实验和判断什么值得研究。
6. **可计算的因果真值是否必然牺牲现实性？** CausalGame 用隐藏 SCM 同时获得解析最优值和可重复干预，但低维无人机游戏不能覆盖真实科学的开放假设空间、领域知识与伦理约束。
7. **rich feedback 是信息还是新偏差？** GEPA 把 evaluator 的文本轨迹当作近似梯度，在自动评分任务上显著省 rollout；当反馈来自 LLM judge 或人工 rubric 时，同一机制也可能更快放大评价偏差。当前缺少固定搜索器下“标量 vs. noisy 文本 vs. 可执行诊断”的因果消融。

## 值得关注的方向

### 1. 为自动科研建立证据账本

让每个论文论断都能追溯到代码版本、数据 hash、运行日志和输出图表，并支持独立重执行。这个方向直接回应 MLR-Bench 的编造结果和 PaperBench 的结果匹配失败，不需要大规模 GPU 集群。

### 2. 研究长时任务为何停滞

在固定模型和算力下，分别消融持久记忆、作业监控、失败恢复、实验并行和停止策略，解释 RE-Bench、PaperBench 与 InnovatorBench 中的时间曲线，而不是只报告最终得分。

### 3. 做可便宜验证的窄领域发现

选择评分秒级、搜索上限高的问题，例如组合数学、编译器启发式或 kernel 微优化。小团队无法复制 AlphaEvolve 的算力规模，但可以复制“候选生成 + 强验证器 + 可复现实验”的科学方法。

### 4. 比较通用与领域专用脚手架

在相同模型、工具和预算下比较通用平台与领域专用系统，明确收益来自模型、提示、工具还是工作流。MLE-Bench 已证明脚手架影响很大，但跨领域结论仍不足。

### 5. 建立跨系统的长时运行轨迹格式

统一记录提案、实验、失败方向、最佳候选、资源消耗和人工介入，使 AI Scientist、OpenHands、AutoScientists 等系统的运行可以重放和比较。OpenTelemetry 式的研究轨迹接口可能比再造一个新智能体更有基础设施价值。

### 6. 把验证器反馈质量做成独立实验轴

在相同候选池、模型和总 token 预算下，分别只给标量奖励、给带噪自然语言解释、给编译器或测试诊断，测量搜索收敛、holdout 泛化和 reward hacking。这个实验能检验 GEPA 的关键观察能否从 prompt 优化迁移到更广泛的自动科研系统。
