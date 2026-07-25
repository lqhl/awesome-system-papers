---
type: paper
name: HeurekaBench
full_title: "HeurekaBench: A Benchmarking Framework for AI Co-scientist"
authors: [Siba Smarak Panigrahi, Jovana Videnović, Maria Brbić]
venue: ICLR
year: 2026
tags: [auto-research, ai-co-scientist, benchmark, scientific-agent, single-cell-biology]
source_pdf: "[[iclr26-panigrahi-heurekabench.pdf]]"
source_md: "[[iclr26-panigrahi-heurekabench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-23
---

# HeurekaBench: A Benchmarking Framework for AI Co-scientist (ICLR 2026)

> **一句话总结**：HeurekaBench 把「AI co-scientist 是否真的从实验数据得到发现」转成由论文、代码和数据共同支撑的开放问题：sc-HeurekaBench 从 22 篇 single-cell 论文中人工执行验证出 13 篇的 41 条 insight、生成 50 个 OEQ 与 50 个 MCQ；其关键结果不是 agent 已接近科学家，而是同一 Claude-4-Sonnet 下最佳 agent 的 OEQ correctness 仍只有 2.34/5，且 End-critic 对 GPT-OSS-120B 可把单次均分从 2.04 提到 2.49（约 22%），显示 benchmark 测到的主要仍是 workflow execution 与 scaffold 质量（§3.4，Table 1、3）。

## 问题与动机

现有科学 agent benchmark 往往给出明确的计算指令，测试 factual recall、tool use 或单步统计；这与真实探索不同：研究者通常拿到实验数据与一个宽问题，自行选择分析、解释输出并形成结论。作者认为，若 benchmark 把中间步骤直接写进题目，测到的是 instruction following，而不是 agent 作为 co-scientist 的 workflow-level reasoning。

HeurekaBench 因而把任务写成三元组 \((D,Q,A)\)：真实实验数据 \(D\)、不规定分析方法的开放问题 \(Q\)、由已发表研究结果得到的答案 \(A\)。与仅由 LLM 从论文生成选择题的 BaisBench 相比，它要求问题对应的 insight 能通过论文代码与数据被人工复现，再将其转为 OEQ/MCQ，以降低不可回答问题与纯记忆命中的比例（§3.1–3.3）。

论文在 single-cell biology 上实例化该框架，并用它比较 Biomni、CellVoyager、BixBench-Agent 以及 planner、critic、retriever 设计。这里的 claim 边界很重要：它评估的是**重发现已发表、可复现的 dataset-level finding**，不是评估 agent 能否提出并验证此前未知的生物学发现。

## 关键观察 / 隐含假设

- **观察 1：科学问题只有同时绑定 paper、code、data，才有机会区分 dataset-driven analysis 与语言模型记忆。** 22 篇候选论文最终只有 13 篇的 41 条 insight 通过执行验证；未通过者常因数据版本不符、缺少 sub-cluster metadata、依赖领域工具或 insight 过于泛化（§3.4、§C.4）。
  - **依赖假设**：复现出与论文 grounding text 一致的图或统计量，足以证明 workflow 与 insight 的对应关系。
  - **可能失效场景**：原论文代码本身有错误、存在多条等价分析路径，或人工 reviewer 的三类“minor edit”实质改变 workflow 时，validation 可能验证的是 reviewer 修复后的流程。

- **观察 2：当前 agent 的瓶颈不只在 base model，也在 scaffold 的 flexibility 与 tool selection。** 同用 Claude-4-Sonnet 时，BixBench-Agent/ Biomni 的 OEQ correctness 为 2.34/2.31，CellVoyager 为 2.03；关闭 retriever 后 GPT-OSS-120B 从 2.15 降至 1.56（Table 1、4）。
  - **依赖假设**：三种 agent 的 compute、输入和终止条件足够可比；Lite subset 能代表完整 benchmark。
  - **可能失效场景**：CellVoyager 被移除 hypothesis proposal step、步数从默认 6 改为 8；BixBench-Agent 又会在大数据上崩溃，因此比较同时混入了适配质量与系统可靠性。

- **观察 3：critic 的位置比“是否有 critic”更重要。** 对 GPT-OSS-120B，End-critic 的单次 correctness 从 2.04 提至 2.49，而 Plan-critic 降至 1.91；对 Qwen3-235B-Thinking，End-critic 反而使三次平均从 1.85 降至 1.73（§4.3.2，Table 3）。
  - **依赖假设**：用 Claude-4-Sonnet 作为 critic 的反馈不会把其能力直接注入 open model agent，且三次运行足以吸收 agent 随机性。
  - **可能失效场景**：更强 planner 已形成较好 trajectory 时，额外 critique 会扰动正确分析；弱 critic 或不匹配领域的 critic 也可能放大错误。

- **假设 1：published finding 可作为 open-ended discovery 的 ground truth。**
  - **证据强度**：**中**。它提供可审计答案，但天然奖励“重发现作者报告过的事实”，无法奖励 ground truth 之外的新发现，也可能惩罚同样合理的替代解释。

- **假设 2：GPT-4o 基于 atomic facts 的 1–5 分可以稳定代替领域专家。**
  - **证据强度**：**中**。25 个回答上，[[LLM|LLM]] 分数与 11 位专家 median 的差不超过 1 分者为 24/25，Spearman 相关为 0.90、κ 为 0.85；但样本小、来自单一 Biomni/GPT-OSS-120B 配置，且 judge 只对 ground truth coverage 评分（§4.3.1）。

## 核心方法

HeurekaBench 的 insight generation pipeline 有四个 LLM 模块（Fig. 1、§3.2）：InsightExtractor 从论文抽取候选发现及 grounding text；CodeDescriber 总结 repository scripts；CodeMatcher 将 insight 匹配到相关文件；CodeGenerator 基于这些文件合成多步分析 workflow。随后由人类执行代码，允许加载数据、映射 Ensembl gene ID、对齐变量与 metadata 名等修改，只有输出能复现论文结果的 insight 才保留。

对每条 validated insight，问题生成器产生两个 OEQ 与两个 MCQ。自动过滤阶段让 GPT-4o 与 Claude-4-Sonnet 在**不给数据**时答题：两者都答对的 MCQ、两者 G-Eval 都高于 3.0 的 OEQ 被删除；人工阶段再去除 hallucination、duplicate 与基于未验证 insight 部分的问题（§A.2、§A.4）。这一步直接回应“预训练记忆冒充分析”的观察，但只能降低、不能证明消除 contamination。

OEQ 用改造后的 G-Eval（LLM-as-a-Judge）：先把 ground truth 和 agent response 拆成 atomic facts，再标记 PRESENT/PARTIAL/MISSING/INCORRECT。只有带 dataset identifier 或量化/统计证据的对应事实才算 PRESENT；额外且不矛盾的发现不扣分（§3.3、Appendix B）。MCQ 报 accuracy、precision、recall，以容纳 LLM 生成 distractor 仍可能科学上成立的情形。

single-cell 实例 sc-HeurekaBench 包含 50 OEQ、50 MCQ；另保留 12 个依赖 SCENIC、CellPhoneDB、CellChat 等领域工具、但 CodeGenerator 未能验证的 OEQ，形成 ToolUsage 子集（§3.4.1）。这实际上把 benchmark 分成“已复现 insight”与“专门测试 tool selection 的未复现 workflow”两种证据等级。

## 设计取舍

- **强 grounding vs 人工成本**：论文、代码、数据与人工执行显著提升问题可信度，但 22 篇只能保留 13 篇，且迁移到新领域必须重新投入 domain expert。
- **开放答案 vs judge 依赖**：OEQ 更接近研究解释，却把评分可信度交给 closed-source LLM；atomic fact rubric 约束了 recall，但不验证中间代码是否科学正确。
- **近期论文 vs contamination**：只选 2024–2025 年 Nature/Cell 论文降低训练语料记忆风险，但未来模型仍可能见过全部结果，benchmark 需要持续换新。
- **统一模型 vs 公平比较**：三种 agent 都用 Claude-4-Sonnet 有利于隔离 scaffold 差异，但每个系统被不同程度修改，且只能在小于 750 MB 的 Lite subset 上共同运行。
- **边界条件**：适合有公开数据、公开代码、可由专家重放分析的 computational science；对 wet-lab、代码缺失、负结果或尚无 accepted answer 的探索不适用。

## 实验与结果

- InsightExtractor 在 FlyBase 的 50 个 publication–expert finding pair 上得到 44 strong、2 weak、4 unrelated；在 BixBench 的 21 对上为 14/4/3。CodeMatcher 在 50 个 insight、215 个脚本上正确匹配 158 个脚本，平均召回 74.6%（§4.1，Fig. 2）。
- 完整 sc-HeurekaBench 为 50 OEQ + 50 MCQ，但三 agent 公平比较只使用小于 750 MB 数据的 Lite subset：22 OEQ + 18 MCQ。BixBench-Agent、CellVoyager、Biomni 的 OEQ correctness 分别为 2.34、2.03、2.31；MCQ accuracy 分别为 44.44%、27.78%、50.00%（§4.2，Table 1）。
- Biomni planner ablation 中 Claude-4-Sonnet 的 OEQ correctness 为 2.58±0.05，第二名 GPT-OSS-120B 为 2.08±0.05；但 MCQ accuracy 最好的是 Qwen3-235B-Thinking 的 46%，Claude 为 44%，模型排序依赖题型（§4.3.1，Table 2）。
- GPT-4o judge 与 Claude-4.5-Sonnet/Gemini-2.5-Pro judge 的平均 Spearman 分别为 0.84±0.03/0.79±0.01，κ 为 0.81±0.03/0.71±0.04；对 25 个回答的人类对齐中，GPT-4o 与 expert median 的 Spearman 为 0.90、κ 为 0.85（§4.3.1，Fig. 3、Table 6）。
- GPT-OSS-120B 加 End-critic 后，三次平均 correctness 从 2.08±0.05 提至 2.40±0.08；单次分类分析为 2.04→2.49，改善 16 个、恶化 9 个问题。Qwen3-235B-Thinking 则从 1.85±0.03 降至 1.73±0.09（§4.3.2，Table 3）。
- 关闭 retriever 后，GPT-OSS-120B 在 12 个 ToolUsage OEQ 上从 2.15±0.09 降至 1.56±0.22；Qwen3-235B-Thinking 从 1.92±0.13 降至 1.80±0.07（§4.3.3，Table 4）。
- 相同 Claude-4-Sonnet 从裸 LLM 变为 Biomni agent 后，OEQ correctness 由 1.90 升至 2.56，MCQ accuracy 由 22% 升至 44%，证明 environment/tool loop 有增益，但仍远未接近满分（Appendix H，Table 7）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| paper+code+data 的半自动流程能构建可执行验证的开放科学问题 | §3.4、§C.4：22 篇候选中 13 篇、41 条 insight 通过人工执行验证，生成 50 OEQ/50 MCQ | 2024–2025 single-cell 论文；需公开 code/data 与人工修复 | medium |
| 当前 single-cell agent 在开放问题上仍明显不足 | §4.2，Table 1：Lite subset 上最佳 OEQ 2.34/5，最佳 MCQ accuracy 50% | 22 OEQ、18 MCQ；三 agent；Claude-4-Sonnet | strong |
| End-critic 可缩小 open/closed planner 差距，但增益依赖 planner | §4.3.2，Table 3：GPT-OSS 三次均值 2.08→2.40，Qwen 1.85→1.73 | Biomni、50 OEQ、Claude critic、各三次运行 | strong |
| GPT-4o judge 与专家评分基本对齐 | §4.3.1：25 回答中与 expert median 差不超过 1 分为 24/25，Spearman 0.90、κ 0.85 | 单一 agent/model 输出；11 位 single-cell 专家 | medium |
| 问题比 BaisBench 更难靠无数据记忆答出 | §C.5：GPT-5 无数据 MCQ accuracy 为 34.69%，BaisBench 为 53.37% | 单一模型；不同 benchmark 的题目构造与领域分布 | medium |

## Critical Analysis

### 论证链条

论文的主链条基本闭合：静态题目不代表 co-scientist → 从真实 paper/code/data 生成并执行验证 insight → 转为开放问题 → 用 benchmark 暴露 planner、critic、retriever 差异。最强贡献是把“问题本身是否可回答”纳入构建流程，而不是又做一个只靠 LLM 生成的题库。

主要跳步是把**已发表 finding 的重发现**称为 open-ended scientific discovery。问题不指定方法确实开放，但答案空间仍由论文 ground truth 封闭；judge 又只按 GT atomic facts 给分。系统可能找到新的、正确但未被论文报告的 pattern，却不会因此得到额外信用。因此 HeurekaBench 更准确地测量“grounded exploratory analysis”，而非 frontier discovery。

### 假设压力测试

如果论文代码不完整、数据版本变化或关键步骤依赖人工 tacit knowledge，构建 pipeline 的保留率会进一步下降；在物理实验、化学合成或临床研究中，code execution 也无法替代真实实验。Appendix C.4 已显示即使 single-cell 这一高度计算化领域，CodeGenerator 仍会因缺数据、缺 metadata、工具 hallucination 失败。

自动过滤用 GPT-4o/Claude 判断题目能否靠记忆回答，但未来模型或检索 agent 可能直接找到原论文；近期性只延迟 contamination。更强的版本应在 agent 环境中隔离网络、使用未公开 holdout study，或构造与原文不同但可验证的 counterfactual dataset。

### 实验可信度

数字充分展示了 agent 仍弱，也有 planner/critic/retriever 消融和人类 judge 对齐；但三 agent 主比较被迫缩到 22/50 OEQ、18/50 MCQ，且 CellVoyager 被改流程、BixBench-Agent 对大数据 crash。Table 1 因而更像系统兼容性测试，不能干净地给 agent 架构排名。

InsightExtractor 的 expert-finding matching 由 GPT-4o judge，而 InsightExtractor 本身也用 GPT-4o，存在 model self-preference；CodeMatcher 的 74.6% 是 proxy repository 上的 file retrieval，不等于端到端 workflow 可运行。最重要的最终指标仍由 LLM judge 决定，人类对齐只有 25 个答案，尚不足以覆盖 novel extra finding、adversarial answer 与不同领域。

### 系统性缺陷

- **可靠性**：BixBench-Agent 在大数据 crash、CellVoyager 单题可耗时一小时，说明 benchmark 运行受到 memory、timeout 和 API cost 主导；论文未报告完整 failure/retry rate。
- **安全性**：agent 会执行 LLM 生成代码，论文只建议 sandbox，没有评估数据泄漏、恶意 package 或权限隔离。
- **可观测性**：最终分只看 answer，不验证 intermediate workflow；作者也将 step-level partial credit 列为 future work。
- **可维护性**：题库要保持低 contamination 就需不断引入新论文，但每个 insight 都依赖 domain expert 执行验证，更新成本可能限制规模。

## 局限与 Future Work

- **局限 1**：benchmark 只覆盖 single-cell computational analysis，且主 agent 比较是 22/50 OEQ 的 Lite subset；不能外推到其他科学域或大数据 workload。
- **局限 2**：ground truth 来自已发表结果，测量的是重发现而非真正未知发现；额外正确 finding 不扣分，也不加分。
- **局限 3**：GPT-4o judge 的人类对齐仅验证 25 个回答，未覆盖 adversarial response、judge contamination 与跨领域迁移。
- **局限 4**：人工允许对 workflow 做三类修改，论文未量化每条 insight 的修复量，自动化程度难以复核。
- **Future work 1**：为每个 OEQ 发布 executable step graph 与中间 artifact checksum，比较 final-answer-only、stepwise partial credit、真实重执行三种评分对 agent 排名的影响。
- **Future work 2**：在至少三个新科学域各抽样 20 篇 paper，报告 insight validation yield、人工分钟数、修复类型与 inter-reviewer agreement，客观测量框架迁移成本。
- **Future work 3**：加入隐藏的 counterfactual dataset 或未公开 holdout study，测量 agent 在无法检索原答案时的 correctness，并量化 contamination 导致的分数差。
- **Future work 4**：固定 planner 后系统扫描 critic model、插入位置与触发策略，报告每个问题的 paired delta，验证 End-critic 的 22% 增益是否跨模型稳定。

## 相关

- **相关概念**：LLM-as-a-Judge、LLM Agent、Agent Scaffold、scientific benchmark、data-driven discovery
- **同类系统**：[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[MLAgentBench-ICML24]]、BixBench、DiscoveryBench
- **相关科研 agent**：Biomni、CellVoyager、BixBench-Agent、[[Kosmos-AI-Scientist-arXiv25]]
- **同主题**：[[Auto-Research]]
- **同会议**：ICLR 2026
