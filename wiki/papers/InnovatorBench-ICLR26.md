---
type: paper
name: InnovatorBench
full_title: "InnovatorBench: Evaluating Agents' Ability to Conduct Innovative LLM Research"
authors: [Yunze Wu, Dayuan Fu, Weiye Si, Zhen Huang, Mohan Jiang, et al.]
venue: ICLR
year: 2026
tags: [ai-agents, llm-research, benchmark, long-horizon, research-environment]
source_pdf: "[[iclr26-wu-innovatorbench.pdf]]"
source_md: "[[iclr26-wu-innovatorbench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# InnovatorBench：评测智能体开展创新性 LLM 研究的能力（ICLR 2026）

> **原题**：InnovatorBench: Evaluating Agents' Ability to Conduct Innovative LLM Research

> **一句话总结**：InnovatorBench 用 14 篇已发表论文衍生的 20 个隐藏-reference LLM 研究任务，加上支持 42 种动作、多机异步执行和快照的 ResearchGym，将评测时长拉到智能体达到峰值需超过 11 小时；Claude Sonnet 4 的加权 best 分数仍仅 24.54/约 80 分 reference 锚点，并暴露 impatience、GPU 冲突和模板化推理（§3–5，表 2，图 4–5）。

## 问题与动机

[[MLE-Bench-ICLR25]]、[[PaperBench-ICML25|PaperBench]] 等基准证明智能体能完成部分 ML 工程或论文复现，但复现已知流水线不等于提出和实现新方法；短时单容器环境又排除了真实 LLM 研究中的多小时训练、分布式 GPU、异步监控和反复提交。InnovatorBench 因而问：在接近 LLM 研发的资源和时间尺度上，智能体能否自行选择方法、实现、训练、根据反馈迭代，并超过隐藏参考解（§1–3）。

论文同时发布 ResearchGym，定位为基准-agnostic 研究环境。它将 command、file、parse、web 搜索/browse 和多机控制统一为智能体动作，支持后台训练与快照/branch。贡献重点既是 20 个任务，也是在基础设施层把「等待 10 小时训练、记住已占用 GPU、从中间状态恢复」纳入智能体能力（§4）。

## 关键观察 / 隐含假设

- **观察 1：长时科研失败往往来自执行治理，而非没有生成想法。** 日志显示智能体会在训练已运行约 10 小时、尚余约 21 小时时主动杀掉进程；或在 55 步后忘记已有单 GPU 推理 job，再启动占满全部 GPU 的训练（§5.4，图 4）。
  - **依赖假设**：ReAct 轨迹中观察到的行为能代表模型，而非提示词、context compression 或 ResearchGym 动作 semantics 的特例。
  - **可能失效场景**：加入显式 resource ledger、job scheduler 或更强 persistent 记忆后，所谓「模型科研能力」缺陷可能被简单系统机制消除。
- **观察 2：数据任务对局部错误较鲁棒，loss/reward 设计对小错误呈灾难性敏感。** 四个模型在 Data Construction/Filtering/Augmentation 普遍高于 Loss/Reward Design；后两者常因错误公式、工具参数或训练未启动得到接近 0 分（§5.2，表 2）。
  - **依赖假设**：六类任务的分数 calibration 可横向比较；各类别样本数和难度并不完全匹配。
- **观察 3：给出 ground-truth hint 也不能补偿实现能力。** Claude Sonnet 4 有 hint 时 Loss Design best 分数从 12.98 升至 25.32，但 Data Augmentation 从 22.73 降至 1.00，说明复制正确方向仍会被脚本/数据实现错误击穿（§5.3，表 3）。
  - **证据强度**：中。现象清晰，但只在一个模型/脚手架上评估，且 hint 会改变探索策略与运行时间。
- **假设 1：从已发表论文移除核心新颖性、保留 runnable 仓库，再要求超过 hidden reference，可以测「创新」。**
  - **证据强度**：中到弱。它比逐步复现开放，但任务、指标和 solution family 仍由原论文定义，更像 bounded rediscovery/optimization，不是开放问题选择。

## 核心方法

InnovatorBench 从 14 篇有开源代码的论文构造 20 个任务，覆盖 Data Construction、Data Filtering、Data Augmentation、Loss Design、Reward Design、脚手架 Construction。13 名标注者各花 3 天至 2 周复现原论文、构建 workspace/评估器；任务要求可在两天内显著改善，并使用 Llama 3.1、Qwen 2.5 等常见模型（§3，附录 A–B）。

每个 workspace 含最小可运行 conda 环境、train/dev/test 数据与模型 checkpoint，以及删去原论文核心实现和 git history 的仓库。智能体获得 motivation、目标、数据、约束、指标、脚本和环境说明，但不获逐步解法。hidden test 在 workspace 外评分，避免直接修改评估器；允许最多多次提交并返回即时分数（§3，图 2–3）。

分数用基线约锚定 0、参考解约锚定 80 的函数校准。可选 hint 描述原论文 ground-truth 想法；主实验关闭 hint，消融实验则立即提供并付分数 penalty。这个设计使主实验偏向 bounded innovation，hint 实验偏向复现，直接检验想法与实现的分工（§3，附录 B）。

ResearchGym 提供 42 个 primitive 动作，分为 Command、File、Parse、Web 搜索、Web Browse。多台机器通过 HTTP 接收命令；异步 session 让训练继续时智能体可规划或轮询，sleep 动作避免无意义操作。快照保存任务、智能体 context、workspace 和剩余预算，并支持从同一点分支（§4，附录 F）。

基线是带 context summarization 的轻量 ReAct 智能体，分别搭配 Claude Sonnet 4、GPT-5、GLM-4.5、Kimi-K2。主机为 Ubuntu 22.04、800 GB 记忆；任务可调度到每台 8×80GB GPU、1600 GB 记忆的 server。只有 Data Construction/Augmentation 开网络，其余任务禁用 web 搜索/browse（§5.1）。

## 设计取舍

- **真实长训练 vs 基准成本**：2–36 小时任务和 8×80GB GPU 更接近 [[LLM|LLM]] 研发，但复现门槛、环境维护和排行榜吞吐显著变高。
- **即时 test 反馈 vs test-set 过拟合ting**：Kaggle-style 多次提交帮助智能体迭代，也使三次评测反馈成为可优化信号；它测的是带 oracle 反馈的研究闭环，不是 blind 泛化。
- **hidden 评估器 vs 可审计性**：外部评分降低奖励投机，但第三方难检查 reference、分数 calibration 和指标是否偏向原论文方法。
- **删新颖性的仓库 vs 真正开放创新**：固定数据、仓库、指标和两天预算让评测可重复，却把问题发现、目标选择和跨范式验证排除在外。
- **丰富动作空间 vs 脚手架 confounder**：42 个动作允许真实操作，也使模型成绩强依赖工具 schema、ReAct 提示词和 summarization 策略。

## 实验与结果

- Claude Sonnet 4 在六类任务加权 final/best 分数为 24.01/24.54，GPT-5 为 12.04/12.52，GLM-4.5 为 11.85/13.35，Kimi-K2 为 5.35/5.45；参考解设计目标约为 80（§5.2，表 2，附录 B）。
- Claude Sonnet 4 在 Data Filtering best 31.47、Data Construction 26.88、Data Augmentation 22.73，但 Loss Design/Reward Design 仅 12.98/11.56；这支持数据稳健性与 algorithm brittleness 的观察（§5.2，表 2）。
- GPT-5 的脚手架 Construction 得 60.07，远高于其余类别并将加权 final 拉至 12.04；轨迹显示其显式重述选项、最多重试 3 次、严格约束输出格式（§5.2，表 2）。
- Claude Sonnet 4 加 hint 后加权 best 从 24.54 降至 16.67；Loss Design 从 12.98 升至 25.32、Reward Design 从 11.56 升至 15.06，但 Data Augmentation 从 22.73 降至 1.00、脚手架 Construction 从 37.74 降至 27.71（§5.3，表 3）。
- 智能体在 InnovatorBench 超过 11 小时才达到峰值，[[PaperBench-ICML25|PaperBench]] 约 1.75 小时；论文据此报告约 6.5× 更长的 saturation time（§5.5，图 5）。
- 失败轨迹包括：10 小时后提前杀掉仍有 21 小时预算的训练、遗忘 55 步前的 GPU job 导致资源争用、用 Transformers 代替更适合吞吐的 [[vLLM]]，以及在 [[Chain-of-Thought|CoT]] 数据增强中生成语义空洞模板（§5.4，图 4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| InnovatorBench 比复现型基准需要更长的有效交互 | §5.5，图 5 | 同类智能体曲线；峰值超过 11 小时，PaperBench 为 1.75 小时；任务与硬件不完全相同 | 中 |
| 当前前沿模型在边界明确的 LLM 研究任务上仍整体低分 | §5.1–5.2，表 2 | 20 个任务、单一 ReAct 脚手架、4 个模型；最佳加权最高分 24.54，参考实现约 80 | 强 |
| 长程决策和资源管理是可观察的失败源 | §5.4，图 4 | 代表性轨迹案例；未报告各类失败的总体发生率 | 中 |
| 创意和实现缺一不可，正确提示不保证高分 | §5.3，表 3 | Claude Sonnet 4 单模型消融实验；部分数据任务加入提示后反而大幅下降 | 中 |
| ResearchGym 比单容器同步环境支持更真实的研究操作 | §4，图 3，附录 F | 42 个动作、多机 HTTP、异步会话和快照；论文未评测各机制的边际收益 | 强 |

## 批判性分析

### 论证链条

论文从现有基准的短时、复现导向和受限动作空间出发，构造长训练任务与异步多机环境，动机到设计的对应关系清楚。日志案例也说明等待、资源占用和工具选择确实是长程智能体的一等问题，而非普通代码生成细节。

「创新基准」的命名需要收窄：20 个任务均从已知论文和仓库派生，参考解、指标、数据和改动区域预先确定。智能体可以发明不同实现并超过 reference，但不需要发现值得研究的问题，也不需要说服评审器为什么指标有科学意义。它比 reproduction 难，却仍属于 constrained 研究 optimization。

### 假设压力测试

分数将基线锚定约 0、reference 锚定约 80，假设不同任务的线性区间具有相同含义。若一个任务的原始指标有饱和、阈值或高方差，统一分数会扭曲难度；论文没有报告 calibration sensitivity 或人类 researcher 分布。

ResearchGym 将调度细节暴露给 LLM，观察到 GPU 冲突后将其解释为智能体缺陷。但生产环境研究 OS 通常会提供 scheduler、resource lock 和 job registry。若加几十行确定性 guard 即可消除失败，基准测到的可能是脚手架 completeness，而不是模型的科学推理。

### 实验可信度

四个强模型在相同 ReAct 脚手架和大致相同资源下比较，主表有 final 与 best，避免只报峰值。可是论文正文一度称「compare three 智能体」却实际列四个模型，且没有 seed/置信区间；训练随机性、服务端模型更新和任务数量不均可能显著影响加权均值。

只有一个智能体脚手架，无法区分 base 模型与 编排。任务由 13 名标注者从原论文构造，后因先进模型无法正确保存 SFT 数据而降低 Data Augmentation 难度（附录 B），说明基准难度受 pilot 模型能力反馈塑造，存在基准-to-模型 co-adaptation。

### 系统性缺陷

多机 HTTP 控制、完整文件写权限和开放网络带来 credential、恶意下载、提示词注入和资源滥用风险，论文未讨论认证、网络隔离、配额 enforcement 或跨 tenant 隔离。快照保存智能体 context 和 workspace，但未描述后台进程、GPU state、外部下载和分布式训练状态是否能一致恢复。

即时 test 分数反馈虽在外部评估器中避免直接改评分代码，仍可能被三次提交用于 test-set selection。系统也未报告 job 失败 recovery、尾部 completion time、环境设置失败或快照 restore 正确性；这些恰恰是长程平台的关键 SLO。

## 局限与后续工作

- **局限 1**：仅 20 个 LLM 研究任务、来自 14 篇论文，不覆盖其他科学领域、问题选择或论文论证。
- **局限 2**：只有 ReAct + context summarization，一个模型排名不能外推到其他脚手架；无重复运行和误差条。
- **局限 3**：分数 calibration 以作者 reference 约 80 为锚，缺少人类 researcher 在同预算下的分布与跨任务可比性验证。
- **局限 4**：代表性失败案例没有 prevalence；无法判断 impatience、资源冲突或模板化推理分别贡献多少失分。
- **后续工作 1**：加入人类专家 8h/24h 基线，并按相同 GPU、submission 和网络预算比较 best 分数与成功率。
- **后续工作 2**：对 deterministic resource manager、persistent job ledger、不同 context summarizer 做消融实验，分离科研推理与基础设施失误。
- **后续工作 3**：为每个任务至少运行 3 个 seed，报告 final/best 分数、wall time、GPU 小时和 dollar 成本的置信区间。
- **后续工作 4**：增加从零定义指标/实验计划的 hidden 任务，并让独立专家评分新颖性、正确性与产物可复现性，测试更开放的研究能力。
- **后续工作 5**：验证快照对多机后台训练的一致恢复，并加入 crash、网络分区和评估器超时 fault injection。

## 相关

- **相关概念**：[[Auto-Research]]、长程智能体、resource management、智能体评测、测试时规模扩展
- **相关环境/系统**：ResearchGym、[[OpenHands-ICLR25]]、[[AutoScientists-arXiv26]]、[[vLLM]]
- **同类基准**：[[AstaBench-ICLR26]]、[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[PaperBench-ICML25|PaperBench]]
- **同会议**：ICLR 2026
