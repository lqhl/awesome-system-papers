---
type: paper
name: CausalEvolve
full_title: "CausalEvolve: Towards Open-Ended Discovery with Causal Scratchpad"
authors: [Yongqiang Chen, Chenxi Liu, Zhenhao Chen, Tongliang Liu, Bo Han, Kun Zhang]
venue: ICLR
year: 2026
tags: [auto-research, evolutionary-coding, causal-guidance, llm-agent, program-search]
source_pdf: "[[iclr26-chen-causalevolve.pdf]]"
source_md: "[[iclr26-chen-causalevolve]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# CausalEvolve：用因果草稿本引导开放式发现（ICLR 2026）

> **原题**：CausalEvolve: Towards Open-Ended Discovery with Causal Scratchpad

> **一句话总结**：CausalEvolve 用 LLM 生成的结果描述符、程序过程标签和 bandit 选择来引导 ShinkaEvolve 式程序进化；在 Grok-4.1-FR、3 seeds 下，最终平均分相对 ShinkaEvolve 在 Hadamard、Second Autocorrelation、AIME 三项更高，但 Circle Packing 为 2.476 vs 2.479，因此证据支持的是「因子引导可改善部分搜索」，尚未证明系统识别了任务的因果机制（§3–5，表 1）。

## 问题与动机

[[AlphaEvolve-arXiv25]] 一类进化式编程智能体依靠「LLM 变异候选程序—自动评估—保留优解」循环搜索。作者观察到，纯粹依赖进化算子或历史最优程序时，搜索接近已知边界后容易在局部区域振荡；已有 memory 虽能总结历史，却没有显式表示哪些设计因素可能造成性能变化，也缺乏按这些因素选择下一次尝试的机制。

论文把程序搜索形式化为带静态隐变量的 POMDP：未知的“科学知识”记为结构因果模型（SCM），程序评估被写成对程序设计变量的 `do(X=x_p)`。基于这一叙事，CausalEvolve 引入“因果草稿本”，在进化前构造结果层因素，在进化中从程序及历史分数提取过程层因素，并用所谓干预方向与“惊讶模式”指导后续候选生成。

需要区分作者的两层论断。理论层讨论的是：若候选共享已知低维结构，则结构化搜索比把每个候选当独立 arm 更省样本；系统层实际实现的是：用 LLM 提议描述符和文本标签，再从观测到的程序—分数历史估计相对有用性。论文没有学习 SCM 的图、结构方程或可识别的因果效应，也没有在真实分布转移下检验因果泛化。

## 关键观察 / 隐含假设

- **观察 1：主目标之外的可执行结果描述符能提供多样化搜索方向。** 表 3 的因素包括 Hadamard 矩阵的行正交偏差和元素平衡、函数的平滑度和稀疏度、圆布局的中心分散度和半径方差，以及 AIME agent 的格式率、成本效率和连续错误数。
  - **依赖假设**：LLM 能从任务描述中提出与优解结构有关、计算正确且不重复的描述符；沿某个描述符高/低值选 inspiration program，能产生可利用的变异方向。
  - **可能失效场景**：描述符只是目标函数的重编码、与真正有效的程序机制无关，或在搜索后期与主目标冲突时，bandit 会把预算集中到错误代理上。

- **观察 2：程序历史中的过程标签可以帮助解释性能差异。** 系统让 LLM 从程序中识别优化技术等过程因素，估计其对目标分数的近似平均处理效应，并针对符号反转或幅度突变生成新的解释性因素（§4.2）。
  - **依赖假设**：从选择性产生的进化轨迹中，因素出现与分数变化之间的排序足以近似干预收益。
  - **可能失效场景**：程序组件共同变化、优胜者选择和隐藏混杂会让相关性倒置。作者明确承认样本少且存在隐藏混杂，估计可能有偏，只要求数值大致保序；这不足以建立标准因果识别。

- **观察 3：共享低维结构可降低 best-arm identification 的样本复杂度。** 定理 3.2/B.1 比较已知 `d` 维线性特征且存在 basis programs 的结构化类别，与 `K` 个均值彼此独立的 black-box 类别，前者随 `d log K`、后者随 `K` 扩展。
  - **依赖假设**：实际程序空间具有已知、正确、低维且可干预的特征表示。
  - **可能失效场景**：CausalEvolve 的 LLM 因素不满足线性模型、basis 或无偏估计条件。该定理证明的是共享结构的价值，不是任意 SCM 或当前实现的因果正确性。

- **假设 1：自动评估分数足以代表“开放式科学发现”。**
  - **证据强度**：弱到中。四项任务均有数值 evaluator，但没有专家新颖性审查、独立重执行或科学机制验证；其中 AIME 测的是 agent 准确率，另外三项是构造/数值优化。

## 核心方法

**结果层因素（outcome-level factors）** 在搜索开始前生成。LLM 读取任务提示和程序输出格式，为每个因素给出名称及从输出到标量的可执行函数。CausalPlanner 的动作是 `(m,+1)` 或 `(m,-1)`：按因素 `m` 的高值或低值排序已有程序，从极端样本中选择 inspiration program。它并未直接设置候选程序的因素值，而是干预父代/灵感样本的选择分布。

每个动作的 reward 为 `(y_c - τv_t)_+`，其中 `y_c` 是子程序主目标、`v_t` 是当前最佳值。为缓解真正刷新 best-so-far 过于稀疏的问题，`τ` 允许接近最优的候选产生正反馈。控制器先对各动作探索 `K` 次，再连续利用当前最佳动作 `K` 次；它更接近基于描述符的多臂 bandit 搜索策略，而不是对 SCM 的显式实验设计（§4.1）。

**过程层因素（procedure-level factors）** 来自 COAT：LLM 比较程序实现，提取可能解释分数差异的技术标签；系统依据进化记录估计各标签的近似处理效应。若因素的相关方向与局部效果相反，或弱相关因素出现大幅负效应，系统把它标为“惊讶模式”，再让 LLM 进行溯因推理，提出新的因素或假说，加入之后的搜索上下文（§4.2）。

完整 CausalEvolve 将上述两个模块接到 ShinkaEvolve 式进化循环。对照包括原始 ShinkaEvolve、结果因素 + Shinka meta-summary 的 `CausalPlanner (Meta)`、仅过程因素的 COAT，以及二者结合的 CausalEvolve。所有方法固定 Grok-4.1-fast-reasoning，以减少 backbone 差异。

理论部分另给出两个边界：定理 3.2 说明正确共享结构可提高样本效率；定理 3.3 说明若源环境无法区分两个在目标环境中最优决策相反的世界，则任何仅访问源环境的策略都有不可消除的目标 regret。后者是一般不可识别性结论，但实验没有设置 `e_src → e_tgt` 转移来测试 CausalEvolve 是否比基线更能跨环境泛化。

## 设计取舍

- **因果模型 vs 因素启发式**：不用显式学习 SCM，能把任意程序输出快速转成搜索特征；代价是“causal”退化为 LLM 提议因素、观测相关和 bandit 选样，缺少识别保证。
- **多维描述符 vs 单一目标**：描述符能维持搜索多样性，也可能制造与主目标无关的极端方向；论文没有与随机描述符、专家描述符或等维非因果特征做预算匹配对照。
- **溯因解释 vs 可检验机制**：新因素可为下一轮提供灵感，但论文不评估因素精度、稳定性、跨 seed 一致性或是否对应真实机制。
- **共享 evaluator vs 科学外部有效性**：确定性/数值评估让候选可快速筛选，却不验证新颖性、实际部署泛化或开放问题的数学最优性。

## 实验与结果

- 四项任务分别在不同 step 预算下评测：Hadamard Matrix `n=29` 为 20/40/80/100；Second Autocorrelation 和 Circle Packing `N=26` 为 50/100/150/200；AIME 2024 agent 为 20/40/60/80。每种方法运行 3 seeds，表 1 同时报均值和三次运行中的 best-so-far。
- Hadamard 最终平均/最佳分：CausalEvolve 0.568/0.576，ShinkaEvolve 0.521/0.540；`CausalPlanner (Meta)` 为 0.567/0.573（表 1）。完整系统相对结果层-only 变体增益很小。
- Second Autocorrelation 最终为 0.793/0.809，ShinkaEvolve 为 0.737/0.751，COAT 为 0.783/0.786；这是完整系统最清楚的优势（表 1）。
- Circle Packing 最终平均分 CausalEvolve 2.476，略低于 ShinkaEvolve 2.479；最佳分 2.564 高于 ShinkaEvolve 2.500，但仍低于 COAT 的 2.568。因而“所有任务平均分均显著更好”和“每个模块都必要”都不由表 1 直接支持。
- AIME 最终平均/最佳准确率为 38.89%/40.00%，相同实验中的 ShinkaEvolve 为 34.44%/36.67%；COAT 平均同为 38.89%，最佳为 43.33%。正文另与 ShinkaEvolve 原论文的 34.4% ensemble 结果比较，但那不是同表同配置基线。
- 论文没有报告方差、置信区间或显著性检验，也未披露候选总数、token、模型调用、硬件、wall-clock 或成本；“significantly”在这里应理解为作者的定性措辞，而非统计结论。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CausalEvolve 在四项任务中的三项提高最终平均分 | §5.1–5.2，表 1 | Grok-4.1-FR；3 seeds；100/200/200/80 steps；仅对比 ShinkaEvolve 与内部变体 | 强 |
| 完整方法在 Circle Packing 的平均分不优于 ShinkaEvolve，最佳分也不优于 COAT | 表 1 | 最终 step；2.476 vs 2.479，best 2.564 vs 2.568 | 强 |
| 结果层因素有早期搜索收益 | 表 1 Step 1 | `CausalPlanner (Meta)` 在四题 Step 1 均略高于 ShinkaEvolve；不是完整 CausalEvolve 的统一收益 | 中 |
| “因果知识”带来样本复杂度优势 | 定理 3.2/B.1 | 已知线性特征、basis programs、Gaussian noise；未证明实验因素满足这些条件 | 弱 |
| 系统发现了可泛化因果机制 | §3.2、§4.1–4.2 | 无 SCM 恢复、因果 ground truth、干预效应校准或目标环境实验 | 弱 |

## 批判性分析

### 论证链条

从“盲目进化会振荡”到“用辅助因素分层选择候选”这条工程链条合理，表 1 也显示因子指导在若干任务和预算上有收益。真正的逻辑跳步发生在从 **结构化特征搜索** 到 **因果科学发现**：把一次程序评估记作 `do(X=x_p)` 并不会自动让从这些评估中提取的描述符成为因果变量；从选择偏置的历史轨迹估计因素效应，也不会自动消除混杂。

定理 3.2 的增益来自已知低维线性共享结构和可观测 basis，而实际系统的因素由 LLM 提议、数量和质量未知。定理 3.3 则说明源环境信息不足时无法保证目标环境最优，反而强调了当前实验的缺口：四项实验只在同一 evaluator 上搜索和报告，没有证明草稿本改善 OOD 或 exact-verifier 转移。

### 假设压力测试

若把 outcome factors 替换为随机但同维的可执行描述符，或由专家手写同数量特征，CausalPlanner 是否仍有优势，论文未测。这个对照能区分收益究竟来自“任何多样性坐标”、LLM 的领域先验，还是可识别的因果结构。

过程因素更脆弱：进化算法只保留有竞争力候选，因素出现概率受父代选择、LLM 生成偏好和其他共同修改影响。即使估计只需保序，隐藏混杂也可能改变排序；“惊讶模式”再由同类 LLM 解释，容易把统计噪声包装成机制故事。

### 实验可信度

优点是四项任务异质、固定同一 backbone、报告 3 seeds，并同时给均值和最好值。缺点是没有误差条和统计检验，best-of-3 会放大选择收益；仅一个外部进化基线，且缺少等预算 random search、descriptor diversity、纯 bandit、专家因素和无溯因版本。表 1 实际上已经出现多个内部简化变体胜过完整方法的格子，因此不能据此宣称所有模块必不可少。

更重要的是，实验只测目标分数，不测因素是否正确、处理效应是否校准、假说是否可复用、或结果是否跨 evaluator 泛化。它证明的是 evaluator-guided 程序搜索效率，而不是新的科学因果机制。

### 系统性缺陷

论文未披露并发模型、失败重试、程序沙箱、evaluator 防 reward hacking、候选去重、token/GPU 成本和 wall-clock，因此无法判断额外 LLM 因素分析相对分数收益的系统开销。对 Circle Packing 的 relaxed vs exact verifier 只作为定理 3.3 的例子出现，没有报告实际 exact revalidation。过程标签和草稿本若持续累积错误，也没有版本化、冲突消解或 rollback 机制说明。

## 局限与后续工作

- **局限 1**：实现没有恢复 SCM 或满足因果效应可识别条件；“causal”主要是因素引导和因果语言包装。
- **局限 2**：没有源环境—目标环境、公开测试—私有测试或 relaxed—exact verifier 的实证转移，理论泛化动机未落地。
- **局限 3**：完整系统并非所有任务/指标最优；3 seeds 无方差和统计检验，且缺少强外部与等预算非因果控制组。
- **局限 4**：没有报告总调用、硬件、时间和成本，也没有对因素质量、稳定性与错误累积做审计。
- **后续工作 1**：在有 ground-truth SCM 与可控混杂的程序搜索环境中，比较估计因素、真实因果变量和随机描述符的干预 regret。
- **后续工作 2**：固定 evaluator calls 与 token 预算，对比 CausalEvolve、ShinkaEvolve、专家描述符、随机描述符、纯 novelty search 和多目标 MAP-Elites。
- **后续工作 3**：对公开/私有分布及 relaxed/exact verifier 分别训练和测试，报告目标环境 regret，而不只报告源 evaluator 的 best score。
- **后续工作 4**：至少运行 10 seeds，公开每步轨迹、因素集合、效应估计和调用成本，检验因素排序能否跨 seed 与模型复现。

## 相关

- **相关概念**：[[Auto-Research]]、[[LLM]]、进化搜索、因果推断、多臂老虎机、程序搜索、溯因推理
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[FunSearch-Nature24]]、[[ASI-ARCH-arXiv25]]、[[BES-arXiv26]]
- **评测边界**：[[MLE-Bench-ICLR25]]、[[InnovatorBench-ICLR26]]
- **同会议**：ICLR 2026
