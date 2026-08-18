---
type: paper
name: SR-Scientist
full_title: "SR-Scientist: Scientific Equation Discovery With Agentic AI"
authors: [Shijie Xia, Yuhan Sun, Pengfei Liu]
venue: ICLR
year: 2026
tags: [auto-research, symbolic-regression, scientific-discovery, llm-agent, reinforcement-learning, domain/auto-research]
source_pdf: "[[iclr26-xia-sr-scientist.pdf]]"
source_md: "[[iclr26-xia-sr-scientist]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# SR-Scientist：用智能体 AI 发现科学方程（ICLR 2026）

> **原题**：SR-Scientist: Scientific Equation Discovery With Agentic AI

> **一句话总结**：在 129 个合成 symbolic-regression 问题中，直接把 [[LLM]] 放进「数据分析—方程执行—反馈改写」长程闭环，比只让 LLM 充当 equation proposer 更有效；SR-Scientist 以 GPT-OSS-120B 将整体 Acc$_{0.01}$ 从 LLM-SR 的 28.16% 提至 63.57%，但该结论依赖强 BFGS 评估器、每题 1,000 次 LLM call 和已知生成方程的合成基准，尚不能等价为开放科学发现（§4.1–4.3，表 1）。

## 问题与动机

Symbolic regression（SR）试图从观测数据恢复简洁、可解释的方程。传统 genetic programming 在指数级表达式空间中搜索，神经方法则从大量合成数据直接预测表达式；近期 LLM-SR、LaSR 等方案利用 LLM 的科学先验提出候选方程，但 LLM 仍只是固定搜索流水线中的静态 proposer，不能主动分析数据、检查残差并据反馈改变探索策略。

SR-Scientist 的核心问题是：如果让智能体自己决定何时分析数据、何时提交方程、如何根据评估器反馈继续搜索，能否优于「LLM 生成候选 + 外部算法筛选」？作者将此表述为从 passive 工具到 autonomous 科学家的转变。不过论文实际覆盖的是一个验证器很强、目标函数明确的窄域：输入数值表格，输出不超过 10 个参数的可执行方程；它与 [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]] 同属 [[Auto-Research]] 中「生成器 + 硬评估器」路线，而不是完整的开放式科研生命周期。

## 关键观察 / 隐含假设

- **观察 1：数据分析是有效搜索动作，而不只是结果解释。** GPT-OSS-120B 移除数据-analyzer 工具后，Acc$_{0.01}$ 从 63.57% 降至 35.66%；Qwen3-Coder-480B 从 49.09% 降至 41.08%（§4.3，表 3）。
  - **依赖假设**：LLM 能从 tabular statistics、correlation 和 residual 中形成有用的结构假设；输入变量数量与数据规模仍适合在代码 interpreter 中探索。
  - **可能失效场景**：高维、稀疏、强混杂或必须依赖图像/频域特征的科学数据。主实验仅使用纯文本模型，论文也未提供 causal identifiability。

- **观察 2：固定总调用预算时，单次轨迹需要足够深，但越长不一定越好。** 将 maximum turns 从 10 增至 25，三个 backbone 的 Acc$_{0.01}$ 均上升；继续到 30 turns 则停滞或下降，GPT-OSS-120B 约从 63.5% 回落到 60.5%（§4.3，图 5）。
  - **依赖假设**：约 1,000 次 LLM call 的预算固定，turn 与独立 restart 可以互换；25 turns 的最优点可能是该基准、提示词与模型组合的产物。
  - **可能失效场景**：更强记忆、更长 context、不同工具延迟或需要数百步实验的任务，都会改变 depth–breadth 平衡。

- **观察 3：只保留 top-performing equations 的轻量记忆能跨迭代积累进展。** 移除 experience buffer 后，Qwen3-Coder-480B 的 Acc$_{0.01}$ 从 49.09% 降至 35.66%，GLM-4.5-Air 从 48.32% 降至 37.21%；随机采样历史方程也劣于前 k 名（§4.3，表 3）。
  - **隐含假设**：训练集上的 MAPE 排名与最终 ID/OOD 质量对齐，精英保留不会过早挤掉结构不同但潜力更高的候选。
  - **证据强度**：中。三种 backbone 的消融实验一致支持记忆有用，但只比较前 k 名、random 与 no-记忆，没有 diversity-aware 或失败-记忆基线。

- **假设 1：准确恢复合成方程可代表科学 equation 发现。**
  - **证据强度**：弱到中。LSR-Synth 用「known term + synthetic novel term」构造 129 题，并由两位专家检查，降低了直接记忆风险；但所有 ID/OOD 样本仍来自已知生成方程，缺少真实测量噪声、未观测变量和多解不可辨识性（§4.1）。

## 核心方法

SR-Scientist 采用类似 ReAct 的多轮智能体循环。每轮给定一个目标 MAPE，智能体在自然语言推理与两个工具之间自由切换：`data analyzer`（T1）允许写任意代码检查样本、统计量、相关性或残差；`equation evaluator`（T2）接收带常数占位符的 Python 方程，用 BFGS 拟合常数并返回误差。智能体可以据反馈反复改写结构，直到达到目标或耗尽最大轮数（§3.2，图 1）。

外层最多运行 40 轮，每轮最多 25 次交互。系统把探索过的方程及其 MAPE 放入经验缓冲区（experience buffer），下一轮取前 K 个作为上下文示例；若当前目标已达到便收紧目标，最后提交观测数据上误差最低的方程。这个设计回应了「长轨迹有用但上下文有限」的观察，却只保存成功方程，不抽象失败模式或维护结构多样性。

训练部分为 Qwen3-Coder-30B-A3B 构造 1,024 个合成问题：Claude 4 Sonnet 生成包含 known/novel terms 的 equation skeleton，再实例化常数与数值数据，两位作者手工去除与基准相似的方程。运行轨迹只跑一个迭代，以最佳方程的 MAPE 通过 log-线性 函数映射为连续 reward，再用 GRPO 训练 60 steps；训练使用 32 张 NVIDIA H200、每个提示词采样 8 个运行轨迹，并将 KL coefficient 设为 0 以鼓励探索（§3.3，§4.1，§C.1–C.3）。

这套方法与 [[FunSearch-Nature24]] 的共同点是把 LLM 的不可靠生成置于可执行评估器后；区别是 SR-Scientist 让智能体主动选择分析与评估动作，并用 BFGS 作为常数优化 oracle，而不是只进化固定程序 skeleton。相对 [[AlphaEvolve-arXiv25]]，它搜索的对象更窄、验证更便宜，也没有多目标 fitness 或生产环境部署。

## 设计取舍

- **自治性换取可验证性**：智能体可自由编排工具调用，但任务目标、两类工具、MAPE schedule、前 k 名记忆、参数上限与 BFGS 评估器都由人预设；所谓「minimal 人类-defined 流水线」是相对既有 SR 流水线的自治，不是无脚手架的科学家。
- **精英记忆换取简单性**：前 k 名 buffer 简单且有效，却不记失败原因、不鼓励新颖性；论文承认会重复探索差方程。
- **长程搜索换取成本**：每题最多约 1,000 次 LLM call；作者估算 GPT-OSS-120B/20B 分别为 \$0.25/\$0.10 每题，但价格基于特定 API 单价且未计 RL 的 32×H200 训练成本（§D.2，表 8）。
- **可聚合指标换取尾部真实性**：Acc-to-tolerance 比平均 NMSE 稳定，但计算时丢弃每个样本最差 5% predictions；这降低极端值影响，也可能掩盖真实科学场景最关键的失效区（§4.1，§D.1）。

## 实验与结果

- **主结果**：LSR-Synth 共 129 题，覆盖 chemistry 36、biology 24、physics 44、materials 25；在每题约 1,000 次 LLM call、三次重复下，GPT-OSS-120B 的 SR-Scientist 达到 Acc$_{0.01}$ 63.57% / Acc$_{0.001}$ 49.35%，对比同 backbone 的 LLM-SR 28.16% / 11.37%（§4.1–4.2，表 1）。
- **跨 backbone**：Qwen3-Coder-480B、GLM-4.5-Air、GPT-OSS-20B 的 Acc$_{0.01}$ 分别为 49.09%、48.32%、42.64%，对应 LLM-SR 为 41.08%、35.92%、33.33%；说明收益不只来自单一模型，但幅度从 8.01 到 12.40 个百分点不等（§4.2，表 1）。
- **RL 收益**：Qwen3-Coder-30B-A3B 经 RL 后，Acc$_{0.01}$ 从 32.30% 提至 40.92%，Acc$_{0.001}$ 从 16.02% 提至 20.69%；训练数据同样由合成 equation family 构造，跨真实域迁移仍未知（§4.2，表 1）。
- **组件消融**：GPT-OSS-120B 去掉 T1、experience、前 k 名后 Acc$_{0.01}$ 分别为 35.66%、57.36%、58.14%，完整系统为 63.57%；对 Qwen3-Coder-480B，随机历史采样甚至降至 26.36%（§4.3，表 3）。
- **symbolic exactness**：最佳 symbolic 准确率仅 7.75%（SR-Scientist + GLM），高于 LLM-SR 的 5.43% 和 PySR 的 4.65%，但表明多数数值上合格的答案并未恢复 ground-truth 结构（§4.2，表 2）。
- **噪声边界**：训练数据加入 Gaussian noise 后所有方法显著下降；在 $\sigma=0.01$ 时最佳模型从无噪声约 63.6% 降至约 18% Acc$_{0.01}$，到 $\sigma=0.1$ 仅约 10%–13%，虽仍领先基线，但绝对可靠性很低（§4.2，图 3）。
- **OOD**：Qwen3-Coder-480B 下总体 OOD Acc$_{0.01}$ 约 47%，略低于 ID 的 49.09% 且高于 LLM-SR；这里的 OOD 是同一生成方程取更高 temperature/time 区间，不是跨实验装置或跨机制分布（§4.2，图 2；§C.1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 智能体式分析—评估循环显著优于使用同一基础模型的 LLM-SR | GPT-OSS-120B：Acc$_{0.01}$ 为 63.57%，LLM-SR 为 28.16%（§4.2，表 1） | 129 个 LSR-Synth 合成问题；每题约 1000 次 LLM 调用；丢弃最差 5% 预测 | 强 |
| 数据分析工具是主要收益来源之一 | 移除 T1 后 GPT 从 63.57% 降至 35.66%，Qwen 从 49.09% 降至 41.08%（§4.3，表 3） | 三种前沿或编程基础模型；无真实实验数据 | 强 |
| 保留前 k 个经验有助于跨轮次长程优化 | 不使用经验时 Qwen 从 49.09% 降至 35.66%，GLM 从 48.32% 降至 37.21%；随机采样更差（§4.3，表 3） | 固定约 1000 次调用预算；只比较三种简单记忆策略 | 中 |
| 强化学习能提高智能体发现方程的能力 | Qwen3-Coder-30B 的 Acc$_{0.01}$ 从 32.30% 提高到 40.92%（§4.2，表 1） | 1024 个合成训练题；32×H200；同类型四学科基准 | 中 |
| 系统已具备稳健、可泛化的科学发现能力 | OOD 上仍领先，但 $\sigma=0.01$ 后最佳 Acc$_{0.01}$ 约降至 18%，符号准确率最高 7.75%（§4.2，图 2–3，表 2） | OOD 仍来自同一方程；高斯合成噪声；无真实湿实验或观测数据 | 弱 |

## 批判性分析

### 论证链条

「静态 proposer 缺乏数据反馈 → 给智能体可执行分析/评估工具 → 长程轨迹与记忆累积候选 → 准确率提升」这条局部链条闭合得较好：T1、记忆、前 k 名和 turn 数都有消融，且多 backbone 结果方向一致。尤其 T1 的大幅下降说明收益不只是增加 token 或多采样。

跳步出现在命名与外推：论文把一个受控 symbolic-regression optimizer 称为 autonomous 科学家，并将合成方程 recovery 外推为科学发现。它没有选择研究问题、设计采样实验、处理不可辨识模型、提出因果机制或请求新数据；ground-truth equation 与评估器均已给定。更准确的定位是「agentic symbolic regression with 可执行反馈」。

### 假设压力测试

方法最依赖 cheap、稠密、可信的评估器。BFGS 不仅打分，还替智能体优化常数，因此 LLM 主要搜索结构；若实验反馈昂贵、异步、有噪声，或单次验证需要湿实验，40×25 的交互预算不可直接移植。多变量共线、hidden variable、piecewise/discontinuous mechanism 也可能使 correlation-based 分析误导。

experience buffer 以 observed-数据 MAPE 排序，默认训练拟合与 OOD/结构正确性一致。表 2 的最高 symbolic 准确率只有 7.75%，已经显示数值 fitness 与真实结构之间有明显缝隙。若研究目标强调机制解释而不只是预测精度，需要复杂度惩罚、equivalence checking、uncertainty 与 diversity-aware selection。

### 实验可信度

优点是基线覆盖 GP、deep SR 与 LLM-SR/LaSR，LLM 方法统一约 1,000 calls，实验重复三次，并对数据工具、记忆、turn 预算做了直接消融。作者也专门构建含 novel terms 的 LSR-Synth，降低模型背诵教科书方程的风险。

主要边界有三点。第一，100,000 个传统候选与 1,000 次 LLM call 只控制候选/调用数量，没有统一 FLOPs、wall time 或 token 成本；BFGS 与代码执行的计算也未纳入等价预算。第二，OOD 仅是同一方程在参数轴尾部的 extrapolation，不能支持跨机制 泛化。第三，Acc-to-tolerance 丢弃最差 5% predictions，噪声图又显示轻微噪声即可让绝对准确率剧降，因此稳健性论断应理解为「相对基线更稳」，不是「在噪声下可靠」。

symbolic 准确率先由 GPT-OSS-120B 投票 10 次，票不一致时才交给人；作者在 121 个 unanimous cases 上报告与人工 **98.3%** 一致（§D.6）。该流程比纯 LLM 评审器严谨，但仍以同一模型家族参与系统与评估，且 exact recovery 绝对值很低。

### 系统性缺陷

- **资源与复现**：主推理可用 API，但 RL 使用 32×H200；论文只给估算 API 价格，未报告各 backbone 的 token 分布、工具执行成本、能耗或端到端 P50/P95 延迟。
- **沙箱与安全**：智能体可写任意分析代码，论文未讨论代码沙箱、资源限额、恶意/失控执行或数据泄露。
- **故障恢复与可观测性**：buffer 保存方程和分数，但未说明 API 失败、invalid 代码、BFGS 不收敛、长任务 checkpoint/restart 的语义。
- **选择偏差**：最终取观测数据上最佳方程，缺少验证-aware selection 与多重假设校正，可能在 1,000 次尝试后过拟合。
- **规模扩展**：129 题可 batch 推理，作者报告本地 2×H100 不超过 5 小时（§D.2），但没有并发度、单题尾延迟或随变量数/表达式长度增长的曲线。

## 局限与后续工作

- **真实数据迁移**：在带 测量 noise、hidden variables 和 irregular sampling 的公开科学数据集上，与 PySR/LLM-SR 按实际时间、energy、候选评测数三种预算分别对比；预注册 Acc、symbolic equivalence 与 calibration。
- **主动实验设计**：允许智能体选择下一批观测点，测量在固定采样预算下恢复方程所需数据量是否低于 passive sampling；这才检验智能体是否能从「分析已有表格」迈向实验设计。
- **记忆机制**：对比前 k 名、Pareto（error/complexity/新颖性）、diversity 档案库与失败-summary 记忆，报告重复方程率、unique structure 数及 OOD 准确率。
- **噪声处理**：在 $\sigma=0.01/0.05/0.1$ 下加入 robust loss、bootstrap uncertainty 与异常值建模，目标应是提升绝对 Acc$_{0.01}$，而非只保持相对排名。
- **结构可信度**：将 symbolic equivalence 验证器或最小描述长度纳入 selection，检验能否把最高 7.75% symbolic 准确率提升而不牺牲 OOD prediction。
- **系统审计**：公开每次工具 call、候选方程、BFGS 状态与 token/成本轨迹，使不同智能体脚手架能在相同 replay harness 下复现。

## 相关

- **相关概念**：[[LLM]]、Symbolic Regression、Agentic AI、Reinforcement Learning、experience 记忆、可执行评估器
- **同类系统**：[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AI-Scientist-arXiv24]]
- **同主题**：[[Auto-Research]]
- **同会议**：ICLR 2026
- **对比**：相对 FunSearch/AlphaEvolve，SR-Scientist 让智能体自主调用数据-分析工具，但评估器与任务边界更窄；相对 LLM-SR，核心增量是长程工具 interaction、跨迭代 experience 与智能体 RL
