---
type: paper
name: BES
full_title: "Self-Improving Language Models with Bidirectional Evolutionary Search"
authors: [Guowei Xu, Zhenting Qi, Huangyuan Su, Weirui Ye, Himabindu Lakkaraju, et al.]
venue: arXiv
year: 2026
tags: [auto-research, llm-agent, evolutionary-search, self-improvement, test-time-scaling, post-training]
source_pdf: "[[arxiv26-xu-bes.pdf]]"
source_md: "[[arxiv26-xu-bes]]"
---

# Self-Improving Language Models with Bidirectional Evolutionary Search (arXiv 2026)

> **一句话总结**：BES 把 LLM/agent 的自改进建模为 forward evolutionary search + backward goal decomposition，在 MuSiQue post-training 上让 Llama-3.2-3B accuracy 从 4.0% 提到 7.0%、Llama-3.1-8B 从 6.6% 提到 10.4%，并在三个 open problem solving benchmark 上超过 OpenEvolve、GEPA、ShinkaEvolve 等开源框架。

## 问题

LLM 自改进和 test-time scaling 常用 best-of-N、beam search、MCTS、Tree-GRPO 这类采样/搜索方法。它们的问题有两个：第一，verifier 通常只给最终二值或粗粒度 reward，搜索过程缺少 dense intermediate signal；第二，候选解主要靠 autoregressive expansion 逐步延伸，容易被限制在模型自身高概率区域，难以组合不同 rollout 中各自正确的局部结构。

这篇论文的核心问题是：如果 hard problem 的正确解落在模型低概率区域，单纯增加 rollout 或沿树扩展前缀是否本质上不够？作者给出的回答是“是”，并把解决路径定义成结构化搜索：用 backward search 把目标拆成可验证 sub-goal，再用 evolutionary operators 重组不同 partial trajectory，让搜索能越过单一 rollout 的分布边界。

## 核心方法

BES（Bidirectional Evolutionary Search）由两条耦合的搜索组成。Forward search 维护候选 trajectory pool，每步选择 expansion 或 evolution operator 生成新候选；backward search 维护 goal tree，把原始任务递归拆成 finer-grained sub-goals，并用每个 sub-goal 的 verifier 给候选打分。Forward search 的 parent selection 不只看最终 reward，也看 candidate 对 goal tree 的覆盖度；两父节点 operator 还会优先选择互补覆盖不同 sub-goal 的 parent pair。

Forward search 有五类操作：expansion 继续从 policy 采样新 step；combination 拼接两个 trajectory 的 suffix；deletion 删除内部 step；translocation 把一个 trajectory 的 step 移植到另一个 trajectory；crossover 用一个 trajectory 的前缀接另一个 trajectory 的尾部。对于 reasoning trace，这些操作可以直接作用在 step sequence 上；对于 executable program discovery，论文把它们实现为 LLM-driven rewrite prompt。

Backward search 的作用是把 sparse verifier 变成 dense guidance。它从 root goal 开始递归分解，每个 goal 带一个 local verifier，可以是 rule-based checker、test executor、embedding similarity 或 LLM judge。论文的理论动机有两点：expansion-only search 的 trajectory 会集中在 entropy shell 内，而 block recombination 可以生成 native policy 下低概率的候选；terminal-only search 要同时命中所有 sub-goal，样本复杂度是乘法项，而 backward-guided search 先收集各个 sub-goal 证据，再用 evolution 重组，样本复杂度从乘法问题变成局部覆盖问题。

在 post-training 中，BES 替换 sample generation：每个训练问题先用 BES 找高质量 trajectory，再交给 GRPO/MaxRL 类算法训练。在 inference 中，BES 在固定预算下搜索 open problem，返回 verifier score 最高的 terminal candidate。

## 关键结果

- Knights-and-Knaves 逻辑推理：GRPO 和 MaxRL 在困难训练集上几乎不提升，BES 的 validation accuracy 随训练持续上升；ablation 显示去掉 answer reweighting 或 evolution operators 都弱于完整 BES。
- MuSiQue multi-hop reasoning post-training：Llama-3.2-3B-Instruct base accuracy 4.0%，GRPO 降到 2.1%，Tree-GRPO 3.9%，BES 达 7.0%；Llama-3.1-8B-Instruct base 6.6%，GRPO 5.6%，Tree-GRPO 7.4%，BES 达 10.4%。
- MuSiQue 行为指标：3B 模型上 BES 的 valid search/action/finish ratio 为 2.31 / 3.29 / 0.97，高于 Tree-GRPO 的 1.50 / 2.14 / 0.64，说明 agent 学到的是主动检索而不是跳过搜索直接猜。
- Open problem solving（GPT-5 backbone）：BES 在 Circle Packing Square/Rect 和 Heilbronn Convex 上的 average objective 分别为 2.623、2.349、0.026，均超过 OpenEvolve、GEPA、ShinkaEvolve；best result 接近 human / AlphaEvolve 高算力闭源结果。
- 成本：3B MuSiQue post-training 中 BES walltime 309s/step，比 Tree-GRPO 240s 多约 29%，但 accuracy 从 3.9% 提到 7.0%；open problem solving 上 BES 比 ShinkaEvolve API cost 更高（如 Circle Square \$18.6 vs \$13.0），但均值和 best objective 更好。

## 批判与局限

BES 最有价值的地方是把“self-improving LLM”从单轨 rollout/树搜索推进到**可重组的 evidence collection**：先让不同 candidate 覆盖不同 sub-goal，再通过 evolution 合并局部正确性。这和 [[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]] 的 LLM-as-mutator 路线相通，但 BES 更明确处理了 reasoning / agent trajectory 中 verifier 稀疏的问题。

局限也很清楚。第一，BES 仍然依赖客观 reward 或可写 verifier；论文明确没有验证 academic writing 这类主观任务。第二，backward search 依赖模型能拆出有意义的 sub-goal，弱模型或不可分解任务上可能失效。第三，post-training 只做到了 8B 级模型，且 MuSiQue 绝对 accuracy 仍低，说明结果更像 hard-setting 下的相对改进，而不是直接可部署的 QA agent。第四，open problem solving 结果使用 GPT-5 和 \$50/run 预算，对小团队可复现性比 FunSearch 式 cheap evaluator 更弱。

对 auto-research 系统的启发是：BES 可以看作 [[Auto-Research]] 里 evolutionary discovery 路线的新抽象补丁。它不只让 LLM mutation 生成新候选，而是显式维护 goal decomposition 和 sub-goal verifier，把“为什么两个 parent 值得重组”变成可计算信号。这对量化因子挖掘、kernel optimization、time-series model search 这类有 noisy evaluator 的任务很相关：关键不是让 agent 多想，而是把失败 trajectory 中可复用的局部证据保存下来并可重组。

## 相关

- **相关概念**：evolutionary search、bidirectional search、test-time scaling、self-improvement、verifier、sub-goal decomposition
- **同类系统**：[[FunSearch-Nature24]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AutoScientists-arXiv26]]
- **同主题**：[[Auto-Research]]
