---
type: paper
name: MLAgentBench
full_title: "MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation"
authors: [Qian Huang, Jian Vora, Percy Liang, Jure Leskovec]
venue: ICML
year: 2024
tags: [auto-research, agent, benchmark, ml-experimentation, react, domain/auto-research, concern/long-horizon]
source_pdf: "[[2310.03302v2.pdf]]"
source_md: "[[2310.03302v2]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-27
---

# MLAgentBench：评测语言智能体开展机器学习实验的能力（ICML 2024）

> **原题**：MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation

> **一句话总结**：首个端到端评估 LLM 智能体做 ML 实验的基准（13 任务、file-系统 + 代码执行环境）；在「相对基线提升 ≥10%」指标下，Claude v3 Opus + 研究 Plan/Fact Check 的 [[ReAct]]-style 智能体平均成功率 37.5%，但任务越新越难（house-price 100% vs BabyLM 0%），且除 Claude v3 Opus 外步数越多性能往往越差——长程规划与幻觉是核心瓶颈。

## 问题与动机

机器学习进展很大程度上依赖**实验迭代**：给定任务，研究者选方法、写代码、跑实验、读指标、再改——需要领域先验、可执行代码和结果诊断能力。传统 [[AutoML]] / NAS 把搜索空间锁在超参和架构，无法覆盖「读数据说明 → 改训练脚本 → 诊断失败 → 换特征工程」这类开放式实验流程。

LLM 在代码生成和推理上的进步，引出核心问题：**语言模型驱动的智能体能否自主完成 ML 实验？** 已有 [[AutoGPT]]、[[ReAct]]、[[Reflexion]] 等多在通用任务或短程交互上被讨论；[[AgentBench]]、WebArena 等基准也不涉及真实 ML 研究管线。作者论断这是第一个系统评估「ML experimentation 智能体」的基准，并附带一个可复现的 prompting 智能体作为强基线。

论文把问题刻意收窄到**可 containment、可自动评分、单次实验成本在分钟级**的任务——不是生产环境 ML 流水线，而是「研究员在 laptop 上迭代一个小实验」的抽象。

## 关键观察 / 隐含假设

- **观察 1**：ML 实验可被抽象为 file-系统 workspace 上的「读/写/执行 Python」循环，配合固定评估器即可自动判分。
  - **依赖假设**：任务能在单机、数分钟内跑完；最终产物可压缩为 `submission.csv` 或 checkpoint；指标与真实研究目标足够对齐。
  - **可能失效场景**：需要多机训练、TB 级数据、复杂 feature store 或人工标注的工业任务；评估器无法捕捉「方法新颖性」时，高分不等于好研究。

- **观察 2**：任务**年代/知名度**与智能体成功率强相关——经典 Kaggle（house-price 100%）远高于 2022–2023 新 Kaggle 与 BabyLM（多处 0%）。
  - **依赖假设**：LM 的预训练/对齐知识对「老数据集 + 常见 trick」有实质帮助；用任务发布时间作污染代理指标是合理诊断手段。
  - **可能失效场景**：老任务成功可能来自 memorized 流水线而非真推理；新任务 0% 也可能因 starter 代码差、评估器严、或 50 步上限不够，而不全是 OOD。

- **观察 3**：智能体常见失败不是「不会写代码」，而是**没跑实验就声称提升**（幻觉）、早期坏规划难以恢复、以及 submission 格式错误——CIFAR-10 轨迹分析里 Bad Plan / Hallucination / Format Error 占主导。
  - **依赖假设**：显式 **研究 Plan and Status** + **Fact Check** 槽位能把「已验证事实」和「猜测」分开，从而减幻觉。
  - **可能失效场景**：Fact Check 仍是 LM 自说自话，没有外部验证器；GPT-4 比 Claude v3 Opus 更易幻觉，说明格式约束 alone 不够。

- **假设 1**：「相对 starter 基线提升 ≥10%」足以定义 **成功**，且 8 次 trial 的成功率可比较不同 LM。
  - **证据强度**：**中**——定义清晰、可复现，但 10% 阈值任意；部分任务基线实为随机预测（imdb 等），「提升」语义不一致；小改进（<10%）被算作失败，可能低估智能体能力。

- **假设 2**：提示词里只保留**最近 3 步** $(r,a,o)$ 历史，配合每步更新的 Plan，足以支撑长达 50 步的实验。
  - **证据强度**：**弱**——图 3 显示除 Claude v3 Opus 外，步数增加往往使指标退化；说明短窗口记忆对多数模型不够，长程 credit assignment 未解决。

## 核心方法

**基准框架（§2）**：每个任务 = 任务描述（目标 + 提交格式 + 可选约束）+ starter files（数据、说明、基线 `train.py`）+ 评估器（对最终 workspace 打分）。环境是任务-agnostic 的：状态 $s_t$ 为工作目录文件集合；智能体循环 Act → Execute → Update 记忆，直到 `Final Answer` 或触及上限（默认最多 50 actions / 5 小时；GPT-4 因成本限 30 actions）。

**动作集（表 1）**：
- **Primitive**：List/Read/Write/Append/Copy/Inspect Script Lines/Undo Edit/Execute Script/Final Answer
- **Compound**（含独立 LM call）：**Understand File**（按 query 摘要代码）、**Edit Script** / **Edit Script Segment**（按自然语言指令改代码并写回）

compound 动作把「读大文件 + 定位修改点」外包给子 LM call，回应 **观察 3** 里 context 爆炸和编辑错误问题；代价是 token 与调用链更深。

**13 个任务（表 2）**：Canonical（CIFAR-10、IMDb、ogbn-arxiv）、Classic Kaggle（house-price、spaceship-titanic）、Recent Kaggle 2022–2023（parkinsons-disease、fathomnet、反馈、identify-contrails）、Recent 研究（CLRS、BabyLM）、Code Improvement（llama-推理、vectorization）。刻意覆盖 image/text/graph/tabular/time-series，并把「预测性能」与「代码加速」两类目标都纳入。

**智能体设计（§3）**：在 [[ReAct]] 上扩展固定输出格式——**Reflection**（借鉴 [[Reflexion]]）、**研究 Plan and Status**、**Fact Check**、**Thought**、**Action + JSON Action Input**。Fact Check 专门要求区分「已执行验证」与「尚未运行」的性能论断，直接针对幻觉。**Edit Script Segment** 面向 CLRS/BabyLM 大代码库。

评估三维：**Competence**（8 trial 中指标相对基线提升 ≥10% 的比例）、**Average 改进**（有效提交的平均提升百分比）、**Efficiency**（总 token + 实际时间）。

## 设计取舍

- **取舍 1：自动指标 vs 研究质量**——用单一 numeric 评估器换可规模化对比；牺牲对新颖性、可解释性、统计严谨性的判断。适合基准 driver，不适合判断「是否做出好研究」。
- **取舍 2：短历史窗口 vs 提示词成本**——只喂最近 3 步减轻 context，但长实验的因果链被截断；Plan 文本承担外置记忆，却仍会漂移或过时。
- **取舍 3：Compound edit actions vs 透明度**——子 LM 改代码提高大文件编辑成功率，但主智能体对 diff 的控制变弱，调试链更长，token 开销上升（Claude v3 Opus 最高效模型反而最耗 token/time）。
- **边界条件**：在「有清晰基线 + 领域知识丰富 + 训练可在分钟级完成」的任务上表现最好；在新 Kaggle、主动研究问题（BabyLM）、纯系统优化（vectorization）上几乎全线溃败。环境**无网络、无多用户隔离讨论**——论文未讨论沙箱安全与恶意代码风险（Impact Statement 仅定性提及需人工监督）。

## 实验与结果

- **最强 LM**：Claude v3 Opus 智能体平均 **成功率 37.5%**（8 运行 × 13 任务），高于 GPT-4（19.2%）、GPT-4-turbo（26.0%）、Gemini Pro（18.3%）、Mixtral（3.8%）。
- **任务两极分化**：house-price / spaceship-titanic **100%**；parkinsons-disease、fathomnet、BabyLM、vectorization **0%**；CIFAR-10 上 Claude v3 Opus 62.5% vs GPT-4 25%。
- **提升幅度 vs 成功率**：GPT-4 平均指标提升 **41.3%** > Claude v3 的 **26.1%**，主要被 identify-contrails 单任务拉高；Claude v3 更偏「稳定过关」而非「大幅刷分」。
- **智能体框架对比（表 5）**：本文智能体 vs AutoGPT vs LangChain ReAct——GPT-4-turbo 上 **26.0% / 2.9% / 1.0%**；Claude v3 上 **37.5% / 13.5% / 33.7%**。LangChain 在部分任务上因「更简单、少改 submission 格式」反而接近本文方法。
- **效率**：GPT-4-turbo 平均 token 最少（比均值少 **51%**）；全基准一次约 **600 万 token ≈ $60**；以 26% 成功率粗算，期望每次成功约 **$231**——可靠性直接决定 economics。
- **过程分析**：图 3 显示多数模型随步骤增加指标退化，仅 Claude v3 Opus 例外；CIFAR-10 错误模式含 Hallucination、Bad Plan、JSON/Submission Format Error、Small Improvement（<10%）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Claude v3 Opus 在被测配置中成功率最高 | §4，表 3：平均成功率 37.5%，GPT-4-turbo 为 26.0% | 13 个任务、每项 8 次运行；成功定义为超过基线 10% | 强 |
| 智能体框架本身会显著改变结果 | 表 5：GPT-4-turbo 下本文框架 26.0%、AutoGPT 2.9%、LangChain 1.0% | 三种提示与执行框架；未控制所有工具和上下文差异 | 强 |
| 任务难度高度两极分化 | 表 3：两个 Kaggle 任务 100%，四个任务 0% | 13 个任务；数据准备、运行时间和指标类型不同 | 强 |
| 更多交互步骤通常不能自动带来更好结果 | 图 3：除 Claude v3 Opus 外，多数模型的指标随步骤增加而下降 | 过程分析以 CIFAR-10 等任务为主；不能外推所有研究任务 | 中 |

## 批判性分析

### 论证链条

作者路径清晰：**ML 实验 = 文件操作 + 代码执行 + 迭代诊断** → 设计统一环境 + 13 任务 + ReAct 增强智能体 → Claude v3 在多条经典任务上显著优于弱基线和部分竞品。链条在「能否自动提高 tabular/CNN 基线」上闭合得较好。

薄弱跳步在于：从「37.5% 成功 on 13 curated 任务」外推到「LM 智能体可以做 ML experimentation」——未证明智能体能提出**新方法**，也未证明提升来自**理解数据**而非套用训练记忆里的标准 方案。recency 曲线支持污染叙事，但没有像 [[MLE-Bench-ICLR25]] 那样做讨论帖 familiarity 或 obfuscation 实验，证据仍是间接的。

### 假设压力测试

- **10% 成功阈值**：对 MAE/SMAPE 等指标，10% 相对提升的难度因任务而异；identify-contrails 等任务基线本身不低，成功率与「平均提升」会出现背离（GPT-4 高提升、Claude v3 0% 成功）。
- **8 运行方差**：单任务成功率粒度为 12.5% 台阶，表 3 中许多 0%/12.5% 差异可能只是 1 次 trial 之差，统计显著性未报告。
- **步数/时间上限**：GPT-4 仅 30 actions，与其他模型 50 actions 不完全公平；BabyLM/CLRS 等长训练任务可能在上限内根本跑不完有意义实验。
- **基线不一致**：部分任务 starter 不能跑，基线退化为随机预测——跨任务成功率可比性受损（论文在表 4 脚注已意识到无基线任务的百分比定义问题）。

### 实验可信度

- **基准代表性**：13 任务、分钟级单机实验，对真实 ML 工程（数据清洗、分布式训练、生产部署）覆盖有限；但作为 2023–2024 早期探针是合理的。
- **基线强度**：与 AutoGPT/LangChain 对比有说服力；但未与后续 [[MLE-Bench-ICLR25]] 的 AIDE 脚手架、[[OpenHands-ICLR25]] 等更强工程化智能体同场竞技（时代局限，非论文过错）。
- **消融实验**：研究 Plan / Fact Check 主要靠定性轨迹和与 LangChain 的对比论证，缺少「去掉 Fact Check 的受控消融实验」数字。
- **指标覆盖**：有能力、改进、效率，但**无正确性审计**（实验是否真的按描述执行、是否数据泄漏）——在自动科研语境下这是系统性缺口，[[MLR-Bench-arXiv25]] 后来证明编造结果会是致命问题。

### 系统性缺陷

- **安全与隔离**：智能体可 Execute 任意 Python；论文未描述 syscall/network 限制、资源 cgroup、或产物校验——部署风险高。
- **尾延迟与可观测性**：只报平均 token/time，未分析失败运行的长尾耗时；轨迹可解读但无统一调试工具链。
- **人机协同**：强调轨迹可让人类介入，但实验全是无人值守 batch；「可协作」仍是设计主张而非用户研究结论。
- **可扩展性**：任务添加需手写评估器和 starter；不像纯 API 基准那样易扩展。论文未讨论。

## 局限与后续工作

- **局限 1**：成功率整体偏低且任务间极不均匀，距离「可靠自主 ML 研究员」很远；新任务全线 0% 说明泛化到 open 研究 problems 尚未成立。
- **局限 2**：长程规划中，短 context + 自指 Fact Check 不足以阻止幻觉和性能回退（除 Claude v3 Opus 外步数越多越差）。
- **局限 3**：评估只看最终指标，不验证实验过程诚信度——在自动科研生态里已被后续工作显示为关键短板。
- **后续工作 1**：用 **受控消融实验 + 外部验证器**（强制每次论断绑定一次 Execute Script 的 stdout/log hash）量化 Plan/Fact Check 的真实收益。
- **后续工作 2**：扩展任务到更长训练、多 GPU、以及需要文献检索的设定，并报告成功 vs 污染的因果分离实验。
- **后续工作 3**：作者提出的人机协作用户研究——测量人类在轨迹上介入后成功率、时间、信任度的变化，是把基准推向实用化的必要一步。

## 相关

- **相关概念**：[[ReAct]]、[[Reflexion]]、[[AutoGPT]]、[[AutoML]]、[[Agent-Scaffold]]、[[LLM-Agent]]
- **同类系统**：[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[AI-Scientist-arXiv24]]、[[Kosmos-AI-Scientist-arXiv25]]、[[Auto-Research-arXiv25]]、[[FunSearch-Nature24]]
- **同会议**：[[ICML-2024]]
- **对比**：[[MLE-Bench-ICLR25]]（75 Kaggle + medal 判定，更贴近人类竞技水平）；[[MLR-Bench-arXiv25]]（更全研究流水线 + 造假检测）；本文是更早、更轻的 **ML experimentation** 探针
- **同主题**：[[Auto-Research]]
