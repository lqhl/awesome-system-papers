---
type: theme
topic: Long-Horizon-Agents
theme_kind: lens
member_tag: concern/long-horizon
candidate_tags: [long-horizon, long-horizon-agent, long-horizon-agents, long-running-agent]
paper_count: 13
first_generated: 2026-08-18
last_updated: 2026-08-18
tags: [topic-overview, llm-agent, long-horizon]
---

# 长程智能体（Long-Horizon Agents）综述

> 13 篇核心论文表明，长程能力不是“给模型更多时间”或“塞入更长上下文”，而是让 model、harness 与 environment 在长依赖链中共同维持目标、状态、反馈和恢复语义。AVO 补充了 7 天单 lineage 的系统优化证据，也暴露模型、成本和恢复实验透明度仍不足。

## 定义与边界

本文把长程任务（long-horizon task）定义为：后续决策的正确性持续依赖早期行动、外部环境变化和中间证据，且这些依赖可能跨越 context compaction、异步作业、失败重试或进程重启。真正的 horizon 因而是**最长有效因果链**，不是单一时钟数字。

以下概念不能替代长程能力：long context 只扩大一次推理可见的信息；long-term memory 只提供跨回合存取；长 wall-clock 可能只是等待训练；高总算力可能来自大量独立候选并行。[[DeepScientist-ICLR26]] 的一个月 campaign、[[MLE-Bench-ICLR25]] 的 24 小时预算和 [[Agentix-NSDI26]] 的多轮 program 都很长，但它们携带状态与反馈的方式不同，不能用同一“运行时长”排序。

纳入核心集合需满足两项条件：论文以多阶段依赖任务为主要对象；其核心论断直接涉及 horizon-dependent degradation、跨阶段状态、反馈控制、恢复，或完整 program 的调度。只优化记忆检索、长上下文、并行吞吐或 24 小时到达流量而未验证单任务依赖链的工作放入邻接区。

## 核心论文

### 过程与时间尺度评测（7 篇）

- [[MLAgentBench-ICML24|MLAgentBench]] — 最多 50 actions / 5 小时的 ML 实验中，除最强模型外步数增加常伴随退化；坏规划、未执行便宣称成功和格式错误是早期长程失效信号。
- [[MLE-Bench-ICLR25|MLE-Bench]] — 固定 24 小时单 A10；pass@1 为 16.9%，pass@8 可到 34.1%，说明重复运行能买到成功，但不等于单条轨迹持续进步。
- [[RE-Bench-ICML25|RE-Bench]] — 2 小时时智能体领先，8 小时后人类反超；它把 time horizon 与人类专家在同任务、硬件和预算下直接比较。
- [[PaperBench-ICML25|PaperBench]] — 12–36 小时论文复现中，agent 约 1 小时后趋于停滞；代码、实际执行和结果匹配之间存在断崖式差距。
- [[InnovatorBench-ICLR26|InnovatorBench]] — 2–36 小时真实 LLM 研发环境中，最佳结果常在 11 小时后出现，同时暴露异步 job、早停和资源管理失败。
- [[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] — 将长循环拆成 Solution Framing、Execution 与 Feedback Control；36 个 2–12 小时任务的 756 条 rollout 显示，稳定性差异主要来自方向、best state 与 regression recovery。
- [[DDR-Bench-ICML26|DDR-Bench]] — 不给具体问题，让 agent 自选调查目标与停止时机；部分轨迹陷入 debugging loop 并在 100 rounds 被截断，说明目标形成和终止本身是长程能力。

### 长时科研系统、搜索与显式状态（5 篇）

- [[Kosmos-AI-Scientist-arXiv25|Kosmos]] — 用结构化世界模型压缩 12 小时、20 cycles、200 多条轨迹；它能保存来源，却仍难保证解释与综合类 claim 正确。
- [[AutoScientists-arXiv26|AutoScientists]] — 以共享 champion、失败登记、论坛和动态组队维持 4–16 小时实验，重点是减少重复探索与协作状态漂移。
- [[DeepScientist-ICLR26|DeepScientist]] — 一个月、约 20,000 GPU-hours 的 campaign 从 4,879 个想法筛到 21 个进展；它证明大规模筛选可运行，也暴露总算力不能代表单轨自主性。
- [[EviGraph-arXiv26|EviGraph]] — 把 Problem→Claim 依赖写成版本化证据图，以 checkpoint 和事务式 rollback 保护有效链；关键恢复分支尚缺 days-long 故障注入。
- [[AVO-arXiv26|AVO]] — 用 git lineage、完整历史、profiler/evaluator 和停滞 supervisor 维持 7 天 attention-kernel evolution；40 个 committed versions 单调保护 best state，但没有 context compaction、crash injection 或多 seed 稳定性。

### 长程序 Runtime（1 篇）

- [[Agentix-NSDI26|Agentix]] — 把 serving 调度对象从 request 提升为完整 agent program，用 program identity 和已完成调用数缓解两级队首阻塞；相同 latency 下 program throughput 提高 4–15×，但 call count 可能误判动态分支的剩余工作。

## 设计空间矩阵

| 论文 | 任务与 horizon | 状态载体 | 反馈延迟 | 恢复 / 控制 | 主要评测边界 |
|---|---|---|---|---|---|
| [[MLAgentBench-ICML24\|MLAgentBench]] | ML 实验，最多 50 actions / 5h | workspace + 短记忆 | 训练与任务分数 | Plan / Fact Check，无持久恢复 | 13 个单机任务 |
| [[MLE-Bench-ICLR25\|MLE-Bench]] | Kaggle 工程，24h | repo、checkpoint、submission | 训练 + private leaderboard | scaffold-dependent persistence | 75 个竞赛，1×A10 |
| [[RE-Bench-ICML25\|RE-Bench]] | AI R&D，2–32h 预算曲线 | workspace 与实验产物 | 可执行任务评分 | 人机时间比较；恢复机制不是主变量 | 7 个自包含任务 |
| [[PaperBench-ICML25\|PaperBench]] | 论文复现，12–36h | repo、日志、结果文件 | 训练 / fresh VM 重执行 | IterativeAgent 强制续作，无显式 best-state control | 20 篇 ICML 论文，1×A10 |
| [[InnovatorBench-ICLR26\|InnovatorBench]] | LLM 研发，2–36h | repo、训练 job、提交结果 | 异步训练与 executable score | 监控、早停和资源管理由 agent 决定 | 隐藏参考方法与特定环境 |
| [[Li-LongHorizonResearchEvaluation-arXiv26\|Beyond Final Scores]] | 研究优化，2–12h | solution lineage、经验与 harness state | verifier + 过程诊断 | best-state preservation、regression recovery | 36 题、756 rollouts |
| [[DDR-Bench-ICML26\|DDR-Bench]] | 开放数据调查，最多 100 rounds | 完整 trajectory 与数据库 | 查询结果 + 隐藏 checklist | 自主终止；异常 loop 被硬截断 | 291 entities、三类数据库 |
| [[Kosmos-AI-Scientist-arXiv25\|Kosmos]] | 数据—文献研究，12h / 20 cycles | 结构化 world model | 文献、数据分析与专家抽检 | 跨轨迹综合，无进程恢复实验 | 7 个案例，抽样 claim 审核 |
| [[AutoScientists-arXiv26\|AutoScientists]] | 多智能体实验，4–16h | champion、论坛、失败登记 | benchmark execution | 动态组队与 dead-end sharing | 给定任务、数据、指标和初始程序 |
| [[DeepScientist-ICLR26\|DeepScientist]] | 月级并行 campaign | idea / implementation / result pool | GPU 实验 + 脚本 / 人工核验 | 大规模筛选，持续人工监督 | 约 20,000 GPU-hours |
| [[EviGraph-arXiv26\|EviGraph]] | 多阶段研究链 | typed evidence graph + checkpoint | artifact 与 LLM inspector | descendant invalidation + rollback | 未报告统一 wall-clock / cost |
| [[Agentix-NSDI26\|Agentix]] | 多调用 agent program | program ID + call progress | LLM queue 与 tool gap | token-level preemption，无 tool side-effect recovery | 高并发 agent graph |
| [[AVO-arXiv26\|AVO]] | B200 attention kernel evolution，7 天 | git lineage + conversation memory + 评分 | compile/correctness/profiling | 只提交不退化版本；停滞 supervisor 转向 | 单内部 agent、单 lineage、无故障注入 |

## 与 Auto-Research 的交集和差集

[[Auto-Research]] 按**任务目标**组织：系统是否在做研究、复现、算法搜索或科学发现。Long-Horizon-Agents 按**任务结构**组织：结果是否依赖跨阶段状态和反馈。前者是 domain，后者是 lens，因此 [[RE-Bench-ICML25]]、[[AutoScientists-arXiv26]] 和 [[EviGraph-arXiv26]] 同时属于二者不是重复，而是两条正交信息。

交集的核心问题是研究反馈慢、失败昂贵且证据会随上游变化失效。差集则同样重要：[[Agentix-NSDI26]] 研究通用 agent program 的 serving，不判断科研新颖性；反过来，[[FunSearch-Nature24]] 和 [[AlphaEvolve-arXiv25]] 可以运行很久并产生可靠候选，但大量异步、独立搜索不自动构成单条长依赖链。

## 共同观察

1. **增加预算不会自动延长有效 horizon。** [[RE-Bench-ICML25]] 出现 2h 到 8h 的人机反转，[[PaperBench-ICML25]] 约 1h 后停滞，[[InnovatorBench-ICLR26]] 却常在 11h 后才出现最佳结果；反馈周期和控制策略比统一的小时阈值更关键。
2. **Execution 已不是唯一分化点。** [[Li-LongHorizonResearchEvaluation-arXiv26]] 中不同模型的 Execution 相对集中，差异主要来自 Solution Framing 与 Feedback Control；[[DDR-Bench-ICML26]] 也显示“决定查什么、何时停”独立于 SQL/Python 执行。
3. **显式状态必须带失效语义。** [[AutoScientists-arXiv26]] 保存失败方向，[[EviGraph-arXiv26]] 传播上游变更并 rollback，[[Kosmos-AI-Scientist-arXiv25]] 压缩跨轨迹证据；仅保存更多文字不能保证旧结论仍有效。
4. **best-of-k 会掩盖单轨不稳定。** [[MLE-Bench-ICLR25]] 的 pass@8 明显高于 pass@1，[[Li-LongHorizonResearchEvaluation-arXiv26]] 的 best@3 差距也小于 avg@3；应同时报告发现上限和稳定复现能力。
5. **长程序需要暴露比 request 更多的语义。** [[Agentix-NSDI26]] 证明 program identity 已能改善调度，但 call count 仍看不到关键路径、retry、tool side effect 和真实剩余工作。
6. **单调 best-state 能保护成果，却可能限制跨谷探索。** [[AVO-arXiv26]] 只提交匹配或改善当前 best 的 kernel，避免七天轨迹回退；与 [[Li-LongHorizonResearchEvaluation-arXiv26]] 的 regression recovery 呼应，但也可能拒绝需要暂时退化的大重构。

## 假设冲突与脆弱点

- **时间代理冲突**：METR 风格 human-equivalent time 适合跨模型趋势，actions 适合协议控制，wall-clock 适合部署成本；三者都不能独立代表因果依赖深度。[[MLAgentBench-ICML24]]、[[RE-Bench-ICML25]] 与 [[DeepScientist-ICLR26]] 的数字不可直接排序。
- **记忆收益冲突**：更多经验可能帮助恢复，也可能固化错误方向。[[DDR-Bench-ICML26]] 的 long-short-term memory 在两个场景反而降分；[[Li-LongHorizonResearchEvaluation-arXiv26]] 也观察到经验的正负迁移。
- **过程信号冲突**：outcome-only reward 随 horizon 变稀疏，但 process evaluator 可能与训练共享偏差。[[EviGraph-arXiv26]] 的证据成员判断仍大量依赖 LLM，结构正确不等于科学解释正确。
- **单轨持续与可复现性冲突**：[[AVO-arXiv26]] 的 7 天连续轨迹证明系统可维持方向和 best state，却没有多 seed、公开 agent 或 restart stress；长时间成功案例不能单独给出稳定成功概率。
- **完成优先与公平性冲突**：[[Agentix-NSDI26]] 优先推进已有进度的 program 可降低平均 JCT，却可能让新任务或调用多的任务 starvation。

## 邻接与排除案例

- [[PithTrain-arXiv26]] 的 ATE-Bench 包含最多 199 Agent Turns、最长约 140.6 分钟中位 session 的训练框架修改任务，并证明代码紧凑性、错误局部性与 task skill 会降低 agent 成本；但它固定 agent、比较 framework，未测 horizon scaling、context compaction、restart/recovery 或 best-state preservation，因此属于环境可操作性的邻接证据。
- [[OpenHands-SDK-MLSys26]] 提供 event-sourced state、condensation 与 pause/resume，但没有直接测 session recovery 成功率或 horizon scaling。
- [[HIPPOCAMPUS-MLSys26]] 和 [[Tag2Graph-MLSys26]] 优化长期记忆检索；它们解决“过去信息能否取回”，尚未证明 agent 能维持长行动链。
- [[AgenticCache-MLSys26]] 用异步缓存规划降低具身任务延迟，但没有按依赖深度报告退化曲线。
- [[SkVM-SOSP26]] 解决 skill 在 model、harness 与 environment 间的 portability；论文明确没有数小时、多日、context compaction 或 crash recovery 实验。
- [[Murakkab-OSDI26]] 回放 24 小时请求流，优化的是平台 workload，而非单个 agent 连续执行 24 小时；它提出的 idempotency、checkpoint 和补偿动作仍是后续工作。
- [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]] 和 [[DeepScientist-ICLR26]] 提醒我们：大量并行候选与 GPU-hours 是 campaign scale，不应默认写成长程自主性。

## 外部补缺候选

- [The Horizon Gap](https://arxiv.org/abs/2608.06663)：按 planning、memory、execution、training、evaluation、safety 划分生命周期，并区分 context 内、跨 context 单任务和跨任务持久化。
- [HORIZON](https://arxiv.org/abs/2604.11978)：跨四个 agent domain 构造 horizon-dependent failure 诊断任务与轨迹归因。
- [METR Task-Completion Time Horizons](https://evals.alignment.org/time-horizons/)：以人类专家完成时间标定固定成功概率，适合作为能力趋势而非唯一任务定义。
- [SWE-bench Pro](https://arxiv.org/abs/2509.16941)：补充 repository-scale software engineering 的长程任务证据。

## 值得关注的研究方向

1. **Horizon-normalized benchmark**：同时报告最长依赖链、wall-clock、actions、并行度、总 compute 和恢复次数；在相同任务上测这些口径何时分叉。
2. **可失效的 agent state**：把 plan、artifact、claim、environment snapshot 与 evaluator version 组成依赖图，上游变化时自动 invalidate 下游状态，并测错误传播距离。
3. **恢复优先的故障注入**：固定模型和预算，注入 context compaction、异步 job 超时、进程重启、错误高分和损坏 checkpoint，报告恢复率、best-state 保持率和额外成本。
4. **Model–harness 解耦评测**：交叉固定 model、harness、memory 和 scheduler，分别报告 avg@k 与 best@k，避免把 scaffold persistence 当成模型能力。
5. **带副作用工具的事务语义**：为外部 API、实验设备和云资源建立 idempotency key、commit point 与补偿动作，使 agent restart 不会重复执行不可逆操作。
