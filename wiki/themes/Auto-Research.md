---
type: theme
topic: Auto-Research
theme_kind: domain
member_tag: domain/auto-research
candidate_tags: [auto-research, ai-scientist, scientific-discovery, research-agent, research-benchmark]
paper_count: 38
first_generated: 2026-04-24
last_updated: 2026-08-19
tags: [topic-overview, auto-research, ai-scientist, llm-agent]
---

# 自动科研（Auto-Research）综述

> Auto-Research 研究如何自动生成、实现、复现或验证研究产物，并让实验或证据反馈改变后续研究动作。Agent 只是实现形态之一；程序搜索、研究 benchmark、verifier 和证据基础设施同样属于这个研究目标。

## 定义与边界

一篇论文进入核心集合，至少满足以下一项：连接两个以上研究阶段，且反馈会改变后续假设、实现或选择；自动产生算法、模型、证明或系统制品，并有明确 evaluator；专门评测或保障上述研究循环的执行、证据、选择或恢复。输出可以是科学论断，也可以是经验证、可复用的算法或系统 artifact，但不能只是一次模型调用生成的文本。

以下工作只放邻接区：仅检索、总结、写作或评审的 research assistant；没有科研专用闭环或评测的通用 agent 平台；只因运行时间长便自称自动科研的系统；以及只在某个领域使用 AI、却没有自动化研究过程的应用论文。

“科研智能体（research agent）”不是平级 theme，而是本主题中的一种系统形态。AI Scientist、科学家参与闭环和量化 R&D agent 都可属于这一类；FunSearch、AlphaEvolve、研究 benchmark 和 verifier infrastructure 则说明 Auto-Research 并不等于“由一个 agent 模仿科学家”。

## 阅读指南：先在六条轴上定位

| 轴 | 应问什么 | 容易误读的代理 |
|---|---|---|
| **目标自主性** | 人类给的是完整复现目标、优化指标、宽泛研究问题，还是只有数据与观察对象？智能体能否自行决定什么值得研究？ | 把“方法开放”误写成“自主选题” |
| **闭环完整性** | 系统覆盖哪些研究阶段？执行或证据反馈是否真正改变下一轮假设、实现或候选选择？ | 把工具链长或 agent 数多当成闭环 |
| **输出产物** | 结果是代码、模型、算法、证明、实验 finding，还是可公开主张的 claim？ | 把更高 benchmark 分数自动写成新知识 |
| **验证强度** | 验证的是代理分数、程序确实执行、精确约束、形式命题，还是现实世界科学结论？ | 凡是有 evaluator 就称为“可验证发现” |
| **筛选分母** | 总共生成、执行和丢弃了多少候选？最好结果能否被独立重复？ | 只报 best-of-k 或最终 SOTA |
| **人工介入** | 人类在哪些关口提供问题、数据、搜索空间、候选选择、实验操作、结果解释与最终验真？ | 只统计 agent 内部循环，忽略 campaign 外的 meta-selection |

这些轴不是互斥等级。[[GEPA-ICLR26|GEPA]]、[[FunSearch-Nature24]] 和 [[Co-Scientist-Nature26]] 都有反馈循环，但分别证明 prompt 优化、合法数学构造和科学家参与的生物医学发现；三者的 verifier、候选分母与知识主张不能放在同一证据格中。任务持续性与恢复问题另见 [[Long-Horizon-Agents|长程智能体可靠性]]。

## 核心论文

### 研究闭环系统与科学家协作（10 篇）

- [[AI-Scientist-arXiv24|AI Scientist]] — 串联 ML 想法、代码、实验、写作与自动评审；能自动成稿，但主要依赖 LLM 评 LLM。
- [[AI-Scientist-v2-arXiv25|AI Scientist v2]] — 用 agentic tree search 扩大实验循环；约 40 个想法经人工跨运行筛到 3 篇投稿、1 篇 workshop 过线。
- [[Auto-Research-arXiv25|Auto-Research Vision]] — 给出八阶段研究自动化路线图与局部原型，证明组件可行性而非完整闭环。
- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] — 用结构化 world model 支撑文献—数据联合分析；抽样 claim 支持率高于解释与综合类 claim。
- [[AutoScientists-arXiv26|AutoScientists]] — 用共享 champion、论坛、失败登记和动态组队维持多智能体实验状态。
- [[DeepScientist-ICLR26|DeepScientist]] — 从 4,879 个想法筛到 21 个进展发现；约 60% 抽样失败仍来自实现错误。
- [[Co-Scientist-Nature26|Co-Scientist]] — 生成并排序生物医学假设，强证据来自专家选择和体外实验，而非无人实验室。
- [[Robin-Nature26|Robin]] — 自动化文献、假设和数据分析，湿实验协议、执行与关键决策仍由科学家完成。
- [[OmniScientist-arXiv26|OmniScientist]] — 让多模态原始证据贯穿选题、实验与写作，并用 execution ledger 约束数字和来源。
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] — 在量化投研中闭合规格、假设、factor/model 代码、回测、分析与下一轮选择。

### 可验证算法、模型与机制发现（8 篇）

- [[FunSearch-Nature24|FunSearch]] — 用精确程序评估器搜索数学构造，最终合法性强，但最好结果只在少数独立运行中出现。
- [[AlphaEvolve-arXiv25|AlphaEvolve]] — 在数学、算法和生产系统中演化整份代码，以精确检查、性能测试和专家复核分层验证。
- [[AlphaProofNexus-arXiv26|AlphaProof Nexus]] — 用 Lean 给出形式正确性，题意、新颖性和意义仍由专家判断。
- [[ASI-ARCH-arXiv25|ASI-ARCH]] — 从大规模架构实验筛出候选，混合 verifier 证明窄域性能而非通用发现规律。
- [[BES-arXiv26|BES]] — 用反向子目标提供稠密反馈，局部 verifier 仍可能只是 embedding 或 LLM proxy。
- [[SR-Scientist-ICLR26|SR-Scientist]] — 用数值拟合引导方程搜索，主要重发现已知生成机制。
- [[MetaMuse-ICLR26|MetaMuse]] — 以多样性和 waypoint feedback 生成系统算法，模拟器分数不等于生产正确性或新颖性。
- [[CausalEvolve-ICLR26|CausalEvolve]] — 用 outcome/procedure factor 与 bandit 干预引导程序进化，但近似 ATE 不构成真实因果识别。

### 系统制品与执行优化（4 篇）

- [[GEPA-ICLR26|GEPA]] — 在固定任务、数据与反馈函数下反思优化 prompt；属于短程系统 R&D，不是科学发现。
- [[AdaExplore-arXiv26|AdaExplore]] — 从失败中学习 Triton validity skills，再搜索更快 kernel。
- [[AVO-arXiv26|AVO]] — 用七天单 lineage 演化 B200 attention kernel；最终结果强，但模型、成本和复现方差不透明。
- [[CAKE-arXiv26|CAKE]] — 让 compiler IR、verifier 与 agent 共演，在 matched budget 下优于直接 CUDA/PTX。

### 给定目标的研究执行与复现评测（7 篇）

- [[MLAgentBench-ICML24|MLAgentBench]] — 测量 agent 在给定 ML 任务中规划、执行与迭代实验的能力。
- [[MLE-Bench-ICLR25|MLE-Bench]] — 用 Kaggle private leaderboard 测 ML 工程；pass@k 强依赖重复运行与 scaffold。
- [[MLR-Bench-arXiv25|MLR-Bench]] — 测 workshop 研究任务，暴露结果编造与产物检查缺口。
- [[PaperBench-ICML25|PaperBench]] — 用独立重执行与细粒度 rubric 测论文复现，而非自主选题。
- [[AstaBench-ICLR26|AstaBench]] — 将研究子任务分解为可执行环境与混合 rubric，端到端成功率仍很低。
- [[HeurekaBench-ICLR26|HeurekaBench]] — 测已发表单细胞洞见的重发现，不重执行完整 workflow。
- [[ResearchClawBench-arXiv26|ResearchClawBench]] — 用隐藏目标论文和跨学科数据审计 protocol、证据与结论匹配。

### 选题、长程与反馈机制评测（6 篇）

- [[RE-Bench-ICML25|RE-Bench]] — 展示短预算 agent 优势与长预算人类优势的时间尺度反转。
- [[InnovatorBench-ICLR26|InnovatorBench]] — 在 2–36 小时研发任务中暴露异步 job、早停和资源管理失败。
- [[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] — 把过程拆成 Solution Framing、Execution 与 Feedback Control，并测经验的正负迁移。
- [[DDR-Bench-ICML26|DDR-Bench]] — 只给数据库与 metadata，让 agent 自行决定调查目标与停止时机。
- [[CausalGame-ICML26|CausalGame]] — 用隐藏 SCM 给出硬真值，但问题和动作空间由设计者封闭。
- [[ICL-EF-ICML26|Lab-in-the-Loop Feedback]] — 证明模型能使用迭代实验反馈，但实验来自预计算数据库回放。

### 证据、验证与可审计基础设施（3 篇）

- [[EviGraph-arXiv26|EviGraph]] — 把 Problem→Claim 依赖变成可检查、可失效和可回滚的研究状态。
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — 用真实 serving workload、正确性 sandbox 与 deployment contract 评测 agent kernel 工程。
- [[SOL-ExecBench-arXiv26|SOL-ExecBench]] — 用硬件上界、output check 和 anti-hacking 检测约束 235 个 B200 kernel problems。

## 邻接资料

- [[OpenHands-ICLR25|OpenHands]] 提供 CodeAct、事件流和 Docker 沙箱，是 [[Agent-Systems]] 的平台工作，也是重要 scaffold 与实验变量；论文本身不自动化或评测研究过程。
- [[Optimize-Anything|optimize_anything]] 把 GEPA 的声明式接口扩展到代码、agent 架构、skill、配置和视觉制品。GEPA 算法有 ICLR 2026 正式证据；八类扩展案例来自项目方材料，不能当作跨领域独立复现。

## 38 篇设计空间总表

| 论文 | 主角色 | 目标由谁设定 | 时长证据 | 最强验证 | 实际证明与人工边界 |
|---|---|---|---|---|---|
| [[MLAgentBench-ICML24\|MLAgentBench]] | benchmark | 人给任务、基线与指标 | 最多 5h/50 actions | 运行后的任务分数 | 测短程 ML 实验；不测新颖性 |
| [[RD-Agent-Quant-arXiv25\|R&D-Agent(Q)]] | 垂直研究闭环 | 人给市场、数据、目标与策略规则 | 30 loops；约 12h | 执行检查 + Qlib 历史 OOS 回测 | 自动化量化内环；无实盘，重复选择仍可能 research-overfit |
| [[AI-Scientist-arXiv24\|AI Scientist]] | 端到端系统 | 人给方向与代码模板 | 单次约 12h | 执行产物 + LLM review | 能自动成稿；无独立科学验真 |
| [[MLE-Bench-ICLR25\|MLE-Bench]] | benchmark | 人给 Kaggle 任务 | 主设定 24h，扩展 100h | private leaderboard | 测 ML 工程；pass@k 强依赖重复运行 |
| [[AI-Scientist-v2-arXiv25\|AI Scientist v2]] | 端到端系统 | 人给研究方向，人工跨运行选稿 | 单 run 最多 15h；seed 数未披露 | 执行产物 + workshop review | 1/3 投稿过线；约 40 个想法先经人工筛选 |
| [[Auto-Research-arXiv25\|Auto-Research Vision]] | 路线图/原型 | 各原型均由人给目标 | 无完整持续轨迹 | 人工抽查与局部指标 | 证明阶段组件可行，不证明闭环 |
| [[MLR-Bench-arXiv25\|MLR-Bench]] | benchmark | workshop 主题到给定 triple | 重环节仅 10 个样本 | LLM judge + 产物检查 | 暴露 8/10 编造结果；不是真实发现评测 |
| [[AlphaEvolve-arXiv25\|AlphaEvolve]] | 程序搜索 | 人给问题、代码边界与 evaluator | 大规模异步；统一 wall-clock 未披露 | 精确/数值检查 + 专家/生产部署 | 发现算法与工程优化；选择空间由人限定 |
| [[ASI-ARCH-arXiv25\|ASI-ARCH]] | 架构搜索 | 人给 seed、约束和 benchmark | 约 20k GPU-hours，并行 campaign | loss/benchmark/LLM judge | 证明窄域搜索 yield；不证明长程自治 |
| [[Kosmos-AI-Scientist-arXiv25\|Kosmos]] | 数据—文献系统 | 科学家给目标和预处理数据 | 12h、20 cycles、200+ trajectories | 专家抽检 + 独立计算验证 | 79.4% 抽样 claim 支持；专家选取有意义结论 |
| [[FunSearch-Nature24\|FunSearch]] | 数学程序搜索 | 人给 skeleton 与 evaluator | 最难实验约 2 天并行搜索 | 精确构造检查 | 新构造成立；意义与搜索空间迭代依赖人类 |
| [[AutoScientists-arXiv26\|AutoScientists]] | 长时多智能体系统 | 人给任务、数据、指标、初始程序 | 4–16h | 可执行 benchmark 指标 | 证明协作 scaffold；不测自主选题/湿实验 |
| [[BES-arXiv26\|BES]] | 搜索算法 | 人给任务与最终目标 | 每题约 50–200 calls | 最终 exact/数值目标，局部 proxy | 改善搜索；未产出外部确认的新知识 |
| [[GEPA-ICLR26\|GEPA]] | prompt optimizer | 人给系统、数据划分与反馈函数 | 17–92 次反思调用；非长程研究轨迹 | held-out 自动评测 | 短程工程成功；不是可验证科学发现 |
| [[AlphaProofNexus-arXiv26\|AlphaProof Nexus]] | 形式证明搜索 | 人给/审核形式命题 | 24–48h 异步搜索 | Lean + SafeVerify | 形式正确；题意、新颖性与意义仍由专家把关 |
| [[AstaBench-ICLR26\|AstaBench]] | benchmark | 多数给定目标和详细步骤 | 多数少于 12 steps；cell timeout 5min | 程序检查与 LLM rubric 混合 | 测研究子任务；E2E 成功最高仍约 5% |
| [[DeepScientist-ICLR26\|DeepScientist]] | 前沿计算搜索 | 人给任务、SOTA 起点与指标 | 最长一个月、16×H800，持续人工监督 | 脚本重执行 + 人类核验 | 21 个进展；搜索自主不等于无人科研 |
| [[InnovatorBench-ICLR26\|InnovatorBench]] | 长时 benchmark | 人给隐藏-reference 研究任务 | 2–36h；峰值常在 11h 后 | executable score + rubric | 暴露异步作业、早停与资源管理失败 |
| [[RE-Bench-ICML25\|RE-Bench]] | 人机 benchmark | 人给 7 个 R&D 任务 | 2–32h 总预算比较 | 任务评分器 | 2h agent 领先、8h 后人类反超；32h 为 best-of-4 |
| [[Co-Scientist-Nature26\|Co-Scientist]] | 假设协作系统 | 科学家给目标、约束并选候选 | 异步多轮；不以无人时长为证据 | 专家 + 体外湿实验 | 有科学发现证据；最终选择与实验由人完成 |
| [[SR-Scientist-ICLR26\|SR-Scientist]] | 方程搜索 | 人给数据与任务 | 每题约 1,000 calls，最长 25-turn 内环 | BFGS/数值误差 + LLM 等价判断 | 重发现已知方程；结构/机制不由数值拟合保证 |
| [[HeurekaBench-ICLR26\|HeurekaBench]] | benchmark | 人给问题，答案来自已发表论文 | CellVoyager 每题约 1h | GPT-4o final-answer judge | 测已知单细胞洞见重发现；不重执行 workflow |
| [[DDR-Bench-ICML26\|DDR-Bench]] | 开放调查 benchmark | 只给 entity/schema，无 query | 自主停止，少数到 100 rounds | checklist + LLM support judge | 目标自主性高；新洞见真值与预算控制较弱 |
| [[PaperBench-ICML25\|PaperBench]] | 论文复现 benchmark | 人给目标论文与数据 | 主设定 12h，o1 扩展 36h；人类子集 48h | 独立重执行 + 8,316 个 rubric leaf | 测复现而非选题；最佳 agent 总分 21.0% |
| [[CausalGame-ICML26\|CausalGame]] | 机制 benchmark | 人给生存目标与动作空间 | 10 次部署 + final 1,000 drones | 隐藏 SCM + 语言 rubric | 硬真值但封闭世界；高任务分不等于因果理解 |
| [[Robin-Nature26\|Robin]] | 生物发现系统 | 人给疾病，科学家筛选并运行实验 | agent 认知少于 2h；实验周期间断由人衔接 | 人类分析 + 多轮体外实验 | 支持药物 repurposing 发现；实验协议/操作并未自动化 |
| [[MetaMuse-ICLR26\|MetaMuse]] | 系统算法生成 | 人给问题、API、workload 与模拟器 | 每方法生成 350 候选 | workload 仿真 + safety checks | 证明性能/多样性；新颖性与生产泛化需专家/线上验证 |
| [[CausalEvolve-ICLR26\|CausalEvolve]] | 程序进化 | 人给四个优化目标与 evaluator | 约 80–200 evolution steps | 可执行目标，3 seeds | 更高分/更快；“causal”因子未被真实干预识别 |
| [[ICL-EF-ICML26\|Lab-in-the-Loop Feedback]] | 反馈能力实验 | 人给 feature、候选库与历史结果 | 10 iterations × 800 offline campaigns | 预计算 p-value + 随机反馈对照 | 证明能用反馈；没有在线湿实验 |
| [[ResearchClawBench-arXiv26\|ResearchClawBench]] | 跨学科 benchmark | 人给问题、文献、原始数据；隐藏目标论文 | 代表系统平均约 26–27min/题 | 专家 rubric + GPT-5.1 judge | 最佳 agent 21.5/100；仍是参考论文锚定的重发现 |
| [[Li-LongHorizonResearchEvaluation-arXiv26\|Beyond Final Scores]] | 过程 benchmark | 人给 36 个目标、起点、参考与 verifier | 2–12h，756 rollouts | rule-based C1/C2/C3 + 人工 novelty review | 仅 3/252 best solutions 判为 novel；经验可正负迁移 |
| [[EviGraph-arXiv26\|EviGraph]] | 证据状态系统 | 人给研究目标与 benchmark | 有预算 repair loop；未做 days-long stress | run artifact + LLM claim/value membership | CSR 37.85%、EDC 87.73%；按其抽取协议，62.15% claim 未判为 supported |
| [[OmniScientist-arXiv26\|OmniScientist]] | 多模态研究系统 | 人给数据、subject、target property | ideation 24 steps、experiment 50 steps | execution ledger/code gate + LLM judge | 36/36 成稿；无独立专家或外部实验验真 |
| [[FlashInfer-Bench-MLSys26\|FlashInfer-Bench]] | kernel benchmark/deployment | 人给 definition、workload 与 reference | 每题固定 agent budget | correctness sandbox + 专家 kernel | 测 AI kernel 工程；不测自主选题或科学新颖性 |
| [[SOL-ExecBench-arXiv26\|SOL-ExecBench]] | hardware-grounded benchmark | 人给 235 个 kernel problems | 多 agent/round baseline generation | output checks + SOL bound + anti-hacking | 14.5% submission 被拒；SOL model 自身仍需 audit |
| [[AdaExplore-arXiv26\|AdaExplore]] | kernel search | 人给 task、DSL 与 runtime objective | 最高 100 search steps | compile/correctness/runtime | 学 failure skills；主要证明窄域工程优化 |
| [[AVO-arXiv26\|AVO]] | 长时 kernel evolution | 人给 seed、B200、attention benchmark | 7 天单 lineage、40 commits | numerical checks + cuDNN/FA4 timing | 发现微架构优化；agent/model/cost 未充分公开 |
| [[CAKE-arXiv26\|CAKE]] | compiler-agent co-evolution | 人给 kernel spec、oracle 与硬件 | clean start 80M tokens | typed verifier + on-GPU checks + baseline | 证明 IR 共设计收益；compiler evolution 含累积先验 |

## 综合判断

### 1. “验证器强”必须先说清验证对象

| 证据层 | 能排除什么 | 不能自动排除什么 | 代表工作 |
|---|---|---|---|
| **软评审/自评** | 明显不完整、格式或叙事问题 | 同源偏好、事实错误、实验未运行 | [[AI-Scientist-arXiv24]]、[[MLR-Bench-arXiv25]] |
| **代理分数与独立 holdout** | 固定任务上的性能退化、部分过拟合 | 指标错位、新颖性、机制真实性 | [[GEPA-ICLR26]]、[[MLE-Bench-ICLR25]]、[[ASI-ARCH-arXiv25]] |
| **执行来源追踪/独立重执行** | 数字编造、代码未运行、产物错配 | 错误分析程序、选择偏差、结论越界 | [[PaperBench-ICML25]]、[[OmniScientist-arXiv26]]、[[EviGraph-arXiv26]] |
| **精确约束/编译器** | 构造无效、程序不编译、确定性约束违反 | 搜索空间外的更优解、科学意义、新颖性 | [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]] |
| **形式化证明** | 给定形式系统中的逻辑漏洞 | 自然语言题意映射、新颖性与重要性 | [[AlphaProofNexus-arXiv26]] |
| **专家、独立数据与湿实验** | 一部分领域错误和现实效应缺失 | 外部有效性、长期安全性、临床有效性 | [[Robin-Nature26]]、[[Co-Scientist-Nature26]]、[[Kosmos-AI-Scientist-arXiv25]] |

强 verifier 的真实贡献是把“候选可能胡说”转化为“候选能否通过某个明确检查”。它没有消灭幻觉，而是把错误候选自动丢弃，并把主要代价转移到**搜索 yield、评估器覆盖与目标对齐**。GEPA 的 test-set 改进、FunSearch 的合法构造和 AlphaProof Nexus 的 Lean 定理因此是三种不同的成功。

### 2. 长墙钟、总算力和长程自主不是同一量

这里的长程只作为自动科研的过程维度；状态、恢复、故障注入和副作用语义的完整诊断框架见 [[Long-Horizon-Agents|长程智能体可靠性]]。

[[RE-Bench-ICML25]] 的时间尺度反转最直接：2 小时智能体约为人类 4 倍，8 小时后人类均值已领先；32 小时点又是四名专家各做 8 小时后的 best-of-4，不是一名研究者连续工作 32 小时。[[PaperBench-ICML25]] 中 agent 约 1 小时后趋于停滞，[[InnovatorBench-ICLR26]] 的最佳结果却常在 11 小时之后出现，表明任务反馈周期会改变“合理的长程”定义。

[[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] 进一步把长循环拆成 Solution Framing、Execution 和 Feedback Control。七个模型的 Execution 都相对强，真正分化来自选对方向、保护 best state、从 regression 恢复和正确使用经验。36 个 2–12 小时任务、756 次 rollout 中，最高 avg@3 与最低相差 0.237，best@3 只差 0.122：很多模型偶尔能找到好解，却不能稳定复现。

因此至少要同时报告：单条 lineage 的连续时长、最长依赖链、并行度、总 GPU-hours、上下文压缩/恢复次数、最佳状态丢失率和人工 intervention。FunSearch 的两天、ASI-ARCH 的约 20,000 GPU-hours、DeepScientist 的一个月 campaign 都是重要规模证据，但不能单独证明通用长程自治。

### 3. 最佳结果必须与筛选分母一起读

| 系统/基准 | 公开筛选分母 | 应如何解释 headline |
|---|---|---|
| [[AI-Scientist-arXiv24\|AI Scientist]] | 616 ideas → 525 自判 novel → 327 实验通过 → 290 成文 | 证明流水线吞吐，不等于 290 篇科学上成立 |
| [[AI-Scientist-v2-arXiv25\|AI Scientist v2]] | 约 40 个想法 → 人工选 3 篇投稿 → 1 篇 workshop 过线 | 1/3 不是无条件 campaign 成功率 |
| [[FunSearch-Nature24\|FunSearch]] | cap-set 512 为 4/140 次独立运行 | 最佳构造正确，但复现该最好值概率低 |
| [[DeepScientist-ICLR26\|DeepScientist]] | 4,879 ideas → 1,108 implementations → 21 progress findings | 约 1–3% 筛选后成功率；工程失败占主导 |
| [[ASI-ARCH-arXiv25\|ASI-ARCH]] | 1,773 trials → 约 1,350 promising → 约 400 扩大验证 → 106 gallery → 5 full runs | “106 个 SOTA”是本文协议中的多层选择产物 |
| [[AlphaProofNexus-arXiv26\|AlphaProof Nexus]] | 9/353 Erdős；OEIS 44/492 | 最终证明零容错，campaign yield 仍低 |
| [[MLE-Bench-ICLR25\|MLE-Bench]] | pass@1 16.9%，pass@8 34.1% | 重复尝试可将奖牌率翻倍，不能只报 best-of-8 |
| [[Li-LongHorizonResearchEvaluation-arXiv26\|Beyond Final Scores]] | 252 个 best-of-3 solution 中仅 3 个经人工保留为 novel，16 个是 evaluator shortcut | 高分更常来自组合既有技巧，偏离常规时也更可能利用漏洞 |

强 verifier 可以让**被选中的最终候选**很可靠，却不能让**每次 campaign** 都高产。成功率、候选总数、独立重复、被丢弃原因和人工筛选工时必须进入发现成本。

### 4. 证据状态正从日志升级为研究操作系统

长程系统的关键抽象逐渐从“更长 prompt”转向可失效、可回滚的研究状态：

- [[AutoScientists-arXiv26]] 记录 champion、失败方向、论坛讨论和团队拓扑，解决多人重复探索与状态漂移。
- [[EviGraph-arXiv26]] 把上游节点变更传播到下游 claim，并用 checkpoint 拒绝让一次修复破坏已验证链；但只给出一个未触发 rollback 的案例，关键恢复分支仍主要是设计而非经验事实。
- [[OmniScientist-arXiv26]] 用 execution record 约束每个数字和论断；36 次运行中有 115 次 finalize 被代码 gate 退回、67 项分析被降级，说明结果选择比数字 fabrication 更常见。
- [[Kosmos-AI-Scientist-arXiv25]] 用结构化世界模型压缩 200 多条轨迹；解释/综合 claim 的支持率仍显著低于数据与文献 claim，说明“记住证据”和“正确解释证据”是两种能力。

这类基础设施应允许 claim 随数据、代码、假设或 evaluator 版本变化自动失效，而不是只保存一份成功报告。MLR-Bench 的结果编造、PaperBench 的极低 Result Match 和 ResearchClawBench 的 Evidence Mismatch 都指向同一缺口。

### 5. 真正的科学证据仍是科学家参与闭环

[[Robin-Nature26]] 从 dAMD 文献出发提出增强 RPE phagocytosis，筛出药物候选，分析 flow cytometry 与 RNA-seq，并得到 ripasudil、KL001 和可能的 ABCA1 机制线索。证据包含多轮体外实验和人类复核，但科学家选择候选、改变细胞/assay、撰写实验 protocol、实际操作实验并决定何时继续；Robin 自动化的是关键认知环节，不是实验室执行。

[[Co-Scientist-Nature26]] 同样由科学家定义目标并从 agent 候选中选择，后续以 AML、肝纤维化和 AMR 的专家/体外实验检验；结果仍是早期 in vitro 证据，不是临床确认。[[DeepScientist-ICLR26]] 的三项 AI 结果经脚本与三名监督者验证，但没有湿实验；[[Kosmos-AI-Scientist-arXiv25]] 有独立计算重分析和专家 claim 审核，部分生物机制仍待实验。

与之相反，[[ICL-EF-ICML26|Lab-in-the-Loop Feedback]] 的“lab”完全来自 JUMP 数据库中已经存在的 p-value：800 个 campaign、10 轮反馈、每轮 100 个 gene 都是离线查询。随机反馈对照确实说明 Sonnet 4.6 会利用反馈内容，但不能证明 agent 能处理真实 plate noise、batch effect、延迟、实验失败或仪器异常。

### 6. 开放发现与可重复评测仍有结构性张力

三种新 benchmark 正好形成三角：

- [[DDR-Bench-ICML26]] 的目标最开放——只给 schema，由 agent 决定查什么；但“新洞见”主要由 checklist 和 LLM 比较，真值覆盖最软，且自选轮数混入计算预算。
- [[CausalGame-ICML26]] 的真值最硬——隐藏 SCM 和主动干预可计算最优策略；但目标、变量和动作空间都封闭，恢复的是设计者已知机制。
- [[ResearchClawBench-arXiv26]] 用 40 篇隐藏论文锚定十个领域的真实问题、数据和 multimodal rubric；可审计性较强，却仍主要测 target-paper re-discovery。最佳 agent 只有 21.5/100，失败集中在 protocol mismatch、evidence mismatch 与遗漏科学核心。

越开放，越难建立完整真值；越容易评分，越可能重走已知路径。合理做法不是选一端，而是明确 benchmark 测的是目标形成、过程控制、重发现还是新发现，并把任何超越 reference 的结果交给独立领域团队验证。

### 7. Scaffold 是实验变量，不是背景常量

同一模型换 scaffold 会改变可观测能力。[[MLE-Bench-ICLR25]] 中 GPT-4o + AIDE 的奖牌率为 8.7%，OpenHands 为 4.4%，MLAgentBench 风格 scaffold 只有 0.8%。AstaBench 的专用 Asta v0 含 task router 和模块先验，不能与极简 ReAct 当作只差模型。Beyond Final Scores 则在固定 36 题上发现 native/open-source harness 主要提升 avg@3 稳定性，best@3 与模型排序变化较小；自动演化 harness 的收益只稳定迁移到同类 System Optimization，跨任务族不清楚。

公平比较至少应固定模型、任务、环境、总 wall-clock、token/GPU 预算、重启次数和可见反馈，并分别报告 model、harness 与并行选择器的贡献。OpenHands 的价值因而是提供可复用实验底座，而不是作为科研能力的直接证据。

## 共同结论

1. **“自主”通常从问题形成之后才开始。** skeleton、数据、evaluator、形式命题、基线和停止规则仍大多由人提供；DDR-Bench 只在目标选择上走得更远，[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 也仍由人设定市场、数据、目标和回测协议。
2. **执行能力已经领先于证据控制与方法新颖性。** Beyond Final Scores 中 Execution 最集中，只有 3/252 best solutions 判为 novel；ResearchClawBench 也显示完整报告常缺核心 protocol 和 evidence chain。
3. **强 verifier 提高最终正确率，却把问题转成 yield 与 evaluator 覆盖。** 它不能自动判断任务是否值得、指标是否正确或结果是否新颖。
4. **长时失败主要是系统问题。** 过早停止、异步作业冲突、忘记最佳状态、错误经验迁移和 context compression 都会让更长预算失效；具体测量与恢复语义见 [[Long-Horizon-Agents|长程智能体可靠性]]。
5. **过程反馈既能教学，也能误导。** Lab-in-the-Loop Feedback 的随机标签会显著伤害 agent；Beyond Final Scores 的跨任务 lessons 有时提分、有时诱发 local optimum 或 evaluator shortcut。
6. **“causal”需要真实识别证据。** CausalGame 有已知 SCM 但世界封闭；CausalEvolve 的因子和近似 ATE 用于搜索引导，却没有满足无混杂或跨环境识别条件。
7. **多模态感知扩展了问题空间，不自动扩展真值。** OmniScientist 证明原始记录会改变研究问题，但最终 claim 仍需独立领域验证。
8. **成本必须统一记账。** rollout、LLM call、GPU-hour、候选评估 compute、美元、wall-clock、人工审查和湿实验成本不能互换。

## 假设冲突与脆弱点

1. **通用性与硬验证能否兼得？** 通用系统的 claim 空间开放，精确 verifier 只能覆盖局部；窄域搜索的 verifier 强，却把问题 formulation 留给人。
2. **证据账本能否检查错误分析本身？** 来源追踪可证明数字来自某次运行，不能证明统计模型、数据清洗和因果解释正确。
3. **发现数量是否随算力扩展？** ASI-ARCH 与 DeepScientist 都给出上升曲线，但缺少多 seed、固定总 trial 和独立 campaign；不能据此建立 scaling law。
4. **更多经验为何有时更差？** 未经验证的 summary 会固化错误结论，跨任务 lesson 可能携带 evaluator-specific shortcut；记忆需要删除、反证和版本语义。
5. **自动评审能否成为最终科学 gate？** EviGraph、OmniScientist、ResearchClawBench 都让 LLM 参与 claim/rubric 判断；当前缺乏足够大的盲法人类一致性和跨实验室复现。
6. **离线反馈能否外推到真实实验室？** 清洁的数据库 hit/miss 没有 batch effect、失败实验和延迟；Robin/Co-Scientist 的真实湿实验又依赖大量人工操作，二者之间仍有系统鸿沟。
7. **reference-anchored benchmark 会不会惩罚真创新？** Hidden paper 提供可审计锚点，却让评分器偏向已知 protocol；超过 reference 的候选仍需另建外部验证流程。

## 值得关注的研究方向

### 1. 建立可失效的论断—证据账本

将每条 claim 绑定 problem 版本、数据 hash、代码 commit、环境、完整 test family、输出和解释；上游节点变化时自动使下游 claim 失效。先在 MLR-Bench/PaperBench 风格任务上测 fabrication、stale claim 与独立重执行率，再扩展到科研数据。

### 2. 对长程研究系统做故障注入

在固定模型和总预算下，注入 context compaction、异步 job 延迟、节点重启、错误高分、过期经验和 evaluator 版本变化，分别测最佳状态保持率、恢复时间和错误 claim 传播距离。它比单报最终分更能检验研究操作系统；统一指标见 [[Long-Horizon-Agents|长程智能体可靠性]]。

### 3. 把候选选择偏差纳入 verifier 设计

除最终 holdout 外，保存从未参与搜索的二级 holdout；随候选数报告 generalization gap，并用固定候选池比较标量、带噪语言反馈、编译器诊断和形式证明。这样才能分离 GEPA/MetaMuse/CausalEvolve 的反馈信息量与搜索器贡献。

### 4. 做等预算 scaffold 因果实验

固定 model、token、wall-clock、并行度和 evaluator calls，对比极简 ReAct、OpenHands/AIDE、证据图、共享论坛和 auto-harness；报告 avg@k、best@k、状态丢失、人工 intervention 与真实总成本。

### 5. 为科学家参与闭环建立 intervention log

Robin、Co-Scientist、Kosmos 和 DeepScientist 应统一记录人类何时改题、换 assay、删候选、修代码、解释结果和决定停止。目标不是消除人类，而是能区分 agent 贡献、领域安全 gate 和不可替代的实验劳动。

### 6. 从便宜、强验证的窄域建立可复现发现率

小团队可选择组合数学、编译器 heuristic、kernel 或量化投研中的预注册任务，运行多独立 campaign，完整公开候选分母、失败类型、验证 compute 与专家新颖性判断。[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 提供了低成本闭环起点，但还需要 blind time split、交易成本、候选选择偏差和独立重执行。比复制超大并行搜索更重要的是建立可复现的 **discovery yield**。
