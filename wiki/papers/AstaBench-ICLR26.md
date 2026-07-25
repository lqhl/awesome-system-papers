---
type: paper
name: AstaBench
full_title: "AstaBench: Rigorous Benchmarking of AI Agents with a Scientific Research Suite"
authors: [Jonathan Bragg, Mike D'Arcy, Nishant Balepur, Dan Bareket, Bhavana Dalvi, et al.]
venue: ICLR
year: 2026
tags: [ai-agents, scientific-discovery, benchmark, evaluation, reproducibility]
source_pdf: "[[iclr26-bragg-astabench.pdf]]"
source_md: "[[iclr26-bragg-astabench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-23
---

# AstaBench: Rigorous Benchmarking of AI Agents with a Scientific Research Suite (ICLR 2026)

> **一句话总结**：AstaBench 把 11 个 benchmark、2,400 多道题和统一的文献/计算工具放进同一成本可追踪环境，控制「模型能力还是工具/预算优势」这一核心混杂因素；57 个 agent、22 类架构的结果显示 Asta v0 总分 53.0、比 ReAct+GPT-5 高 9.0 个百分点，但端到端科研即使逐步完成率最高约 70%，完整任务成功率仍最高仅 5%（§3–5，Table 4、10、20）。

## 问题与动机

科学 agent 的评测长期混合了三种变量：底层模型、agent scaffold，以及可访问的搜索语料和计算工具。不同系统在各自环境中报告分数，既无法确定收益来自 planning 还是更强的信息源，也无法在 API 价格变化后比较成本；许多 benchmark 又只覆盖科研流水线中的单点能力。作者因此将问题定义为：如何在统一、可复现且考虑成本的条件下，横跨文献理解、代码执行、数据分析和端到端发现来比较科学 agent（§1）。

AstaBench 汇集 11 个 benchmark、2,400 多个问题，既复用 LitQA2、CORE-Bench、DS-1000、DiscoveryBench 等任务，也新增 PaperFindingBench、ScholarQA-CS2 和 E2E-Bench 系列。它不是一个自动科研系统，而是一套 benchmark + environment + evaluation toolkit + baseline agents；因此它与 [[AI-Scientist-arXiv24]]、[[AutoScientists-arXiv26]] 的关系是测量者与被测系统，而非同类 discovery pipeline（§3–4）。

## 关键观察 / 隐含假设

- **观察 1：不控制工具和推理成本，agent 排名无法归因于核心 agentic capability。** Asta Environment 为同一任务提供日期冻结的 Asta Scientific Corpus 或统一 Computational Notebook，agent-eval 再用冻结的 LiteLLM 价格快照换算成本（§4.1–4.2）。
  - **依赖假设**：相同工具接口和 corpus cutoff 足以消除主要的信息访问差异；模型提供商未报告或价格表未覆盖的服务差异不会显著改变排名。
  - **可能失效场景**：真实科研中 corpus、新软件和硬件持续变化；冻结环境提高可复现性，却可能低估善用最新知识和异构实验设施的系统。
- **观察 2：科研链条存在强烈的 compounding failure。** E2E-Bench 每项约 10–15 个 rubric step，单步完成率最高约 70%，但完整任务成功率最高仅 5%（§5、Appendix E.9，Table 10、20）。
  - **依赖假设**：rubric step 的完备性和 [[LLM|LLM]] judge 对 report、code、artifact 三类证据的判定足以代表真正完成科研任务。
  - **可能失效场景**：rubric 遗漏关键科学错误时会高估成功；过细或高度相关的 step 又会放大乘法式失败。
- **观察 3：专用科学工具带来显著收益，但工程与推理成本同时上升。** Asta v0 总分 53.0，高于 ReAct+GPT-5 的 44.0；前者每题平均成本 \$3.40，后者为 \$0.31（§5，Table 4）。
  - **证据强度**：中。统一 benchmark 支持直接比较，但 Asta v0 是针对任务类别路由的 specialist mixture，收益无法分解为工具、路由和各 specialist 的独立贡献。
- **假设 1：把异质 benchmark 的规范化得分作 macro average，可以形成有意义的「整体科研能力」。**
  - **证据强度**：弱到中。它便于 leaderboard 排序，但文献 QA、代码复现和开放发现的 score semantics 不同；一个总分不能说明系统是否能完成任一真实科研项目。

## 核心方法

AstaBench 将科研能力拆成四类：Literature Understanding、Code & Execution、Data Analysis、End-to-End Discovery。任务既包含 [[MLE-Bench-ICLR25]] 所代表的 ML engineering 邻近能力，也覆盖论文检索、长答案引用、数据驱动假设与完整 research report。各任务通过统一 Inspect 接口暴露，允许 ReAct 等通用 agent 直接接入（§3，Table 2）。

Asta Environment 提供两类标准工具。Asta Scientific Corpus 通过 MCP 暴露文献搜索、snippet、论文/作者/引用查询，并能按 benchmark 创建日期截断返回结果以减轻未来论文污染；Computational Notebook 提供有状态 Python、shell 和隔离 sandbox。这个设计直接回应观察 1：agent 可以不同，但信息源和执行边界保持一致（§4.1）。

agent-eval 在 Inspect 日志上增加 benchmark suite、leaderboard 和时间不变的成本核算。排行榜还显式标记 agent openness 与 tooling：开源/闭源，以及标准工具、等价自定义接口或完全自定义工具。它没有把不可控系统伪装成严格同组，而是将可比性作为结果维度公开（§4.2，Appendix B）。

agent-baselines 提供 16 类标准接口 agent；论文实验进一步覆盖 57 个 agent 实例和 22 类架构。Asta v0 先根据输入字符级重叠识别任务类别，再路由到 Paper Finder、Scholar QA、DataVoyager、Panda、ReAct 等 specialist；validation set 上路由准确率为 100%，但这也使其成为 task-aware mixture，而非未知科研任务上的通用 planner（Appendix F.7）。

端到端任务的 scorer 用任务专属 rubric，分别检查生成 report、code 和 artifact。只有三类证据一致且至少一类明确满足时才记为完成；开发集抽查 50 个 rubric item，LLM judge 与人工判断一致率为 92%。这种多证据检查比只读论文文本更能压低 fabrication false positive，但仍不是完整的科学正确性验证（Appendix F.9，Fig. 10、Table 21）。

## 设计取舍

- **可复现环境 vs 真实开放世界**：冻结 corpus cutoff、工具和价格让时间点之间可比，但牺牲对最新论文、非标准实验设施和真实团队协作的覆盖。
- **覆盖广度 vs 总分可解释性**：11 个 benchmark 覆盖科研链条，却把不同 metric 的标准化分数聚合为一个 macro average；总分适合导航，不适合当作「完成科研」概率。
- **LLM judge 的可扩展性 vs 评价偏差**：开放答案和端到端任务必须依赖 rubric judge；ScholarQA-CS2 的系统级 Kendall τ 为 0.467，排除 Elicit 后才升至 0.800，说明 judge 排名对输出风格/系统具有可见偏差（Appendix E.3）。
- **specialist routing vs 通用性**：Asta v0 获得最高总体分，但需要较高工程成本和任务类别先验；分布外科研任务的路由与 specialist coverage 未被测试。

## 实验与结果

- 在能覆盖全套任务或至少完整类别的 agent 中，Asta v0 总分 53.0、每题平均成本 \$3.40；ReAct+GPT-5 为 44.0/\$0.31，ReAct+o3 为 39.4/\$0.16，开源权重最佳 Smolagents+Llama-4-Scout 仅 11.1/\$0.11（§5，Table 4）。
- ReAct+GPT-5-mini 以 \$0.04/题得到 31.6，总分比 Asta v0 低 21.4 个百分点但成本低约两个数量级，是低成本 Pareto 点；较弱模型可能因更多步骤或循环而比昂贵模型总成本更高（§5，Fig. 2、Table 4）。
- Code & Execution 仍是瓶颈：SUPER-Expert 上除 ReAct+GPT-5（41%）和 GPT-5-mini（37%）外，其余 agent 均低于 25%；Data Analysis 的 DiscoveryBench 最高仅 34%（§5，Table 8–9）。
- Literature Understanding 相对成熟：ScholarQA-CS2 的 Asta Scholar QA、Elicit、SciSpace Deep Review 均约 85% 或更高；但 ArxivDIGESTables-Clean 最佳 recall 仍约 43%（§5，Table 6–7）。
- E2E-Bench 的平均 rubric-step 完成率最高约 70%，完整任务成功率最高仅 5%；三类 artifact 联合评分还纠正了 16%「report 声称完成但 code/artifact 不支持」的潜在 false positive（§5，Appendix F.9，Table 10、20–21）。
- GPT-5 相对 o3 在多数 benchmark 只提升 0–5 个百分点，但在 ScholarQA-CS2、SUPER-Expert、LitQA2-FullText-Search、E2E-Bench-Hard 分别提升 13.4、24.8、25.3、21.1 个百分点；同一模型升级对 specialist agent 反而常降分（§5，Table 5–10）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| 统一工具与成本核算能更严格地比较科学 agent | §4.1–4.2，Table 2，Appendix B | 日期冻结的文献 corpus、统一 notebook、冻结 API 价格；不覆盖真实开放实验设施 | strong |
| 专用科学工具/路由能显著提高总体得分 | §5，Table 4 | 11 个 benchmark 的 macro average；Asta v0 53.0 vs ReAct+GPT-5 44.0 | medium |
| 当前 agent 距离完整端到端科研仍很远 | §5，Appendix E.9，Table 10、20 | 50 个 AI/NLP E2E task；逐步最高约 70%，完整成功最高 5% | strong |
| 开放权重 agent 与闭源模型 agent 仍有巨大差距 | §5，Table 4 | 最佳 open-weight 11.1 vs Asta v0 53.0；架构与模型同时变化 | medium |
| LLM judge 的多 artifact 评分能减少虚假完成 | Appendix F.9，Fig. 10、Table 21 | 50 个 dev rubric item 人工抽查 92%；仍有过度乐观和概念细节错误 | medium |

## Critical Analysis

### 论证链条

论文从「现有评测混入工具、成本和接口差异」出发，给出标准环境、成本账本和多架构基线，逻辑链条完整；尤其把 score-cost Pareto frontier 和 openness/tooling 状态同时公开，比只报最高分更有解释力。较大的跳步是将跨任务 macro average 命名为 holistic scientific research ability：AstaBench 确实覆盖更多阶段，但覆盖多个代理任务不等于验证一个 agent 能形成新颖且正确的科学结论。

E2E-Bench 的完整成功率是最有力的反证性结果：高单步分数不会自动组合成可靠科研闭环。另一方面，其 50 个任务由 2021 年后高引 ACL 论文两两组合、LLM 生成并经人工修订而来，测到的是软件型 AI/NLP mini-project；不能外推到湿实验、理论证明或需要多年数据采集的科学。

### 假设压力测试

统一工具假设在 leaderboard 中成立，但 production scientist 通常依赖持续更新的数据库、组织内数据和特殊仪器。agent 若通过发现并整合新工具创造价值，在 AstaBench 中反而可能因「fully custom」失去严格可比性。相反，熟悉 Asta API 或任务分布的 specialist 会获得结构性优势。

成本报告冻结 token 单价，但不包含开发 specialist 的 engineering cost、服务延迟折扣、人工监督和基础设施摊销。Asta v0 的 \$3.40/题不能与 ReAct 的 \$0.31/题解释成总拥有成本的 11 倍；它只表示论文定义下的 inference spend。

### 实验可信度

57 个 agent、22 类架构、95% CI 和完整 cost logs 提供了罕见的覆盖度。任务评分却混合 programmatic evaluator 和 LLM judge；ScholarQA-CS2 的人工一致性只有中等，held-out rubric 还使部分系统平均下降 2.5 分，表明 pooled-answer rubric 存在 held-in bias（Appendix E.3）。端到端 scorer 的 92% 是 50 个 rubric item 的 dev 抽查，不足以证明对所有科学错误稳健。

Baseline 比较对标准接口 agent 较公平，但闭源 UI/API 系统不能执行全类任务，于是「整体榜」主要比较作者可运行的通用 agent。模型升级与 scaffold 交互显著，论文正确提醒不能把底模 SOTA 当作 agent SOTA；不过没有 factorial design 分离 model、tool、router 和 specialist prompt 的贡献。

### 系统性缺陷

Asta Scientific Corpus 是可复现性的关键依赖，也形成集中式基础设施风险：语料覆盖、索引版本、API 可用性和长期维护会决定 benchmark 能否真正复跑。论文未讨论 corpus outage、sandbox 隔离故障、恶意论文内容对 agent 的 prompt injection，以及长任务的 checkpoint/recovery SLO。

leaderboard 允许 custom tooling 并做显式标记，而不是完全禁止；这提高生态兼容性，却意味着不同 openness/tooling 桶之间不可直接解释成同一受控实验。Asta v0 的字符重叠路由在 validation 上 100% 正确，也可能利用固定任务措辞，面对自然研究请求的鲁棒性没有证据。

## 局限与 Future Work

- **局限 1**：2,400 多题不等于 2,400 个开放科研项目；大量任务仍是检索、QA、代码和结构化数据代理目标，科学新颖性与长期复现覆盖不足。
- **局限 2**：E2E-Bench/E2E-Bench-Hard 来自 AI/NLP 论文种子并依赖 LLM judge，领域与 evaluator 外部有效性有限。
- **局限 3**：宏平均总分掩盖能力形状；53.0 分的 agent 仍可能在某个真实任务所需的关键步骤上接近零。
- **Future work 1**：在同一组隐藏任务上做 model × scaffold × tool 的 factorial ablation，报告各因素对分数、成本和方差的独立贡献。
- **Future work 2**：用独立专家盲审至少 500 个端到端 rubric item，并报告分领域 false-positive/false-negative，而不是单一 92% 总一致率。
- **Future work 3**：加入污染抵抗的滚动新题、人类协作任务和 biomedicine 等领域，同时保留可版本化的 corpus snapshot。
- **Future work 4**：为长任务增加 checkpoint、失败恢复、资源冲突和 prompt-injection 测试，使环境从功能 benchmark 扩展到 research-agent reliability benchmark。

## 相关

- **相关概念**：[[Auto-Research]]、agent evaluation、scientific discovery、reproducibility、LLM-as-a-judge
- **同类 benchmark**：[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[PaperBench-ICML25|PaperBench]]
- **被测系统**：[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[AutoScientists-arXiv26]]、[[Kosmos-AI-Scientist-arXiv25]]
- **同会议**：ICLR 2026
