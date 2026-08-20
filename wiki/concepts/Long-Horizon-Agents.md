---
type: concept
aliases: [Long-Horizon Agents, long-horizon agent, long-running agent, agent horizon, long-horizon agent reliability]
last_updated: 2026-08-20
tags: [agent-reliability, long-horizon, state-management, fault-recovery]
---

# 长程智能体可靠性（Long-Horizon Agent Reliability）

> 长程能力不是运行时间长、上下文长或并行尝试多，而是 model、harness 与 environment 能在长因果依赖链中维持目标、有效状态、反馈语义和恢复能力。

## 核心思想

任务的有效 horizon 应按**最长因果依赖链**衡量：后续决策持续依赖早期行动、外部环境变化和中间证据，而且这些依赖可能跨越 context compaction、异步作业、失败重试或进程重启。长 context 只扩大单次推理的可见信息，长期记忆只提供跨回合存取，长 wall-clock 可能只是等待训练，大量 GPU-hours 也可能来自彼此独立的候选；这些代理都不能单独证明长程可靠性。

可靠的长程智能体至少需要四种语义：目标在局部优化中不漂移；状态能区分当前 best、失败经验和未经验证的猜测；反馈能改变后续方向而不是只累积分数；失败后能恢复到仍然有效的状态，并避免重复执行带副作用的工具调用。

## 为什么重要

随着任务从一次调用扩展到多阶段研究、软件修改和 agent program，主要故障会从“单步不会做”转向“早期错误在后续被放大”。[[MLAgentBench-ICML24]] 中坏规划和未执行便宣称成功会随步数累积，[[PaperBench-ICML25]] 中代码、真实执行和结果匹配之间出现断层，[[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] 则把差异进一步定位到方案定向和反馈控制，而不只是执行能力。

当前直接相关的 13 篇论文中有 12 篇同时属于 [[Auto-Research]]。现有语料更支持把长程可靠性视为自动科研与 [[Agent-Systems]] 的**过程属性和诊断维度**，而不是独立应用领域；论文是否具备这一属性，应由退化、状态失效和恢复证据判断，而不是由固定成员集合判断。

## 与 Auto-Research 的关系

[[Auto-Research]] 问的是“研究过程是否被自动化”，本概念问的是“任意 agent workflow 能否跨长依赖链保持正确”。自动科研经常需要长程可靠性，但两者并不等价：[[FunSearch-Nature24]] 和 [[AlphaEvolve-arXiv25]] 可以用大量异步搜索产生硬验证候选，却不一定维持一条长单轨状态；[[Agentix-NSDI26]] 调度通用 agent program，又不评价科研新颖性。

因此，运行数小时或拥有 persistent memory 只能成为候选信号。只有论文直接测量 horizon-dependent degradation、状态失效、best-state 保护、restart/recovery 或带副作用工具的安全性时，才能构成长程可靠性的强证据。

## 关键观察 / 隐含假设

- **增加预算不会自动延长有效 horizon。** [[RE-Bench-ICML25]] 在短预算下观察到 agent 优势，预算增加后人类反超；[[MLE-Bench-ICLR25]] 的 pass@8 高于 pass@1，说明重复运行可以买到成功，却不能证明单条轨迹持续进步。
- **显式状态必须带失效语义。** [[AutoScientists-arXiv26]] 保存 champion 与失败方向，[[EviGraph-arXiv26]] 传播上游变化并重建下游，[[Kosmos-AI-Scientist-arXiv25]] 压缩跨轨迹证据；只保存更多文字无法判断旧结论是否仍然有效。
- **反馈频率和反馈质量共同决定可控性。** [[InnovatorBench-ICLR26]] 暴露异步 job、早停和资源管理失败，[[DDR-Bench-ICML26]] 表明“决定查什么、何时停止”独立于 SQL/Python 执行，[[Li-LongHorizonResearchEvaluation-arXiv26|Beyond Final Scores]] 还观察到经验既可正迁移也可负迁移。
- **best-state 保护与跨谷探索存在冲突。** [[AVO-arXiv26]] 只提交不劣于当前 best 的 kernel，能避免七天轨迹回退，却可能拒绝需要暂时退化的大重构。
- **长程序需要 request 之外的语义。** [[Agentix-NSDI26]] 用 program identity 和已完成调用数改善调度，但 call count 看不到关键路径、retry、tool side effect 和真实剩余工作。

## 设计空间与取舍

| 路线 | 代表论文 | 保存什么 | 主要收益 | 主要盲点 |
|---|---|---|---|---|
| 过程评测 | [[MLAgentBench-ICML24]]、[[RE-Bench-ICML25]]、[[PaperBench-ICML25]] | trajectory、workspace、最终产物 | 暴露随时间或步骤增加的退化 | 很少主动注入 restart 或状态损坏 |
| 状态压缩 | [[Kosmos-AI-Scientist-arXiv25]] | 结构化 world model 与来源 | 跨大量轨迹保留研究上下文 | 记住证据不等于正确解释证据 |
| 协作状态 | [[AutoScientists-arXiv26]] | champion、论坛、失败登记 | 减少重复探索和协作漂移 | 协议违反率与共享状态一致性证据有限 |
| 证据依赖图 | [[EviGraph-arXiv26]] | typed evidence graph、checkpoint | 上游变化可失效并重建下游 | provenance 不能发现错误统计或数据泄漏 |
| 单调 lineage | [[AVO-arXiv26]] | git history、评分与 profiler 反馈 | 保护当前 best 并支持长时迭代 | 单 lineage、无 crash injection、多 seed 不足 |
| program-aware runtime | [[Agentix-NSDI26]] | program ID 与 call progress | 缓解两级队首阻塞 | 不了解工具副作用和动态剩余工作 |

## 测量框架

长程评测至少应同时报告：最长依赖链、wall-clock、actions、并行度、总 compute、反馈延迟、有效状态大小、restart 次数、恢复率、best-state 保持率和额外恢复成本。只报告其中一个代理，会把高并行搜索、长训练等待或 best-of-k 幸运样本误写成单轨自主性。

故障注入比继续拉长运行时间更有辨识度。可固定模型与总预算，分别注入 context compaction、异步 job 超时、进程重启、错误高分、过期经验和损坏 checkpoint，再测错误传播距离、恢复成功率以及是否重复执行不可逆操作。

## 引用本概念的论文

### 直接诊断长程退化与反馈控制

- [[MLAgentBench-ICML24]] — 步数增加常伴随坏规划、幻觉和性能回退。
- [[RE-Bench-ICML25]] — 展示短预算 agent 优势与长预算人类优势的时间尺度反转。
- [[PaperBench-ICML25]] — 揭示长时论文复现中的执行停滞与结果断裂。
- [[InnovatorBench-ICLR26]] — 在 2–36 小时研发任务中暴露异步作业和资源控制失败。
- [[Li-LongHorizonResearchEvaluation-arXiv26]] — 将过程拆为 Solution Framing、Execution 和 Feedback Control。
- [[DDR-Bench-ICML26]] — 将目标形成、自主终止和 debugging loop 纳入评测。

### 状态、证据与 runtime 机制

- [[TradeTrap-arXiv25]] — 通过记忆投毒和仓位视图篡改直接证明，长期状态一旦与真实执行账本分离，局部错误会跨回合累积为集中度和回撤失控。
- [[Kosmos-AI-Scientist-arXiv25]] — 用结构化 world model 压缩文献与数据轨迹。
- [[AutoScientists-arXiv26]] — 用共享 champion、失败登记和动态组队维持多智能体实验。
- [[EviGraph-arXiv26]] — 用证据依赖与 rollback 保护跨阶段 claim。
- [[AVO-arXiv26]] — 用单调 git lineage 保护七天 kernel evolution 的 best state。
- [[Agentix-NSDI26]] — 将完整 agent program 而非单次 request 暴露给调度器。

### 规模证据与边界案例

- [[MLE-Bench-ICLR25]] — 24 小时预算和 pass@k 主要证明重复尝试收益，不直接证明单轨 horizon。
- [[DeepScientist-ICLR26]] — 月级 campaign 和约 20,000 GPU-hours 证明大规模筛选可运行，但持续人工监督与并行候选不能替代单轨恢复证据。
- [[Cordis-TechReport26]] — 形式化组件效应撤销与依赖有序卸载，并已用于 DeepSeek Harness；论文没有测量进程重启、外部副作用或智能体任务的跨故障恢复。
- [[PithTrain-arXiv26]]、[[OpenHands-SDK-MLSys26]]、[[HIPPOCAMPUS-MLSys26]]、[[Tag2Graph-MLSys26]]、[[SkVM-SOSP26]]、[[Murakkab-OSDI26]] — 分别提供环境可操作性、状态持久化、记忆或平台机制；现有实验尚未直接测 horizon scaling 与故障恢复。

## 已知局限 / 开放问题

- 现有证据主要来自自动科研，缺少量化投研、软件维护、通用工作流和带外部副作用工具的跨领域对照。
- 多数论文没有在相同任务上同时控制 wall-clock、总 compute、并行度和单轨长度，难以分离“更久”与“更多尝试”。
- checkpoint、memory 和 evidence graph 常只展示正常路径，缺少 crash、stale state、错误 evaluator 与 corruption 注入。
- 只有在至少约 5 篇非 Auto-Research 工作提供直接可靠性证据后，这一问题才足以形成独立 `Long-Horizon-Agent-Reliability` lens；当前按 concept 组织更符合现有语料。
