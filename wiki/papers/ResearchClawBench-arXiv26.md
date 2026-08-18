---
type: paper
name: ResearchClawBench
full_title: "ResearchClawBench: A Benchmark for End-to-End Autonomous Scientific Research"
authors: [Wanghan Xu, Shuo Li, Tianlin Ye, Qinglong Cao, Yixin Chen, et al.]
venue: arXiv
year: 2026
tags: [auto-research, scientific-discovery, benchmark, research-agent, llm-as-a-judge, domain/auto-research]
source_pdf: "[[arxiv26-xu-researchclawbench.pdf]]"
source_md: "[[arxiv26-xu-researchclawbench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# ResearchClawBench：端到端自主科研基准（arXiv 2026）

> **原题**：ResearchClawBench: A Benchmark for End-to-End Autonomous Scientific Research

> **一句话总结**：ResearchClawBench 把 10 个科学领域的 40 篇已发表论文隐藏为 target，为智能体提供问题、相关文献、原始数据和可执行环境，再由 GPT-5.1 按专家从 target paper 抽取的文字/图像 rubric 评分；最佳自主智能体 Claude Code 平均仅 21.5/100，距论文级重发现锚点 50 很远，但该分数验证的是对隐藏论文证据链的重建，不是新发现已经通过专家、独立重执行或湿实验确认（§3–§6，表 5–6，图 5–7）。

## 问题与动机

传统科研问答测试可以验证局部知识，却不能要求系统把问题理解、文献调查、实验设计、代码执行、证据组织和论文写作连成闭环；完全开放的“请做研究”又缺少可复核真值。本文试图在两者之间找到可评测的中间点：以真实已发表研究为参考，但不向系统暴露 target paper，让系统从相同目标、相关文献和原始数据独立恢复关键证据。

这一设计把“端到端”落到可观察产物上：实验代码与执行过程、中间结果和图表、最终研究报告。它比只看 final metric 的 coding benchmark 更接近科研工作流，也比开放式专家主观打分更可批量运行；代价是答案空间仍由隐藏论文的贡献结构锚定，系统最容易获得信用的行为是**重发现已知结果**。

论文提出参考锚定发现分数（Reference-Anchored Discovery Score, RADS）：50 分表示证据达到 target paper，低于 50 表示证据不足，高于 50 只表示“可能具有超越参考研究的发现潜力”。作者明确说明，高于 50 不是经过验证的新发现。因而本工作的核心证据应归为**科研重发现能力评测**，而不是“科学发现成功”。

## 关键观察 / 隐含假设

- **观察 1：现有智能体能生成专业报告，却经常缺失决定性科学证据。** 七个智能体的 Professionalism 多在 70 分以上，但主 RADS 最佳均分只有 21.5，且四个补充质量维度与 rubric 分数相关性弱（§4.2–4.3，表 5–6）。
  - **依赖假设**：rubric 确实覆盖了 target paper 的决定性证据，而不是只覆盖了专家容易形式化的段落和图。
  - **可能失效场景**：系统采用同样有效但不同于 target 的分析路径时，参考锚定 rubric 可能把真正正确的替代证据判成缺失。

- **观察 2：失败主要发生在协议和证据链，而不是工具完全无法执行。** 280 次自主智能体运行中，实验设计不匹配、证据不匹配、科学核心缺失分别出现在 89.5%、78.5%、68.0% 的运行；执行失败仅 1.5%（§4.5，图 6）。
  - **依赖假设**：由 rubric 缺项映射到错误类型的规则能区分“没有做”与“做了不同但合理的实验”。
  - **可能失效场景**：target paper 自身协议不是唯一正确路线，或任务材料不足以推导其隐含设置时，偏离协议不等于科研能力不足。

- **观察 3：不同系统对任务难度的判断高度一致，但没有单一系统普遍占优。** Claude Code 只在 40 题中的 12 题获胜；自主智能体两两任务分数相关的中位数为 0.77、范围为 0.64–0.86，说明困难更多来自任务本身而非单一脚手架（§4.2）。
  - **依赖假设**：不同系统获得了可比的时间、token、网络和工具权限；论文没有给出一个统一的硬性 task budget 来完全排除资源差异。

- **假设 1：隐藏 target paper 可充当“同一科学目标下的人类参考研究”。**
  - **证据强度**：**中**。真实论文提供可审计证据链，但单篇论文可能不完整、有争议，且只代表一种研究路径。

- **假设 2：GPT-5.1 能稳定地把文本和图像产物映射到专家 rubric。**
  - **证据强度**：**偏弱**。rubric 由专家构建并交叉检查，但论文没有报告 judge–专家一致性、重复评分方差或 adversarial report 测试。

## 核心方法

**任务构建。** 领域专家筛选问题清楚、数据可得且有研究价值的论文，抽取核心问题，整理相关文献与原始数据，再把 target paper 的关键文字、定量结果、机制和图像制成带权 rubric。另一位专家交叉检查并过滤不合格任务。最终形成 40 题，覆盖 Astronomy、Chemistry、Earth、Energy、Information、Life、Material、Math、Neuroscience 和 Physics 十个领域（§3.1–3.2，图 2–3，表 3）。论文没有报告初筛论文总数和各环节淘汰数，因此无法估计构建选择偏差。

**统一任务包。** 被测系统看到 task description、related literature、raw data 与 executable environment，看不到 target paper；需要留下代码、执行轨迹、中间文件、图和报告。任务可分为 target optimization 与 diagnostic analysis，但最终都以是否恢复或推进参考研究的关键 artifact 评分（§3.1、§3.4）。

**ResearchHarness。** 为没有原生 agent scaffold 的 17 个模型提供轻量 ReAct 循环。工具面包括 Serper 搜索、Jina Reader 网页读取、本地文件和图片读取、MinerU PDF 抽取、一次性 shell 与持久 terminal；历史接近 128k token 时自动压缩为记忆（§3.3，表 4）。这使模型可以参加同一 benchmark，但 harness 与原生 agent 的工具、提示和上下文管理仍不完全相同。

**RADS 与补充指标。** GPT-5.1 对最终报告及生成 artifacts 逐项检查专家 rubric，文字和图像项各自加权，满分 100，50 为 target-paper-level。另从完整性、深度、指令遵循和专业性四个维度评价报告，以区分“写得像论文”和“恢复了关键证据”（§3.4、§4.3）。论文没有描述对最终 code 的统一重执行、环境 checksum 或数值 oracle；可执行环境是任务条件，不等于评分时每个结果都被独立重算。

## 设计取舍

- **真实论文锚定换取答案封闭性**：rubric 可检查，但系统若发现 target 未报告的新模式，只能由同一个参考框架判断其“超越”，没有独立验证协议。
- **跨十领域换取单域深度**：40 题能暴露跨域不稳定性，却平均每域只有 4 题；很难把领域排名外推为能力画像。
- **最终产物评分换取过程盲区**：保存代码和中间 artifacts 提高可审计性，但主分数仍围绕最终报告；错误在哪一步出现、工具结果是否被忠实使用未被细粒度量化。
- **统一轻量 harness 换取系统可比性问题**：17 个模型共享 ResearchHarness，而七个原生 agent 保留各自 scaffold；表 5 不能干净分离 base model、agent design 与预算。
- **参考阈值 50 换取直观尺度**：50 是人工定义的锚点，不是统计校准后的“论文复现概率”；超过阈值也没有自然转化成 discovery validity。

## 实验与结果

- 所有系统运行 40 题，主文称评测七个自主 agent 与 17 个 ResearchHarness 模型。最佳自主 agent Claude Code 平均 21.5，最佳 harness 模型 Claude-Opus-4.7 平均 20.7，均远低于 50（§4.1–4.2，表 5）。
- Claude Code 只赢 12/40 题；不同模型各自在不同领域领先，说明聚合均分掩盖了明显的 domain–system interaction（§4.2）。
- 在 280 次自主智能体任务运行中，实验设计不匹配的 error rate 为 89.5%，相比执行失败的 1.5% 高 88.0 个百分点；证据不匹配和科学核心缺失分别为 78.5% 与 68.0%（§4.5，图 6）。
- 成本与均分相关系数为 0.66、决定系数为 0.44；运行时间与均分相关系数为 0.54、决定系数为 0.29。Claude Code 约 5.1 美元/题、27 分钟/题，Opus-4.7 harness 约 4.9 美元/题、26 分钟/题；资源投入只解释部分差异（§4.4，图 5）。这些运行是几十分钟级，不能证明数天状态保持。
- Physics_002 上，OpenClaw 虽为该题最佳 agent，也只有 27.45：它恢复直接 XEB 趋势，却漏掉多尺度分析、验证、mirror-circuit 推断、gate-counting error model 与多估计器一致性（§4.6，图 7）。
- 附录四个详细案例进一步暴露“报告完整但证据未执行”：Math_003 的 task winner 得 29.6，却主要复述 AlphaGeometry 已知结果而未运行系统；Energy_000 用时约 27 分钟仍产生与参考数量级不符的 RMSE（附录 D）。
- 报告的 frontier mean 口径内部不一致：自主 agent 在引言写 24.6、§4.2 写 25.8；摘要和正文给 LLM frontier 26.5。frontier 是逐题取不同系统最佳后的 oracle 聚合，不能与单系统均分直接比较。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 当前 agent 距可靠的 target-paper-level 重发现很远 | §4.2、表 5：最佳自主 agent 21.5，最佳 harness 模型 20.7，参考锚点为 50 | 40 个干实验任务；每配置每题看似单次运行；GPT-5.1 评分 | 中偏强 |
| 主要瓶颈是科学协议和证据链，而非程序完全跑不起来 | §4.5、图 6：设计不匹配 89.5%、证据不匹配 78.5%、核心缺失 68.0%，执行失败 1.5% | 错误标签由 target rubric 派生；可多标签重叠 | 中 |
| 报告专业性不能代理科研正确性 | §4.3、表 6：Professionalism 多超过 70，且补充指标与 rubric 分相关性弱 | 同一个 LLM-as-a-judge 体系；未做人类对齐 | 中 |
| 更高成本和更久运行只带来有限可预测收益 | §4.4、图 5：cost/score `r = 0.66`，runtime/score `r = 0.54` | 跨不同模型和脚手架的观察相关，不是受控 scaling 实验 | 中偏弱 |
| RADS 能验证新科学发现 | 只有“50 以上代表 reference-surpassing potential”的定义；作者明确说不等于 validated discovery | 无独立重执行、专家确认或湿实验 | 弱／不成立 |

## 批判性分析

### 论证链条

“科研任务需要端到端证据 → 真实论文能提供锚点 → 隐藏论文并要求重建 artifacts → 当前系统普遍漏掉关键证据”的主链条成立。40 个任务、跨域数据和具体 error taxonomy 比只给一个 final score 更有诊断价值。

真正需要收窄的是从 re-discovery 到 discovery 的跃迁。RADS 的 50 分阈值只说明 rubric evidence 不弱于 target；它既不能证明新结论正确，也不能证明 target 之外的机制具有 novelty。将分数高于 50 命名为“discovery potential”可以作为 triage 指标，却不能把基准归入经专家、独立复现或湿实验确认的科学发现证据层。

### 假设压力测试

如果 target paper 使用一套有争议的 preprocessing，而智能体选择更稳健方案，rubric 可能同时触发 protocol mismatch 与 evidence mismatch。反过来，智能体也可能从相关文献复述 target 的关键词和图形形态，在没有忠实执行分析时得到部分分数。附录 Math_003 的高分案例正显示，final-report judge 与真实执行之间仍有缝隙。

隐藏 target 不等于防污染。系统拥有 web search 和 related literature，可能定位到原论文或高度相似材料；论文没有报告检索泄漏审计。即使没有直接找到 target，训练数据记忆也会让“重发现”混入文献回忆。严格版本需要离线网络、时间切分或未公开数据来量化这部分贡献。

### 实验可信度

专家构题、跨专家检查、原始数据和多模态 rubric 是明显优点；逐题结果与详细案例也让失败不只停留在均分。然而，主实验缺少重复 seed、置信区间和统一 wall-clock/token 上限，运行成本与时长又差异较大。一个系统每题一次运行不足以区分架构能力和采样偶然性。

论文还存在评测配置口径问题：正文列出七类 agent，却在 per-task 表中同时给 EvoScientist v0.0.4/v0.1.1，形成八个配置；错误分析仍按 `7 × 40 = 280`，未说明排除了哪一列。自主 frontier 的 24.6/25.8 也前后不一致。这些不改变“均低于 50”的结论，但削弱精确比较。

### 系统性缺陷

- **验证闭环不足**：最终评分没有统一代码重执行和数值 verifier，图与数字可能来自错误运行、旧缓存或报告幻觉。
- **评审器单点风险**：GPT-5.1 同时承担跨十领域的主评分，未报告 human agreement、judge seed 或模型替换敏感性。
- **任务泄漏风险**：web 可用且 target 源自已发表论文，没有检索命中审计或训练污染控制。
- **预算不可比**：原生 agent 与 ResearchHarness 的工具、终止策略、上下文压缩和成本不同；资源–分数图是观察性结果。
- **长程范围有限**：平均二十多分钟级的运行展示多步工具使用，不是十几小时到数天的状态一致性测试。

## 局限与后续工作

- **局限 1**：40 题都以现有 data/code/literature 做 dry-lab 分析，不覆盖样本制备、仪器、伦理与真实实验失败。
- **局限 2**：主指标锚定已发表论文且主要看 final report，过程忠实性和 target 之外的正确发现都难评分。
- **局限 3**：没有重复运行、统一预算、人类 judge 对齐或最终 artifacts 的独立重执行。
- **局限 4**：论文未报告论文筛选分母、淘汰原因和每题专家工时，基准可扩展性与选择偏差未知。
- **后续工作 1**：为 rubric item 绑定可执行 notebook、数据 checksum 与数值容差，分别报告 report score 和 independent rerun score。
- **后续工作 2**：每个系统每题运行至少 3 个 seed，在统一美元、token 和 wall-clock 上限下报告均值、best-of-k、失败率与置信区间。
- **后续工作 3**：让领域专家盲评所有高于 50 或声称 novel 的结果，并要求独立重执行；涉及实验科学时再进入真实实验验证。
- **后续工作 4**：加入未公开、时间切分数据与禁网条件，比较有无检索时的分数，测量论文定位和记忆污染。

## 相关

- **相关概念**：[[LLM]]、科研智能体、LLM-as-a-评审器、科研重发现、过程评测
- **同类基准**：[[PaperBench-ICML25]]、[[RE-Bench-ICML25]]、[[HeurekaBench-ICLR26]]、[[InnovatorBench-ICLR26]]
- **相关系统**：[[DeepScientist-ICLR26]]、[[Co-Scientist-Nature26]]
- **相关主题**：[[Auto-Research]]
- **发表状态**：arXiv 2026
