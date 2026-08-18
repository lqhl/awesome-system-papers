---
type: paper
name: BES
full_title: "Self-Improving Language Models with Bidirectional Evolutionary Search"
authors: [Guowei Xu, Zhenting Qi, Huangyuan Su, Weirui Ye, Himabindu Lakkaraju, Sham M. Kakade, Yilun Du]
venue: arXiv
year: 2026
tags: [auto-research, llm-agent, evolutionary-search, self-improvement, test-time-scaling, post-training, domain/auto-research]
source_pdf: "[[arxiv26-xu-bes.pdf]]"
source_md: "[[arxiv26-xu-bes]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# 用双向进化搜索实现语言模型自我改进（arXiv 2026）

> **原题**：Self-Improving Language Models with Bidirectional Evolutionary Search

> **一句话总结**：BES 把 LLM/智能体自我改进中的样本生成建模为**前向进化搜索（forward evolutionary search）+ 反向目标分解（backward goal decomposition）**：前者用扩展与四种重组算子跳出模型的高概率区域，后者用稠密的子目标验证器指导搜索。它在 MuSiQue 后训练中把 Llama-3.2-3B 的准确率从 4.0% 提到 7.0%、Llama-3.1-8B 从 6.6% 提到 10.4%，并在三个开放问题基准上超过 OpenEvolve、GEPA 和 ShinkaEvolve，且运行间方差更低。

## 问题与动机

LLM 与智能体的后训练、自我改进和 [[Test-Time-Scaling|测试时规模扩展]] 高度依赖采样与搜索，例如 best-of-N、束搜索（beam search）、MCTS、[[Tree-of-Thoughts]] 和 Tree-GRPO。作者认为这些方法共享两个根本限制：

1. **验证器信号稀疏**：[[RLVR]] 等设定里的奖励往往只是最终二值或粗粒度分数，搜索中的部分轨迹很难获得有信息量的反馈。
2. **候选生成受限于策略分布**：候选主要靠自回归扩展沿单条谱系延伸，难以组合不同运行轨迹中各自正确的局部结构，而高难问题的正确解常落在低概率区域。

作者的核心问题是：当正确解不在模型的高概率壳层内时，单纯增加运行轨迹或扩大搜索树是否仍然不够？论文的回答是「是」。其解决路径是结构化双向搜索：反向搜索把任务拆成可验证子目标，提供稠密信号；前向搜索用进化算子重组部分轨迹，使候选越过单条运行轨迹的分布边界。BES 既可替换后训练中的样本生成，也可在固定推理预算下求解开放问题。

## 关键观察 / 隐含假设

- **观察 1：仅靠扩展得到的终止候选，会集中在策略的狭窄熵壳层内；分块重组可以产生在模型原生轨迹下概率极低的候选。** 定理 4.4 在「单步意外度有界、步骤依赖衰减、分块总相关近似线性」三个假设下证明：纯扩展轨迹几乎都在典型集 $A(T)_\epsilon$ 内，而组合、移植、交叉等进化算子能把候选的期望对数概率推到壳层之外。
  - **依赖假设**：轨迹可切成 contiguous 步骤 blocks 且 block 间存在足够 total correlation（$\gamma T$）；evolution 算子能打破 inter-block dependence。
  - **可能失效场景**：步骤边界定义不当（token vs paragraph vs 动作 triple）、强长程依赖使 block 假设不成立、或程序级 evolution 完全依赖 LLM rewrite 时 recombination 成功率骤降。

- **观察 2：只在终止态评分，会把子目标命中变成乘法样本复杂度；反向目标树则把它变成局部覆盖问题。** 定理 4.5 表明：若 $m$ 个叶子子目标相互独立、命中概率分别为 $p_i$，只看终止态需要 $\Omega(1/\prod p_i)$ 个候选；反向引导搜索只需 $O(p_{\min}^{-1}\log(m/\delta))$ 就能收集全部子目标证据。
  - **依赖假设**：子目标验证器可自动实例化且与终止成功一致（终止成功 $\Rightarrow$ 所有 leaf satisfied）；子目标近似独立或至少局部可分解。
  - **可能失效场景**：子目标强耦合（后一步依赖前一步精确答案）、验证器与真值不一致、或分解本身噪声大时稠密信号反而误导父节点 selection。

- **观察 3：在 GRPO/MaxRL/Tree-GRPO 都拿不到足够高质量训练样本的 高难设定下，更好的样本生成比换 RL 算法更关键。** Knights-and-Knaves 与 MuSiQue 3–4 hop 上，主流 后训练几乎不提升甚至退化；BES 作为 sampling plug-in 仍能稳定发现可用轨迹。
  - **依赖假设**：瓶颈在样本覆盖率而非 optimizer；每个训练问题能承受 $B=50$–$200$ 次策略 call 的搜索预算；验证器足够客观。
  - **可能失效场景**：任务本身可被 reward hack（MuSiQue 上 GRPO 学会 skip 搜索直接猜）、base 模型太弱无法产出可重组片段、或搜索预算相对问题难度过小。

- **假设 1：策略能把任务递归分解成有意义、可验证的子目标 tree。**
  - **证据强度**：中。MuSiQue 用 Llama-3.1-8B 做分解、开放问题用 GPT-5；K&K 上 1B 模型不可靠，作者退化为 traversing 预定义模板 tree 而非开放式分解——说明该假设对弱模型并不普适。

- **假设 2：失败轨迹中的部分进展可通过 evolution 算子与互补父节点重组为正确解。**
  - **证据强度**：中。MuSiQue 案例研究展示移植把两错误分支合成正确答案；但论文未系统量化 recombination 成功率，也未覆盖自然语言推理之外的全部智能体形态。

## 核心方法

BES（Bidirectional Evolutionary 搜索）维护 forward 候选池 $P$ 与 backward 目标 tree $G$，在固定预算内交替执行前向步骤与 periodic backward refine。

**前向搜索** 把每个部分轨迹视为节点 $n=(y_1,\ldots,y_t)$。每步以固定概率采样五类算子：扩展（0.70）、组合（0.10）、删除（0.05）、移植（0.075）、交叉（0.075）。Expansion 从 $\pi_\theta$ 续采样最多 $K_{\max}$ 个步骤；四种 evolution 算子在步骤序列上直接编辑——组合拼接共享前缀后的后缀，删除删内部步骤，移植移植单步，交叉交换尾部。对可执行程序发现（circle packing、Heilbronn），直接 concatenation 无意义，改由 LLM 提示词实现算子专用 rewrite。

Parent selection 由 backward 分数驱动：单父节点算子按 Boltzmann 分布 $\propto \exp(s(n)/\tau_t)\cdot(\deg(n)+\lambda)^{-1}$ 采样，$\lambda=0.1$ 奖励未探索节点；双父节点算子用 pair 分数 $s(n_a,n_b)$ 偏好覆盖不同子目标的互补组合。$\tau_t$ 从 $\tau_0$ 线性退火到 $\tau_{\mathrm{end}}$，逐步从探索转向利用。

**反向搜索** 从根目标 $g_{\mathrm{root}}$ 出发，周期性让 $\pi_\theta$ 把未满足叶节点拆成更细子目标，每个目标带局部验证器 $V_g(x,n)\in[0,1]$（rule 检查器、test executor、embedding similarity、LLM 评审器等）。节点分数 $s(n)$ 递归聚合父节点/子节点子目标分数，参数 $\alpha$ 平衡粗/细粒度贡献。每 $K_{\mathrm{dec}}$ 个前向步骤触发一次分解并重新评分全 pool。

**后训练用法**：BES 替换运行轨迹/样本生成——每个训练问题先跑 BES 得到高质量轨迹，再交给 [[GRPO]]/MaxRL 等算法。K&K 上与 MaxRL answer reweighting 组合；MuSiQue 上与 GRPO 组合。**推理阶段用法**：固定算力/API 预算搜索开放问题，返回最高验证器分数的终止候选。开放问题实验基于 [[ShinkaEvolve]] 的 islanded 程序档案库，BES 叠加 evolution operators 与 backward 目标 tree；原始目标仍主导排序，backward 分数主要作 bucket 内 tie-breaker。

与 [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]] 的 LLM-as-mutator 路线相比，BES 更明确处理 **推理/智能体轨迹中验证器稀疏** 的问题，并把「为何两个父节点值得重组」变成可计算的子目标覆盖率信号，而非仅依赖 population diversity 或 MAP-Elites。

## 设计取舍

- **Dense 子目标信号 vs 分解成本**：backward 搜索需要额外 LLM call、验证器设计与 periodic 重新评分；收益是部分失败仍可指导搜索。代价是弱模型或不可分解任务上分解可能失效，K&K 1B 实验被迫用模板 tree 而非开放分解。

- **Direct 序列 edit vs LLM-driven rewrite**：推理轨迹上算子可精确作用在步骤边界，成本低、可解释；程序进化上只能提示词 LLM 做「移植一个 trick」式 edit，mutation 成功率与提示词工程绑定，复现门槛高于 [[FunSearch-Nature24]] 的单函数 patch。

- **搜索质量 vs 训练步开销**：MuSiQue 上 BES 每步骤实际时间比 Tree-GRPO 高约 29%，但准确率近乎翻倍（3B：3.9%→7.0%）。这是用样本生成算力换 RL 有效信号；未讨论更大模型或更长训练下是否仍划算。

- **Plug-in 通用性 vs 任务特定验证器**：BES 框架与 后训练算法正交，但每个任务必须手工/半自动设计目标 tree 与 $V_g$——K&K 用规则评分器 + 模板树，MuSiQue 用 embedding 覆盖搜索 query，开放问题用 Python 部分-进展 expression。通用智能体场景的可扩展性依赖验证器工程，论文未给出自动 synthesize 验证器的方法。

- **边界条件**：在目标可自动评估、轨迹可分段、子目标可定义的任务上设计优雅；对学术写作等主观任务、湿实验、或评估器易被 hack 的开放环境会变脆。论文明确排除主观评估场景。

## 实验与结果

- **Knights-and-Knaves logical 推理（Gemma-3-1B-it + MaxRL）**：困难训练集上 GRPO/MaxRL 验证准确率几乎不提升；BES 随训练稳步上升。消融实验去掉 answer reweighting 或 evolution operators 都弱于完整 BES，但仍优于 GRPO/MaxRL 基线。
- **MuSiQue multi-hop 智能体 后训练**：Llama-3.2-3B base / GRPO / Tree-GRPO / BES 为 4.0% / 2.1% / 3.9% / 7.0%；Llama-3.1-8B 为 6.6% / 5.6% / 7.4% / 10.4%（§5.1.2，表 1；3–4-hop solvable 训练 split、2 epochs、offline Wikipedia retrieval、每问题 8 轨迹）。
- **MuSiQue 行为指标（3B）**：BES valid searches / valid actions / finish ratio = **2.31 / 3.29 / 0.97**，Tree-GRPO 为 **1.50 / 2.14 / 0.64**——智能体学到主动检索而非 skip 搜索猜答案。
- **开放问题求解**：GPT-5、每运行上限 $50、每基准 3 运行下，BES 在 Circle Packing (Square/Rect)、Heilbronn (Convex) 的 average 目标为 2.623±.014 / 2.349±.012 / .026±.001，均高于 OpenEvolve、GEPA、ShinkaEvolve（§5.2，表 2；single CPU 节点，BES 建于 ShinkaEvolve）。表 2 的三项标准差均低于三个开源基线，但 3 运行不构成显著性检验；人类/AlphaEvolve 不在同等预算下运行。
- **成本**：MuSiQue 3B 后训练 median 实际时间 **309s/步骤** vs Tree-GRPO **240s/步骤**（+29%）；开放问题上 BES API 成本高于 ShinkaEvolve（如 Circle Square **\$18.6** vs **\$13.0**），但 mean/best 目标更好。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| BES+GRPO 在 MuSiQue 上将 3B/8B 准确率提高到 7.0%/10.4% | §5.1.2，表 1 | 3–4 跳划分；训练 2 个 epoch；离线检索；每题 8 条轨迹 | 强 |
| BES 提高 3B MuSiQue 的有效搜索、动作和完成比例 | §5.1.2，表 1 | 同一智能体搜索设置；行为指标不直接证明泛化 | 强 |
| BES 在三个开放优化基准上提高平均目标值 | §5.2，表 2；附录 D.3 | GPT-5；每次运行 50 美元；3 次运行；单 CPU 节点；基线数据来自 SkyDiscover | 中 |
| BES 的 MuSiQue 3B 中位墙钟时间为每步 309 秒，对照为 240 秒 | §5.4，表 3 | 后训练搜索步骤；不是总训练成本或服务延迟 | 强 |

## 批判性分析

### 论证链条

论文的观察 → 设计 → 结果链条在 hard 后训练与开放问题两类场景上基本闭合：熵壳层理论解释为何需要 recombination，子目标理论解释为何需要 backward 分解，MuSiQue 案例研究把移植 + embedding 验证器机制串起来。薄弱环节在于：**理论假设（block independence、子目标 independence）与真实 LLM 轨迹的相关性未被直接测量**；作者用消融实验证明 evolution 与 bidirectional 都必要，但未分解「仅 backward / 仅 evolution / 二者交互」的边际贡献各占多少。开放问题结果建立在 GPT-5 + SkyDiscover 统一配置上，外部团队复现成本显著高于 [[FunSearch-Nature24]] 的 cheap CPU 评估器设定。

### 假设压力测试

- **Sub-目标质量**：MuSiQue 依赖 8B 模型分解 + embedding 验证器，threshold $\sigma_{\mathrm{cov}}=0.6$ 是否稳健论文未做 sensitivity 分析；若子目标过粗，backward 信号退化为终止代理指标；过细则分解噪声放大。
- **弱模型**：1B K&K 实验已证明不能完全依赖开放式 backward 分解，需要人工模板——向更小或更弱开源模型外推时，BES 的核心卖点可能缩水为「带启发式的 tree 搜索」。
- **规模**：后训练仅到 8B，MuSiQue 绝对准确率仍很低（10.4%），更像前沿 高难设定的相对改进，不能直接等同于生产环境-ready QA 智能体。
- **Reward hacking**：GRPO 在 MuSiQue 上退化说明验证器设计关键；BES 缓解的是样本覆盖率，不自动解决 RL 阶段的 hacking——若 evolution 重组出的轨迹分布与部署分布偏移，后训练收益可能不稳定。

### 实验可信度

- **基准代表性**：K&K 与 MuSiQue 3–4 hop 都是可控验证器的 hard 推理；开放问题是 continuous optimization with 代码评估器——三类都偏向「易评估、难求解」，与主观科研任务差距大，但对 [[Auto-Research]] 主题高度相关。
- **基线公平性**：MuSiQue 上 每个问题搜索预算对齐（8 轨迹/问题）；Tree-GRPO 是强智能体基线。开放问题直接用 SkyDiscover 公布的 OpenEvolve/GEPA/ShinkaEvolve 结果，配置一致，可信度高。
- **消融实验**：仅 K&K 上做了 evolution vs reweighting 消融；MuSiQue 与开放问题缺少对 backward-only、forward-only、算子子集的系统消融实验，设计分解证据不完整。
- **指标覆盖**：后训练覆盖准确率与智能体行为指标；开放问题覆盖 mean/best/方差与 API 成本；**未报告尾延迟、搜索失败率、验证器误报/负面率**，也未讨论多 tenant 或在线 serving 场景。

### 系统性缺陷

- **工程复杂度**：每个任务需定义步骤 granularity、目标 tree、$V_g$、算子实现（直接编辑 vs 提示词），落地成本高于 plug-and-play best-of-N。论文未讨论自动化验证器综合或分解质量 monitoring。
- **可观测性**：backward 目标 tree 提升可解释性（案例研究可视化子目标命中），但大规模运行时如何调试错误分解或 pair selection 论文未涉及。
- **故障恢复**：异步 distributed 设定下候选池一致性与预算耗尽后的回退策略论文未讨论。
- **兼容性**：BES 与 GRPO/MaxRL 正交，但与 online RL 闭环、continuous 训练流水线的集成开销（每步骤 50–200 策略 calls × retrieval server × decomposer server）仅在一组 hardware 设定下报告。

## 局限与后续工作

- **局限 1**：必须有目标 reward / 可写验证器；未在学术写作等主观任务上验证（附录 H 明确承认）。
- **局限 2**：backward 搜索依赖策略的分解能力；极弱模型需退化为模板 tree，开放分解并非普适。
- **局限 3**：后训练实验受资源限制只到 8B；MuSiQue 绝对性能仍低，结论应理解为 高难设定样本效率改进。
- **后续工作 1**：在 FrontierMath、代码竞赛等更难基准上测量 evolution escape rate 与子目标命中率，验证 Theorem 4.4/4.5 的经验有效性而非仅作动机。
- **后续工作 2**：研究自动或半自动 synthesize 子目标验证器 / 分解，降低 每个任务工程成本，并向 [[AutoScientists-arXiv26]] 类长时间运行多智能体系统提供可插拔搜索 后端。
- **后续工作 3**：与 [[AlphaEvolve-arXiv25]] 式整文件差分进化对比——BES 的成对分数引导的重组是否在程序发现上优于仅依赖种群多样性，尤其在评估器昂贵、需控制方差的科学发现场景。

## 相关

- **相关概念**：[[Test-Time-Scaling]]、[[RLVR]]、[[Evolutionary-Search]]、[[Tree-of-Thoughts]]、[[Program-Synthesis]]、[[LLM-as-Mutator]]
- **同类系统**：[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ShinkaEvolve]]、[[ASI-ARCH-arXiv25]]、[[AutoScientists-arXiv26]]
- **同主题**：[[Auto-Research]]
- **对比**：BES 侧重推理/智能体轨迹的 bidirectional 搜索 + 子目标验证器；[[FunSearch-Nature24]] 侧重 island evolution + 单函数 patch；[[AlphaEvolve-arXiv25]] 侧重前沿 LLM whole-file diff + MAP-Elites
