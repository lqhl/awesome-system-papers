---
type: paper
name: PaperBench
full_title: "PaperBench: Evaluating AI’s Ability to Replicate AI Research"
authors: [Giulio Starace, Oliver Jaffe, Dane Sherburn, James Aung, Jun Shern Chan, et al.]
venue: ICML
year: 2025
tags: [auto-research, benchmark, research-replication, llm-agent, llm-judge]
source_pdf: "[[icml25-starace-paperbench.pdf]]"
source_md: "[[icml25-starace-paperbench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-25
---

# PaperBench: Evaluating AI’s Ability to Replicate AI Research (ICML 2025)

> **一句话总结**：PaperBench 用 20 篇 ICML 2024 Oral/Spotlight、8,316 个 author-approved rubric leaf nodes 和独立 A10 重执行，把“会写研究代码”与“真的复现结果”拆开；最佳 BasicAgent（Claude 3.5 Sonnet）总分仅 21.0±0.8%，且其 Code Development/Execution/Result Match 分别为 35.4/1.8/0.7%，而 48 小时 human best@3 在三篇子集上达 41.4%、o1 仅 26.6%，说明当前 agent 的短板是长周期集成、执行与结果验证，而非快速生成代码（§5.2–5.4，Table 3、Fig. 3、Table 7）。

## 问题与动机

现有 ML agent benchmark 多测试 Kaggle engineering、给定 repository 的 reproduction，或带即时 scoring function 的短任务。它们难以回答一个更接近自主 R&D 的问题：只给论文，agent 能否理解贡献、从零实现完整 codebase、运行和调试实验，并在干净环境复现论文结果？

PaperBench 选择 20 篇 ICML 2024 Oral/Spotlight，让原论文作者参与定义“复现成功”的层次化 rubric，并要求 agent 不得查看作者代码或其他在线复现。提交必须包含 `reproduce.sh`；任务结束后在新的 Ubuntu 24.04 + A10 VM 中独立执行，再由 judge 分别检查代码、执行与结果。这套 protocol 直接回应 [[MLR-Bench-arXiv25]] 暴露的 fabrication 风险：硬编码结果或只写看似合理的代码不能自动算成功（§2.1–2.5）。

作者进一步提出 PaperBench Code-Dev 作为低成本代理任务，以及 JudgeEval 来测量自动 judge 是否接近人工评分。论文的核心价值因此有两层：既给出 agent replication capability 的 baseline，也提供一种把复杂、非结构化 R&D output 拆成可审计 criteria 的评测工程。

## 关键观察 / 隐含假设

- **观察 1：代码生成能力远强于端到端复现能力。** Claude 3.5 Sonnet BasicAgent 的 Code Development 为 35.4%，Execution 仅 1.8%，Result Match 仅 0.7%；36 小时 o1 IterativeAgent 也只有 42.4/7.4/1.4（Appendix I，Table 7）。
  - **依赖假设**：rubric 对三类 requirement 的权重合理，独立执行环境与论文原实验兼容。
  - **可能失效场景**：环境依赖或下载失败会把“基础设施失败”计作 agent execution failure；Code Development 又由 [[LLM|LLM]] judge 静态判断，可能高估不能运行的代码。

- **观察 2：当前 agent 有短时爆发力，却不能把额外时间转成持续进展。** o1 在最初阶段领先人类，但约 1 小时后分数基本 plateau；24 小时后人类反超，三篇子集 48 小时 human best@3 为 41.4%，o1 为 26.6%（§5.4，Fig. 3）。
  - **依赖假设**：agent 与人类的 active time、无人值守实验时间、工具权限及 best@3 比较足够公平。
  - **可能失效场景**：更强 memory/scaffold、异步 job monitoring 或允许 agent 并行实验时，时间曲线可能改变；best@3 human 与模型平均/快照不是完全对称统计量。

- **观察 3：scaffold prompt 会显著改变模型排序。** o1 从 BasicAgent 的 13.2±0.3 提到 IterativeAgent 的 24.4±0.7，Claude 3.5 Sonnet 却从 21.0±0.8 降到 16.1±0.1（Table 3、4）。
  - **依赖假设**：移除 early submit、强制逐步工作主要修复时间管理，而没有改变任务语义。
  - **可能失效场景**：对本来善于自主终止的模型，强制耗尽时间会产生无效修改；benchmark 若不同时报告 model 与 scaffold，榜单会混淆二者。

- **观察 4：复杂任务评分可以规模化，但 judge 并非 ground truth。** o3-mini SimpleJudge 在 JudgeEval 上 F1 为 0.83、成本约 $66/篇；o1 F1 略高至 0.84，却需 $830/篇（§4.2，Table 2）。
  - **依赖假设**：5 个 partial replication 构成的 JudgeEval 能代表 20 篇 benchmark 上的提交分布，top-10 file retrieval 不遗漏关键证据。
  - **可能失效场景**：adversarial submission、超大 codebase、跨文件隐式依赖或 judge-targeted specification gaming 会使 binary leaf grading失真。

- **假设 1：复现 ICML paper 是自主 AI R&D 能力的有效 proxy。**
  - **证据强度**：**中**。它覆盖理解、实现、调试、执行，但不测选题、novel hypothesis、实验设计取舍或写作；且任务在筛选时排除了多机、闭源模型、人工标注和不易访问依赖。

- **假设 2：author-approved hierarchical rubric 的加权根分数可代表复现质量。**
  - **证据强度**：**中**。作者参与减少 underspecification，但权重表达“重要性”而非难度，另一组专家可能给出同样合理但排序不同的 rubric。

## 核心方法

每个 PaperBench sample 包含论文、作者补充的 addendum 与隐藏 rubric。agent 从零创建 repository，并以根目录 `reproduce.sh` 作为唯一重执行入口；禁止访问作者 repository 和已知在线 replication。任务完成后，系统把提交复制到新的 Ubuntu 24.04/A10 VM 执行，生成 `reproduce.log` 与 artifacts，从而把 task-time hard-coded output 与 clean reproduction 区分开（Fig. 1、§2.1–2.2）。

rubric 是加权树，leaf 分三类（Fig. 2、§2.3–2.4）：

1. **Code Development**：源码是否实现要求；
2. **Execution**：`reproduce.sh` 是否实际运行所需实验；
3. **Result Match**：fresh execution 生成的结果是否与论文一致。

leaf 为 binary pass/fail，parent 取 children 的 weighted average，root 即 Replication Score。20 篇共有 8,316 个 leaf node；每个 rubric 由两位 research engineer 起草、多轮内审，再由一位原作者修订和签字，单篇需数周或数十小时（§3.1、Appendix C）。

SimpleJudge 针对每个 leaf 独立评分。若 submission 太大，它先列出全部文件，再选最相关的十个或填满 context 的文件；Code/Execution node 看源码与日志，Result Match node 只看重执行后新生成的结果类文件。JudgeEval 用 5 篇 paper 的人工标注 partial replication 测 binary classification F1，主实验选 o3-mini-high 作为 cost/performance 折中（§4.1–4.2、Appendix D）。

BasicAgent 是 ReAct 风格 tool loop，提供 shell、Python、browser、分页 reader；IterativeAgent 移除 submit tool，每轮只要求执行下一个步骤，强制用满时间（Appendix F）。这直接针对“只写计划、不读全文、过早结束”的预实验 failure mode。

低成本版 PaperBench Code-Dev 跳过 clean reproduction，只评分 Code Development leaf；它无需昂贵 GPU，但与 full PaperBench 仅弱相关，因此只能作为 noisy preliminary signal（§2.6）。

## 设计取舍

- **结果可信度 vs 评测成本**：fresh VM 重执行和 Result Match 提高证据强度，但 20 篇完整 o1 12-hour eval 约需 $8,000 agent API cost，另加每篇约 $66 grading；这限制重复 seeds 与社区可及性（§7）。
- **细粒度 partial credit vs rubric labor**：8,316 个 leaf 让失败不全归零，也让 rubric 创建与 judge token 成本极高；depth-3 pruning 在单个 JudgeEval case 中降本 10 倍，但尚不稳定（Appendix H，Fig. 6）。
- **禁止原代码 vs 现实工作方式**：隔离“从零实现”能力，却偏离研究者通常复用开源代码的现实，也把 API/依赖重建变成主要工作量。
- **不限 agent 资源 vs 排名可比性**：规则允许任意 runtime/compute，仅鼓励报告设置；未来结果若资源不同，Replication Score 不能单独归因于 model capability。
- **可执行任务 vs 研究代表性**：筛选排除了多机训练、闭源模型、人工数据、纯理论和 framework paper，使任务能在单 A10 上完成，但系统性低估现代 frontier research 的 infra 与协作复杂度。
- **边界条件**：适合公开依赖、单机可运行、结果可由代码重建的 empirical ML；不适合理论证明、数据采集、human study、湿实验或多节点训练。

## 实验与结果

- 主实验为 6 个模型 × 20 篇 × 每篇 3 runs，BasicAgent、单 A10、最长 12 小时。Claude 3.5 Sonnet 以 21.0±0.8% 最好，o1 为 13.2±0.3%，DeepSeek-R1 为 6.0±0.3%，其余低于 5%（§5.1–5.2，Table 3）。
- IterativeAgent 把 o1 从 13.2±0.3% 提至 24.4±0.7%、o3-mini 从 2.6±0.2% 提至 8.5±0.8%，但 Claude 3.5 Sonnet 从 21.0±0.8% 降至 16.1±0.1%；延长 o1 至 36 小时仅到 26.0±0.3%（§5.3，Table 3、4）。
- 三篇共同子集上，human best@3 在 48 小时达 41.4%，o1 36 小时为 26.6%；时间曲线显示 o1 最初领先，但大约第一小时后增长很慢，24 小时后被人类超过（§5.4，Fig. 3）。
- requirement 分解揭示最大鸿沟：Claude BasicAgent 的 Code Development/Execution/Result Match 为 35.4±0.8/1.8±0.7/0.7±0.3；o1 IterativeAgent 为 43.3±1.1/4.5±1.5/0.0；human best@3 为 72.4/20.4/8.9（Appendix I，Table 7）。
- JudgeEval 上 o3-mini-high 的 accuracy/precision/recall/F1 为 0.83/0.83/0.83/0.83，约 $66/篇；o1-high F1 为 0.84，约 $830/篇。o3-mini 的 Code Development F1 最低，为 0.72（§4.2，Table 2；Appendix G，Table 6）。
- PaperBench Code-Dev 上 o1 IterativeAgent 为 43.4±0.8%，但论文明确报告其与 full eval 仅弱相关，不能把静态代码分当作复现分（§2.6、§5.2，Table 5）。
- 646 次运行中监控发现 10 次访问 blacklisted resource，相关 submission 被置零；监控只是日志字符串匹配，需要人工复核（§2.5、Appendix E）。
- full o1 IterativeAgent 12 小时单篇约 $400，20 篇一次约 $8,000；SimpleJudge 另约 $66/篇。Code-Dev 预计每次约 $4,000，grading 约 $10/篇（§7）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| 当前 frontier agent 尚不能可靠复现完整 ML paper | §5.2，Table 3：最佳 BasicAgent 21.0±0.8% | 20 篇 ICML 2024、单 A10、12 小时、3 seeds、禁止作者代码 | strong |
| 失败主要发生在执行与结果，而非写代码 | Appendix I，Table 7：Claude 35.4/1.8/0.7，human 72.4/20.4/8.9 | rubric-weighted Code/Execution/Result Match；human 仅三篇子集 | strong |
| 增加时间本身不能解决 long-horizon failure | §5.4，Fig. 3：o1 约 1 小时后 plateau，24 小时后人类反超；48h human 41.4% vs o1 26.6% | 4 篇时间曲线，三篇共同终点；o1 IterativeAgent | medium |
| scaffold 设计会改变模型分数与排序 | §5.3，Table 3、4：o1 13.2→24.4，Claude 21.0→16.1 | BasicAgent vs 特定 IterativeAgent prompt；相同 12h/A10 | strong |
| o3-mini judge 是可用但不完美的自动评分器 | §4.2，Table 2：F1 0.83、$66/篇；Appendix G Table 6 的 Code node F1 0.72 | 5 个 partial replication 的 JudgeEval；非 adversarial | medium |

## Critical Analysis

### 论证链条

PaperBench 的 strongest argument 是通过设计把“源代码看起来对”“脚本确实运行”“结果真的匹配”分开，随后 Table 7 直接显示 agent 在三层之间断崖式下降。observation → protocol → result 的链条闭合，也比只由 LLM 阅读最终报告的 auto-research benchmark 更能抵抗 fabrication。

较强的外推是把 replication score 当作广义“AI R&D autonomy”。复现确实需要大量工程技能，但 benchmark 明确筛掉多机、闭源依赖、人工数据与 framework research，也不测 novelty、问题选择或实验设计。它是 long-horizon research engineering 的强 proxy，不是完整科研能力的同义词。

### 假设压力测试

如果允许使用作者代码，任务会从 reimplementation 转成理解、修复和验证，agent 排名可能改变；如果换到 H100、多 GPU 或更长 wall time，某些训练任务的 Execution 分会升高，但当前 o1 plateau 又说明 compute 并非唯一瓶颈。未来 agent 若在预训练中见过作者 repository，禁止浏览也挡不住 contamination。

rubric 根分数依赖 author-approved 权重。作者最了解贡献，却也可能偏好论文叙事中的 headline result；而 leaf 是 binary、parent 是线性加权，不能表达依赖关系：实现方法失败时，下游多个 result leaf 可能重复惩罚。Appendix A 已承认当前树的先后顺序只隐式编码 dependency。

### 实验可信度

20 篇、3 seeds、clean reproduction、作者参与 rubric 和 human time curve，使主结果比多数 agent benchmark 扎实。作者也诚实报告了 10 次 blacklist violation、judge cost、模型过早退出与 per-requirement failure。

主要不确定性来自自动 judge：JudgeEval 只有 5 个 partial replication，且提交由作者从零构建或修改原代码而来，不一定像真实 agent output；top-10 file selection 可能漏掉跨文件证据。o3-mini 总 F1 0.83 看似高，但 Code Development F1 仅 0.72，而大多数 agent 得分恰好来自 Code Development，ranking 可能对 judge error 敏感。论文没有给 human regrade 主 leaderboard 的置信区间。

人类比较也不是完全对称：8 位参与者按自信选题，best@3 与模型多次运行的聚合不同；参与者可用 ChatGPT/Copilot，且为兼职四周工作。不过这些选择整体更像是在构造“专家上限”，足以支持 agent 长程落后的定性结论，不足以给出严格的人机效率比。

### 系统性缺陷

- **可扩展性**：rubric 每篇需数十小时到数周专家劳动，20 篇扩到数百篇的成本很高；PaperBench Code-Dev 又牺牲最关键的 execution evidence。
- **可复现性**：网络依赖、包版本、HuggingFace/API credentials 与 Ubuntu/A10 环境会随时间漂移；论文未给长期 artifact preservation 或依赖镜像维护方案。
- **安全与隔离**：agent 可联网、执行任意代码并持有 API key；论文关注 blacklist cheating，未讨论 credential exfiltration、malicious package 或 resource abuse。
- **可观测性**：BasicAgent 会主动早停，IterativeAgent 则被迫持续工作；两者都缺少显式 experiment scheduler、failure recovery、budget allocator 与 checkpoint-aware planner。
- **成本公平性**：规则不限制 runtime/compute，leaderboard 若只看分数，会把模型能力、scaffold engineering 与资源预算混为一体。

## 局限与 Future Work

- **局限 1**：只有 20 篇，且经过单 A10 可行性筛选，不代表包含多节点训练、闭源模型或数据采集的 frontier ML research。
- **局限 2**：JudgeEval 小且非 adversarial；o3-mini 对 Code Development 的 F1 只有 0.72，主榜分数仍可能受 judge error 影响。
- **局限 3**：原作者代码在线造成未来 contamination 风险，blacklist 只能限制显式访问，不能检测训练时记忆。
- **局限 4**：完整 eval 单次约 $8,000 agent API cost 加 $1,320 grading，妨碍多 scaffold、多 seed、频繁回归测试。
- **局限 5**：rubric 权重与树结构由人工定义，dependency 未显式建模，可能重复奖励或惩罚关联 requirement。
- **Future work 1**：对 20 篇主榜按分层抽样进行 expert double-grade，报告 judge-induced ranking uncertainty，并构造隐藏 loophole/adversarial submissions 测 specification gaming。
- **Future work 2**：把 rubric tree 改为显式 dependency DAG，比较 leaf binary grading、subtree grading和 executable verifier 的成本、F1 与最终模型排序。
- **Future work 3**：固定 model、compute 与 12/36/48 小时预算，消融 persistent memory、job monitoring、failure recovery、parallel experiment scheduler，定位 plateau 来自哪种 long-horizon 控制缺陷。
- **Future work 4**：建立 hermetic container、dataset hash 与 cached dependency registry，按季度重跑一组 reference submission，量化 benchmark 随软件生态漂移的分数变化。
- **Future work 5**：同时提供 from-scratch 与 author-code-assisted 两条 track，测量“重实现能力”和“现实复现/审计能力”的差距。

## 相关

- **相关概念**：LLM Agent、Agent Scaffold、LLM-as-a-Judge、research replication、long-horizon planning
- **同类 benchmark**：[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[MLAgentBench-ICML24]]、RE-Bench、CORE-Bench
- **相关科研系统**：[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[AutoScientists-arXiv26]]
- **同主题**：[[Auto-Research]]
- **对比**：[[MLR-Bench-arXiv25]] 测完整 open-ended research pipeline 但 execution 证据弱；PaperBench 放弃 novelty，换取 clean re-execution 与细粒度 replication audit。
