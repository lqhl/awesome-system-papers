---
type: paper
name: FunSearch
full_title: "Mathematical discoveries from program search with large language models"
authors: [Bernardino Romera-Paredes, Mohammadamin Barekatain, Alexander Novikov, Matej Balog, M. Pawan Kumar, "et al."]
venue: Nature
year: 2024
tags: [auto-research, evolutionary-search, program-synthesis, scientific-discovery, combinatorics, llm]
source_pdf: "[[funsearch.pdf]]"
source_md: "[[funsearch]]"
---

# Mathematical discoveries from program search with large language models (Nature 2024)

> **一句话总结**：DeepMind FunSearch 把 **frozen LLM 当 mutation operator + 系统 evaluator 做 fitness 过滤**，跑 island-based 进化搜索在 cap set 问题上把 $n{=}8$ 最优解从 496 推到 **512**、cap set capacity 下界 20 年来首次从 2.2180 提升到 **2.2202**，同时在 online bin packing 上把 excess-bin 比例从 Best-Fit 的 3.79-5.81% 压到 **0.03-5.30%**——第一例用 LLM 在开放数学难题上做出**可验证**的新发现。

## 问题

LLM 在代码、推理上很强，但**幻觉**让它在需要严格可验证性的科学发现上无法直接用——随便生成一个 "cap set 构造"，LLM 说的话可能优美但不正确。过去把 LLM 用于搜索的工作（Evolution through Large Models）多是在合成 benchmark、NAS 或小 puzzle 上刷分，**没人用 LLM 真解决过公开开放的数学难题或产出工业可用的新算法**。

另一方面，许多组合/数学问题属于"**易评估、难求解**"的 NP 族：`evaluate(solution)` 便宜可靠，但搜索空间爆炸（cap set 在 $n{=}8$ 就是 $3^{1600}$ 级）。如何把 LLM 的**创造力**和 evaluator 的**可验证性**耦合起来、避开幻觉、做出真正超越 SOTA 的发现，是 FunSearch 要回答的问题。

## 核心方法

FunSearch 的核心洞察：**不搜索"解"本身，而搜索"生成解的程序"**。程序更短、更可解释、更易 generalize 到大规模 instance，还天然偏向低 Kolmogorov complexity 的解——这点和传统遗传编程或暴力枚举解完全不同。

**系统输入**：
- `evaluate(solution) -> score`：黑盒 scorer
- 一个程序 skeleton：大部分 boilerplate 固定，**只把关键逻辑函数（如 greedy 里的 `priority(...)`）留给 LLM 进化**。把 LLM 算力聚焦在核心 1 个函数而非重写整段代码，大幅降低生成出错概率。
- 一个初始可跑的 trivial 实现（如常数 priority）

**进化循环四要素**：

1. **Pre-trained LLM（Codey / PaLM2 家族）作 mutation operator**，frozen、不 fine-tune，追求"快推理"而非"顶尖质量"——单次实验采样 \~$10^6$ 次。作者在 StarCoder 上做了对照，说明结果对具体 LLM 不敏感，关键是代码训练语料充分。

2. **Best-shot prompting**：prompt 由数据库里采样的 $k{=}2$ 个 high-scoring 程序拼成——先按分数升序，命名为 `priority_v0`、`priority_v1`，prompt 末尾留一个 `priority_v2` 空函数头让 LLM 续写。这种"比较两个好解再写第三个"的结构，让 LLM 捕捉改进模式。

3. **Islands model（多 deme 进化）**：候选池切成多个独立岛，每岛内部按分数 + 程序长度做 sampling（偏好短程序）。**周期性淘汰一半最差的岛**，用其它岛的 best 克隆填充——宏观层面避免 local optima、维持多样性。

4. **异步分布式**：三类 worker 松耦合——programs database、samplers（带 GPU 跑 LLM）、evaluators（便宜 CPU）。典型配置 15 samplers + 150 CPU evaluators（5 × 32），以 LLM 推理和程序评估**并行化**压低 wall clock。

**关键工程经验**：(a) Evolver 只改 `priority` 函数，skeleton 固定显著提高成功率；(b) `evaluate` 要返回**连续分数**（如不合法构造的部分分、MAX-SAT 满足的子句数），二值 pass/fail 会让进化无从梯度化；(c) program 必须是**可执行**代码而非自然语言——进化本质是代码级别的 iterative refinement。

## 关键结果

- **Cap set（extremal combinatorics）**：$n{=}3\ldots7$ 追平已知最优，**$n{=}8$ 得到 512，超过此前最优 496**；cap set capacity 下界 $C$ 从 Tyrrell (2022) 的 2.2180 推到 **2.2202**（由 $\mathcal{A}(24,17)$ 构造），**20 年来最大一次下界提升**。
- **解释性 → 再发现**：对 $\mathcal{I}(12,7)$ 构造程序做人工 simplification，发现它在 4 组 coordinate triple 上有 cyclic 对称；把该 symmetry 硬编进搜索空间后，系统进一步得到 $\mathcal{I}(15,10)$ 和 $\mathcal{A}(24,17)$——"**inspect code → spot pattern → refine search**"的 human-AI feedback loop 首次在数学发现上落地。
- **Online bin packing**：在 OR1-4 和 Weibull 5k/10k/100k 上全面碾压 First Fit / Best Fit——excess-bin 比例从 Best Fit 的 3.79-5.81% 压到 **0.03-5.30%**；Weibull 100k 上只差最优 0.03%。学到的启发式在 training size 之外**跨规模 generalize**，规模越大优势越大。
- **可解释启发式**：发现的 bin packing heuristic 只有十几行代码——不是"best fit 就选最小剩余"，而是"只在 fit 非常紧时才用最小剩余，否则留大 bin"——规避"留下永填不满的小缝"这一 First Fit / Best Fit 的经典病。
- **解 vs 程序的压缩性**：$\mathcal{A}(24,17)$ 明码列表要 20 万 + 向量，FunSearch 生成的程序只有几十行——程序表示让 FunSearch 能 scale 到传统 SAT-based 方法不可企及的维度。

## 相关

- **相关概念**：[[Evolutionary-Search]]、[[Genetic-Programming]]、[[Program-Synthesis]]、[[Island-Model]]、[[LLM-as-Mutator]]、[[Kolmogorov-Complexity]]
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
