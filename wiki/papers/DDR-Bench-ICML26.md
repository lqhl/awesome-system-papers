---
type: paper
name: DDR-Bench
full_title: "Hunt Instead of Wait: Evaluating Deep Data Research on Large Language Models"
authors: [Wei Liu, Peijie Yu, Michele Orini, Yali Du, Yulan He]
venue: ICML
year: 2026
tags: [auto-research, data-agent, investigatory-intelligence, benchmark, long-horizon-agent]
source_pdf: "[[icml26-liu-deep-data-research.pdf]]"
source_md: "[[icml26-liu-deep-data-research]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-23
---

# Hunt Instead of Wait: Evaluating Deep Data Research on Large Language Models (ICML 2026)

> **一句话总结**：DDR-Bench 把 data agent 从“回答已知问题”推进到“只给实体 ID 和数据库，自主决定查什么、何时停止”，并以 291 个实体、2,058 个 fact checklist 检验可验证 insight；最佳 Claude 4.5 Sonnet 的综合 accuracy 仍只有 47.73%，而把 checklist 直接变成问题后 Qwen3-Next 的平均 accuracy 从 proactive message/trajectory 的 32.59%/28.26% 升至 reactive 的 43.21%，说明当前瓶颈首先是发现目标与维持探索策略，而不只是执行 SQL/Python（§2–3，§5.2，Table 1、2、5）。

## 问题与动机

多数 data-science agent benchmark 预先给出 question、objective 或详细 workflow，测量的是 agent 执行既定目标的能力。作者将其称为 **executional intelligence**，并提出另一层能力 **investigatory intelligence**：面对原始数据，agent 是否能自行判断什么值得查、形成和验证假设、在宽度与深度间分配注意力，并自主决定何时停止。

Deep Data Research（DDR）把这一问题形式化为 query-free exploration。agent 只拿到一个任务实体与数据库 metadata，例如“分析 user 2048”，没有问题、目标或交互轮数上限；它通过 SQL/Python 持续探索，最后报告发现。DDR-Bench 则提供可规模化评分：从数据库的 unstructured/semantic counterpart 提取 fact checklist，检查 agent 从 structured data 得到的 insight 是否足以支持这些事实（§2.1–2.4）。

这一区分与 [[PaperBench-ICML25]]、[[MLE-Bench-ICLR25]] 等给定目标的 R&D/engineering benchmark 互补：DDR-Bench 不要求复现某个指定结果，而是观察 agent 是否主动找到潜在结果。但它仍不是“未知科学发现”评测，因为 checklist 来自已有文本或 survey，最终奖励的是**自主找回预先可验证的事实**。

## 关键观察 / 隐含假设

- **观察 1：query-free 目标发现比 goal-directed 执行显著更难。** Qwen3-Next-80B-A3B 在 proactive DDR 中 message-wise/trajectory-wise 平均 accuracy 为 32.59%/28.26%；把每个 checklist item 变成显式问题后，reactive accuracy 为 43.21%（§5.2，Table 5）。
  - **依赖假设**：reactive 与 proactive 两种设置的 tool budget、调用次数和评价粒度足够可比。
  - **可能失效场景**：reactive 模式逐 checklist item 发问，等于暴露目标并可能提供更多总 inference/tool budget；差值不全是“agency tax”。

- **观察 2：高分模型呈现“先广后深”的 implicit planning，但这是相关性而非因果证据。** 交互曲线常为 sigmoid；Claude、GLM、DeepSeek 较晚进入快速增益阶段，后期用少量复杂 query 获得高价值 insight；适中的 coverage 与 entropy 也对应更高 accuracy（§4.1–4.2，Fig. 1、5）。
  - **依赖假设**：field coverage 与 normalised entropy 能分别代表探索 breadth/depth，且不同 schema 的字段具有可比信息量。
  - **可能失效场景**：一个高信息字段可能胜过大量低信息字段；schema denormalisation、重复列或宽表会扭曲 coverage/entropy。跨模型的自选轨迹也不能证明“延迟行动”本身提升结果。

- **观察 3：更大模型、更长 context 或更多显式 reasoning 并不单调提升 investigatory intelligence。** Qwen2.5 参数增大约 10 倍，最终 accuracy 增益仍少于 3%；Qwen3-Next 增加 reasoning budget 后交互轮数显著减少，但 10-K message accuracy 从 45.58% 降至 36.40%，trajectory accuracy则从 31.10% 升至 37.34%（§5.1–5.2，Fig. 7、Table 3）。
  - **依赖假设**：Qwen 跨代差异可主要归因于 agentic-first training，而不是数据、架构、post-training recipe 等未控制因素。
  - **可能失效场景**：在固定训练配方或更长 task 上，scale/context 可能重新成为主导；当前结论来自 family-level observational comparison。

- **观察 4：通用 agent module 常改变行为，却不稳定提高 accuracy。** Qwen3-Next 加 memory 后，10-K trajectory/message accuracy 从 31.10/45.58 降至 25.21/37.34，MIMIC 从 20.80/16.80 降至 14.34/15.63；Appendix B 的 planning/memory/multi-agent 多数也弱于 ReAct baseline（§5.2，Table 4、Table A1）。
  - **依赖假设**：所选 CoALA、Plan-and-Execute、AutoGen 实现能代表 memory/planning/multi-agent 范式。
  - **可能失效场景**：case-specific compression、retrieval policy、角色划分或 termination control 经调优后可能反转结论；论文只能否定“通用模块即插即涨分”。

- **假设 1：从 unstructured text/survey 提取的 checklist 可作为 structured-data discovery 的 objective ground truth。**
  - **证据强度**：**中**。超过 50 位领域专家筛选、共 2,058 个 item；但 checklist 只覆盖文本已记载的事实，无法穷举正确 insight，且“surjective mapping”不保证每个事实从当前工具与预算下都容易推导。

- **假设 2：用最小 ReAct scaffold 能测到模型“intrinsic agency”。**
  - **证据强度**：**中偏弱**。统一 SQL/Python 接口减少 scaffold confound，但 system prompt 仍反复强调格式和多步探索，message-wise insight 还由额外的同模型调用生成；测到的是 model+prompt+tool protocol，而非纯模型属性。

## 核心方法

DDR 将一次轨迹写成多轮 \((r,t,o)\)：reasoning、tool invocation 与 observation。模型只获得 entity-level start prompt 与 schema metadata，通过 SQL/Python 自主查询，并自行发出 termination。输出分为两类：**message-wise insight \(I_m\)** 是每轮结束后由同一底座模型通过独立 prompt 将当前 \((r,t,o)\) 解释成 insight；**trajectory-wise insight \(I_t\)** 是 agent 终止后对完整历史生成的最终报告（§2.1，Appendix H.2）。

DDR-Bench 采用轻量 ReAct agent，不含显式 planner 或 memory，工具通过 MCP 暴露。论文刻意不限制交互轮数，以便把 termination 本身纳入能力；但实际存在模型陷入 debugging loop 的异常 run，达到 100 rounds 后被强制停止，并在部分 trajectory-length 图中忽略（§2.2，Appendix D）。

三个场景覆盖不同结构（§2.3，Table 1）：

- **MIMIC-IV**：100 位患者，29 tables、318 fields、200M+ records；结构化 EHR 对齐临床 note，774 checklist items。
- **GLOBEM**：91 位用户，6 tables、222 fields、55K+ records；用 wearable time series 推断 intervention 前后 survey 趋势，435 items。
- **10-K**：100 家公司，5 tables、5,832 fields、3M+ records；用 XBRL financial facts 对齐 filing text，849 items。

总计 291 个 entity、203M+ records、40 tables、6,372 fields 与 2,058 个 verified checklist item。GPT-5-mini 从文本/调查中抽取事实，超过 50 位 domain expert 审查其可由 structured data 推导。MIMIC/10-K 由 GPT-5-mini 判断 insight 是否为 ground-truth fact 提供 CORRECT_INFO；GLOBEM 则让 checker 基于 insight 回答三选一趋势题并 exact match（§2.4、Appendix H.4）。

为降低 checklist 漏标对强模型的惩罚，作者把未匹配任何 item 的 \(I_m\) 当作 candidate novel insight，用匿名、随机顺序的 GPT-5-mini pairwise usefulness comparison，再用 Bradley–Terry 聚合排名。novelty rank 与 checklist accuracy rank 在三场景高度接近，但论文未给具体相关系数（§3.2，Fig. 4）。

## 设计取舍

- **最大开放性 vs 预算公平**：不限制 rounds 能观察 self-termination，却允许模型用不同 token、tool time 与 API cost；更高分可能部分来自更高支出，且不终止 run 最终仍被 100-round safety cap 截断。
- **客观 checklist vs insight completeness**：per-fact checking 比 report-level subjective score可审计，但 checklist 必然漏掉新 insight；pairwise novelty 又重新引入 closed-source [[LLM|LLM]] 的主观判断。
- **最小 scaffold vs 可用系统上限**：轻量 ReAct 有助于比较 base model，却刻意排除 production data agent 常用的 memory、planner、schema retrieval 与 multi-agent；分数是“最小 scaffold 下能力”，不是最佳系统上限。
- **structured/unstructured 对齐 vs task construct validity**：MIMIC 与 10-K 的文字确实总结结构化事实；GLOBEM 则要求 wearable signal 推断 survey 改善，二者未必有稳定可识别映射，低分可能反映信号不足而非 agency 不足。
- **traceability vs 隐私/安全**：每个 insight 链回 reasoning、query 与 observation，便于审计；但医疗/行为数据仍需 credentialed access，完整 trace 也可能泄露敏感派生信息。
- **边界条件**：适合有大型 structured database、可从独立文本/调查构造事实清单的领域；不适合 ground truth 尚未知、只能靠因果实验验证或没有 semantic counterpart 的数据。

## 实验与结果

- DDR-Bench 含 291 个 task entity、2,058 checklist item 与 203M+ records；MIMIC/GLOBEM/10-K 分别为 100/91/100 entities 和 774/435/849 items（§2.3–2.4，Table 1）。
- 22 个 proprietary/open-source model 中，仅 Claude 4.5 Sonnet overall average 超过 40%，为 47.73%；第二名 open model DeepSeek-V3.2 为 38.80%，GPT-5.2 为 37.09%，Llama3.3-70B 为 12.30%（§3.1，Table 2）。
- Claude 的 message-wise sample accuracy 在 MIMIC/GLOBEM/10-K 为 36.07/40.13/77.61%，trajectory-wise 为 34.67/38.72/60.58%；同一模型的 \(I_m\) 与 \(I_t\) 排名/分数并不一致，最终摘要会丢失部分逐轮信息（§3.1，Table 2）。
- Qwen3-Next 增加 reasoning budget 后，每轮 reasoning tokens 在 10-K 从 1.20 增到 357.78，turns 从 27.93 降到 11.89；10-K \(I_m\) accuracy 45.58→36.40、\(I_t\) 31.10→37.34，显示 reasoning/interaction trade-off 而非单调收益（§5.2，Table 3）。
- 加 long-short-term memory 后，Qwen3-Next 在 10-K 与 MIMIC 的 trajectory accuracy 分别从 31.10→25.21、20.80→14.34；仅 GLOBEM 从 32.87→35.86。总 token 反而在三个场景都增加（§5.2，Table 4）。
- reactive 显式问题模式平均 accuracy 为 43.21%，高于 proactive message-wise 32.59% 和 trajectory-wise 28.26%；但 GLOBEM reactive 为 31.95%，低于 proactive message-wise 35.40%（§5.2，Table 5）。
- 206 个错误 item 的人工分类中，58% 归因于 exploration breadth/depth 不足；其余包括 superficial analysis、misinterpretation、over-reasoning、debug loop 与 summarisation loss（§6，Fig. 8）。
- 1,850 个 insight 的 hallucination audit 中，模型平均 rate 为 0.61%–5.69%；场景级最大值为 MiniMax-M2/MIMIC 的 9.09%。论文声称“remaining models below 5%”与 Table 6 的多个值不一致（§7，Table 6）。
- checker 在约 10% 样本上重复 5 次，所有 coefficient of variation 低于 5%；对人工标注，MIMIC/10-K 的 macro F1 为 89.88%–93.97% 与 90.05%–92.03%（§8，Table 7）。
- hallucination rate 与 accuracy 的相关在 10-K/MIMIC/GLOBEM 分别为 \(r=0.125/0.056/-0.046\)，p=0.8779/0.7305/0.9001，未见显著关系（Appendix G，Fig. A10）。
- Appendix B 中复杂 scaffold 多数降分：例如 MIMIC 上 GPT-5-mini 的 ReAct/Plan/Memory/Multi-Agent 为 28.81/23.67/22.22/12.66；仅 10-K 的 plan 在 Qwen3-30B-A3B、GPT-5-mini 上由 42.33→47.59、46.35→49.82（Table A1）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| DDR-Bench 能在大数据库上规模化评估 query-free insight discovery | §2.3–2.4，Table 1：291 entities、203M+ records、2,058 expert-screened items | MIMIC/GLOBEM/10-K；SQL/Python；事实来自文本或 survey counterpart | strong |
| 当前 frontier model 的 investigatory intelligence 仍未饱和 | §3.1，Table 2：最佳 Claude overall 47.73%，仅其超过 40% | 22 个模型、统一最小 ReAct；资源支出不统一 | strong |
| 目标发现比给定问题的执行更难 | §5.2，Table 5：proactive 32.59/28.26% vs reactive 43.21% | 单一 Qwen3-Next；reactive 逐 item 询问且预算未对齐 | medium |
| 增加 reasoning、memory 或复杂 scaffold 不保证涨分 | §5.2，Table 3–4；Appendix B，Table A1 | 主要基于 Qwen3-Next 与三种通用 framework 实现 | strong |
| checker 足够稳定但仍有约 10% 判断误差 | §8，Table 7：CV 2.31%–4.49%，human macro F1 89.88%–93.97% | 约 10% 抽样；MIMIC/10-K；GPT-5-mini checker | medium |

## Critical Analysis

### 论证链条

论文的核心链条很有启发性：给定问题只测执行 → 去掉问题让 agent 自行选择目标 → 用隐藏 checklist 恢复可验证性 → 通过轨迹分析识别 breadth/depth/termination failure。reactive ablation 与 58% exploration error 为“investigatory intelligence 是独立难点”提供了直接证据。

但作者进一步把高分轨迹解释为“implicit planning”“delaying commitment 带来更准 insight”，证据主要来自跨模型曲线与 coverage/entropy 相关性，没有对同一模型随机操控 delay、breadth 或 termination。更强模型可能同时更会规划、更会写 SQL、更懂领域；当前设计不能把这些因素分开。

### 假设压力测试

checklist ground truth 的构造决定 benchmark 测什么。MIMIC note 与 10-K narrative 很大程度是 structured fact 的自然语言总结，适合验证检索与综合；GLOBEM 从 wearable behaviour 推断心理 survey trend，映射更弱，模型即使全面探索也可能无法唯一推出答案。应报告 human analyst 在相同 structured-only 条件下的 ceiling，否则“47.73% 很低”缺少任务可解性锚点。

所谓 contamination resistance 也不是 prevention。模型不看问题确实无法直接 target checklist，列名被改写也降低记忆命中，但 10-K company 和 MIMIC pattern 仍可能被记忆。更重要的是，Table 6 的场景级 hallucination 达 9.09%，与正文“非零均低于 5%”矛盾；虽然与 accuracy 无显著相关，但样本模型数少，p 值很大只能说明未检测到关系，不能证明 contamination 风险“very low”。

### 实验可信度

三类真实数据库、22 个模型、轨迹级 measurement、206 个 error annotation、1,850 个 hallucination annotation 和 checker-human 对齐，使实验覆盖面很强。Table 2 同时报 sample/item average 与 \(I_m/I_t\)，避免单一汇总掩盖差异；Table 3–5 也展示了 counterintuitive negative result。

缺口是没有 human data-scientist baseline、没有成本/轮数对齐的 model comparison，也没有多 seed 重跑 agent trajectory。探索无上限意味着模型之间比较的是不同预算下的自选 operating point；Claude 最贵且最高分，论文的 cost curves只是观察，不是 budget-controlled frontier。novelty ranking 只说“高度相关”却未报告 Spearman/Kendall 或 judge-human agreement，因此不足以证明 checklist 不系统性漏掉强模型的额外发现。

### 系统性缺陷

- **终止与故障恢复**：少数 run 陷入 debugging loop，在 100 rounds 被截断；论文在图中忽略异常点，未把 non-termination rate 作为可靠性指标。
- **上下文与成本**：默认把完整 trajectory 不删减地回传，数据库 observation 主导 token；规模更大或 API context 更小时不可持续。
- **评分耦合**：checklist extraction、open-form checking、novelty comparison 都使用 GPT-5-mini，可能形成共同偏差；checker F1 约 90% 仍会影响相近模型排序。
- **额外推理调用**：每轮 \(I_m\) 由同一模型的独立 prompt 生成，并非原始 ReAct 行为；其 accuracy 与 token/cost 应和 agent trajectory 分开核算。
- **安全与隐私**：MIMIC/GLOBEM 需 credentialed access，traceable reasoning/query/output 可能包含敏感派生信息；论文强调 anonymisation，但未给 access control、audit retention 与删除策略。
- **部署边界**：只有 SQL/Python 两种工具，没有 schema index、semantic layer、权限模型、data quality monitor 或 human approval，离 production analytics agent 仍有明显工程距离。

## 局限与 Future Work

- **局限 1**：checklist 来自已有文本/调查，衡量可验证“重发现”而不是真正未知 insight；没有 human baseline 就无法估计各场景 ceiling。
- **局限 2**：模型可自选 rounds、tokens 与 cost，主榜未按固定预算比较；最高分同时也是最昂贵模型。
- **局限 3**：reactive/proactive ablation 的目标暴露、调用粒度与总预算不同，43.21% 对 32.59%/28.26% 不能被解释为纯粹 agency gap。
- **局限 4**：hallucination 正文与 Table 6 不一致，且无显著相关不等于证明 contamination 不影响分数。
- **局限 5**：checker、checklist extraction 与 novelty judge 共享 GPT-5-mini；human validation 只覆盖 checker 抽样，未覆盖 checklist completeness 或 novelty ranking。
- **Future work 1**：在固定 10K/50K/100K token 与 10/25/50 rounds 预算下绘制每个模型的 accuracy–cost Pareto frontier，并把 non-termination/tool-error rate 纳入主指标。
- **Future work 2**：招募领域分析师在 structured-only 条件下完成相同实体，报告 human checklist recall、novel insight precision 与耗时，建立可解性和效率 ceiling。
- **Future work 3**：对同一模型随机干预 breadth、entropy、planning delay 与 termination threshold，验证 Fig. 1/5 的 implicit-planning 相关是否具有因果性。
- **Future work 4**：用独立模型与专家分别构造 checklist、执行 checker、评 novelty，测量 shared-judge bias 对模型排名的影响。
- **Future work 5**：为每条 novel insight 引入 query replay + evidence provenance + expert adjudication 子集，客观估计 checklist false-negative rate，而不只比较 LLM pairwise usefulness。

## 相关

- **相关概念**：LLM Agent、Agent Scaffold、LLM-as-a-Judge、ReAct、long-horizon planning、open-ended data analysis
- **同类 benchmark**：[[HeurekaBench-ICLR26]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、DiscoveryBench、ScienceAgentBench
- **相关科研系统**：[[AutoScientists-arXiv26]]、[[Kosmos-AI-Scientist-arXiv25]]、DeepAnalyze
- **同主题**：[[Auto-Research]]
- **同会议**：ICML 2026
- **命名说明**：论文标题是 *Hunt Instead of Wait*；DDR 是任务设定，DDR-Bench 是本文提出的 benchmark 与评测套件。
