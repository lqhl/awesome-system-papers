---
type: paper
name: FunSearch
full_title: "Mathematical discoveries from program search with large language models"
authors: [Bernardino Romera-Paredes, Mohammadamin Barekatain, Alexander Novikov, Matej Balog, M. Pawan Kumar, et al.]
venue: Nature
year: 2024
tags: [auto-research, evolutionary-search, program-synthesis, scientific-discovery, combinatorics, llm]
source_pdf: "[[funsearch.pdf]]"
source_md: "[[funsearch]]"
---

# Mathematical discoveries from program search with large language models (Nature 2024)

> **一句话总结**：DeepMind FunSearch 在「**易评估、难求解**」问题上把 frozen [[LLM]] 当 mutation/crossover operator、用可执行 evaluator 过滤幻觉，在 **function space** 而非解空间做 island-based 进化；cap set $n{=}8$ 从 496 推到 **512**、capacity 下界 20 年来首次从 2.2180 提到 **2.2202**，online bin packing excess-bin 从 Best-Fit 的 3.79–5.81% 压到 **0.03–5.30%**——首例 LLM 在开放数学难题上产出**外部可验证**新结果。

## 问题与动机

[[LLM]] 在代码合成与复杂推理上能力暴涨，但 **confabulation / hallucination** 使其难以直接用于科学发现：生成的 cap set 构造可能语法优美却数学错误。既有 [[Evolution-through-Large-Models]] 类工作多在合成 benchmark、[[Neural-Architecture-Search]] 或小 puzzle 上改进，**尚未在公认开放难题或工业算法上做出超越人类 SOTA 的可验证突破**。

另一方面，大量数学与组合问题属于「**easy to evaluate, hard to solve**」：`evaluate(solution)` 可在多项式时间内可靠打分，但解空间指数爆炸（cap set 在 $n{=}8$ 约 $3^{1600}$）。传统计算机搜索往往直接枚举解（向量列表），难以 scale、也难让人类专家从结果中提炼结构。FunSearch 要回答：**如何把 LLM 的创造力与 evaluator 的可验证性耦合，在 function space 搜索「生成解的程序」而非解本身，并真正超越已知最优？**

## 关键观察 / 隐含假设

- **观察 1：结构化问题的真解往往对应短程序（低 [[Kolmogorov-Complexity]]），搜索程序比枚举解更可扩展。** $\mathcal{A}(24,17)$ 明文要 20 万+ 向量，生成程序仅数十行；population sampling 还偏好更短程序，形成对简洁构造的归纳偏置。cap set / admissible set 实验直接支撑该观察。
  - **依赖假设**：目标问题高度结构化、非随机；关键逻辑可压缩进一个小函数（如 greedy 的 `priority`）。
  - **可能失效场景**：解本质无短描述（随机实例、需全局耦合的约束）；skeleton 把表达力锁死在 greedy + priority 模板时，最优构造可能根本不在可达程序族内。

- **观察 2：LLM 不必「懂题」，只需在 skeleton 约束下产出语法正确、偶尔有创意的局部变异；进化 + evaluator 负责累积改进。** 作者明确说 LLM 贡献的是多样代码与偶发想法，而非深度领域知识；配合 **best-shot prompting**（$k{=}2$ 个历史程序拼 prompt）和 islands 多样性，边际改进可滚成 SOTA。
  - **依赖假设**：存在可执行的 **program skeleton**，把 boilerplate 固定、只进化 10–20 行关键逻辑；`evaluate` 返回**连续、信息丰富**的 fitness（非二值 pass/fail）。
  - **可能失效场景**：定理证明等只有二值正确性信号的任务（论文 Discussion 自认不适配）；skeleton 设计错误会导致大量样本直接执行失败。

- **观察 3：吞吐导向的异步分布式架构让「百万级 LLM sample + 分钟级 evaluation」在可接受成本内可行。** 典型配置 **15 samplers（GPU）+ 150 CPU evaluators（5×32）**，LLM 推理与程序执行并行；$\mathcal{I}(15,10)$ 实验约 **200 万**程序，云成本约 **\$800–\$1400**、能耗 **250–500 kWh**（约为训练 StarCoder 的 0.5%）。
  - **依赖假设**：evaluation 可 embarrassingly parallel；快推理 LLM（[[Codey]] / [[PaLM2]]）优于慢而强的模型，因总 sample 数 $\sim 10^6$ 决定上限。
  - **可能失效场景**：单次 evaluation 达小时级（后作 [[AlphaEvolve-arXiv25]] 场景）时，本架构的 evaluator 瓶颈会恶化；闭源 API 依赖使外部复现与成本审计受限。

- **假设 1：超越公开 SOTA 即可反驳「只是从训练集检索」的质疑。**
  - **证据强度**：**中强**——$n{=}8$ cap 512、capacity 2.2202 均为文献可查新记录；但论文未做训练语料污染的系统审计，论证依赖结果新颖性而非直接测量。

- **假设 2：online bin packing 上 First Fit / Best Fit 足以代表工业实践基线。**
  - **证据强度**：**弱**——论文承认存在 worst-case 更优的在线算法族，但称实践中 FF/BF 更常用；未与 [[Genetic-Programming]] / hyper-heuristics 文献中的 evolved heuristic 做 head-to-head。

## 核心方法

FunSearch 输入为：**`evaluate(solution) -> score`**、初始 trivial 程序、以及含固定 skeleton 的 solve 模板（只进化如 `priority(...)` 或 `heuristic(...)` 的核心函数）。循环为：programs database 采样 → 构造 prompt → frozen LLM 生成新函数 → evaluator 执行 `main()` 打分 → 合法程序入库。

**Best-shot prompting**：从单岛采样 $k{=}2$ 个程序，按分数升序标为 `priority_v0/v1`，prompt 末尾留 `priority_v2` 空头让 LLM 续写——促使模型跨样本归纳改进模式；ablation 显示 $k{=}1$ 明显更差，$k{=}2$ 后收益递减。

**Programs database + [[Island-Model]]**：$m$ 个岛独立进化；每 **4 小时**淘汰一半最差岛，用幸存岛 best 程序克隆重初始化，兼顾探索与避免局部最优。岛内按 **signature**（各测试输入得分向量）聚类，cluster 用 Boltzmann 选择偏好高分，簇内再偏好**更短**程序——与 [[Genetic-Programming]] 随机变异相比，[[LLM-as-Mutator]] 省去手工定义 mutation primitive。

**异步分布式**：database / samplers / evaluators 三类 worker 松耦合通信（基于 launchpad + sandbox 执行不可信生成代码）。评估失败（超时、OOM、非法输出）直接丢弃，形成对幻觉的硬过滤。

**人机协同闭环（cap set 案例）**：对 $\mathcal{I}(12,7)$ 生成程序人工读码，发现四组 coordinate triple 的 cyclic 对称；把 symmetry 硬编码进搜索空间后，进一步得到 $\mathcal{I}(15,10)$ 与 $\mathcal{A}(24,17)$——「**inspect code → spot pattern → refine search**」首次在数学发现管线中示范。后作 [[AlphaEvolve-arXiv25]] 将同一范式扩展到整文件 diff、frontier LLM 与多目标 fitness，样本量从百万降到数千但评估可更贵。

## 设计取舍

- **Function space vs solution space**：程序可解释、可部署、可压缩，使 SAT 不可达的 $\mathcal{I}(15,10)$、$\mathcal{A}(24,17)$ 仍可搜索；代价是强依赖用户提供的 skeleton 与 greedy 模板，可能错过非贪心构造。

- **固定 skeleton vs 全程序进化**：聚焦关键逻辑显著提高合法程序比例（ablation「W/O Skeleton」在 $\mathcal{I}(15,10)$ 上无法满规模）；代价是人为限制表达空间，需要领域专家设计 skeleton。

- **快推理 LLM vs 高质量 LLM**：选 [[Codey]] 追求 sample 吞吐，总采样 $\sim 10^6$；StarCoder 略弱但仍能破 capacity 记录，说明代码语料比具体权重更关键，但最强结果仍依赖闭源 API。

- **Islands + 周期性灭岛 vs 单种群**：灭岛防止全体陷入同一局部最优；代价是超参敏感（岛数、重置周期、温度 $T_{\mathrm{cluster}}$），且 hardest 任务（$n{=}8$ 直接构造）成功率极低。

- **连续 fitness vs 二值验证**：cap set 大小、excess-bin 比例、满足子句数等连续信号支撑进化；无法提供丰富分数的问题（自动定理证明）被排除在 scope 外。

- **边界条件**：问题需「秒–分钟级」可并行 evaluation、可隔离的进化块、且存在从 trivial 出发的改进路径；不适合湿实验、无 simulator 的调度问题或 evaluator 易被 hack 的代理指标。

## 实验与结果

- **Cap set 直接构造**：$n{=}3\ldots7$ 追平已知最优；**$n{=}8$ 得 512**，超过此前 496；**140 次独立实验仅 4 次**达到 512，说明 headline 结果方差极大。
- **Admissible sets / capacity**：$\mathcal{I}(12,7)$ 将下界推到 **2.2184**；读码发现对称性后，$\mathcal{I}(15,10)$ 得 **2.2194**，$\mathcal{A}(24,17)$（size 237984）得 **2.2202**——**20 年来最大下界提升**，仍远低于上界 2.756。
- **SAT 对比**：CP-SAT 在 $\mathcal{I}(12,7)$ 以上即失败，FunSearch 在加入 discovered symmetry 后可满规模 $\mathcal{I}(15,10)$。
- **Online bin packing**：OR1–OR4 与 Weibull 5k/10k/100k 上 excess-bin 全面低于 First Fit / Best Fit（如 Weibull 100k：**0.03%** vs Best Fit **3.79%**）；训练仅用 OR1 规模实例，测试更大规模仍改进。10 次重复在 Weibull 10k 上平均 **0.44%±0.11%** excess。
- **Ablation（$\mathcal{I}(15,10)$）**：去 skeleton、去进化、减多样性、$k{=}1$ 均难满规模；随机 AST 变异显著弱于 LLM。
- **附录**：Shannon capacity（$\mathcal{C}_{11}$ 改进）、corners problem 新下界、与 [[AlphaEvolve-arXiv25]] 共享多位作者，构成 DeepMind auto-research 演进前奏。

## Critical Analysis

### 论证链条

作者链条清晰：**幻觉 LLM 不能单独发现 → evaluator 硬过滤 → 程序空间搜索压缩解 → 进化累积边际改进 → 超 SOTA 即新颖**。cap set 与 admissible set 上 evaluator 为确定性数学检查，链条闭合度高。薄弱环节在 **(1) 最难的 $n{=}8$ 直接构造成功率 <3%**，headline 512 依赖多次试验与运气，论文诚实报告但 Nature 叙事易让读者高估稳定性；**(2) bin packing 链条外推到「工业调度」** 时，只验证模拟分布与 OR-Library，未接真实 cluster trace；**(3) 对称性二次突破** 有人类读码参与，全自动闭环在 hardest 数学问题上并未完全闭合。

### 假设压力测试

| 假设 | 论文内证据 | 可能失效 |
|------|-----------|----------|
| 短程序偏置 | $\mathcal{A}(24,17)$ 压缩性、偏好短程序 | 非结构化或无贪心充分性时 |
| LLM 当通用 mutator | 优于手工 AST 变异 | 低资源语言、极长函数、无 API 时 |
| FF/BF 为强基线 | 全面碾压 Table 1 | 对 GP/hyper-heuristic、predictions-augmented online BP 未比 |
| 新颖性 ⇔ 非记忆 | 破 20 年记录 | 未系统检测 pretraining 污染 |
| 跨规模泛化 | OR1 训练 → OR4/100k 测试仍赢 | 分布偏移更大（重尾、相关性 item）时未测 |

### 实验可信度

- **数学实验**：benchmark 为领域公认开放问题，baseline 为历史人类构造 + SAT，可信度高；统计上 admissible set **15/15** 次破纪录，bin packing **10/10** 次赢 FF/BF，但 $n{=}8$ cap **4/140** 成功率提示不能把单次 Nature 结果当稳定算法。
- **Bin packing**：metric（相对 L2 下界的 excess-bin %）合理，但 baseline 偏「教科书」而非研究前沿；训练/测试分布部分重叠（同族合成实例），泛化 claim 对 OR 系列强于对任意工业 workload。
- **Ablation**：在 $\mathcal{I}(15,10)$ 上做组件剔除，支撑 skeleton / evolution / diversity 必要性；LLM 对比仅两种模型 + 一种随机变异，未覆盖开源 frontier 模型。
- **成本透明度**：给出 \$800–\$1400 与 kWh 估算，利于判断「百万 sample 是否划算」；外部团队用 StarCoder 复现门槛仍高（工程 + 分布式 + 2 天 GPU farm）。

### 系统性缺陷

- **人工 skeleton 与后验对称注入**：全自动程度低于摘要暗示；复杂问题仍需专家写 greedy 框架并解读程序，与 [[AI-Scientist-arXiv24]] 的「端到端科研」不是同一路线。
- **Evaluator 工程**：论文未讨论 sandbox 逃逸、恶意生成代码、evaluation 侧 channel 安全；生产部署需额外隔离层。
- **尾延迟与可观测性**：异步系统下 samplers/evaluators 慢节点如何拖尾、如何调试「为何 136/140 次失败」——论文未讨论可观测性与故障恢复，属 **论文未讨论** 的运维风险。
- **闭源依赖**：主结果用 [[Codey]] API；可复现性依赖 Google 基础设施与内部 launchpad，社区 fork（GitHub funsearch）为单线程简化版，难复现 Nature 级数字。
- **多目标与约束**：单标量 fitness，未处理多约束调度；与 Borg 级多目标优化（后作 AlphaEvolve）比表达力窄。

## 局限与 Future Work

- **局限 1**：仅适用于 **高效 evaluator + 丰富标量 fitness + 可隔离 skeleton** 三类前提同时满足的问题；定理证明等二值信号领域需另建 reward（论文自认）。
- **局限 2**：cap set capacity **2.2202 仍远低于 2.756 上界**；$n{=}8$ 直接构造成功率极低，说明方法在「无对称先验的硬构造」上仍脆弱。
- **局限 3**：bin packing 基线与工业场景有 gap；未验证与 learning-augmented / 强 worst-case 在线算法对比。
- **Future work 1**：用更强、更便宜的 [[LLM]] 推理（论文预判）在同等 \$800 预算下提高 hardest 任务成功率——应报告 **成功率–成本–sample 数** 三维曲线，而非只报 best run。
- **Future work 2**：自动推断 skeleton 或 symmetry hint，减少人类读码环节，向 [[AlphaEvolve-arXiv25]] 的 `# EVOLVE-BLOCK` 与 meta-prompt 共进化靠拢。
- **Future work 3**：对「训练集污染」做 retrieval / membership 审计，巩固「真发现」claim；对 bin packing 用公开 hyper-heuristic 冠军与真实 datacenter trace 重测。

## 相关

- **相关概念**：[[Evolutionary-Search]]、[[Genetic-Programming]]、[[Program-Synthesis]]、[[Island-Model]]、[[LLM-as-Mutator]]、[[Kolmogorov-Complexity]]、[[LLM]]、[[Neural-Architecture-Search]]
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[Auto-Research-arXiv25]]、[[BES-arXiv26]]、[[AlphaProofNexus-arXiv26]]
- **同主题**：[[Auto-Research]]
- **对比**：相对 [[AlphaEvolve-arXiv25]] 进化单函数 Python、百万 sample、无 rich context；相对 [[AI-Scientist-arXiv24]] 有强 evaluator 约束但无 manuscript/review 管线；相对传统 hyper-heuristics 用 LLM 免去手工 mutation 设计但依赖 API 与 skeleton 人工工程