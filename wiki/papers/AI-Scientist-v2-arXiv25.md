---
type: paper
name: AI-Scientist-v2
full_title: "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search"
authors: [Yutaro Yamada, Robert Tjarko Lange, Cong Lu, Shengran Hu, Chris Lu, Jakob Foerster, Jeff Clune, David Ha]
venue: arXiv
year: 2025
tags: [autoresearch, agent, tree-search, scientific-discovery, vlm]
source_pdf: "[[2504.08066v1.pdf]]"
source_md: "[[2504.08066v1]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (arXiv 2025)

> **一句话总结**：Sakana AI 在 [[AI-Scientist-arXiv24|AI Scientist v1]] 基础上去掉人工 code template、用 experiment-manager 四阶段流水线 + 并行 agentic tree search（受 AIDE / [[MLE-Bench-ICLR25|MLE-Bench]] 启发）+ VLM 图文反馈环跑端到端科研；向 ICLR 2025 ICBINB workshop 盲审投稿 3 篇全 AI 生成论文，仅 1/3 获 6.33/10 均分（前 45%）过线——里程碑意义在「首次全 AI 稿件过 peer review」，但作者自评离 main-track 标准仍远，且人类在 idea 筛选与 best-run 选择上仍有 meta-selection。

## 问题与动机

[[AI-Scientist-arXiv24|AI Scientist v1]]（Lu et al., 2024）首次跑通 idea → code → experiment → manuscript → auto-review 全流程，但有两处结构性瓶颈制约其从 demo 走向 domain-general 部署：

1. **Template 依赖**：每个新 topic 需人工撰写 baseline 代码模板，LLM 只能在其上做 sequential 增量修改，autonomy 和 out-of-the-box 可部署性受限。
2. **线性浅层实验**：hypothesis 沿单链逐步 refine，无回溯、无并行分支，复杂科研问题上的探索深度不足；作者观察到 v1 实验常「短视」（short-sighted）。

v2 的目标是把自主科研系统推进到 **无需人工模板、可跨 ML 子领域部署、能系统性探索 hypothesis 空间** 的级别，并用 **真实 peer review**（而非仅内部 LLM reviewer）验证产出质量。评估设计选择与 ICBINB workshop 主题（negative / unexpected results）对齐，也降低了「必须做出正面 SOTA」的压力——但这同时意味着 milestone 的 claim 边界是 workshop-level，而非 conference-level discovery。

## 关键观察 / 隐含假设

- **观察 1**：ML engineering agent 在 code-as-action-space 上，tree search + scalar/LLM evaluation 比线性 ReAct 式 refine 更能覆盖解空间——证据来自 AIDE 在 [[MLE-Bench-ICLR25|MLE-Bench]] 上的 SOTA scaffold 表现，以及 v1 线性流水线在复杂 agenda 上的浅层行为。
  - **依赖假设**：每个 experiment node 的 metric（accuracy、loss curve、plot 质量）能被 LLM evaluator 可靠排序，且「更好 metric → 更接近好论文」成立。
  - **可能失效场景**：需要深层 domain insight、统计功效分析或因果推断的任务；metric 与 scientific insight 脱钩时（如 accepted paper 的 57% train/test overlap 仍产出「看起来合理」的曲线），tree search 会在错误目标上高效收敛。

- **观察 2**：科研实验天然分阶段（feasibility → tuning → core agenda → ablation），每阶段选 checkpoint 再进入下一阶段，比一次性 open-ended search 更接近人类 lab workflow。
  - **依赖假设**：四阶段划分（Preliminary / Hyperparameter / Research Agenda / Ablation）对多数 ML 实证论文足够；stage 间「LLM 选 best node + replication 统计」能传递有效信息。
  - **可能失效场景**：需要长期在线学习、多轮人机协作或不可分阶段的研究（如大规模分布式训练、需要昂贵仪器的 wet lab）；stage budget 固定（每 stage 12–21 nodes）可能在高维搜索空间过早耗尽。

- **观察 3**：figure 质量是 workshop 可接收性的重要组成——VLM 能在实验期与写作 reflection 期捕获 label/legend/caption 不一致，减少「图好看但讲错故事」的稿件。
  - **依赖假设**：GPT-4o 级 VLM 对科学图表的错误检测覆盖率足够高，且 buggy-node 标记不会过度惩罚「视觉上丑但正确」的结果。
  - **可能失效场景**：复杂多 panel 图、3D 可视化、统计置信区间图；VLM 漏检时系统仍会把有 caption 错误的图写进正文（accepted paper 的 Figure 3 caption 即为例证）。

- **假设 1**：去掉 template 后，LLM 从 grant-proposal 级 idea + Semantic Scholar 文献检索出发，仍能生成 **可执行且领域合理** 的初始实验代码。
  - **证据强度**：**中**——三篇投稿均完成流水线，但 pest detection 需人工下载 Kaggle 数据集并缩减规模；label noise 稿出现 CIFAR-10 (?) 等占位 citation，说明 data / literature grounding 仍脆。

- **假设 2**：「全自主」claim 在 **单次 run 内部** 成立，但 **跨 run 的 idea 筛选与 best-manuscript 选择** 可由人类以 meta-selection 完成而不破坏 milestone 叙事。
  - **证据强度**：**弱（对 fully autonomous 而言）**——作者明确从 ~40 个 AI idea 中人工挑 3 个、每 idea 多 seed 跑完整 pipeline 后再人工选最佳稿；这是合理的 compute 管理，但 1/3 acceptance rate 不能直接外推为系统稳态成功率。

## 核心方法

v2 仍是端到端流水线（Figure 1），相对 v1 的改动集中在 **idea 抽象层、实验搜索结构、感知反馈、写作范式** 四块。

**更开放的 Idea Generation（§3.1）**：不再基于已有 codebase 做增量改动，而是在更高抽象层（类似 grant proposal）brainstorm；循环调用 Semantic Scholar 评估新颖性。回应观察：摆脱 template 对 topic 的隐式约束。与 v1 的 archive-driven mutation 相比，更偏向前置 novelty filter，但仍是 LLM 自评 + 检索，无外部 hard verifier。

**Experiment Progress Manager（§3.2.1）**：四阶段流水线：
1. **Stage 1 Preliminary Investigation**：最小可运行原型，验证 feasibility。
2. **Stage 2 Hyperparameter Tuning**：搜索 learning rate 等，要求 training curve 收敛且 ≥2 个 dataset 跑通。
3. **Stage 3 Research Agenda Execution**：执行核心研究议程直至 compute budget 耗尽；若实验过快结束则提示增加复杂度。
4. **Stage 4 Ablation Studies**：组件消融。

每 stage 结束由 **LLM evaluator** 按 metrics、训练动态、plot 质量选 best node，并启动 **replication nodes**（不同 seed）计算 mean ± std，再 seed 下一阶段。回应观察 2 的分阶段科研结构。

**Parallelized Agentic Tree Search（§3.2.2）**：四阶段均启用并行 best-first tree search，直接借鉴 AIDE（Jiang et al., 2025）的 code-generation-as-action-space。每个 node 含 {experiment script, plan, error trace, runtime, metrics, LLM feedback, plot script, figure paths, VLM feedback, status}。节点类型：
- **Buggy / Non-buggy**：执行失败 vs 成功+VLM 通过；
- **Hyperparameter node**（Stage 2）：记录已测超参避免重复；
- **Ablation node**（Stage 4）；
- **Replication node**：同 parent 不同 seed；
- **Aggregation node**：仅合并 replication 结果出带 error bar 的图。

每轮以概率 \(p=1.0\) 优先选 buggy node 做 debug（max depth 3），否则用 LLM-guided best-first 选 non-buggy node refine；多个子节点 **并行执行**。每 stage 节点配额：Stage 1 为 21，Stage 2–4 各 12；单 node 最长 runtime 1 小时。回应观察 1。

**Dataset Loading（§3.3）**：优先 `datasets.load_dataset` 从 Hugging Face Hub 拉数据——降低 data plumbing 摩擦，但非 HF 数据集需人工介入（pest detection 案例）。

**VLM Reviewer（§3.4）**：GPT-4o 在两处介入：(1) 实验期审查 figure 的 label/legend/误导性可视化，问题则标 buggy；(2) 写作 reflection 期检查 figure–caption–正文引用一致性、重复图。回应观察 3。

**Manuscript Writing**：v1 用 [[Aider]] 增量填 LaTeX；v2 改为 **single-pass 生成 + o1 reasoning model reflection**，配合 VLM 审图。reflection 时注入目标页数与当前 PDF 页数，自动压缩篇幅。

**模型配置（Appendix A）**：代码生成 Claude 3.5 Sonnet (v2)，反馈/VLM/summary 用 GPT-4o；单篇生成耗时数小时至 15 小时（硬上限）。

## 设计取舍

- **取舍 1：LLM evaluator 替代硬 verifier**——为获得与 AIDE 类似的灵活 tree search，用 LLM 判 node 优劣 + VLM 判图，而非 [[FunSearch-Nature24|FunSearch]] / [[AlphaEvolve-arXiv25|AlphaEvolve]] 式确定性 evaluator。收益是 open-ended ML 实验可搜索；代价是 metric gaming、数据泄漏、caption 错误仍可通过（accepted paper 的内部复盘已证实）。
- **取舍 2：四阶段硬编码 vs 完全 open-ended**——收益是模拟真实 lab 节奏、控制搜索预算；代价是 agenda 不适合标准四段式时效率低，且每 stage 12–21 node 上限可能不够做大规模实验。
- **取舍 3：Debug 优先（\(p=1.0\)）**——优先修 buggy node 避免浪费 branch；代价是探索新方向的速度下降，可能困在局部修复循环。
- **取舍 4：去掉 template，换 grant-level idea**——提升跨领域泛化；代价是初始代码质量方差大，Stage 1 21 nodes 的负担加重。
- **边界条件**：在 **HF 可获取的小中型 benchmark + 4-page workshop 格式 + negative-result-friendly 主题** 下系统表现最可辩护；换到需定制数据工程、大规模训练、理论证明或湿实验的领域会显著变脆。

## 实验与结果

- 主评估：ICLR 2025 ICBINB workshop 盲审。3 篇全 AI 生成稿混入 43 篇投稿；审稿人事先知悉可能有 AI 稿但不知具体哪篇。1 篇均分 6.33/10（6/6/7），超过 workshop 接收线、约前 45%；另 2 篇被拒。接收稿按约定 撤稿，不进入 OpenReview 公开记录（IRB H24-02652，与 ICLR 领导层协调）。
- **接收稿科学内容**：compositional regularization——在 LSTM **input embedding** 上加相邻 time step 一致性惩罚，期望提升 compositional generalization；合成算术任务上得到 **negative result**（正则未显著提升，有时伤害性能）。符合 ICBINB「unexpected findings」主题。
- **作者内部质检（同篇）**：发现 citation hallucination、train/test **57% overlap**、regularization 作用位置描述易误解、Figure 3 caption 对 validation loss 解释错误、Figure 5 结论与 attention model 实际优势矛盾。内部评分 workshop 5/10、conference 4/10——与外部 6.33 存在张力。
- **被拒稿 1（label noise → calibration）**：作者内部评 workshop **3/10**、conference 2/10；外部审稿 3/3（clear rejection）。问题包括占位引用 `CIFAR-10 (?)`、claim 缺乏实证支撑。
- **被拒稿 2（pest detection）**：需 **人工下载** Kaggle 数据集并缩减至 1/10；核心发现为低 learning rate 略改善 ERS，但换数据集（EuroSAT/CIFAR-10/MedMNIST）后结论混乱——暴露跨域泛化与 data automation 短板。
- **v1 → v2 能力对比（Table 1）**：codebase drafting 从 topic-specific → domain-general；execution 从 linear → tree-based；新增 parallel experiment、VLM reviewer、首次 human peer review 评估。
- **成本与规模**：单篇 3–15 GPU-hours 量级（取决于问题复杂度）；3 个 idea × 多 seed × 人工选优，总实验成本远高于 v1 的 ~\$15/paper 叙事，但论文未给出精确 dollar 数。
- 开源：[github.com/SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) 及 ICBINB 实验数据。

## Critical Analysis

### 论证链条

作者链条为：**(v1 局限) template + 线性实验 → (v2 设计) tree search + stage manager + VLM → (评估) 1/3 workshop acceptance → (结论) 自主科研 milestone**。前两步有清晰的工程因果；第三步到第四步存在明显跳步：

1. **选择偏差**：从 ~40 个 idea 人工挑 3 个、每 idea 多 seed 后挑最佳稿，评估的是「system + human curator」的上限，而非期望成功率。作者诚实承认目标是「能否至少产出一篇过审」而非 pass rate——但 headline「first AI paper through peer review」易让读者忽略 curation。
2. **venue 层级**：workshop 接收率 60–80% vs main track 20–30%（§5 自述）；ICBINB 鼓励 negative results，与系统「实验跑通即可成稿」的能力.profile 匹配。将 6.33/10 外推为「接近人类科研产出」证据不足。
3. **接收稿质量 paradox**：外部审稿认可 negative result 的清晰性；作者内部却发现数据泄漏与图文错误——说明 **peer review 未覆盖代码级正确性**，而 VLM+LLM 内部质检也未阻止投稿。论证链条在「科学正确性」环节未闭合。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 无 template 可跨 ML 域部署 | 3 个差异较大 topic 均出稿 | 非 HF 数据、需专有仪器、理论证明类研究 |
| Tree search 加深探索 | 相对 v1 的结构改进 | 评估函数误导时更高效地走向错误结论 |
| VLM 提升 figure/写作质量 | 流程描述 + 仍存 caption 错误案例 | 复杂统计图、需领域专家解读的图 |
| Full autonomy | 单 run 内无人工改代码/文字 | Idea 筛选、数据集准备、best-run 选择仍需人 |

**推断（非论文证明）**：若将同一系统以 **无人工 idea 筛选、单 seed、直接投稿** 模式跑 N 次，pass rate 可能远低于 33%，且数据/引用错误率会成为主要失败模态——需类似 [[MLR-Bench-arXiv25|MLR-Bench]] 的大规模 end-to-end 审计才能量化。

### 实验可信度

- **Benchmark 代表性**：三篇均为小规模 empirical ML（合成算术、带噪分类、农业图像），**不含** LLM 训练、系统性能优化、因果推断等 [[Auto-Research]] 前沿关心的 hard task。与 [[MLE-Bench-ICLR25|MLE-Bench]] 75 场 Kaggle 竞赛相比，难度和外部有效性都更窄。
- **Baseline 对比**：未与 [[AI-Scientist-arXiv24|v1]]、AIDE-only、[[OpenHands-ICLR25|OpenHands]] 等 scaffold 在相同 idea 上对照「论文质量 / 实验正确性」——只有 feature table 级 v1/v2 对比。无法分离 tree search、VLM、stage manager 各自的边际贡献。
- **Ablation**：系统级 ablation（关掉 tree search / VLM / stage manager）缺失；接收稿内的 ablation 由系统自动做，但未能阻止错误结论进入投稿。
- **Metric 覆盖**：评估几乎只看 peer review score，未系统度量 **可复现性、数据完整性、引用准确率、统计功效**——而这些恰是内部复盘发现的问题。

### 系统性缺陷

- **可复现性与正确性**：无 automatic train/test split verifier；accepted paper 57% overlap 表明 numpy 存盘 + LLM 写代码链路缺数据治理。论文未讨论 sandbox 隔离强度（cf. v1 中 agent 改 time limit 的先例）。
- **尾延迟 / 成本可预测性**：单 node 1h 上限 × 57 nodes/stage 配额，worst-case 数十 GPU-hours/篇，但失败 run 的成本回收策略未述。
- **故障恢复**：buggy node debug depth 仅 3；无描述分布式实验中断后如何 resume tree。
- **可观测性**：node 级日志开源，但缺统一 dashboard 追踪「为何选此 node / 为何写此 caption」的 provenance chain——不利于审计 AI 科研伦理。
- **运维与部署**：依赖 Claude 3.5 + GPT-4o + o1 多模型 API，论文未讨论成本随 model price 波动的敏感性。
- **兼容性**：HF-only 数据策略限制领域；LaTeX 编译错误处理流程相对 v1 的 [[Aider]] 迭代可能更脆（改为 single-pass）。

## 局限与 Future Work

- **局限 1（论文承认）**：仅 1/3 workshop acceptance，**未达 main-track 稳定质量**；novel high-impact hypothesis、深度 domain justification 仍难。
- **局限 2（论文承认）**：真正「全自主」仍受人类 meta-selection、数据集人工准备（pest case）制约。
- **局限 3（可从实验推出）**：内部质检与外部审稿对同一稿的评价分歧，说明当前 **peer review 不足以验证 AI 生成科学** 的代码级正确性。
- **Future work 1**：在固定 compute budget 下测量 **无人工 idea 筛选的 pass@k workshop acceptance**，并与 v1 / AIDE baseline 对照——可客观量化 tree search 边际价值。
- **Future work 2**：加入 **hard verifier**（自动 data split 检查、统计检验、引用 existence check、[[MLR-Bench-arXiv25|MLR-Bench]] 式 fabrication detector），在 node selection 与投稿前阻断 overlap / hallucination。
- **Future work 3**：扩展 data agent 自动化非 HF 数据源（Kaggle、专有数据库），否则「real-world domain」prompt 只是表面修饰。
- **Future work 4**：系统级 ablation + 公开 dollar cost per accepted paper，回应 [[AI-Scientist-arXiv24|v1]] ~\$15 的成本叙事是否仍成立。

## 相关

- **相关概念**：[[Agentic-Tree-Search]]、[[LLM-as-Judge]]、[[Vision-Language-Model]]、[[Open-Endedness]]、[[Reflexion]]、[[Semantic-Scholar-API]]、Compositional Generalization
- **同类系统**：[[AI-Scientist-arXiv24]]（v1）、[[Kosmos-AI-Scientist-arXiv25]]、[[AutoScientists-arXiv26]]、[[Auto-Research-arXiv25]]、AI-Researcher、Agent Laboratory、agentRxiv、CycleResearcher、AI Co-Scientist
- **相关 scaffold / benchmark**：AIDE、[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、SciCode、BixBench
- **同主题**：[[Auto-Research]]
- **对比**：[[AI-Scientist-arXiv24]]（template+线性 vs template-free+tree）、AIDE（ML engineering vs full manuscript pipeline）
