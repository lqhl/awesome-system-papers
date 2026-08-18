---
type: paper
name: DDR-Bench
full_title: "Hunt Instead of Wait: Evaluating Deep Data Research on Large Language Models"
authors: [Wei Liu, Peijie Yu, Michele Orini, Yali Du, Yulan He]
venue: ICML
year: 2026
tags: [auto-research, data-agent, investigatory-intelligence, benchmark, long-horizon-agent, domain/auto-research, concern/long-horizon]
source_pdf: "[[icml26-liu-deep-data-research.pdf]]"
source_md: "[[icml26-liu-deep-data-research]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# 主动寻找而非等待：评测大语言模型的深度数据研究能力（ICML 2026）

> **原题**：Hunt Instead of Wait: Evaluating Deep Data Research on Large Language Models

> **一句话总结**：DDR-Bench 把数据智能体从“回答已知问题”推进到“只给实体 ID 和数据库，自主决定查什么、何时停止”，并以 291 个实体、2,058 个 fact 核对清单检验可验证洞见；最佳 Claude 4.5 Sonnet 的综合准确率仍只有 47.73%，而把核对清单直接变成问题后 Qwen3-Next 的平均准确率从主动探索 message/轨迹的 32.59%/28.26% 升至响应式问答的 43.21%，说明当前瓶颈首先是发现目标与维持探索策略，而不只是执行 SQL/Python（§2–3，§5.2，表 1、2、5）。

## 问题与动机

多数数据-science 智能体基准预先给出问题、目标或详细工作流，测量的是智能体执行既定目标的能力。作者将其称为 **executional intelligence**，并提出另一层能力 **investigatory intelligence**：面对原始数据，智能体是否能自行判断什么值得查、形成和验证假设、在宽度与深度间分配注意力，并自主决定何时停止。

Deep Data 研究（DDR）把这一问题形式化为无显式问题探索。智能体只拿到一个任务实体与数据库 metadata，例如“分析 user 2048”，没有问题、目标或交互轮数上限；它通过 SQL/Python 持续探索，最后报告发现。DDR-Bench 则提供可规模化评分：从数据库的 unstructured/semantic counterpart 提取 fact 核对清单，检查智能体从结构化数据得到的洞见是否足以支持这些事实（§2.1–2.4）。

这一区分与 [[PaperBench-ICML25]]、[[MLE-Bench-ICLR25]] 等给定目标的 R&D/工程基准互补：DDR-Bench 不要求复现某个指定结果，而是观察智能体是否主动找到潜在结果。但它仍不是“未知科学发现”评测，因为核对清单来自已有文本或 survey，最终奖励的是**自主找回预先可验证的事实**。

## 关键观察 / 隐含假设

- **观察 1：无显式问题目标发现比目标驱动执行显著更难。** Qwen3-Next-80B-A3B 在主动探索 DDR 中逐消息/逐轨迹平均准确率为 32.59%/28.26%；把每个核对清单 item 变成显式问题后，响应式问答准确率为 43.21%（§5.2，表 5）。
  - **依赖假设**：响应式问答与主动探索两种设置的工具预算、调用次数和评价粒度足够可比。
  - **可能失效场景**：响应式问答模式逐核对清单 item 发问，等于暴露目标并可能提供更多总推理/工具预算；差值不全是“agency tax”。

- **观察 2：高分模型呈现“先广后深”的 implicit 规划，但这是相关性而非因果证据。** 交互曲线常为 sigmoid；Claude、GLM、DeepSeek 较晚进入快速增益阶段，后期用少量复杂 query 获得高价值洞见；适中的覆盖率与熵也对应更高准确率（§4.1–4.2，图 1、5）。
  - **依赖假设**：field 覆盖率与 normalised 熵能分别代表探索 breadth/depth，且不同 schema 的字段具有可比信息量。
  - **可能失效场景**：一个高信息字段可能胜过大量低信息字段；schema denormalisation、重复列或宽表会扭曲覆盖率/熵。跨模型的自选轨迹也不能证明“延迟行动”本身提升结果。

- **观察 3：更大模型、更长 context 或更多显式推理并不单调提升 investigatory intelligence。** Qwen2.5 参数增大约 10 倍，最终准确率增益仍少于 3%；Qwen3-Next 增加推理预算后交互轮数显著减少，但 10-K message 准确率从 45.58% 降至 36.40%，轨迹准确率则从 31.10% 升至 37.34%（§5.1–5.2，图 7、表 3）。
  - **依赖假设**：Qwen 跨代差异可主要归因于 agentic-first 训练，而不是数据、架构、后训练 方案 等未控制因素。
  - **可能失效场景**：在固定训练配方或更长任务上，扩展/context 可能重新成为主导；当前结论来自 family-level observational comparison。

- **观察 4：通用智能体 module 常改变行为，却不稳定提高准确率。** Qwen3-Next 加记忆后，10-K 轨迹/message 准确率从 31.10/45.58 降至 25.21/37.34，MIMIC 从 20.80/16.80 降至 14.34/15.63；附录 B 的规划/记忆/多智能体多数也弱于 ReAct 基线（§5.2，表 4、表 A1）。
  - **依赖假设**：所选 CoALA、Plan-and-Execute、AutoGen 实现能代表记忆/规划/多智能体范式。
  - **可能失效场景**：case-specific compression、retrieval 策略、角色划分或终止信号 control 经调优后可能反转结论；论文只能否定“通用模块即插即涨分”。

- **假设 1：从 unstructured text/survey 提取的核对清单可作为 structured-数据发现的目标真值。**
  - **证据强度**：**中**。超过 50 位领域专家筛选、共 2,058 个 item；但核对清单只覆盖文本已记载的事实，无法穷举正确洞见，且“surjective mapping”不保证每个事实从当前工具与预算下都容易推导。

- **假设 2：用最小 ReAct 脚手架能测到模型“内生 agency”。**
  - **证据强度**：**中偏弱**。统一 SQL/Python 接口减少脚手架 confound，但系统提示词仍反复强调格式和多步探索，逐消息洞见还由额外的同模型调用生成；测到的是模型+提示词+工具协议，而非纯模型属性。

## 核心方法

DDR 将一次轨迹写成多轮 \((r,t,o)\)：推理、工具 invocation 与观察。模型只获得 entity-level start 提示词与模式元数据，通过 SQL/Python 自主查询，并自行发出终止信号。输出分为两类：**逐消息洞见 \(I_m\)** 是每轮结束后由同一底座模型通过独立提示词将当前 \((r,t,o)\) 解释成洞见；**逐轨迹洞见 \(I_t\)** 是智能体终止后对完整历史生成的最终报告（§2.1，附录 H.2）。

DDR-Bench 采用轻量 ReAct 智能体，不含显式规划器或记忆，工具通过 MCP 暴露。论文刻意不限制交互轮数，以便把终止信号本身纳入能力；但实际存在模型陷入 debugging 闭环的异常运行，达到 100 rounds 后被强制停止，并在部分轨迹-length 图中忽略（§2.2，附录 D）。

三个场景覆盖不同结构（§2.3，表 1）：

- **MIMIC-IV**：100 位患者，29 tables、318 fields、200M+ records；结构化 EHR 对齐临床 note，774 核对清单 items。
- **GLOBEM**：91 位用户，6 tables、222 fields、55K+ records；用 wearable time series 推断 intervention 前后 survey 趋势，435 items。
- **10-K**：100 家公司，5 tables、5,832 fields、3M+ records；用 XBRL financial facts 对齐 filing text，849 items。

总计 291 个 entity、203M+ records、40 tables、6,372 fields 与 2,058 个 verified 核对清单 item。GPT-5-mini 从文本/调查中抽取事实，超过 50 位领域专家审查其可由结构化数据推导。MIMIC/10-K 由 GPT-5-mini 判断洞见是否为 ground-truth fact 提供 CORRECT_INFO；GLOBEM 则让检查器基于洞见回答三选一趋势题并 exact match（§2.4、附录 H.4）。

为降低核对清单漏标对强模型的惩罚，作者把未匹配任何 item 的 \(I_m\) 当作候选 novel 洞见，用匿名、随机顺序的 GPT-5-mini pairwise usefulness comparison，再用 Bradley–Terry 聚合排名。新颖性 rank 与核对清单准确率 rank 在三场景高度接近，但论文未给具体相关系数（§3.2，图 4）。

## 设计取舍

- **最大开放性 vs 预算公平**：不限制 rounds 能观察 self-终止信号，却允许模型用不同 token、工具 time 与 API 成本；更高分可能部分来自更高支出，且不终止运行最终仍被 100-round 安全 cap 截断。
- **客观核对清单 vs 洞见 completeness**：逐事实检查比报告级主观分数可审计，但核对清单必然漏掉新洞见；pairwise 新颖性又重新引入 closed-source [[LLM|LLM]] 的主观判断。
- **最小脚手架 vs 可用系统上限**：轻量 ReAct 有助于比较 base 模型，却刻意排除生产环境数据智能体常用的记忆、规划器、schema retrieval 与多智能体；分数是“最小脚手架下能力”，不是最佳系统上限。
- **structured/unstructured 对齐 vs 任务 construct 有效性**：MIMIC 与 10-K 的文字确实总结结构化事实；GLOBEM 则要求 wearable 信号推断 survey 改善，二者未必有稳定可识别映射，低分可能反映信号不足而非 agency 不足。
- **可追溯性 vs 隐私/安全**：每个洞见链回推理、query 与观察，便于审计；但医疗/行为数据仍需 credentialed access，完整轨迹也可能泄露敏感派生信息。
- **边界条件**：适合有大型 structured database、可从独立文本/调查构造事实清单的领域；不适合真值尚未知、只能靠因果实验验证或没有 semantic counterpart 的数据。

## 实验与结果

- DDR-Bench 含 291 个任务 entity、2,058 核对清单 item 与 203M+ records；MIMIC/GLOBEM/10-K 分别为 100/91/100 entities 和 774/435/849 items（§2.3–2.4，表 1）。
- 22 个 proprietary/open-source 模型中，仅 Claude 4.5 Sonnet overall average 超过 40%，为 47.73%；第二名 open 模型 DeepSeek-V3.2 为 38.80%，GPT-5.2 为 37.09%，Llama3.3-70B 为 12.30%（§3.1，表 2）。
- Claude 的逐消息样本准确率在 MIMIC/GLOBEM/10-K 为 36.07/40.13/77.61%，逐轨迹为 34.67/38.72/60.58%；同一模型的 \(I_m\) 与 \(I_t\) 排名/分数并不一致，最终摘要会丢失部分逐轮信息（§3.1，表 2）。
- Qwen3-Next 增加推理预算后，每轮推理 tokens 在 10-K 从 1.20 增到 357.78，turns 从 27.93 降到 11.89；10-K \(I_m\) 准确率 45.58→36.40、\(I_t\) 31.10→37.34，显示推理/interaction 权衡而非单调收益（§5.2，表 3）。
- 加 long-short-term 记忆后，Qwen3-Next 在 10-K 与 MIMIC 的轨迹准确率分别从 31.10→25.21、20.80→14.34；仅 GLOBEM 从 32.87→35.86。总 token 反而在三个场景都增加（§5.2，表 4）。
- 响应式问答显式问题模式平均准确率为 43.21%，高于主动探索逐消息 32.59% 和逐轨迹 28.26%；但 GLOBEM 响应式问答为 31.95%，低于主动探索逐消息 35.40%（§5.2，表 5）。
- 206 个错误 item 的人工分类中，58% 归因于探索 breadth/depth 不足；其余包括 superficial 分析、misinterpretation、over-推理、调试闭环与 summarisation loss（§6，图 8）。
- 1,850 个洞见的幻觉 audit 中，模型平均 rate 为 0.61%–5.69%；场景级最大值为 MiniMax-M2/MIMIC 的 9.09%。论文声称“remaining 模型 below 5%”与表 6 的多个值不一致（§7，表 6）。
- 检查器在约 10% 样本上重复 5 次，所有 coefficient of variation 低于 5%；对人工标注，MIMIC/10-K 的 macro F1 为 89.88%–93.97% 与 90.05%–92.03%（§8，表 7）。
- 幻觉 rate 与准确率的相关在 10-K/MIMIC/GLOBEM 分别为 \(r=0.125/0.056/-0.046\)，p=0.8779/0.7305/0.9001，未见显著关系（附录 G，图 A10）。
- 附录 B 中复杂脚手架多数降分：例如 MIMIC 上 GPT-5-mini 的 ReAct/Plan/记忆/Multi-智能体为 28.81/23.67/22.22/12.66；仅 10-K 的计划在 Qwen3-30B-A3B、GPT-5-mini 上由 42.33→47.59、46.35→49.82（表 A1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| DDR-Bench 能在大数据库上规模化评估无预设问题的洞见发现 | §2.3–2.4，表 1：291 个实体、超过 2.03 亿条记录、2058 个专家筛选项 | MIMIC、GLOBEM、10-K；SQL/Python；事实来自文本或配套调查 | 强 |
| 当前前沿模型的自主调查能力仍未饱和 | §3.1，表 2：最佳 Claude 总分 47.73%，仅它超过 40% | 22 个模型、统一最小 ReAct；资源支出不统一 | 强 |
| 自主决定研究目标比执行给定问题更难 | §5.2，表 5：主动模式 32.59%/28.26%，被动模式 43.21% | 单一 Qwen3-Next；被动模式逐项询问且预算未对齐 | 中 |
| 增加推理、记忆或复杂脚手架不保证涨分 | §5.2，表 3–4；附录 B，表 A1 | 主要基于 Qwen3-Next 与三种通用框架实现 | 强 |
| 检查器足够稳定，但仍有约 10% 判断误差 | §8，表 7：变异系数 2.31%–4.49%，人类宏平均 F1 为 89.88%–93.97% | 约 10% 抽样；MIMIC/10-K；GPT-5-mini 检查器 | 中 |

## 批判性分析

### 论证链条

论文的核心链条很有启发性：给定问题只测执行 → 去掉问题让智能体自行选择目标 → 用隐藏核对清单恢复可验证性 → 通过轨迹分析识别 breadth/depth/终止信号失败。响应式问答消融实验与 58% 探索 error 为“investigatory intelligence 是独立难点”提供了直接证据。

但作者进一步把高分轨迹解释为“implicit 规划”“delaying commitment 带来更准洞见”，证据主要来自跨模型曲线与覆盖率/熵相关性，没有对同一模型随机操控 delay、breadth 或终止信号。更强模型可能同时更会规划、更会写 SQL、更懂领域；当前设计不能把这些因素分开。

### 假设压力测试

核对清单真值的构造决定基准测什么。MIMIC note 与 10-K 叙述很大程度是 structured fact 的自然语言总结，适合验证检索与综合；GLOBEM 从 wearable behaviour 推断心理 survey trend，映射更弱，模型即使全面探索也可能无法唯一推出答案。应报告人类 analyst 在相同 structured-only 条件下的 ceiling，否则“47.73% 很低”缺少任务可解性锚点。

所谓污染 resistance 也不是 prevention。模型不看问题确实无法直接 target 核对清单，列名被改写也降低记忆命中，但 10-K company 和 MIMIC pattern 仍可能被记忆。更重要的是，表 6 的场景级幻觉达 9.09%，与正文“非零均低于 5%”矛盾；虽然与准确率无显著相关，但样本模型数少，p 值很大只能说明未检测到关系，不能证明污染风险“very low”。

### 实验可信度

三类真实数据库、22 个模型、轨迹级 测量、206 个 error annotation、1,850 个幻觉 annotation 和检查器-人类对齐，使实验覆盖面很强。表 2 同时报样本/item average 与 \(I_m/I_t\)，避免单一汇总掩盖差异；表 3–5 也展示了 counterintuitive 负面结果。

缺口是没有人类数据-科学家基线、没有成本/轮数对齐的模型 comparison，也没有多 seed 重跑智能体轨迹。探索无上限意味着模型之间比较的是不同预算下的自选 operating point；Claude 最贵且最高分，论文的成本 curves只是观察，不是预算-受控前沿。新颖性排序只说“高度相关”却未报告 Spearman/Kendall 或评审器-人类 agreement，因此不足以证明核对清单不系统性漏掉强模型的额外发现。

### 系统性缺陷

- **终止与故障恢复**：少数运行陷入 debugging 闭环，在 100 rounds 被截断；论文在图中忽略异常点，未把 non-终止信号 rate 作为可靠性指标。
- **上下文与成本**：默认把完整轨迹不删减地回传，数据库观察主导 token；规模更大或 API context 更小时不可持续。
- **评分耦合**：核对清单 extraction、open-form checking、新颖性 comparison 都使用 GPT-5-mini，可能形成共同偏差；检查器 F1 约 90% 仍会影响相近模型排序。
- **额外推理调用**：每轮 \(I_m\) 由同一模型的独立提示词生成，并非原始 ReAct 行为；其准确率与 token/成本应和智能体轨迹分开核算。
- **安全与隐私**：MIMIC/GLOBEM 需 credentialed access，traceable 推理/query/输出可能包含敏感派生信息；论文强调 anonymisation，但未给 access control、audit retention 与删除策略。
- **部署边界**：只有 SQL/Python 两种工具，没有 schema index、semantic layer、权限模型、数据质量 monitor 或人类 approval，离生产环境 analytics 智能体仍有明显工程距离。

## 局限与后续工作

- **局限 1**：核对清单来自已有文本/调查，衡量可验证“重发现”而不是真正未知洞见；没有人类基线就无法估计各场景 ceiling。
- **局限 2**：模型可自选 rounds、tokens 与成本，主榜未按固定预算比较；最高分同时也是最昂贵模型。
- **局限 3**：响应式问答/主动探索消融实验的目标暴露、调用粒度与总预算不同，43.21% 对 32.59%/28.26% 不能被解释为纯粹 agency 缺口。
- **局限 4**：幻觉正文与表 6 不一致，且无显著相关不等于证明污染不影响分数。
- **局限 5**：检查器、核对清单 extraction 与新颖性评审器共享 GPT-5-mini；人类验证只覆盖检查器抽样，未覆盖核对清单 completeness 或新颖性排序。
- **后续工作 1**：在固定 10K/50K/100K token 与 10/25/50 rounds 预算下绘制每个模型的准确率–成本 Pareto 前沿，并把 non-终止信号/工具-error rate 纳入主指标。
- **后续工作 2**：招募领域分析师在 structured-only 条件下完成相同实体，报告人类核对清单 recall、novel 洞见 precision 与耗时，建立可解性和效率 ceiling。
- **后续工作 3**：对同一模型随机干预 breadth、熵、规划 delay 与终止信号 threshold，验证图 1/5 的 implicit-规划相关是否具有因果性。
- **后续工作 4**：用独立模型与专家分别构造核对清单、执行检查器、评新颖性，测量 共享评审器 bias 对模型排名的影响。
- **后续工作 5**：为每条 novel 洞见引入 query replay + 证据来源追踪 + 专家 adjudication 子集，客观估计核对清单 false-负面 rate，而不只比较 LLM pairwise usefulness。

## 相关

- **相关概念**：LLM 智能体、智能体脚手架、LLM-as-a-评审器、ReAct、长程规划、开放式数据分析
- **同类基准**：[[HeurekaBench-ICLR26]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、DiscoveryBench、ScienceAgentBench
- **相关科研系统**：[[AutoScientists-arXiv26]]、[[Kosmos-AI-Scientist-arXiv25]]、DeepAnalyze
- **同主题**：[[Auto-Research]]
- **同会议**：ICML 2026
- **命名说明**：论文标题是 *Hunt Instead of Wait*；DDR 是任务设定，DDR-Bench 是本文提出的基准与评测套件。
