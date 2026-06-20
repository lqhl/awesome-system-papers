---
type: paper
name: BES
full_title: "Self-Improving Language Models with Bidirectional Evolutionary Search"
authors: [Guowei Xu, Zhenting Qi, Huangyuan Su, Weirui Ye, Himabindu Lakkaraju, Sham M. Kakade, Yilun Du]
venue: arXiv
year: 2026
tags: [auto-research, llm-agent, evolutionary-search, self-improvement, test-time-scaling, post-training]
source_pdf: "[[arxiv26-xu-bes.pdf]]"
source_md: "[[arxiv26-xu-bes]]"
---

# Self-Improving Language Models with Bidirectional Evolutionary Search (arXiv 2026)

> **一句话总结**：BES 把 LLM/agent 自改进中的 sample generation 建模为 **forward evolutionary search（expansion + 4 种 recombination operator）+ backward goal decomposition（dense sub-goal verifier）**，在 MuSiQue post-training 上让 Llama-3.2-3B accuracy 从 4.0% 提到 7.0%、Llama-3.1-8B 从 6.6% 提到 10.4%，并在三个 open problem solving benchmark 上超过 OpenEvolve、GEPA、ShinkaEvolve，且 run-to-run variance 更低。

## 问题与动机

LLM 与 agent 的 post-training、self-improvement 和 [[Test-Time-Scaling]] 高度依赖采样/搜索：best-of-N、beam search、MCTS、[[Tree-of-Thoughts]]、Tree-GRPO 等。作者 claim 这些方法共享两个根本限制：

1. **Verifier 信号稀疏**：[[RLVR]] 等设定里 reward 往往是最终二值或粗粒度分数，搜索过程中 partial trajectory 很难获得 informative feedback。
2. **候选生成受限于 policy 分布**：候选主要靠 autoregressive expansion 沿单条 lineage 延伸，难以组合不同 rollout 中各自正确的局部结构，而 hard problem 的正确解常落在低概率区域。

作者的核心问题是：当正确解不在模型高概率 shell 内时，单纯增加 rollout 或树扩展是否本质上不够？论文回答「是」，并把解决路径定义成结构化双向搜索——backward search 把任务拆成可验证 sub-goal 提供 dense signal，forward search 用 evolutionary operators 重组 partial trajectory，让搜索越过单一 rollout 的分布边界。BES 既可替换 post-training 的 sample generation，也可在 inference 固定预算下做 open problem solving。

## 关键观察 / 隐含假设

- **观察 1：expansion-only search 的 terminal candidate 集中在 policy 的 narrow entropy shell 内，而 block recombination 可以生成 native rollout 下极低概率的候选。** Theorem 4.4 在 bounded per-step surprise、decaying step dependence、linear block total correlation 三个假设下证明：纯 expansion 轨迹几乎都在 typical set $A(T)_\epsilon$ 内，而 combination/translocation/crossover 等 evolution operator 能把期望 log-probability 推出 shell 边界，并有正比例候选真正 escape。
  - **依赖假设**：trajectory 可切成 contiguous step blocks 且 block 间存在足够 total correlation（$\gamma T$）；evolution operator 能打破 inter-block dependence。
  - **可能失效场景**：step 边界定义不当（token vs paragraph vs action triple）、强长程依赖使 block 假设不成立、或 program-level evolution 完全依赖 LLM rewrite 时 recombination 成功率骤降。

- **观察 2：terminal-only verifier 把 sub-goal 命中问题变成乘法样本复杂度，而 backward goal tree 把它变成局部覆盖问题。** Theorem 4.5：若 $m$ 个 leaf sub-goal 独立且各自命中概率为 $p_i$，terminal-only 需要 $\Omega(1/\prod p_i)$ 个候选；backward-guided search 只需 $O(p_{\min}^{-1}\log(m/\delta))$ 就能收集全部 sub-goal 证据，对称情形下指数优势为 $\Omega(p^{-(m-1)}/\log(m/\delta))$。
  - **依赖假设**：sub-goal verifier 可自动实例化且与 terminal success 一致（terminal success $\Rightarrow$ 所有 leaf satisfied）；sub-goal 近似独立或至少局部可分解。
  - **可能失效场景**：sub-goal 强耦合（后一步依赖前一步精确答案）、verifier 与 ground truth 不一致、或 decomposition 本身噪声大时 dense signal 反而误导 parent selection。

- **观察 3：在 GRPO/MaxRL/Tree-GRPO 都拿不到足够高质量 training sample 的 hard setting 下，更好的 sample generation 比换 RL 算法更关键。** Knights-and-Knaves 与 MuSiQue 3–4 hop 上，主流 post-training 几乎不提升甚至退化；BES 作为 sampling plug-in 仍能稳定发现可用 trajectory。
  - **依赖假设**：瓶颈在 sample coverage 而非 optimizer；每个 training problem 能承受 $B=50$–$200$ 次 policy call 的搜索预算；verifier 足够客观。
  - **可能失效场景**：任务本身可被 reward hack（MuSiQue 上 GRPO 学会 skip search 直接猜）、base model 太弱无法产出可重组片段、或搜索预算相对问题难度过小。

- **假设 1：policy 能把任务递归分解成有意义、可验证的 sub-goal tree。**
  - **证据强度**：中。MuSiQue 用 Llama-3.1-8B 做 decomposition、open problem 用 GPT-5；K&K 上 1B 模型不可靠，作者退化为 traversing 预定义 template tree 而非 open-ended decomposition——说明该假设对弱模型并不普适。

- **假设 2：失败 trajectory 中的 partial progress 可通过 evolution operator 与互补 parent 重组为正确解。**
  - **证据强度**：中。MuSiQue case study 展示 translocation 把两错误分支合成正确答案；但论文未系统量化 recombination success rate，也未覆盖自然语言推理之外的全部 agent 形态。

## 核心方法

BES（Bidirectional Evolutionary Search）维护 forward candidate pool $P$ 与 backward goal tree $G$，在固定 budget 内交替执行 forward step 与 periodic backward refine。

**Forward search** 把每个 partial trajectory 视为 node $n=(y_1,\ldots,y_t)$。每步以固定概率采样五类 operator：expansion（0.70）、combination（0.10）、deletion（0.05）、translocation（0.075）、crossover（0.075）。Expansion 从 $\pi_\theta$ 续采样最多 $K_{\max}$ 个 step；四种 evolution operator 在 step sequence 上直接编辑——combination 拼接共享 prefix 后的 suffix，deletion 删 interior step，translocation 移植单步，crossover 交换 tail。对 executable program discovery（circle packing、Heilbronn），直接 concatenation 无意义，改由 LLM prompt 实现 operator-specific rewrite。

Parent selection 由 backward score 驱动：单 parent operator 按 Boltzmann 分布 $\propto \exp(s(n)/\tau_t)\cdot(\deg(n)+\lambda)^{-1}$ 采样，$\lambda=0.1$ 奖励未探索节点；双 parent operator 用 pair score $s(n_a,n_b)$ 偏好覆盖不同 sub-goal 的互补组合。$\tau_t$ 从 $\tau_0$ 线性退火到 $\tau_{\mathrm{end}}$，逐步从 exploration 转向 exploitation。

**Backward search** 从 root goal $g_{\mathrm{root}}$ 出发，周期性让 $\pi_\theta$ 把未满足 leaf 拆成更细 sub-goal，每个 goal 带 local verifier $V_g(x,n)\in[0,1]$（rule checker、test executor、embedding similarity、LLM judge 等）。Node score $s(n)$ 递归聚合 parent/child sub-goal 分数，参数 $\alpha$ 平衡粗/细粒度贡献。每 $K_{\mathrm{dec}}$ 个 forward step 触发一次 decomposition 并 re-score 全 pool。

**Post-training 用法**：BES 替换 rollout/sample generation——每个 training problem 先跑 BES 得到高质量 trajectory，再交给 [[GRPO]]/MaxRL 等算法。K&K 上与 MaxRL answer reweighting 组合；MuSiQue 上与 GRPO 组合。**Inference 用法**：固定 compute/API budget 搜索 open problem，返回最高 verifier score 的 terminal candidate。Open problem 实验基于 [[ShinkaEvolve]] 的 islanded program archive，BES 叠加 evolution operators 与 backward goal tree；raw objective 仍主导排序，backward score 主要作 bucket 内 tie-breaker。

与 [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]] 的 LLM-as-mutator 路线相比，BES 更明确处理 **reasoning/agent trajectory 中 verifier 稀疏** 的问题，并把「为何两个 parent 值得重组」变成可计算的 sub-goal coverage signal，而非仅依赖 population diversity 或 MAP-Elites。

## 设计取舍

- **Dense sub-goal signal vs decomposition 成本**：backward search 需要额外 LLM call、verifier 设计与 periodic re-score；收益是 partial failure 仍可指导搜索。代价是弱模型或不可分解任务上 decomposition 可能失效，K&K 1B 实验被迫用 template tree 而非开放分解。

- **Direct sequence edit vs LLM-driven rewrite**：reasoning trace 上 operator 可精确作用在 step boundary，成本低、可解释；program evolution 上只能 prompt LLM 做「移植一个 trick」式 edit，mutation 成功率与 prompt 工程绑定，复现门槛高于 [[FunSearch-Nature24]] 的单函数 patch。

- **搜索质量 vs 训练步开销**：MuSiQue 上 BES 每 step wall-clock 比 Tree-GRPO 高约 29%，但 accuracy 近乎翻倍（3B：3.9%→7.0%）。这是用 sample generation 算力换 RL 有效信号；未讨论更大模型或更长 training 下是否仍划算。

- **Plug-in 通用性 vs 任务特定 verifier**：BES 框架与 post-training 算法正交，但每个任务必须手工/半自动设计 goal tree 与 $V_g$——K&K 用规则 scorer + 模板树，MuSiQue 用 embedding 覆盖 search query，open problem 用 Python partial-progress expression。通用 agent 场景的可扩展性依赖 verifier 工程，论文未给出自动 synthesize verifier 的方法。

- **边界条件**：在 objective 可自动评估、trajectory 可分段、sub-goal 可定义的任务上设计优雅；对学术写作等主观任务、湿实验、或 evaluator 易被 hack 的开放环境会变脆。论文明确排除主观评估场景。

## 实验与结果

- **Knights-and-Knaves logical reasoning（Gemma-3-1B-it + MaxRL）**：困难训练集上 GRPO/MaxRL validation accuracy 几乎不提升；BES 随训练稳步上升。Ablation 去掉 answer reweighting 或 evolution operators 都弱于完整 BES，但仍优于 GRPO/MaxRL baseline。
- **MuSiQue multi-hop agent post-training**：Llama-3.2-3B base **4.0%** → GRPO **2.1%** → Tree-GRPO **3.9%** → BES **7.0%**；Llama-3.1-8B base **6.6%** → GRPO **5.6%** → Tree-GRPO **7.4%** → BES **10.4%**。
- **MuSiQue 行为指标（3B）**：BES valid searches / valid actions / finish ratio = **2.31 / 3.29 / 0.97**，Tree-GRPO 为 **1.50 / 2.14 / 0.64**——agent 学到主动检索而非 skip search 猜答案。
- **Open problem solving（GPT-5 backbone，\$50/run，3 runs/benchmark）**：BES 在 Circle Packing (Square)、Circle Packing (Rect)、Heilbronn (Convex) 的 average objective 分别为 **2.623、2.349、0.026**，均超过 OpenEvolve、GEPA、ShinkaEvolve；best objective 接近 human expert / [[AlphaEvolve-arXiv25]] 高算力闭源结果，且 **cross-run variance 显著低于所有 baseline**。
- **成本**：MuSiQue 3B post-training median wall-clock **309s/step** vs Tree-GRPO **240s/step**（+29%）；open problem 上 BES API cost 高于 ShinkaEvolve（如 Circle Square **\$18.6** vs **\$13.0**），但 mean/best objective 更好。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条在 hard post-training 与 open problem 两类场景上基本闭合：entropy shell 理论解释为何需要 recombination，sub-goal 理论解释为何需要 backward decomposition，MuSiQue case study 把 translocation + embedding verifier 机制串起来。薄弱环节在于：**理论假设（block independence、sub-goal independence）与真实 LLM trajectory 的相关性未被直接测量**；作者用 ablation 证明 evolution 与 bidirectional 都必要，但未分解「仅 backward / 仅 evolution / 二者交互」的边际贡献各占多少。Open problem 结果建立在 GPT-5 + SkyDiscover 统一配置上，外部团队复现成本显著高于 [[FunSearch-Nature24]] 的 cheap CPU evaluator 设定。

### 假设压力测试

- **Sub-goal 质量**：MuSiQue 依赖 8B 模型 decomposition + embedding verifier，threshold $\sigma_{\mathrm{cov}}=0.6$ 是否稳健论文未做 sensitivity analysis；若 sub-goal 过粗，backward signal 退化为 terminal proxy；过细则 decomposition 噪声放大。
- **弱模型**：1B K&K 实验已证明不能完全依赖 open-ended backward decomposition，需要人工 template——向更小或更弱开源模型外推时，BES 的核心卖点可能缩水为「带启发式的 tree search」。
- **规模**：post-training 仅到 8B，MuSiQue 绝对 accuracy 仍很低（10.4%），更像 frontier hard setting 的相对改进，不能直接等同于 production-ready QA agent。
- **Reward hacking**：GRPO 在 MuSiQue 上退化说明 verifier 设计关键；BES 缓解的是 sample coverage，不自动解决 RL 阶段的 hacking——若 evolution 重组出的 trajectory 分布与 deployment 分布偏移，post-training 收益可能不稳定。

### 实验可信度

- **Benchmark 代表性**：K&K 与 MuSiQue 3–4 hop 都是可控 verifier 的 hard reasoning；open problem 是 continuous optimization with code evaluator——三类都偏向「易评估、难求解」，与主观科研任务差距大，但对 [[Auto-Research]] 主题高度相关。
- **Baseline 公平性**：MuSiQue 上 per-problem search budget 对齐（8 trajectories/problem）；Tree-GRPO 是强 agent baseline。Open problem 直接用 SkyDiscover 公布的 OpenEvolve/GEPA/ShinkaEvolve 结果，配置一致，可信度高。
- **Ablation**：仅 K&K 上做了 evolution vs reweighting 消融；MuSiQue 与 open problem 缺少对 backward-only、forward-only、operator 子集的系统 ablation，设计分解证据不完整。
- **Metric 覆盖**：post-training 覆盖 accuracy 与 agent 行为指标；open problem 覆盖 mean/best/variance 与 API cost；**未报告 tail latency、搜索失败率、verifier false positive/negative 率**，也未讨论多 tenant 或在线 serving 场景。

### 系统性缺陷

- **工程复杂度**：每个任务需定义 step granularity、goal tree、$V_g$、operator 实现（直接编辑 vs prompt），落地成本高于 plug-and-play best-of-N。论文未讨论自动化 verifier synthesis 或 decomposition quality monitoring。
- **可观测性**：backward goal tree 提升 interpretability（case study 可视化 sub-goal 命中），但大规模运行时如何 debug 错误 decomposition 或 pair selection 论文未涉及。
- **故障恢复**：异步 distributed 设定下 candidate pool 一致性与 budget 耗尽后的 fallback 策略论文未讨论。
- **兼容性**：BES 与 GRPO/MaxRL 正交，但与 online RL loop、continuous training pipeline 的集成开销（每 step 50–200 policy calls × retrieval server × decomposer server）仅在一组 hardware 设定下报告。

## 局限与 Future Work

- **局限 1**：必须有 objective reward / 可写 verifier；未在学术写作等主观任务上验证（Appendix H 明确承认）。
- **局限 2**：backward search 依赖 policy 的 decomposition 能力；极弱模型需退化为 template tree，开放分解并非普适。
- **局限 3**：post-training 实验受资源限制只到 8B；MuSiQue 绝对性能仍低，结论应理解为 hard-setting sample efficiency 改进。
- **Future work 1**：在 FrontierMath、代码竞赛等更难 benchmark 上测量 evolution escape rate 与 sub-goal 命中率，验证 Theorem 4.4/4.5 的经验有效性而非仅作动机。
- **Future work 2**：研究自动或半自动 synthesize sub-goal verifier / decomposition，降低 per-task 工程成本，并向 [[AutoScientists-arXiv26]] 类 long-running multi-agent 系统提供可插拔 search backend。
- **Future work 3**：与 [[AlphaEvolve-arXiv25]] 式 whole-file diff evolution 对比——BES 的 pair-score-guided recombination 是否在 program discovery 上优于 population diversity alone，尤其在 evaluator 昂贵、需控制 variance 的科学发现场景。

## 相关

- **相关概念**：[[Test-Time-Scaling]]、[[RLVR]]、[[Evolutionary-Search]]、[[Tree-of-Thoughts]]、[[Program-Synthesis]]、[[LLM-as-Mutator]]
- **同类系统**：[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ShinkaEvolve]]、[[ASI-ARCH-arXiv25]]、[[AutoScientists-arXiv26]]
- **同主题**：[[Auto-Research]]
- **对比**：BES 侧重 reasoning/agent trajectory 的 bidirectional search + sub-goal verifier；[[FunSearch-Nature24]] 侧重 island evolution + 单函数 patch；[[AlphaEvolve-arXiv25]] 侧重 frontier LLM whole-file diff + MAP-Elites