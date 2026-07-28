---
type: paper
name: Co-Scientist
full_title: "Accelerating scientific discovery with Co-Scientist"
authors: [Juraj Gottweis, Wei-Hung Weng, Alexander Daryin, Tao Tu, Petar Sirkovic, et al.]
venue: Nature
year: 2026
tags: [ai-agents, scientific-discovery, multi-agent, biomedicine, drug-repurposing]
source_pdf: "[[nature26-gottweis-co-scientist.pdf]]"
source_md: "[[nature26-gottweis-co-scientist]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# 用 Co-Scientist 加速科学发现（Nature 2026）

> **原题**：Accelerating scientific discovery with Co-Scientist

> **一句话总结**：Co-Scientist 用 Gemini 多智能体的生成—反思—排序—进化（Generation–Reflection–Ranking–Evolution）竞赛机制，随测试时算力增加持续改进假设，并在 203 个目标上呈 Elo 上升；其真正强证据来自专家参与闭环的三类生物医学验证——AML 中 KIRA6 对 KG-1a/TK6 的 IC50 为 10/180 nM、肝纤维化 3 个候选中 2 个在类器官中有效、AMR 机制在 2 天内被复现——但系统没有自主执行实验，代码及三类验证数据也未公开（图 1–4，表 1，方法）。

## 问题与动机

科研人员面对「深度与广度」矛盾：单一领域的文献和技术已难以穷尽，重要假设却常来自跨领域连接。普通 deep-研究工具能总结文献，却不负责形成可测试的新假设、比较候选和规划实验。Co-Scientist 的目标因此不是自动写论文，而是充当结构化科学 thinking engine：科学家定义问题和约束，系统大规模生成、批判、比较和演化假设，再由科学家选择进入实验（Introduction，图 1）。

这一区分很关键。与 [[DeepScientist-ICLR26]] 自己写代码、执行基准实验的软件发现闭环不同，Co-Scientist 只自动化计算机内（in-silico）的想法生成和提案精炼；湿实验、候选终选与临床判断仍由人类完成。论文明确将其称为专家参与闭环，而非完全自主科学家（图 1，方法：Expert-in-the-loop interactions）。

## 关键观察 / 隐含假设

- **观察 1：同一研究目标下，持续 tournament/精炼的 auto-evaluated Elo 随计算时间上升。** 203 个研究目标的输出按生成时间切成十个等量 bucket，top-10 平均 Elo 和 best Elo 均持续提高；15 个专家目标上后期 Co-Scientist Elo 超过专家 best guess 和同期前沿模型，未见饱和（System 分析，图 2a–b）。
  - **依赖假设**：由同一系统内部 pairwise 辩论形成的 Elo 与真实科学质量单调相关。
  - **可能失效场景**：排序智能体和生成智能体共享模型偏好时，更多算力可能只是更好地优化评审器 style，而非提高可验证性；图 2 没有将额外算力随机分配给独立基线。
- **观察 2：外部检索是新颖性/正确性 gate，而非可选增强。** Reflection 智能体无搜索时把已发表想法的新颖性评为 6.14/10，加入搜索后降至 2.38；known-correct 想法的正确性从 7.4 升至 8.46（方法: 消融实验分析）。
  - **依赖假设**：搜索 corpus 覆盖关键先前工作，且检索到的结论可复现。
  - **可能失效场景**：paywall 文献、未发表实验和负面结果缺失时，系统会重复已知失败或高估新颖性；论文主动承认这一限制（Discussion）。
- **观察 3：少量专家介入能把大规模想法生成转换成可负担的实验 shortlist。** AML 组合治疗的目标定义少于 1 小时，运行后终选约 3 小时；fibrosis 和 AMR 的设置/final 评审时间相近（方法: Expert-in-the-闭环 interactions）。
  - **依赖假设**：专家能在数小时内识别最值得验证的候选，且这部分 meta-selection 不主导最终成功。
  - **可能失效场景**：没有相同专家筛选 random、单模型或传统 computational biology 候选的对照，无法分离 AI 排序与人类 selection 的收益。
- **假设 1：Gemini 模拟的辩论、评审和成对排序可近似科学共同体的批判过程。**
  - **证据强度**：中。11 个盲评目标中 Co-Scientist 的新颖性/impact 为 3.64/3.09（满分 5），但样本小且评审者就是目标提供者；真正湿实验证据只覆盖少数经过筛选的输出（图 2c）。

## 核心方法

科学家首先以自然语言提交研究目标，可附数万 token 的背景、数百篇 PDF、实验约束和偏好。系统将其解析为研究计划配置，并设置 alignment、plausibility、新颖性、testability、安全等默认评价轴；科学家可在运行中修改目标、提交人工评审，甚至把自己的假设放进 tournament（方法: Architecture and 专家 interactions）。

监督者（Supervisor）智能体管理异步任务队列、工作智能体与测试时算力，周期性将假设数、待评审项、竞赛进展和不同生成策略的效果写入持久上下文。它依据统计量动态抽样生成、反思、排序、进化、邻近性与元评审智能体，而不是按固定顺序各运行一次（图 1b，方法）。

生成（Generation）智能体通过文献检索、模拟科学辩论、假设分解和研究扩展产生候选。反思（Reflection）智能体依次进行无工具初评、带检索的完整评审、假设分解后的深度验证，以及观察、模拟和循环评审，过滤事实错误和伪新颖性。这个结构直接回应观察 2：提案先生成，再以外部证据反驳（方法：Generation/Reflection）。

Ranking 智能体用 pairwise 科学辩论建立 Elo tournament；Proximity 智能体聚类、去重并维持搜索-space diversity；Evolution 智能体合并高分想法、做类比、补文献、探索 unconventional path；Meta-评审将 recurring critique 汇总后附加到下一轮智能体提示词。这里的「学习」不更新模型权重，而是以 context 反馈改变后续生成与评价（方法: Specialized 智能体）。

最终 Meta-评审生成研究 overview，科学家检查 top-ranked 提案并选择实验。与 [[AI-Scientist-v2-arXiv25]] 的稿件流水线、[[AutoScientists-arXiv26]] 的共享实验状态、[[DeepScientist-ICLR26]] 的代码/评估器闭环相比，Co-Scientist 的系统边界止于假设/协议；湿实验结果不会自动回流并触发下一轮实验（Discussion）。

## 设计取舍

- **test-time 搜索 vs 计算效率**：持续 tournament 能探索和精炼，但论文未披露每个目标的 token、实际时间、dollar 或 energy 成本；o3-mini-high、DeepSeek-R1 用更少算力已表现 competitive。
- **Elo 相对排序 vs 客观科学评分**：成对排序为开放假设提供稠密信号，却可能产生循环偏好、position bias 和 self-评审器奖励投机；辩论提示词只缓解其中部分问题。
- **专家参与闭环 vs autonomy**：人类定义目标、约束、终选并执行实验，提高安全性和转化价值；代价是成功不能归因于 autonomous 系统 alone。
- **开放文献依据锚定 vs 证据 completeness**：web 搜索提高新颖性/正确性，但系统依赖 open-access 文献，缺失 paywall 与负面结果。
- **专有基础设施 vs 复现性**：论文公开 pseudocode 和 prompts，但完整代码、算力配置和三类真实世界验证数据不公开，第三方无法复跑 tournament 或选择流程。

## 实验与结果

- 测试时规模扩展：203 个跨领域但以 biomedicine 为主的研究目标分为 10 个 temporal bucket，best 与 top-10 average Elo 均随时间上升；15 个由 7 位 biomedical 专家提供的目标上，后期 Elo 超过专家 best guess、Gemini 2.0、OpenAI o1/o3-mini-high、DeepSeek R1，但评价仍使用 Co-Scientist Elo（图 2a–b）。
- 专家盲评：11 个目标上，Co-Scientist 平均 preference rank 2.36，新颖性 3.64/5、impact 3.09/5，优于三个单模型基线；论文明确称这是 subjective preference，不是真值（图 2c）。
- 智能体消融实验：相比对应的 no-搜索/no-evolution/no-meta-评审基线，Gemini 2.0 Flash 模型的 Reflection 加搜索后 published 想法新颖性由 6.14 降至 2.38/10、正确性准确率分数由 7.4 升至 8.46/10；Evolution 将 GPQA precision 从 70.9% 提至 75.4%，假设质量从 4.7 提至 5.6；Meta-评审在 constructed 数据集的正确性 AUC 从 0.521 提至 0.597（方法: 消融实验分析）。
- AML initial repurposing：在 2,300 个 approved drug × 34 cancer type 空间生成候选；oncologist 从 top 30 中选 5 个实验，binimetinib、pacritinib、cerivastatin 中的 3 个抑制 MOLM-13 viability，另 2 个效果有限（Real-world 验证，图 3a–c，Extended Data 图 4）。
- AML 较少中途监督的单药探索：系统在无 DepMap 和无生成阶段专家反馈下排序，专家从 top 3 选择 nanvuranlat、KIRA6、leflunomide；只有 KIRA6 显示广泛活性，KG-1a/TK6 IC50 为 10/180 nM，形成 18× 体外 window，而另外两种在 MOLM-13 效果有限（图 3d–h，Extended Data 图 4）。
- AML 组合：实验 7 个组合、2 个 cell line、每项 n=3 生物学 replicates；MOLM-13 多数 dual/triple 组合协同，KG-1a 则混合 synergy/antagonism，表明效果强依赖 subtype（图 4，Extended Data 图 5–6、表 2）。
- Liver fibrosis：专家选 3 个 top-ranked epigenetic target/drug，2 个在人类 hepatic organoid 中显示显著 anti-fibrotic activity 且无 cellular toxicity；其中 vorinostat 已获 FDA 批准用于另一癌症（表 1，Real-world 验证）。
- AMR：只给 minimal background 后，系统在 2 天内提出 cf-PICI 通过 diverse phage tails 扩大 host range，复现一个当时尚未完成 同行评审、随后共同定时发表并经 genomic/湿实验验证的独立团队发现（表 1，Real-world 验证）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| tournament/精炼随测试时算力增加而提高假设 Elo | 图 2a–b | 203 个目标的内部 Elo；15 个专家目标；无等算力的独立搜索基线 | 中 |
| 专用智能体与工具确有可测的边际贡献 | 方法的消融分析，补充图 2–6 | 已发表想法集、GPQA 和构造集；多数依赖自动评估 | 中 |
| 系统能提出在湿实验中有效的 AML 候选 | 图 3–4，扩展数据图 3–6 | 专家终选；5 个细胞系、n=3；测细胞活性与协同作用，不含动物或临床结果 | 强 |
| 系统在三类生物医学问题中产生可验证价值 | 表 1，图 3–4 | AML 为本文实验；纤维化和 AMR 与独立配套研究紧密耦合；均有专家参与 | 中 |
| 专家偏好 Co-Scientist 胜过单模型基线 | 图 2c | 11 个目标，目标提供者盲评；新颖性 3.64/5、影响力 3.09/5 | 中 |

## 批判性分析

### 论证链条

论文的 strongest link 不是 Elo，而是提案经专家筛选后进入真实实验，并同时报告若干负面 candidates。KIRA6 的 subtype-dependent dose response、7 个组合在两种 cell line 上的不同 interaction profile，说明系统产出不只是读起来合理。Reflection-搜索消融实验又把「开放文献检索为何必要」落成了定量证据。

但「生成可实验候选」到「accelerating 发现」之间仍有人类 meta-selection。所有三类验证都由专家提供问题、约束、候选终选和实验；AML initial 路线更使用 preclinical mechanism 作为筛选标准。最 autonomous 的 AML 单药生成也由专家从 top 3 选样，且 3 个中只有 KIRA6 成功。系统没有控制 robot、执行实验、解释结果再自主迭代，不能与 fully autonomous closed 闭环等同。

### 假设压力测试

测试时规模扩展的 x 轴是同一系统运行进程，y 轴是同一 tournament 生成的 Elo。若评审器更偏好长、结构化或符合其自身先验的输出，持续 evolution 会单调提升 Elo 而不提升湿实验命中率。论文未展示 early-vs-late bucket 的等量 prospective 实验，因而没有证明 Elo 规模扩展转化为 empirical 发现规模扩展。

Co-Scientist 依赖文献检索来识别新颖性，然而 source 文献系统性缺失负面结果。某条在论文 graph 中「新颖」的路径可能早已在多个实验室失败。系统也能搜索科学家提供的 private 仓库，但这会让不同实验室运行不可比，并可能把内部未发表知识重组后误称 AI 发现。

### 实验可信度

AML dose-response 有 5 个 cell line、生物学 triplicate、IC50 与 95% CI，并报告无效候选，作为初步生物学 reality check 是可信的。它仍只测 cell viability；没有动物模型、patient-derived 样本、pharmacokinetics、off-target toxicity 或临床 endpoint。作者也明确否认体外 activity 等于临床成功。

Fibrosis 的 3→2 命中和 AMR 的 2-day recapitulation 很吸引人，但细节主要在配套论文/补充材料，当前主文未给出与 random、文献专家或单模型在同候选预算下的 prospective hit-rate。AMR 更接近对研究团队已知但未发表结果的 blind rediscovery，证明信息综合能力，不等于首次发现。

### 系统性缺陷

完整源码不公开，且作者称依赖 proprietary 基础设施和 massive test-time 算力；仅 prompts/pseudocode 不足以复现异步调度、Elo tournament、搜索结果和 exact 模型快照。三类真实世界验证数据也明确排除在公开数据范围之外。论文没有报告每个目标的 token、GPU 小时、费用、失败恢复或总候选量，无法计算成本 per validated hit。

系统允许网页/私有语料/专家文本进入长 context，论文未讨论科学提示词注入、恶意论文、数据许可、患者隐私或检索来源追踪的系统防护。作者提出未来加强图表/数据级来源追踪，反向说明当前引用依据锚定尚未达到论断级 audit。

## 局限与后续工作

- **局限 1**：三类主结果全部是专家参与闭环；系统没有自主执行实验或基于湿实验反馈闭环更新。
- **局限 2**：Elo 规模扩展是 self-评测，缺少等算力基线和 early/late 假设的 prospective 湿实验 hit-rate 对照。
- **局限 3**：湿实验规模小且高度筛选；AML 主要是 cell line viability，不能外推到动物、患者或临床疗效。
- **局限 4**：完整代码、真实验证数据、每目标算力/成本与 failed 假设档案库不公开，复现和 selection-bias 审计受限。
- **局限 5**：开放文献缺 paywall 和负面结果，可能同时高估新颖性、低估已知失败风险。
- **后续工作 1**：冻结 100 个前 k 名与随机候选/单模型/仅专家候选，盲法做等预算实验检测，直接测命中率、新颖性和成本 per hit。
- **后续工作 2**：对 early/late temporal bucket 各抽等量候选做湿实验，检验 Elo 增长是否预测 empirical 成功。
- **后续工作 3**：公开去敏的完整假设 funnel，包括被专家拒绝和实验失败项，并报告 selection criteria 与 inter-rater agreement。
- **后续工作 4**：给每个论断建 source 图表/数据来源追踪，并纳入 retraction、contradiction 与负面-结果仓库。
- **后续工作 5**：在 robot lab 上实现提案→实验→结果 parsing→revision 的受控闭环，同时保留人类 approval gate 和完整 intervention log。

## 相关

- **相关概念**：[[Auto-Research]]、科学家参与闭环、test-time 算力、tournament 搜索、drug repurposing
- **同类系统**：[[DeepScientist-ICLR26]]、[[AI-Scientist-v2-arXiv25]]、[[AutoScientists-arXiv26]]、[[Kosmos-AI-Scientist-arXiv25]]
- **评测与验证**：[[AstaBench-ICLR26]]、[[MLR-Bench-arXiv25]]、湿实验验证、[[LLM|LLM]]-as-a-评审器
- **同主题**：[[Auto-Research]]
