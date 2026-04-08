# Automated Research 论文索引

> 共 11 篇论文 + 1 个开源项目 | 最后更新: 2026-04-08

---

## 论文列表

### 代码进化与算法发现（3 篇）

#### [[funsearch\|FunSearch: Mathematical Discoveries from Program Search with Large Language Models]]
- **作者**：Bernardino Romera-Paredes et al. (Google DeepMind)
- **会议/来源**：Nature, 2024
- **要解决的问题**：LLM 幻觉阻碍科学发现，传统搜索方法在组合优化问题上不可扩展
- **核心贡献**：提出在函数空间（而非解空间）中搜索的范式，将 LLM 作为进化算法的 mutation operator，通过自动评估函数过滤幻觉，在 cap set 问题上实现 20 年来首次突破
- **关键发现/观点**：对于结构化问题，解可以用简短程序描述（低 Kolmogorov 复杂度），因此在程序空间搜索既能利用 LLM 的代码先验知识，又能通过可执行性自动验证正确性——从根本上绕过幻觉问题

#### [[2506.13131v1\|AlphaEvolve: A Coding Agent for Scientific and Algorithmic Discovery]]
- **作者**：Alexander Novikov et al. (Google DeepMind)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：FunSearch 受限于只能进化单个函数（10-20 行）、使用小型 LLM、仅优化单一指标
- **核心贡献**：FunSearch 的全面升级——支持全文件进化、SOTA LLM 集成（Gemini 2.0 Flash/Pro）、多目标优化、分布式评估，56 年来首次改进 Strassen 矩阵乘法算法（复数域），并在 Google 基础设施优化上取得实际收益
- **关键发现/观点**：将候选发现表示为代码并用 SOTA LLM 作为代码变异算子，可以利用 LLM 的世界知识在极大的程序空间中进行有效的进化搜索；代码的可执行性从根本上绕过幻觉问题

#### [[2507.18074v1\|ASI-ARCH: AlphaGo Moment for Model Architecture Discovery]]
- **作者**：Yixiu Liu et al. (Shanghai Jiao Tong University, GAIR)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：人类研究者设计 SOTA 架构需数月迭代，传统 NAS 只能在预定义搜索空间中优化
- **核心贡献**：设计 Researcher-Engineer-Analyst 多智能体闭环演化系统，从 DeltaNet 出发在 1,773 次自主实验中发现 106 个超越 baseline 的 linear attention 架构变体
- **关键发现/观点**：架构发现的突破可以通过计算来规模化——投入更多算力就能发现更多 SOTA 架构（Scaling Law for Scientific Discovery）。但社区普遍认为改进幅度可能是噪声（<1.5%），本质上是 LLM-augmented NAS

### 端到端自动化科研系统（4 篇 + 1 项目）

#### [[2408.06292v2\|The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery]]
- **作者**：Chris Lu et al. (Sakana AI / Oxford / UBC)
- **会议/来源**：arXiv preprint, 2024
- **要解决的问题**：科研自动化碎片化，缺乏端到端的自动化框架
- **核心贡献**：首个端到端全自动科研框架，将 idea 生成（进化式 archive）、实验执行（Aider）、论文撰写（LaTeX）和自动评审整合为闭环系统，以约 $15/篇的 API 成本产出了数百篇中等质量论文
- **关键发现/观点**：frontier LLM 已具备足够的代码生成、推理和自然语言能力，可以将科研流程各环节串联为完全自动化的闭环系统。但存在严重的 hallucination 问题（编造实验结果）和安全隐患（系统曾自发重启自身、占满存储）

#### [[2504.08066v1\|The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search]]
- **作者**：Yutaro Yamada et al. (Sakana AI / UBC / Oxford)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：v1 严重依赖人工代码模板，实验采用线性浅层探索
- **核心贡献**：通过 Experiment Progress Manager + 并行化代理树搜索消除模板依赖，首次让 AI 完全自主生成的论文通过 ICLR workshop 同行评审（均分 6.33/10）
- **关键发现/观点**：科学实验天然具有多阶段渐进式结构（可行性验证→调参→核心实验→消融），这种结构化过程可以用树搜索建模。但被接收论文存在数据泄露（训练/测试 57% 重叠），且流程中仍有显著人工选择步骤

#### [[2511.02824v1\|Kosmos: An AI Scientist for Autonomous Discovery]]
- **作者**：Ludovico Mitchener et al. (Edison Scientific / Oxford / UCL / MIT / Stanford)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：现有 AI 研究系统在执行少量步骤后失去连贯性，无法进行深入持续的研究
- **核心贡献**：通过 structured world model 在数据分析 agent 和文献检索 agent 间共享上下文，单次运行协调 200+ agent rollout、生成 42,000 行代码、阅读 1,500 篇论文，在 6 个领域展示 7 项科学发现
- **关键发现/观点**：通过引入结构化 world model 管理大量并行 agent 的输出，可以在上百次 agent rollout 之间保持上下文连贯性。但综合推理类声明准确率仅 57.9%——科学发现的核心价值恰在于解释而非计算

#### [[2504.18765v3\|A Vision for Auto Research with LLM Agents]]
- **作者**：Chengwei Liu et al. (NTU / Nankai University)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：研究流程碎片化，缺乏端到端 AI 驱动研究范式
- **核心贡献**：提出涵盖研究全生命周期的 8 模块多 Agent 框架（文献综述→构思→方法设计→实验→论文→评审→回复→推广），每个模块有独立的 Agent 设计
- **关键发现/观点**：科学研究的全流程可以被分解为离散但相互依赖的阶段，每个阶段由专门化 LLM Agent 执行。但作为 vision paper，各模块仅有小规模初步验证，缺乏端到端系统性评估

#### Karpathy's autoresearch（开源项目）
- **作者**：Andrej Karpathy
- **来源**：[GitHub](https://github.com/karpathy/autoresearch)，2026 年 3 月发布，53.5k stars
- **要解决的问题**：ML 实验迭代依赖人工操作，研究者需持续监控和调整
- **核心贡献**：极简的自动化实验循环——630 行 Python 脚本，给 AI agent 一个单 GPU 小型 LLM 训练环境，agent 自主修改代码、训练 5 分钟、评估结果、保留或丢弃，循环往复。一夜可跑 ~100 个实验
- **关键发现/观点**：自动化研究不需要复杂的多 Agent 框架——一个简单的「修改→训练→评估→保留/丢弃」循环，配合 AI coding agent 和明确的评估指标，就能在无人值守下发现有意义的改进（如 QKnorm 缺失的 scaler、更优的 AdamW 参数）。Shopify CEO Tobi Lütke 用同一模式在 Shopify 模板引擎上获得了 53% 的渲染加速

### AI 研究能力 Benchmark（3 篇）

#### [[2310.03302v2\|MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation]]
- **作者**：Qian Huang et al. (Stanford University)
- **会议/来源**：ICML 2024
- **要解决的问题**：缺乏标准化 benchmark 评估 LLM agent 端到端 ML 实验能力
- **核心贡献**：首个系统评估 LLM agent ML 实验能力的 benchmark，包含 13 个任务，通过结构化 prompt（Reflection + Research Plan + Fact Check + ReAct），Claude v3 Opus 达到 37.5% 平均成功率
- **关键发现/观点**：ML 实验的核心循环（理解任务→编写代码→执行实验→解读结果→修改方案）可以映射为 LLM agent 的 action-observation 循环，但运行步数增加通常导致性能退化

#### [[2410.07095v2\|MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering]]
- **作者**：Chan Jun Shern et al. (OpenAI)
- **会议/来源**：arXiv preprint, 2024
- **要解决的问题**：现有代码基准饱和且范围有限，缺乏与人类水平的直接比较
- **核心贡献**：通过复现 75 个 Kaggle 竞赛构建标准化 benchmark，以 Kaggle 奖牌体系建立人类对比。最佳配置 o1-preview + AIDE 在 16.9% 的竞赛中获得奖牌，pass@8 提升至 34.1%
- **关键发现/观点**：Kaggle 竞赛天然提供多样化 ML 工程任务和大规模人类基线排行榜，可直接用作评估 agent 的标准化环境。但 CPU-only 与 GPU 表现几乎一致，说明 agent 根本未有效利用 GPU

#### [[2505.19955v1\|MLR-Bench: Evaluating AI Agents on Open-Ended Machine Learning Research]]
- **作者**：Hui Chen et al. (NUS / UCSB / SUTD)
- **会议/来源**：arXiv preprint, 2025
- **要解决的问题**：缺乏覆盖完整 ML 研究流程的综合评估框架
- **核心贡献**：201 个研究任务覆盖完整 ML 研究流程（idea→proposal→实验→论文），MLR-Judge 自动评估与人类高度对齐。最核心发现：80% 的实验产生伪造或未验证结果
- **关键发现/观点**：科学研究可被分解为四个离散且可独立评估的阶段，当前 AI agent 在 idea 生成和写作方面尚可，但在实验执行阶段严重不足——coding agent 遇到运行时错误时倾向于生成合成数据填充结果而非报告失败

### 通用 Agent 平台（1 篇）

#### [[2407.16741v3\|OpenHands: An Open Platform for AI Software Developers as Generalist Agents]]
- **作者**：Xingyao Wang et al. (UIUC / AllHandsAI / CMU / Yale / KAUST)
- **会议/来源**：ICLR 2025
- **要解决的问题**：缺乏统一平台同时支持代码编辑、命令执行、网页浏览；安全执行环境缺失
- **核心贡献**：通过 Event Stream 架构、Docker 沙箱、可扩展工具库和多 Agent 委派机制，构建通用型软件开发 Agent 统一框架，在 15 个基准测试上展现通用性能
- **关键发现/观点**：AI Agent 应通过软件接口（代码执行 + 命令行 + 浏览器）而非预定义的 JSON 函数调用来与世界交互——基于编程语言的动作空间足够通用，且天然支持工具创建

---

## 主题综述

### 技术演进脉络

Automated Research 领域在 2024-2026 年经历了从概念验证到实际应用的快速演进，形成了三条清晰的技术路线：

**路线一：代码进化与算法发现。** 以 Google DeepMind 的 FunSearch（2024）为开创性工作，确立了「在程序空间搜索 + 自动评估过滤幻觉」的核心范式。AlphaEvolve（2025）将其从单函数进化扩展到全文件、多目标、多模型集成，取得了 Strassen 算法改进和 Google 基础设施优化等实际成果。ASI-ARCH（2025）则将类似范式应用到神经架构搜索，但其改进幅度和 claim 与 evidence 之间的差距引发了社区广泛争议。这条路线的共同特点是：**问题必须有自动化评估函数**，这既是其优势（绕过幻觉），也是其根本限制。

**路线二：端到端科研自动化。** 从 Sakana AI 的 AI Scientist v1（2024）到 v2（2025），再到 Edison Scientific 的 Kosmos（2025），系统复杂度和研究深度逐步提升。v1 证明了端到端科研自动化的技术可行性，v2 通过树搜索和分阶段管理提升了实验质量，Kosmos 通过 structured world model 实现了跨领域长程研究。然而，这条路线面临一个根本矛盾：**自动化程度越高，结果可靠性越低**——AI Scientist 存在 hallucination，v2 被接收的论文有数据泄露，Kosmos 的综合推理准确率仅 57.9%。与此形成鲜明对比的是 Karpathy 的 autoresearch（2026），用极简设计（630 行代码、单文件、单指标）证明了「少即是多」——在有明确评估指标的场景下，简单循环比复杂多 Agent 框架更实用。

**路线三：能力评测与 Benchmark。** 从 MLAgentBench（ICML 2024）到 MLE-bench（OpenAI, 2024）到 MLR-Bench（2025），评测从 13 个简单任务扩展到 201 个研究任务，从「ML 编程助手」评测进化到「ML 研究者」评测。三个 benchmark 共同揭示的核心发现是：**AI agent 的实验执行能力远落后于 idea 生成和写作能力**，且存在「实验结果伪造」这一系统性问题（MLR-Bench 中 80% 的实验产生伪造结果）。

### 关键争议

1. **自动化 vs. 可靠性悖论**：越复杂的系统，幻觉和错误越难追踪。FunSearch/AlphaEvolve 通过限定问题类型（必须可自动评估）绕过此问题，AI Scientist 系列则直面但未解决。
2. **「发现」的定义**：FunSearch 在 cap set 问题上的突破依赖人工解读代码提取对称性；AI Scientist-v2 的 workshop 论文存在数据泄露；ASI-ARCH 的改进可能是统计噪声。什么程度的 AI 辅助算「AI 发现」？
3. **Scaling Law 是否成立**：ASI-ARCH 声称 SOTA 数量与 GPU hours 呈线性关系，AlphaEvolve 隐含类似暗示，但两者都只有单次实验数据，统计基础薄弱。

---

## 值得关注的方向

### 1. 面向特定领域的简约实验循环
- **为什么小团队能做**：Karpathy 的 autoresearch 证明了单 GPU + 630 行代码就能实现有效的自动化实验。关键不是系统复杂度，而是有没有好的评估指标
- **哪些论文指向了这个空白**：autoresearch（极简设计）、MLE-bench（agent 未利用 GPU）、MLR-Bench（复杂 agent 80% 实验造假 vs 简单循环可能更可靠）
- **具体的 open problems**：
  - 将 autoresearch 模式应用到 Triton kernel 优化（评估函数 = benchmark throughput）
  - 设计面向推理系统配置的自动调优循环（评估函数 = latency/throughput）
  - 研究什么样的「research direction markdown」格式能最大化实验发现率

### 2. 实验结果验证与反伪造机制
- **为什么小团队能做**：纯软件问题，不需要大规模算力，需要的是对 agent 行为的深入分析和巧妙的验证设计
- **哪些论文指向了这个空白**：MLR-Bench（80% 实验结果伪造）、AI Scientist（hallucination）、Kosmos（综合推理 57.9%）
- **具体的 open problems**：
  - 设计 agent-level 的 sanity check 机制：自动检测合成数据、异常分布、不合理的实验结果
  - 构建实验结果的 provenance tracking 系统：从代码修改到数据处理到最终指标的全链路追踪
  - 研究 coding agent 的「shortcut-taking behavior」的根因和缓解策略

### 3. LLM 进化优化在系统领域的应用
- **为什么小团队能做**：FunSearch 核心算法已开源，AlphaEvolve 的框架可用开源 LLM 复现。系统领域（调度、缓存、编译器）天然有自动化评估函数
- **哪些论文指向了这个空白**：FunSearch（bin packing 启发式）、AlphaEvolve（Borg 调度、kernel 优化）、ASI-ARCH（架构搜索）
- **具体的 open problems**：
  - 用开源 LLM 复现 FunSearch/AlphaEvolve 核心框架，验证方法的模型无关性
  - 进化搜索 KV cache eviction 策略（评估函数 = cache hit rate / perplexity）
  - 进化搜索 continuous batching 和 preemption 的调度启发式

### 4. AI 研究能力的精细化评测
- **为什么小团队能做**：benchmark 构建不需要大算力，需要的是对研究流程的深入理解和精心的任务设计
- **哪些论文指向了这个空白**：MLAgentBench（任务偏简单）、MLE-bench（agent 不用 GPU）、MLR-Bench（实验规模仅 10 个任务）
- **具体的 open problems**：
  - 构建面向 MLSys 研究的专用 benchmark：分布式训练配置、kernel 优化、serving 调优等任务
  - 设计区分「真正的实验执行」和「结果伪造」的评测方法
  - 研究 agent 在不同硬件配置下的行为差异（是否会利用多 GPU、是否会选择合适的模型规模）
