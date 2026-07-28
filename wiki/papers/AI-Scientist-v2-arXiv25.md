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
last_reviewed: 2026-07-27
---

# AI Scientist v2：用智能体树搜索实现 Workshop 级自动科学发现（arXiv 2025）

> **原题**：The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search

> **一句话总结**：Sakana AI 在 [[AI-Scientist-arXiv24|AI Scientist v1]] 基础上去掉人工代码模板、用实验管理器 四阶段流水线 + 并行 agentic tree 搜索（受 AIDE / [[MLE-Bench-ICLR25|MLE-Bench]] 启发）+ VLM 图文反馈环跑端到端科研；向 ICLR 2025 ICBINB workshop 盲审投稿 3 篇全 AI 生成论文，仅 1/3 获 6.33/10 均分（前 45%）过线——里程碑意义在「首次全 AI 稿件过 同行评审」，但作者自评离 main-track 标准仍远，且人类在想法筛选与 最佳运行选择上仍有 meta-selection。

## 问题与动机

[[AI-Scientist-arXiv24|AI Scientist v1]]（Lu et al., 2024）首次跑通想法 → 代码 → 实验 → 稿件 → 自动评审全流程，但有两处结构性瓶颈制约其从 demo 走向跨领域 部署：

1. **模板依赖**：每个新主题需人工撰写基线代码模板，LLM 只能在其上做 sequential 增量修改，autonomy 和 out-of-the-box 可部署性受限。
2. **线性浅层实验**：假设沿单链逐步 refine，无回溯、无并行分支，复杂科研问题上的探索深度不足；作者观察到 v1 实验常「短视」（short-sighted）。

v2 的目标是把自主科研系统推进到 **无需人工模板、可跨 ML 子领域部署、能系统性探索假设空间** 的级别，并用 **真实 同行评审**（而非仅内部 LLM 评审器）验证产出质量。评估设计选择与 ICBINB workshop 主题（负面 / unexpected 结果）对齐，也降低了「必须做出正面 SOTA」的压力——但这同时意味着 milestone 的论断边界是 workshop-level，而非 conference-level 发现。

## 关键观察 / 隐含假设

- **观察 1**：ML 工程智能体在以代码生成为动作的空间 上，tree 搜索 + scalar/LLM 评测比线性 ReAct 式 refine 更能覆盖解空间——证据来自 AIDE 在 [[MLE-Bench-ICLR25|MLE-Bench]] 上的 SOTA 脚手架表现，以及 v1 线性流水线在复杂 agenda 上的浅层行为。
  - **依赖假设**：每个实验节点的指标（准确率、loss curve、图质量）能被 LLM 评估器可靠排序，且「更好指标 → 更接近好论文」成立。
  - **可能失效场景**：需要深层领域洞见、统计功效分析或因果推断的任务；指标与科学洞见脱钩时（如 accepted 论文的 57% 训练/测试 overlap 仍产出「看起来合理」的曲线），tree 搜索会在错误目标上高效收敛。

- **观察 2**：科研实验天然分阶段（可行性 → tuning → core agenda → 消融实验），每阶段选 checkpoint 再进入下一阶段，比一次性开放式搜索更接近人类 lab 工作流。
  - **依赖假设**：四阶段划分（Preliminary / Hyperparameter / 研究 Agenda / 消融实验）对多数 ML 实证论文足够；阶段间「LLM 选 best 节点 + 复现统计」能传递有效信息。
  - **可能失效场景**：需要长期在线学习、多轮人机协作或不可分阶段的研究（如大规模分布式训练、需要昂贵仪器的 wet lab）；阶段预算固定（每阶段 12–21 nodes）可能在高维搜索空间过早耗尽。

- **观察 3**：图表质量是 workshop 可接收性的重要组成——VLM 能在实验期与写作 reflection 期捕获 label/legend/图注不一致，减少「图好看但讲错故事」的稿件。
  - **依赖假设**：GPT-4o 级 VLM 对科学图表的错误检测覆盖率足够高，且 buggy-节点标记不会过度惩罚「视觉上丑但正确」的结果。
  - **可能失效场景**：复杂多 panel 图、3D 可视化、统计置信区间图；VLM 漏检时系统仍会把有图注错误的图写进正文（accepted 论文的图 3 图注即为例证）。

- **假设 1**：去掉模板后，LLM 从 grant-提案级想法 + Semantic Scholar 文献检索出发，仍能生成 **可执行且领域合理** 的初始实验代码。
  - **证据强度**：**中**——三篇投稿均完成流水线，但 pest detection 需人工下载 Kaggle 数据集并缩减规模；label noise 稿出现 CIFAR-10 (?) 等占位引用，说明数据 / 文献依据锚定仍脆。

- **假设 2**：「全自主」论断在 **单次运行内部** 成立，但 **跨运行的想法筛选与 best-稿件选择** 可由人类以 meta-selection 完成而不破坏 milestone 叙事。
  - **证据强度**：**弱（对 fully autonomous 而言）**——作者明确从 ~40 个 AI 想法中人工挑 3 个、每想法多 seed 跑完整流水线后再人工选最佳稿；这是合理的算力管理，但 1/3 acceptance rate 不能直接外推为系统稳态成功率。

## 核心方法

v2 仍是端到端流水线（图 1），相对 v1 的改动集中在 **想法抽象层、实验搜索结构、感知反馈、写作范式** 四块。

**更开放的想法生成（§3.1）**：不再基于已有代码库做增量改动，而是在更高抽象层（类似基金申请式提案）头脑风暴；循环调用 Semantic Scholar 评估新颖性。回应观察：摆脱模板对主题的隐式约束。与 v1 的档案库驱动 mutation 相比，更偏向前置新颖性过滤器，但仍是 LLM 自评 + 检索，无外部强验证器。

**实验进展 Manager（§3.2.1）**：四阶段流水线：
1. **Stage 1 Preliminary Investigation**：最小可运行原型，验证可行性。
2. **Stage 2 Hyperparameter Tuning**：搜索 learning rate 等，要求训练 curve 收敛且 ≥2 个数据集跑通。
3. **Stage 3 研究 Agenda Execution**：执行核心研究议程直至算力预算耗尽；若实验过快结束则提示增加复杂度。
4. **Stage 4 消融实验 Studies**：组件消融。

每阶段结束由 **LLM 评估器** 按指标、训练动态、图质量选 best 节点，并启动 **复现 nodes**（不同 seed）计算 mean ± std，再 seed 下一阶段。回应观察 2 的分阶段科研结构。

**Parallelized Agentic Tree 搜索（§3.2.2）**：四阶段均启用并行 best-first tree 搜索，直接借鉴 AIDE（Jiang et al., 2025）的代码-生成-as-动作-space。每个节点含 {实验 script, 计划, error 轨迹, 运行时间, 指标, LLM 反馈, 图 script, 图表 paths, VLM 反馈, status}。节点类型：
- **Buggy / Non-buggy**：执行失败 vs 成功+VLM 通过；
- **Hyperparameter 节点**（Stage 2）：记录已测超参避免重复；
- **消融实验节点**（Stage 4）；
- **Replication 节点**：同父节点不同 seed；
- **Aggregation 节点**：仅合并复现结果出带 error bar 的图。

每轮以概率 \(p=1.0\) 优先选 buggy 节点做调试（max depth 3），否则用 LLM-guided best-first 选 non-buggy 节点 refine；多个子节点 **并行执行**。每阶段节点配额：Stage 1 为 21，Stage 2–4 各 12；单节点最长运行时间 1 小时。回应观察 1。

**数据集 Loading（§3.3）**：优先 `datasets.load_dataset` 从 Hugging Face Hub 拉数据——降低数据 plumbing 摩擦，但非 HF 数据集需人工介入（pest detection 案例）。

**VLM 评审器（§3.4）**：GPT-4o 在两处介入：(1) 实验期审查图表的 label/legend/误导性可视化，问题则标 buggy；(2) 写作 reflection 期检查图表–图注–正文引用一致性、重复图。回应观察 3。

**稿件 Writing**：v1 用 [[Aider]] 增量填 LaTeX；v2 改为 **single-pass 生成 + o1 推理模型 reflection**，配合 VLM 审图。reflection 时注入目标页数与当前 PDF 页数，自动压缩篇幅。

**模型配置（附录 A）**：代码生成 Claude 3.5 Sonnet (v2)，反馈/VLM/summary 用 GPT-4o；单篇生成耗时数小时至 15 小时（硬上限）。

## 设计取舍

- **取舍 1：LLM 评估器替代硬验证器**——为获得与 AIDE 类似的灵活 tree 搜索，用 LLM 判节点优劣 + VLM 判图，而非 [[FunSearch-Nature24|FunSearch]] / [[AlphaEvolve-arXiv25|AlphaEvolve]] 式确定性评估器。收益是开放式 ML 实验可搜索；代价是指标 gaming、数据泄漏、图注错误仍可通过（accepted 论文的内部复盘已证实）。
- **取舍 2：四阶段硬编码 vs 完全开放式**——收益是模拟真实 lab 节奏、控制搜索预算；代价是 agenda 不适合标准四段式时效率低，且每阶段 12–21 节点上限可能不够做大规模实验。
- **取舍 3：Debug 优先（\(p=1.0\)）**——优先修 buggy 节点避免浪费 branch；代价是探索新方向的速度下降，可能困在局部修复循环。
- **取舍 4：去掉模板，换 grant-level 想法**——提升跨领域泛化；代价是初始代码质量方差大，Stage 1 21 nodes 的负担加重。
- **边界条件**：在 **HF 可获取的小中型基准 + 4-page workshop 格式 + 负面-结果-friendly 主题** 下系统表现最可辩护；换到需定制数据工程、大规模训练、理论证明或湿实验的领域会显著变脆。

## 实验与结果

- 主评估：ICLR 2025 ICBINB workshop 盲审。3 篇全 AI 生成稿混入 43 篇投稿；审稿人事先知悉可能有 AI 稿但不知具体哪篇。1 篇均分 6.33/10（6/6/7），超过 workshop 接收线、约前 45%；另 2 篇被拒。接收稿按约定撤稿，不进入 OpenReview 公开记录（IRB H24-02652，与 ICLR 领导层协调）。
- **接收稿科学内容**：compositional regularization——在 LSTM **input embedding** 上加相邻 time 步骤一致性惩罚，期望提升 compositional 泛化；合成算术任务上得到 **负面结果**（正则未显著提升，有时伤害性能）。符合 ICBINB「unexpected 发现」主题。
- **作者内部质检（同篇）**：发现引用幻觉、训练/测试 **57% overlap**、regularization 作用位置描述易误解、图 3 图注对验证 loss 解释错误、图 5 结论与 attention 模型实际优势矛盾。内部评分 workshop 5/10、conference 4/10——与外部 6.33 存在张力。
- **被拒稿 1（label noise → calibration）**：作者内部评 workshop **3/10**、conference 2/10；外部审稿 3/3（clear rejection）。问题包括占位引用 `CIFAR-10 (?)`、论断缺乏实证支撑。
- **被拒稿 2（pest detection）**：需 **人工下载** Kaggle 数据集并缩减至 1/10；核心发现为低 learning rate 略改善 ERS，但换数据集（EuroSAT/CIFAR-10/MedMNIST）后结论混乱——暴露跨域泛化与数据 automation 短板。
- **v1 → v2 能力对比（表 1）**：代码库 drafting 从主题专用 → 跨领域；执行从 线性 → 树搜索；新增 parallel 实验、VLM 评审器、首次人类 同行评审评估。
- **成本与规模**：单篇 3–15 GPU-hours 量级（取决于问题复杂度）；3 个想法 × 多 seed × 人工选优，总实验成本远高于 v1 的 ~\$15/论文叙事，但论文未给出精确 dollar 数。
- 开源：[github.com/SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) 及 ICBINB 实验数据。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| v2 首次让一篇全 AI 生成论文通过真实 Workshop 盲审 | §5：三篇投稿中一篇得分 6/6/7，均分 6.33 | ICLR 2025 ICBINB Workshop；投稿后撤回；只评三篇人工选出的稿件 | 强 |
| 外部接收不代表论文不存在严重科学问题 | §5.1：作者复盘发现 57% 训练/测试重叠、引用幻觉和图文矛盾 | 单篇接收稿；内部评分 5/10，与外审存在差异 | 强 |
| 去除人工代码模板扩大了领域覆盖，但没有消除人工选择 | §3–§5：约 40 个想法中人工选 3 个，再从多次运行中选稿 | 单次运行内部自动；跨运行的选题和稿件选择仍由人完成 | 中 |
| 树搜索和 VLM 反馈改善执行结构，但成本明显高于 v1 | §3.2–§3.4：每篇约 3–15 GPU-hours | 未报告完整美元成本；问题复杂度与种子数不同 | 中 |

## 批判性分析

### 论证链条

作者链条为：**(v1 局限) 模板 + 线性实验 → (v2 设计) tree 搜索 + 阶段管理器 + VLM → (评估) 1/3 workshop acceptance → (结论) 自主科研 milestone**。前两步有清晰的工程因果；第三步到第四步存在明显跳步：

1. **选择偏差**：从 ~40 个想法人工挑 3 个、每想法多 seed 后挑最佳稿，评估的是「系统 + 人类 curator」的上限，而非期望成功率。作者诚实承认目标是「能否至少产出一篇过审」而非 pass rate——但 headline「first AI 论文 through 同行评审」易让读者忽略 curation。
2. **venue 层级**：workshop 接收率 60–80% vs main track 20–30%（§5 自述）；ICBINB 鼓励负面结果，与系统「实验跑通即可成稿」的能力.profile 匹配。将 6.33/10 外推为「接近人类科研产出」证据不足。
3. **接收稿质量 paradox**：外部审稿认可负面结果的清晰性；作者内部却发现数据泄漏与图文错误——说明 **同行评审未覆盖代码级正确性**，而 VLM+LLM 内部质检也未阻止投稿。论证链条在「科学正确性」环节未闭合。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 无模板可跨 ML 域部署 | 3 个差异较大主题均出稿 | 非 HF 数据、需专有仪器、理论证明类研究 |
| Tree 搜索加深探索 | 相对 v1 的结构改进 | 评估函数误导时更高效地走向错误结论 |
| VLM 提升图表/写作质量 | 流程描述 + 仍存图注错误案例 | 复杂统计图、需领域专家解读的图 |
| 完全自主 | 单运行内无人工改代码/文字 | 想法筛选、数据集准备、最佳运行选择仍需人 |

**推断（非论文证明）**：若将同一系统以 **无人工想法筛选、单 seed、直接投稿** 模式跑 N 次，pass rate 可能远低于 33%，且数据/引用错误率会成为主要失败模态——需类似 [[MLR-Bench-arXiv25|MLR-Bench]] 的大规模端到端审计才能量化。

### 实验可信度

- **基准代表性**：三篇均为小规模 empirical ML（合成算术、带噪分类、农业图像），**不含** LLM 训练、系统性能优化、因果推断等 [[Auto-Research]] 前沿关心的 hard 任务。与 [[MLE-Bench-ICLR25|MLE-Bench]] 75 场 Kaggle 竞赛相比，难度和外部有效性都更窄。
- **基线对比**：未与 [[AI-Scientist-arXiv24|v1]]、AIDE-only、[[OpenHands-ICLR25|OpenHands]] 等脚手架在相同想法上对照「论文质量 / 实验正确性」——只有 功能表 级 v1/v2 对比。无法分离 tree 搜索、VLM、阶段管理器 各自的边际贡献。
- **消融实验**：系统级消融实验（关掉 tree 搜索 / VLM / 阶段管理器）缺失；接收稿内的消融实验由系统自动做，但未能阻止错误结论进入投稿。
- **指标覆盖**：评估几乎只看 同行评审分数，未系统度量 **可复现性、数据完整性、引用准确率、统计功效**——而这些恰是内部复盘发现的问题。

### 系统性缺陷

- **可复现性与正确性**：无 automatic 训练/测试 split 验证器；accepted 论文 57% overlap 表明 numpy 存盘 + LLM 写代码链路缺数据治理。论文未讨论沙箱隔离强度（cf. v1 中智能体改 时间限制 的先例）。
- **尾延迟 / 成本可预测性**：单节点 1h 上限 × 57 nodes/阶段配额，worst-case 数十 GPU-hours/篇，但失败运行的成本回收策略未述。
- **故障恢复**：buggy 节点调试 depth 仅 3；无描述分布式实验中断后如何 resume tree。
- **可观测性**：节点级日志开源，但缺统一仪表盘追踪「为何选此节点 / 为何写此图注」的来源追踪 chain——不利于审计 AI 科研伦理。
- **运维与部署**：依赖 Claude 3.5 + GPT-4o + o1 多模型 API，论文未讨论成本随模型 price 波动的敏感性。
- **兼容性**：HF-only 数据策略限制领域；LaTeX 编译错误处理流程相对 v1 的 [[Aider]] 迭代可能更脆（改为 single-pass）。

## 局限与后续工作

- **局限 1（论文承认）**：仅 1/3 workshop acceptance，**未达 main-track 稳定质量**；novel high-impact 假设、深度领域 justification 仍难。
- **局限 2（论文承认）**：真正「全自主」仍受人类 meta-selection、数据集人工准备（pest case）制约。
- **局限 3（可从实验推出）**：内部质检与外部审稿对同一稿的评价分歧，说明当前 **同行评审不足以验证 AI 生成科学** 的代码级正确性。
- **后续工作 1**：在固定算力预算下测量 **无人工想法筛选的 pass@k workshop acceptance**，并与 v1 / AIDE 基线对照——可客观量化 tree 搜索边际价值。
- **后续工作 2**：加入 **强验证器**（自动数据划分检查、统计检验、引用 存在性检查、[[MLR-Bench-arXiv25|MLR-Bench]] 式编造 检测器），在节点 selection 与投稿前阻断 overlap / 幻觉。
- **后续工作 3**：扩展数据智能体自动化非 HF 数据源（Kaggle、专有数据库），否则「真实世界领域」提示词只是表面修饰。
- **后续工作 4**：系统级消融实验 + 公开 dollar 成本 per accepted 论文，回应 [[AI-Scientist-arXiv24|v1]] ~\$15 的成本叙事是否仍成立。

## 相关

- **相关概念**：[[Agentic-Tree-Search]]、[[LLM-as-Judge]]、[[Vision-Language-Model]]、[[Open-Endedness]]、[[Reflexion]]、[[Semantic-Scholar-API]]、Compositional Generalization
- **同类系统**：[[AI-Scientist-arXiv24]]（v1）、[[Kosmos-AI-Scientist-arXiv25]]、[[AutoScientists-arXiv26]]、[[Auto-Research-arXiv25]]、AI-Researcher、智能体 Laboratory、agentRxiv、CycleResearcher、AI Co-Scientist
- **相关脚手架 / 基准**：AIDE、[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、SciCode、BixBench
- **同主题**：[[Auto-Research]]
- **对比**：[[AI-Scientist-arXiv24]]（模板+线性 vs 模板-free+tree）、AIDE（ML 工程 vs full 稿件流水线）
