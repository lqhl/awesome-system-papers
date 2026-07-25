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
last_reviewed: 2026-07-23
---

# Accelerating scientific discovery with Co-Scientist (Nature 2026)

> **一句话总结**：Co-Scientist 用 Gemini 多 agent 的 Generation–Reflection–Ranking–Evolution tournament 随 test-time compute 持续改进假设，并在 203 个目标上呈 Elo 上升；其真正强证据来自 expert-in-the-loop 的三类 biomedical validation——AML 中 KIRA6 对 KG-1a/TK6 的 IC50 为 10/180 nM、肝纤维化 3 个候选中 2 个在 organoid 有效、AMR 机制在 2 天内被复现——但系统没有自主执行实验，代码及三类验证数据也未公开（Fig. 1–4，Table 1，Methods）。

## 问题与动机

科研人员面对「深度与广度」矛盾：单一领域的文献和技术已难以穷尽，重要假设却常来自跨领域连接。普通 deep-research 工具能总结文献，却不负责形成可测试的新假设、比较候选和规划实验。Co-Scientist 的目标因此不是自动写论文，而是充当结构化 scientific thinking engine：科学家定义问题和约束，系统大规模生成、批判、比较和演化假设，再由科学家选择进入实验（Introduction，Fig. 1）。

这一区分很关键。与 [[DeepScientist-ICLR26]] 自己写代码、执行 benchmark 实验的 software discovery loop 不同，Co-Scientist 只自动化 in-silico ideation 和 proposal refinement；wet-lab、候选终选与临床判断仍由人类完成。论文明确将其称为 scientist-in-the-loop，而非 fully autonomous scientist（Fig. 1，Methods: Expert-in-the-loop interactions）。

## 关键观察 / 隐含假设

- **观察 1：同一研究目标下，持续 tournament/refinement 的 auto-evaluated Elo 随计算时间上升。** 203 个研究目标的输出按生成时间切成十个等量 bucket，top-10 平均 Elo 和 best Elo 均持续提高；15 个专家目标上后期 Co-Scientist Elo 超过专家 best guess 和同期 frontier models，未见饱和（System analysis，Fig. 2a–b）。
  - **依赖假设**：由同一系统内部 pairwise debate 形成的 Elo 与真实 scientific quality 单调相关。
  - **可能失效场景**：ranking agent 和 generation agent 共享模型偏好时，更多 compute 可能只是更好地优化 judge style，而非提高可验证性；Fig. 2 没有将额外 compute 随机分配给独立 baseline。
- **观察 2：外部检索是 novelty/correctness gate，而非可选增强。** Reflection agent 无 search 时把已发表 idea 的 novelty 评为 6.14/10，加入 search 后降至 2.38；known-correct idea 的 correctness 从 7.4 升至 8.46（Methods: Ablation analysis）。
  - **依赖假设**：搜索 corpus 覆盖关键先前工作，且检索到的结论可复现。
  - **可能失效场景**：paywall 文献、未发表实验和 negative results 缺失时，系统会重复已知失败或高估 novelty；论文主动承认这一限制（Discussion）。
- **观察 3：少量专家介入能把大规模 ideation 转换成可负担的实验 shortlist。** AML 组合治疗的目标定义少于 1 小时，run 后终选约 3 小时；fibrosis 和 AMR 的 setup/final review 时间相近（Methods: Expert-in-the-loop interactions）。
  - **依赖假设**：专家能在数小时内识别最值得验证的候选，且这部分 meta-selection 不主导最终成功。
  - **可能失效场景**：没有相同专家筛选 random、单模型或传统 computational biology 候选的对照，无法分离 AI ranking 与人类 selection 的收益。
- **假设 1：Gemini 模拟的 debate、review 和 pairwise ranking 可近似科学共同体的批判过程。**
  - **证据强度**：中。11 个盲评目标中 Co-Scientist 的 novelty/impact 为 3.64/3.09（满分 5），但样本小且评审者就是目标提供者；真正 wet-lab 证据只覆盖少数经过筛选的输出（Fig. 2c）。

## 核心方法

科学家首先以自然语言提交 research goal，可附数万 token 的背景、数百篇 PDF、实验约束和偏好。系统将其解析为 research plan configuration，并设置 alignment、plausibility、novelty、testability、safety 等默认评价轴；科学家可在运行中修改目标、提交人工 review，甚至把自己的 hypothesis 放进 tournament（Methods: Architecture and expert interactions）。

Supervisor agent 管理异步任务队列、worker 与 test-time compute，周期性将 hypothesis 数、待 review 项、tournament 进展和不同 generation strategy 的效果写入 persistent context memory。它依据统计量动态抽样 Generation、Reflection、Ranking、Evolution、Proximity、Meta-review agent，而不是固定顺序运行一次（Fig. 1b，Methods）。

Generation agent 通过 literature search、模拟科学辩论、假设分解和 research expansion 产生候选。Reflection agent 依次进行无工具 initial review、带检索 full review、assumption decomposition 的 deep verification、observation/simulation/recurrent review，过滤事实错误和伪 novelty。这个结构直接回应观察 2：proposal 先生成，再以外部证据反驳（Methods: Generation/Reflection）。

Ranking agent 用 pairwise scientific debate 建立 Elo tournament；Proximity agent 聚类、去重并维持 search-space diversity；Evolution agent合并高分 idea、做类比、补文献、探索 unconventional path；Meta-review 将 recurring critique 汇总后附加到下一轮 agent prompt。这里的「学习」不更新模型权重，而是以 context feedback 改变后续生成与评价（Methods: Specialized agents）。

最终 Meta-review 生成 research overview，科学家检查 top-ranked proposal 并选择实验。与 [[AI-Scientist-v2-arXiv25]] 的 manuscript pipeline、[[AutoScientists-arXiv26]] 的共享实验状态、[[DeepScientist-ICLR26]] 的 code/evaluator loop 相比，Co-Scientist 的系统边界止于 hypothesis/protocol；wet-lab 结果不会自动回流并触发下一轮实验（Discussion）。

## 设计取舍

- **test-time search vs 计算效率**：持续 tournament 能探索和 refinement，但论文未披露每个目标的 token、wall-clock、dollar 或 energy cost；o3-mini-high、DeepSeek-R1 用更少 compute 已表现 competitive。
- **Elo 相对排序 vs 客观科学评分**：pairwise ranking 为开放假设提供 dense signal，却可能产生循环偏好、position bias 和 self-judge reward hacking；debate prompt 只缓解其中部分问题。
- **expert-in-the-loop vs autonomy**：人类定义目标、约束、终选并执行实验，提高安全性和转化价值；代价是成功不能归因于 autonomous system alone。
- **开放文献 grounding vs evidence completeness**：web search 提高 novelty/correctness，但系统依赖 open-access 文献，缺失 paywall 与 negative results。
- **专有基础设施 vs 复现性**：论文公开 pseudocode 和 prompts，但完整代码、compute 配置和三类 real-world validation 数据不公开，第三方无法复跑 tournament 或选择流程。

## 实验与结果

- test-time scaling：203 个跨领域但以 biomedicine 为主的 research goal 分为 10 个 temporal bucket，best 与 top-10 average Elo 均随时间上升；15 个由 7 位 biomedical expert 提供的目标上，后期 Elo 超过 expert best guess、Gemini 2.0、OpenAI o1/o3-mini-high、DeepSeek R1，但评价仍使用 Co-Scientist Elo（Fig. 2a–b）。
- 专家盲评：11 个目标上，Co-Scientist 平均 preference rank 2.36，novelty 3.64/5、impact 3.09/5，优于三个单模型 baseline；论文明确称这是 subjective preference，不是 ground truth（Fig. 2c）。
- agent ablation：相比对应的 no-search/no-evolution/no-meta-review baseline，Gemini 2.0 Flash model 的 Reflection 加 search 后 published idea novelty 由 6.14 降至 2.38/10、correctness accuracy score 由 7.4 升至 8.46/10；Evolution 将 GPQA precision 从 70.9% 提至 75.4%，hypothesis quality 从 4.7 提至 5.6；Meta-review 在 constructed dataset 的 correctness AUC 从 0.521 提至 0.597（Methods: Ablation analysis）。
- AML initial repurposing：在 2,300 个 approved drug × 34 cancer type 空间生成候选；oncologist 从 top 30 中选 5 个实验，binimetinib、pacritinib、cerivastatin 中的 3 个抑制 MOLM-13 viability，另 2 个效果有限（Real-world validation，Fig. 3a–c，Extended Data Fig. 4）。
- AML 较少中途监督的单药探索：系统在无 DepMap 和无生成阶段专家反馈下排序，专家从 top 3 选择 nanvuranlat、KIRA6、leflunomide；只有 KIRA6 显示广泛活性，KG-1a/TK6 IC50 为 10/180 nM，形成 18× in-vitro window，而另外两种在 MOLM-13 效果有限（Fig. 3d–h，Extended Data Fig. 4）。
- AML combination：实验 7 个组合、2 个 cell line、每项 n=3 biological replicates；MOLM-13 多数 dual/triple combination 协同，KG-1a 则混合 synergy/antagonism，表明效果强依赖 subtype（Fig. 4，Extended Data Fig. 5–6、Table 2）。
- Liver fibrosis：专家选 3 个 top-ranked epigenetic target/drug，2 个在 human hepatic organoid 中显示显著 anti-fibrotic activity 且无 cellular toxicity；其中 vorinostat 已获 FDA 批准用于另一癌症（Table 1，Real-world validation）。
- AMR：只给 minimal background 后，系统在 2 天内提出 cf-PICI 通过 diverse phage tails 扩大 host range，复现一个当时尚未完成 peer review、随后共同定时发表并经 genomic/wet-lab 验证的独立团队发现（Table 1，Real-world validation）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| tournament/refinement 随 test-time compute 提高 hypothesis Elo | Fig. 2a–b | 203 goals 的内部 Elo；15 expert goals；无等 compute 独立 search baseline | medium |
| specialized agent 与工具确有可测边际贡献 | Methods: Ablation analysis，Supplementary Fig. 2–6 | published-idea set、GPQA、constructed set；多为 auto-evaluation | medium |
| 系统能提出具有 wet-lab 活性的 AML 候选 | Fig. 3–4，Extended Data Fig. 3–6 | 专家终选；5 cell line、n=3；cell viability/synergy，不含动物或临床结果 | strong |
| 系统在三个 biomedical 类型中产生可验证价值 | Table 1，Fig. 3–4 | AML 为本文实验；fibrosis/AMR 与独立配套研究紧密耦合；全为 expert-in-loop | medium |
| Co-Scientist 优于单模型 baseline 的专家偏好 | Fig. 2c | 11 goals，目标提供专家盲评，novelty 3.64/5、impact 3.09/5 | medium |

## Critical Analysis

### 论证链条

论文的 strongest link 不是 Elo，而是 proposal 经专家筛选后进入真实实验，并同时报告若干 negative candidates。KIRA6 的 subtype-dependent dose response、7 个组合在两种 cell line 上的不同 interaction profile，说明系统产出不只是读起来合理。Reflection-search ablation 又把「开放文献检索为何必要」落成了定量证据。

但「生成可实验候选」到「accelerating discovery」之间仍有人类 meta-selection。所有三类 validation 都由专家提供问题、约束、候选终选和实验；AML initial 路线更使用 preclinical mechanism 作为筛选标准。最 autonomous 的 AML 单药生成也由专家从 top 3 选样，且 3 个中只有 KIRA6 成功。系统没有控制 robot、执行实验、解释结果再自主迭代，不能与 fully autonomous closed loop 等同。

### 假设压力测试

test-time scaling 的 x 轴是同一系统运行进程，y 轴是同一 tournament 生成的 Elo。若 judge 更偏好长、结构化或符合其自身先验的输出，持续 evolution 会单调提升 Elo 而不提升 wet-lab hit rate。论文未展示 early-vs-late bucket 的等量 prospective experiment，因而没有证明 Elo scaling 转化为 empirical discovery scaling。

Co-Scientist 依赖 literature search 来识别 novelty，然而 source literature 系统性缺失 negative result。某条在 paper graph 中「新颖」的路径可能早已在多个实验室失败。系统也能搜索 scientist 提供的 private repository，但这会让不同实验室运行不可比，并可能把内部未发表知识重组后误称 AI discovery。

### 实验可信度

AML dose-response 有 5 个 cell line、biological triplicate、IC50 与 95% CI，并报告无效候选，作为 preliminary biological reality check 是可信的。它仍只测 cell viability；没有 animal model、patient-derived sample、pharmacokinetics、off-target toxicity 或临床 endpoint。作者也明确否认 in-vitro activity 等于 clinical success。

Fibrosis 的 3→2 命中和 AMR 的 2-day recapitulation 很吸引人，但细节主要在配套论文/补充材料，当前主文未给出与 random、literature expert 或单模型在同候选预算下的 prospective hit-rate。AMR 更接近对研究团队已知但未发表结果的 blind rediscovery，证明信息综合能力，不等于首次发现。

### 系统性缺陷

完整源码不公开，且作者称依赖 proprietary infrastructure 和 massive test-time compute；仅 prompts/pseudocode 不足以复现异步调度、Elo tournament、搜索结果和 exact model snapshot。三类 real-world validation 数据也明确排除在公开数据范围之外。论文没有报告每个目标的 token、GPU-hour、费用、失败恢复或总候选量，无法计算 cost per validated hit。

系统允许 web/private corpus/专家文本进入长 context，论文未讨论 scientific prompt injection、恶意论文、数据许可、患者隐私或检索 provenance 的系统防护。作者提出未来加强 figure/data-level provenance，反向说明当前 citation grounding 尚未达到 claim-level audit。

## 局限与 Future Work

- **局限 1**：三类主结果全部是 expert-in-the-loop；系统没有自主执行实验或基于 wet-lab feedback 闭环更新。
- **局限 2**：Elo scaling 是 self-evaluation，缺少等 compute baseline 和 early/late hypothesis 的 prospective wet-lab hit-rate 对照。
- **局限 3**：wet-lab 规模小且高度筛选；AML 主要是 cell line viability，不能外推到动物、患者或临床疗效。
- **局限 4**：完整代码、真实验证数据、每目标 compute/cost 与 failed hypothesis archive 不公开，复现和 selection-bias 审计受限。
- **局限 5**：开放文献缺 paywall 和 negative results，可能同时高估 novelty、低估已知失败风险。
- **Future work 1**：冻结 100 个 top-k 与 random/single-model/expert-only 候选，盲法做等预算 assay，直接测 hit rate、novelty 和 cost per hit。
- **Future work 2**：对 early/late temporal bucket 各抽等量候选做 wet-lab，检验 Elo 增长是否预测 empirical success。
- **Future work 3**：公开去敏的完整 hypothesis funnel，包括被专家拒绝和实验失败项，并报告 selection criteria 与 inter-rater agreement。
- **Future work 4**：给每个 claim 建 source figure/data provenance，并纳入 retraction、contradiction 与 negative-result repository。
- **Future work 5**：在 robot lab 上实现 proposal→experiment→result parsing→revision 的受控闭环，同时保留人类 approval gate 和完整 intervention log。

## 相关

- **相关概念**：[[Auto-Research]]、scientist-in-the-loop、test-time compute、tournament search、drug repurposing
- **同类系统**：[[DeepScientist-ICLR26]]、[[AI-Scientist-v2-arXiv25]]、[[AutoScientists-arXiv26]]、[[Kosmos-AI-Scientist-arXiv25]]
- **评测与验证**：[[AstaBench-ICLR26]]、[[MLR-Bench-arXiv25]]、wet-lab validation、[[LLM|LLM]]-as-a-judge
- **同主题**：[[Auto-Research]]
