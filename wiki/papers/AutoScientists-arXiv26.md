---
type: paper
name: AutoScientists
full_title: "AUTOSCIENTISTS: Self-Organizing Agent Teams for Long-Running Scientific Experimentation"
authors: [Shanghua Gao, Ada Fang, Marinka Zitnik]
venue: arXiv
year: 2026
tags: [auto-research, multi-agent, scientific-discovery, long-horizon-agent, llm-agent, ai4science]
source_pdf: "[[arxiv26-gao-autoscientists.pdf]]"
source_md: "[[arxiv26-gao-autoscientists]]"
---

# AUTOSCIENTISTS: Self-Organizing Agent Teams for Long-Running Scientific Experimentation (arXiv 2026)

> **一句话总结**：AutoScientists 把 long-running scientific experimentation 建模为**无中心 planner 的程序搜索**，依赖 shared experimental state + peer critique + 动态 team 重组在固定 **experimental-compute budget** 下并行探索；在 BioML-Bench 24 任务平均 leaderboard percentile **74.40%**（比 Autoresearch-style baseline +8.33）、GPT nanochat 达到 val_bpb≈0.978 只需 **34 vs 65** 次实验（1.9×）、从 champion 继续优化接受 **7 vs 0** 个改进，并在 ProteinGym 217 assays 上将 Kermut 平均 Spearman ρ 从 **0.657→0.700**。

## 问题与动机

[[Auto-Research]] 方向的 agent 已能生成假设、写代码、跑实验并根据反馈迭代，但多数系统仍沿**单一研究轨迹**推进，或依赖中心 planner / 启动时固定的 search-space decomposition。[[MLAgentBench-ICML24|MLAgentBench]]、AIDE、[[Auto-Research-arXiv25|Karpathy Autoresearch]] 等 single-agent loop 在 short-horizon ML engineering 上有效，却在 long-running science 上遇到结构性瓶颈：productive direction 会随证据变化；失败方向必须被记录以免重复探索；新假设往往在分析大量 near-miss 之后才浮现。

作者将问题形式化为**长期程序搜索**：给定任务描述、数据集 D、评估协议 ℓ_eval 和可选初始程序 p₀，n 个持久 agent 不断提出代码变体、在 D_train 上训练、用 ℓ_eval 评估，目标是最大化探索到的 champion 程序 p*。这与 [[AlphaEvolve-arXiv25|AlphaEvolve]] 的 evaluator-driven evolution、[[AI-Scientist-v2-arXiv25|AI Scientist v2]] 的 stage-manager tree search 不同——核心 claim 不是「更好的 mutation operator」，而是**协作结构本身**：在实验预算固定时，如何让多个 agent 维持并行竞争假设、在 stagnation 后重组、并把失败知识跨 team 传播。

## 关键观察 / 隐含假设

- **观察 1**：long-running experimentation 中，search-space partition 在运行开始时不可知，且会随实验结果漂移——单轨迹 agent 会在 exhausted direction 上反复 perturb，而错过从未被提出的 axis（GPT champion 续跑实验中，query-key normalization order 在 Autoresearch 100 次尝试中从未出现）。
  - **依赖假设**：不同 research direction（architecture / schedule / optimizer / featurization 等）在固定 wall-clock 内可**并行**推进，且并行带来的 coverage 增益大于 coordination overhead。
  - **可能失效场景**：实验强串行、方向间强耦合需顺序消融、或 GPU 预算只允许单实验时，team 并行优势消失（BioML-Bench 评测即被限制为每任务 1×H100 串行）。

- **观察 2**：在 GPU 训练/评估主导的成本结构下，**experimental compute** 而非 LLM token 是稀缺资源；在消耗 GPU 前用 peer critique 过滤弱 proposal，比事后分析失败实验更划算。
  - **依赖假设**：agent 的 critique 能识别明显重复、已登记 dead-end、或与 champion 机制矛盾的 proposal；forum 讨论不会系统性压制 bold but correct 的方向。
  - **可能失效场景**：critique 质量随 base LLM 波动；高维搜索空间中「看起来合理但实验无效」的 proposal 仍可能漏过；论文未量化 critique 的 false reject rate。

- **观察 3**：stochastic training metric 下，必须把「噪声带内的提升」与真实改进区分，否则 champion 被随机波动污染会级联误导后续搜索。
  - **依赖假设**：用历史实验估计噪声 σ，Δ > Mσ 直接 promote、0 < Δ ≤ Mσ 需第二 seed 确认，足以控制 false promotion。
  - **可能失效场景**：σ 估计不准、任务 metric 非平稳、或 champion 切换改变后续实验的 baseline 分布时，gate 可能过松或过严。论文未报告 promotion gate 的误接受/误拒绝率。

- **假设 1**：去中心化自组织（无 manager agent、roster 由 discussion 投票形成）在 long horizon 上优于固定 role pipeline 或共识收敛式 debate。
  - **证据强度**：**中**——ablation 显示移除 self-organization 在 GPT optimization 上最伤（val_bpb 0.9777→0.9833），但四个组件在不同任务上各为主导因素，说明没有单一机制普适成立。

- **假设 2**：shared state（champion、experiment log L、forum F、dead-end registry D_k、cross-team readable queue）是避免重复探索的关键，而非更多 agent 数量本身。
  - **证据强度**：**中偏强**——independent-agents ablation 在 Cell-Cell Communication 上 Odds Ratio 从 0.924 跌至 0.435，为最大比例降幅；但正确性依赖 agent 遵守 markdown/JSON protocol，而非强类型 runtime 保证。

## 核心方法

AutoScientists 部署 n 个 long-running agent（默认 **3 analyst + 6 experiment**），由确定性 monitor 以 heartbeat 循环唤起；每个 agent 读共享状态 S 后自主行动，**无中心 orchestrator agent**。系统在 **discussion phase** 与 **execution phase** 间交替，全程由 S 协调而非 planner 派单。

**Discussion & self-organization**：冷启动时无 team、无预设方向。每轮 discussion 中，agent 读任务、p* 和 forum，独立提出修改、critique 竞争方案、识别 search gap；多数 agent 投 `[DISCUSS-DONE]` 后，字母序最后的 analyst 将提案 consolidate 为 roster R = {(T_k, axis_k, members_k)} 写入 S。stagnation（如连续 10 次实验无改进）触发 re-discussion，team 可创建、合并、拆分或退休，变更需受影响 team 背书。

**Execution & 角色分工**：每个 team 持续 propose-execute loop：
- **Analyst**：audit 未测参数、按历史 effect size 排序 proposal、维护 empirical axis priors，向 queue Q_k 投递实验；champion 更新后分析「什么特征带来增益」并 propose 同特征变体。
- **Experiment agent**：从 Q_k claim 实验、对 p* 打 patch、训练、经 noise-aware gate 决定是否 promote、写回 L 和 F。所有结果（含失败）对全 team 可见；失败进入 dead-end registry D_k。

**Shared state 四层**：(1) champion p* 含完整超参与复现说明；(2) experiment log L；(3) shared forum F（proposal / result / 机制分析）；(4) team-local但 cross-team readable 的 Q_k、D_k、hypothesis docs。输出包括最终 p*、model card 和 research findings report。

**实现形态**（开源仓库）：并非大型 Python agent framework，而是 **Claude Code subagents + ClawInstitute 本地协作服务 + markdown runbook/role template**。`launch.py` 创建 run directory，注册 monitor + GPU agents + analysts；`runbook.md` 只做循环调度**不训练模型**；`HEARTBEAT.md` 驱动 mode selector（discussion / no-team / resume result / normal cycle）。共享状态落地为 workspace 内 `champion.md`、`teams/roster.md`、`queue.md` 等文件，queue claim 与 champion update 靠 ClawInstitute 文件 API 的 **optimistic concurrency（If-Match 409）** 控制。相对 [[OpenHands-ICLR25|OpenHands]] 的 event-stream sandbox 或 [[AI-Scientist-v2-arXiv25|AI Scientist v2]] 的 in-memory tree，AutoScientists 把协调契约外显为**可审计的文件协议**——这也是系统论文最值得抽象的部分，但也是脆弱性来源。

## 设计取舍

- **取舍 1：优化 experimental-compute budget，不优化 LLM-call efficiency**——多 agent discussion、re-organization 和 cross-team 传播显著增加 token（Table S8 显示与 Autoresearch 同量级但更高）。收益是在相同 GPU 实验次数下更好 coverage；代价是 dollar cost 可能更高，论文未报告总费用。
- **取舍 2：去中心化 forum 协调 vs 中心 planner**——收益是方向可随证据动态重组，避免启动时错误 decomposition 锁死；代价是 coordination 正确性依赖 LLM 遵守 protocol，且 alphabetically-last analyst consolidate roster 存在单点语义风险。
- **取舍 3：markdown/JSON 软协议 vs 强 runtime enforcement**——收益是快速原型、人类可读 trace、ClawInstitute revision 历史可 replay；代价是 agent 若跳过 `result_latest.json`、直接写 `submission.csv` 或丢失 API trail，系统无硬隔离纠错。
- **取舍 4：peer critique 前置 vs 先跑再议**——收益是减少无效 GPU 实验；代价是可能过滤掉 counter-intuitive 但正确的方向，论文未 ablate「无 critique、仅 shared log」的折中。
- **边界条件**：在**可脚本化 train/eval loop、metric 可标量排序、实验单次成本可控**的 computational science（BioML、nanochat、ProteinGym）下最优雅；换到湿实验、需人类伦理审批、或 metric 需专家判读的领域会显著变脆。

## 实验与结果

- **BioML-Bench**（24 个 biomedical ML 任务，4 域）：AutoScientists 平均 leaderboard percentile **74.40 (6.20)%**，Autoresearch-style baseline **66.07 (7.38)%**，**+8.33**；24/24 完成。drug discovery 提升最大（64.52% vs Biomni 46.16%）；protein engineering 已饱和（~97%）；imaging 最难。匹配 per-domain experimental compute；每任务限制 **1×H100 串行**。
- **GPT nanochat training optimization**（5 min/H100 实验，val_bpb 越低越好）：(a) 从 baseline 0.998 出发，达 ≈0.978 需 **34 vs 65** 实验（**1.9×**），三 team 并行覆盖 architecture/schedule/optimizer；(b) 从 champion 0.9777 续跑，**7/93 accepted → 0.9730**，Autoresearch **0/100 accepted**，best 0.9783。
- **ProteinGym / Kermut 扩展**：ACE2–Spike 开发 assay Spearman ρ **0.747→0.840**（+12.5%）；冻结 recipe 后 217 assays 官方平均 ρ **0.657→0.700**（+0.043，+6.5%）。发现三-GP ensemble + expanded zero-shot features + diversity feature selection + quantile-warped targets；MSE 略升 0.006（rank-oriented 优化副作用）。
- **Ablation**（4 任务 × 4 组件）：full system 全胜。No analyst 最伤 TDC-hERG（AUROC 0.867→0.738）；No cross-agent feedback 最伤 Plasma-Protein Binding（Pearson 0.8729→0.7144）；No self-organization 最伤 GPT（0.9777→0.9833）；Independent agents 最伤 Cell-Cell Communication（OR 0.924→0.435）。
- **实现**：Claude Code + Claude Sonnet 4.6；与 baseline 同 backend。默认 3+6 agent roster。

## Critical Analysis

### 论证链条

作者链条：**(观察) 单轨迹/固定 decomposition 无法支撑 long-running search → (设计) 去中心化 team + shared state + critique + re-organization → (结果) 三域 SOTA-over-baseline under matched experimental budget → (结论) coordination architecture 是瓶颈**。方法到主结果的整体逻辑闭合较好，尤其 GPT champion 续跑（0 accepted vs 7 accepted）直接支撑「不是更多 compute，而是更广 hypothesis coverage」。

薄弱跳步在于：(1) BioML-Bench 的「Autoresearch」baseline 实为 **Autoresearch-style single-agent coding loop**，不是 Karpathy `autoresearch` repo 直接跑 biomedical 任务——开源显示 BioML profile 需从零写 `train.py`，而 GPT 任务才 clone 原版 repo；表格命名易让读者误读。(2) 将 BioML percentile 增益外推为「普适优于一切 single-agent 科研 agent」时，未与 [[AI-Scientist-v2-arXiv25|AI Scientist v2]]、[[Kosmos-AI-Scientist-arXiv25|Kosmos]]、Biomni 等在**相同 orchestration-only 变量**下系统对照（Biomni 仅部分域可比）。(3) ProteinGym 的 217-assay 提升来自**单 assay 开发后冻结**，泛化证据强于 repeated CV tuning，但仍非独立 held-out test protocol 意义上的 blind discovery。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 并行 team 提升 experiment efficiency | GPT 34 vs 65；forum log 案例显示去重与 dead-end 退休 | 单 GPU 串行、强耦合实验、agent 数固定无法扩缩 |
| Peer critique 改善 proposal quality | 定性 forum 案例；无 critique ablation 独立成条 | critique 系统性保守；跨 team 信息过载 |
| Shared state 减冗余 | independent-agents ablation 最大降幅 | protocol 违规、queue claim 竞态、ClawInstitute 非强事务 |
| 匹配 experimental budget 的公平性 | 同 backend、同 task interface、per-experiment 轨迹对比 | BioML domain scaffold（approach menu、diversity 规则）是否对 baseline 同等；LLM token 未匹配 |
| 冻结 recipe 跨 assay 泛化 | 217 assays +6.5% ρ | 开发 assay 选择偏差；quantile warp 损害校准回归 |

**推断（非论文证明）**：若将 team 数、discussion 轮次、approach menu 等 scaffold 去掉，multi-agent 相对 single-agent 的增益可能显著缩水——当前结果混合了 **orchestration + domain prompt engineering** 的贡献，二者未充分分解。

### 实验可信度

- **Benchmark 代表性**：BioML-Bench 覆盖 imaging/drug/protein/single-cell，比 [[MLE-Bench-ICLR25|MLE-Bench]] 更偏 biomedical、比 [[MLR-Bench-arXiv25|MLR-Bench]] 更偏 end-to-end pipeline；GPT nanochat 是 [[Auto-Research-arXiv25|Autoresearch]] 原题，external validity 高；ProteinGym 是标准 protein ML benchmark。三域组合支持「跨 scientific domain」claim，但不覆盖系统性能优化、分布式训练、理论证明类任务。
- **Baseline 强度**：GPT 对比公平（同 repo、同 orchestration-only 变量）；BioML 对 Autoresearch-style loop 而非完整 Biomni/STELLA 全矩阵；ProteinGym 对 Kermut SOTA 合理。缺少与 [[ASI-ARCH-arXiv25|ASI-ARCH]] 式固定 pipeline multi-agent 的 head-to-head。
- **Ablation**：四组件在四任务上互补，支持「非冗余」叙事；但每个 ablation 只跑代表任务，未给出统计重复或 confidence interval。
- **Metric 覆盖**：主 metric 为 leaderboard percentile / val_bpb / Spearman ρ；tail latency、失败恢复时间、protocol 违规率、人类复现成本——**论文未讨论**。MSE 退化被承认但未纳入优化目标。

### 系统性缺陷

- **正确性与隔离**：依赖 agent 自觉遵守 markdown heartbeat 规则；无 Docker 级 sandbox 隔离、无 deterministic replay of LLM decisions。ClawInstitute 本地模式 auth 弱（`X-Agent-Name` 识别），不适合 multi-tenant production。
- **可观测性**：experiment log + forum 提供丰富 trace，但缺少结构化 metrics dashboard 或自动化 protocol linter；运维需人工读 workshop posts。
- **故障恢复**：`result_latest.json` + stale claim sweep（30 min）+ resume posting 机制可恢复部分失败，但训练中途崩溃、GPU OOM、ClawInstitute 409 冲突的处理仍靠 orchestrator 轮询启发式。
- **成本与复现**：需 Claude Code/Sonnet 4.6、H100、多小时 run、大量 Python/ML 依赖；BioML 全量多 seed 重复不可行（论文自述）。论文未讨论 wall-clock vs experiment-count 的 trade-off 在真实 lab 中的可接受性。
- **过拟合风险**：BioML 开发期反复 local CV 选模，最终 private grader 评分；虽排除 `private/answers.csv`，多轮 search 仍可能 overfit validation feedback——与 [[MLE-Bench-ICLR25|MLE-Bench]] 式 held-out test 相比证据更弱。

## 局限与 Future Work

- **局限 1**：不以 LLM-call efficiency 为目标；多 agent 讨论与重组带来更高 token 成本，总 dollar cost 可能高于 single-agent，即使 GPU 实验数更少。
- **局限 2**：BioML-Bench 评测每任务 **1 GPU 串行**，未充分展示 parallel experimentation 的核心能力；多 GPU scaling 仍为 future work。
- **局限 3**：agent 数量启动前固定（默认 9 worker + monitor）；动态扩缩 team 仅有 Appendix B.2 初步探索。
- **局限 4**：ProteinGym 优化 Spearman ρ 时 MSE 略升；multi-objective leaderboard（含校准指标）未实现。
- **Future work 1**：在 matched **token + GPU** 双预算下测量 scaling law——team 数、GPU 数、discussion 频率对 percentile/val_bpb 的边际收益，回答「何时 multi-agent 值得付费」。
- **Future work 2**：将 markdown protocol 收敛为**可验证 runtime contract**（typed queue、hard promotion gate、automated protocol lint），并报告 violation rate 与对结果的影响——这是从 demo 走向 research OS 的关键测量。
- **Future work 3**：明确命名并开源 **Autoresearch-style single-agent baseline** 与 Karpathy GPT repo 的区分，在 BioML 上补充与 Biomni/AIDE 的 orchestration-matched 对照。

## 相关

- **相关概念**：[[Auto-Research]]、long-horizon agent、multi-agent collaboration、shared state、dead-end registry、noise-aware validation
- **同类系统**：[[AI-Scientist-v2-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[OpenHands-ICLR25]]
- **评测基准**：[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]
- **对比**：AutoScientists 强调 **decentralized team + experimental-state protocol**；[[AlphaEvolve-arXiv25]] 强调 evaluator-driven code evolution；[[AI-Scientist-v2-arXiv25]] 强调 stage-manager tree search + manuscript pipeline