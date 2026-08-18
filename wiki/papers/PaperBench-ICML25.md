---
type: paper
name: PaperBench
full_title: "PaperBench: Evaluating AI’s Ability to Replicate AI Research"
authors: [Giulio Starace, Oliver Jaffe, Dane Sherburn, James Aung, Jun Shern Chan, et al.]
venue: ICML
year: 2025
tags: [auto-research, benchmark, research-replication, llm-agent, llm-judge, domain/auto-research, concern/long-horizon]
source_pdf: "[[icml25-starace-paperbench.pdf]]"
source_md: "[[icml25-starace-paperbench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# PaperBench：评测 AI 复现 AI 研究的能力（ICML 2025）

> **原题**：PaperBench: Evaluating AI’s Ability to Replicate AI Research

> **一句话总结**：PaperBench 用 20 篇 ICML 2024 Oral/Spotlight、8,316 个 author-approved 评分细则 leaf nodes 和独立 A10 重执行，把“会写研究代码”与“真的复现结果”拆开；最佳 BasicAgent（Claude 3.5 Sonnet）总分仅 21.0±0.8%，且其 Code Development/Execution/Result Match 分别为 35.4/1.8/0.7%，而 48 小时人类 best@3 在三篇子集上达 41.4%、o1 仅 26.6%，说明当前智能体的短板是长周期集成、执行与结果验证，而非快速生成代码（§5.2–5.4，表 3、图 3、表 7）。

## 问题与动机

现有 ML 智能体基准多测试 Kaggle 工程、给定仓库的 reproduction，或带即时评分函数的短任务。它们难以回答一个更接近自主 R&D 的问题：只给论文，智能体能否理解贡献、从零实现完整代码库、运行和调试实验，并在干净环境复现论文结果？

PaperBench 选择 20 篇 ICML 2024 Oral/Spotlight，让原论文作者参与定义“复现成功”的层次化评分细则，并要求智能体不得查看作者代码或其他在线复现。提交必须包含 `reproduce.sh`；任务结束后在新的 Ubuntu 24.04 + A10 VM 中独立执行，再由评审器分别检查代码、执行与结果。这套协议直接回应 [[MLR-Bench-arXiv25]] 暴露的编造风险：硬编码结果或只写看似合理的代码不能自动算成功（§2.1–2.5）。

作者进一步提出 PaperBench Code-Dev 作为低成本代理任务，以及 JudgeEval 来测量自动评审器是否接近人工评分。论文的核心价值因此有两层：既给出智能体复现能力的基线，也提供一种把复杂、非结构化 R&D 输出拆成可审计 criteria 的评测工程。

## 关键观察 / 隐含假设

- **观察 1：代码生成能力远强于端到端复现能力。** Claude 3.5 Sonnet BasicAgent 的 Code Development 为 35.4%，Execution 仅 1.8%，Result Match 仅 0.7%；36 小时 o1 IterativeAgent 也只有 42.4/7.4/1.4（附录 I，表 7）。
  - **依赖假设**：评分细则对三类 requirement 的权重合理，独立执行环境与论文原实验兼容。
  - **可能失效场景**：环境依赖或下载失败会把“基础设施失败”计作智能体执行失败；Code Development 又由 [[LLM|LLM]] 评审器静态判断，可能高估不能运行的代码。

- **观察 2：当前智能体有短时爆发力，却不能把额外时间转成持续进展。** o1 在最初阶段领先人类，但约 1 小时后分数基本 plateau；24 小时后人类反超，三篇子集 48 小时人类 best@3 为 41.4%，o1 为 26.6%（§5.4，图 3）。
  - **依赖假设**：智能体与人类的 active time、无人值守实验时间、工具权限及 best@3 比较足够公平。
  - **可能失效场景**：更强记忆/脚手架、异步 job monitoring 或允许智能体并行实验时，时间曲线可能改变；best@3 人类与模型平均/快照不是完全对称统计量。

- **观察 3：脚手架提示词会显著改变模型排序。** o1 从 BasicAgent 的 13.2±0.3 提到 IterativeAgent 的 24.4±0.7，Claude 3.5 Sonnet 却从 21.0±0.8 降到 16.1±0.1（表 3、4）。
  - **依赖假设**：移除 early submit、强制逐步工作主要修复时间管理，而没有改变任务语义。
  - **可能失效场景**：对本来善于自主终止的模型，强制耗尽时间会产生无效修改；基准若不同时报告模型与脚手架，榜单会混淆二者。

- **观察 4：复杂任务评分可以规模化，但评审器并非真值。** o3-mini SimpleJudge 在 JudgeEval 上 F1 为 0.83、成本约 $66/篇；o1 F1 略高至 0.84，却需 $830/篇（§4.2，表 2）。
  - **依赖假设**：5 个部分复现构成的 JudgeEval 能代表 20 篇基准上的提交分布，top-10 file retrieval 不遗漏关键证据。
  - **可能失效场景**：adversarial submission、超大代码库、跨文件隐式依赖或评审器-targeted specification gaming 会使 binary leaf grading失真。

- **假设 1：复现 ICML 论文是自主 AI R&D 能力的有效代理指标。**
  - **证据强度**：**中**。它覆盖理解、实现、调试、执行，但不测选题、novel 假设、实验设计取舍或写作；且任务在筛选时排除了多机、闭源模型、人工标注和不易访问依赖。

- **假设 2：author-approved hierarchical 评分细则的加权根分数可代表复现质量。**
  - **证据强度**：**中**。作者参与减少 underspecification，但权重表达“重要性”而非难度，另一组专家可能给出同样合理但排序不同的评分细则。

## 核心方法

每个 PaperBench 样本包含论文、作者补充的补充说明与隐藏评分细则。智能体从零创建仓库，并以根目录 `reproduce.sh` 作为唯一重执行入口；禁止访问作者仓库和已知在线复现。任务完成后，系统把提交复制到新的 Ubuntu 24.04/A10 VM 执行，生成 `reproduce.log` 与产物，从而把任务时硬编码输出与洁净复现区分开（图 1、§2.1–2.2）。

评分细则是加权树，leaf 分三类（图 2、§2.3–2.4）：

1. **Code Development**：源码是否实现要求；
2. **Execution**：`reproduce.sh` 是否实际运行所需实验；
3. **Result Match**：fresh 执行生成的结果是否与论文一致。

leaf 为 binary pass/fail，父节点取 children 的 weighted average，root 即 Replication Score。20 篇共有 8,316 个 leaf 节点；每个评分细则由两位研究 engineer 起草、多轮内审，再由一位原作者修订和签字，单篇需数周或数十小时（§3.1、附录 C）。

SimpleJudge 针对每个 leaf 独立评分。若 submission 太大，它先列出全部文件，再选最相关的十个或填满 context 的文件；Code/Execution 节点看源码与日志，Result Match 节点只看重执行后新生成的结果类文件。JudgeEval 用 5 篇论文的人工标注部分复现测 binary classification F1，主实验选 o3-mini-high 作为成本/性能折中（§4.1–4.2、附录 D）。

BasicAgent 是 ReAct 风格工具闭环，提供壳层、Python、browser、分页 reader；IterativeAgent 移除 submit 工具，每轮只要求执行下一个步骤，强制用满时间（附录 F）。这直接针对“只写计划、不读全文、过早结束”的预实验失败模式。

低成本版 PaperBench Code-Dev 跳过洁净复现，只评分 Code Development leaf；它无需昂贵 GPU，但与 full PaperBench 仅弱相关，因此只能作为 noisy 初步信号（§2.6）。

## 设计取舍

- **结果可信度 vs 评测成本**：fresh VM 重执行和 Result Match 提高证据强度，但 20 篇完整 o1 12-hour eval 约需 $8,000 智能体 API 成本，另加每篇约 $66 grading；这限制重复 seeds 与社区可及性（§7）。
- **细粒度部分 credit vs 评分细则 labor**：8,316 个 leaf 让失败不全归零，也让评分细则创建与评审器 token 成本极高；depth-3 pruning 在单个 JudgeEval case 中降本 10 倍，但尚不稳定（附录 H，图 6）。
- **禁止原代码 vs 现实工作方式**：隔离“从零实现”能力，却偏离研究者通常复用开源代码的现实，也把 API/依赖重建变成主要工作量。
- **不限智能体资源 vs 排名可比性**：规则允许任意运行时间/算力，仅鼓励报告设置；未来结果若资源不同，Replication Score 不能单独归因于模型能力。
- **可执行任务 vs 研究代表性**：筛选排除了多机训练、闭源模型、人工数据、纯理论和框架论文，使任务能在单 A10 上完成，但系统性低估现代前沿研究的 infra 与协作复杂度。
- **边界条件**：适合公开依赖、单机可运行、结果可由代码重建的 empirical ML；不适合理论证明、数据采集、人类研究、湿实验或多节点训练。

## 实验与结果

- 主实验为 6 个模型 × 20 篇 × 每篇 3 运行，BasicAgent、单 A10、最长 12 小时。Claude 3.5 Sonnet 以 21.0±0.8% 最好，o1 为 13.2±0.3%，DeepSeek-R1 为 6.0±0.3%，其余低于 5%（§5.1–5.2，表 3）。
- IterativeAgent 把 o1 从 13.2±0.3% 提至 24.4±0.7%、o3-mini 从 2.6±0.2% 提至 8.5±0.8%，但 Claude 3.5 Sonnet 从 21.0±0.8% 降至 16.1±0.1%；延长 o1 至 36 小时仅到 26.0±0.3%（§5.3，表 3、4）。
- 三篇共同子集上，人类 best@3 在 48 小时达 41.4%，o1 36 小时为 26.6%；时间曲线显示 o1 最初领先，但大约第一小时后增长很慢，24 小时后被人类超过（§5.4，图 3）。
- requirement 分解揭示最大鸿沟：Claude BasicAgent 的 Code Development/Execution/Result Match 为 35.4±0.8/1.8±0.7/0.7±0.3；o1 IterativeAgent 为 43.3±1.1/4.5±1.5/0.0；人类 best@3 为 72.4/20.4/8.9（附录 I，表 7）。
- JudgeEval 上 o3-mini-high 的准确率/precision/recall/F1 为 0.83/0.83/0.83/0.83，约 $66/篇；o1-high F1 为 0.84，约 $830/篇。o3-mini 的 Code Development F1 最低，为 0.72（§4.2，表 2；附录 G，表 6）。
- PaperBench Code-Dev 上 o1 IterativeAgent 为 43.4±0.8%，但论文明确报告其与 full eval 仅弱相关，不能把静态代码分当作复现分（§2.6、§5.2，表 5）。
- 646 次运行中监控发现 10 次访问 blacklisted resource，相关 submission 被置零；监控只是日志字符串匹配，需要人工复核（§2.5、附录 E）。
- full o1 IterativeAgent 12 小时单篇约 $400，20 篇一次约 $8,000；SimpleJudge 另约 $66/篇。Code-Dev 预计每次约 $4,000，grading 约 $10/篇（§7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 当前前沿智能体尚不能可靠复现完整 ML 论文 | §5.2，表 3：最佳 BasicAgent 为 21.0±0.8% | 20 篇 ICML 2024 论文、单张 A10、12 小时、3 个种子、禁止作者代码 | 强 |
| 失败主要发生在执行与结果匹配，而非写代码 | 附录 I，表 7：Claude 为 35.4/1.8/0.7，人类为 72.4/20.4/8.9 | 评分细则加权的代码、执行、结果匹配；人类仅评三篇子集 | 强 |
| 单纯增加时间不能解决长程失败 | §5.4，图 3：o1 约 1 小时后停滞，24 小时后人类反超；48 小时人类 41.4%，o1 26.6% | 4 篇论文的时间曲线，三篇有共同终点；o1 IterativeAgent | 中 |
| 脚手架设计会改变模型分数与排序 | §5.3，表 3、4：o1 13.2→24.4，Claude 21.0→16.1 | BasicAgent vs 特定 IterativeAgent 提示词；相同 12h/A10 | 强 |
| o3-mini 评审器可用但并不完美 | §4.2，表 2：F1 0.83、每篇 66 美元；附录 G 表 6 的代码节点 F1 为 0.72 | JudgeEval 中 5 个部分复现；不是对抗性提交 | 中 |

## 批判性分析

### 论证链条

PaperBench 的最有力的论证是通过设计把“源代码看起来对”“脚本确实运行”“结果真的匹配”分开，随后表 7 直接显示智能体在三层之间断崖式下降。观察 → 协议 → 结果的链条闭合，也比只由 LLM 阅读最终报告的自动科研基准更能抵抗编造。

较强的外推是把复现分数当作广义“AI R&D autonomy”。复现确实需要大量工程技能，但基准明确筛掉多机、闭源依赖、人工数据与框架研究，也不测新颖性、问题选择或实验设计。它是长程研究工程的强代理指标，不是完整科研能力的同义词。

### 假设压力测试

如果允许使用作者代码，任务会从 reimplementation 转成理解、修复和验证，智能体排名可能改变；如果换到 H100、多 GPU 或更长 wall time，某些训练任务的 Execution 分会升高，但当前 o1 plateau 又说明算力并非唯一瓶颈。未来智能体若在预训练中见过作者仓库，禁止浏览也挡不住污染。

评分细则根分数依赖 author-approved 权重。作者最了解贡献，却也可能偏好论文叙事中的 headline 结果；而 leaf 是 binary、父节点是线性加权，不能表达依赖关系：实现方法失败时，下游多个结果 leaf 可能重复惩罚。附录 A 已承认当前树的先后顺序只隐式编码 dependency。

### 实验可信度

20 篇、3 seeds、洁净复现、作者参与评分细则和人类 time curve，使主结果比多数智能体基准扎实。作者也诚实报告了 10 次 blacklist violation、评审器成本、模型过早退出与 per-requirement 失败。

主要不确定性来自自动评审器：JudgeEval 只有 5 个部分复现，且提交由作者从零构建或修改原代码而来，不一定像真实智能体输出；top-10 file selection 可能漏掉跨文件证据。o3-mini 总 F1 0.83 看似高，但 Code Development F1 仅 0.72，而大多数智能体得分恰好来自 Code Development，排序可能对评审器 error 敏感。论文没有给人类 regrade 主排行榜的置信区间。

人类比较也不是完全对称：8 位参与者按自信选题，best@3 与模型多次运行的聚合不同；参与者可用 ChatGPT/Copilot，且为兼职四周工作。不过这些选择整体更像是在构造“专家上限”，足以支持智能体长程落后的定性结论，不足以给出严格的人机效率比。

### 系统性缺陷

- **可扩展性**：评分细则每篇需数十小时到数周专家劳动，20 篇扩到数百篇的成本很高；PaperBench Code-Dev 又牺牲最关键的执行证据。
- **可复现性**：网络依赖、包版本、HuggingFace/API credentials 与 Ubuntu/A10 环境会随时间漂移；论文未给长期产物 preservation 或依赖镜像维护方案。
- **安全与隔离**：智能体可联网、执行任意代码并持有 API key；论文关注 blacklist cheating，未讨论 credential exfiltration、malicious package 或 resource abuse。
- **可观测性**：BasicAgent 会主动早停，IterativeAgent 则被迫持续工作；两者都缺少显式实验 scheduler、失败 recovery、预算 allocator 与 checkpoint-aware 规划器。
- **成本公平性**：规则不限制运行时间/算力，排行榜若只看分数，会把模型能力、脚手架工程与资源预算混为一体。

## 局限与后续工作

- **局限 1**：只有 20 篇，且经过单 A10 可行性筛选，不代表包含多节点训练、闭源模型或数据采集的前沿 ML 研究。
- **局限 2**：JudgeEval 小且非 adversarial；o3-mini 对 Code Development 的 F1 只有 0.72，主榜分数仍可能受评审器 error 影响。
- **局限 3**：原作者代码在线造成未来污染风险，blacklist 只能限制显式访问，不能检测训练时记忆。
- **局限 4**：完整 eval 单次约 $8,000 智能体 API 成本加 $1,320 grading，妨碍多脚手架、多 seed、频繁回归测试。
- **局限 5**：评分细则权重与树结构由人工定义，dependency 未显式建模，可能重复奖励或惩罚关联 requirement。
- **后续工作 1**：对 20 篇主榜按分层抽样进行专家 double-grade，报告评审器-induced 排序 uncertainty，并构造隐藏 loophole/adversarial submissions 测 specification gaming。
- **后续工作 2**：把评分细则 tree 改为显式 dependency DAG，比较 leaf binary grading、subtree grading和可执行验证器的成本、F1 与最终模型排序。
- **后续工作 3**：固定模型、算力与 12/36/48 小时预算，消融 persistent 记忆、job monitoring、失败 recovery、parallel 实验 scheduler，定位 plateau 来自哪种长程控制缺陷。
- **后续工作 4**：建立 hermetic container、数据集 hash 与 cached dependency registry，按季度重跑一组 reference submission，量化基准随软件生态漂移的分数变化。
- **后续工作 5**：同时提供 from-scratch 与 author-代码-assisted 两条 track，测量“重实现能力”和“现实复现/审计能力”的差距。

## 相关

- **相关概念**：LLM 智能体、智能体脚手架、LLM-as-a-评审器、研究复现、长程规划
- **同类基准**：[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[MLAgentBench-ICML24]]、RE-Bench、CORE-Bench
- **相关科研系统**：[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[AutoScientists-arXiv26]]
- **同主题**：[[Auto-Research]]
- **对比**：[[MLR-Bench-arXiv25]] 测完整开放式研究流水线但执行证据弱；PaperBench 放弃新颖性，换取 洁净环境重执行与细粒度复现 audit。
