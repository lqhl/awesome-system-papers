# Mathematical Discoveries from Program Search with Large Language Models (FunSearch)

**作者**：Bernardino Romera-Paredes, Mohammadamin Barekatain, Alexander Novikov, Matej Balog, M. Pawan Kumar, Emilien Dupont, Francisco J. R. Ruiz (Google DeepMind); Jordan S. Ellenberg (University of Wisconsin-Madison); Pengming Wang, Omar Fawzi, Pushmeet Kohli, Alhussein Fawzi (Google DeepMind / Université de Lyon)
**会议**：Nature, 2024
**链接**：[Nature doi: 10.1038/s41586-023-06924-6](https://doi.org/10.1038/s41586-023-06924-6)
**源文件**：[[funsearch.pdf]]

---

## 一、背景

LLM 在代码生成、数学推理等复杂任务上展现了巨大能力，但其"幻觉"（confabulation）问题严重限制了在科学发现中的应用——LLM 可能生成看似合理但实际错误的结论，且难以自动验证。与此同时，数学和组合优化中存在大量"难以求解但容易验证"的问题（如 NP 完全问题），即给定候选解可以高效评估其质量，但寻找最优解极其困难。传统方法（如 SAT solver、暴力搜索）在搜索空间爆炸时力不从心，而遗传编程（genetic programming）虽然能进化程序，但需要人工设计突变算子且缺乏对代码模式的先验理解。

---

## 二、要解决的问题

1. **LLM 幻觉阻碍科学发现**：直接用 LLM 解决开放数学问题时，模型倾向于生成"看似正确但实际错误"的答案，且无法超越训练数据中已有的结果。
2. **传统搜索方法不可扩展**：对于 cap set 等组合问题，暴力搜索空间指数级增长（如 8 维时约 $3^{1600}$），传统 solver 依赖人工施加的搜索空间限制，可能错过最优解。
3. **遗传编程的局限**：传统 GP 需要人工定义 mutation operators，这是 problem-specific 的，且生成的代码质量远低于人类水平。
4. **解的可解释性**：直接搜索解（如一组向量）得到的结果难以理解和推广，也难以部署到实际系统中。

---

## 三、洞察与设计

**关键洞察**：对于结构化问题，解可以用一个简短程序来描述（低 Kolmogorov 复杂度），而非枚举所有元素。在程序空间（function space）而非解空间（solution space）中搜索，既能利用 LLM 对代码模式的先验知识作为高质量突变算子，又能通过自动评估函数过滤掉幻觉——程序要么执行正确并得到可量化的分数，要么被丢弃。

基于此洞察，FunSearch 设计了一个将 LLM 与进化算法结合的闭环系统：

1. **Specification（问题规约）**：用户提供一个 `evaluate` 函数（评估候选解质量）和一个程序骨架（skeleton）。骨架包含 boilerplate 代码，只留出关键逻辑部分（如贪心算法中的 `priority` 函数）交给 FunSearch 进化。这一设计将 LLM 的注意力聚焦在最核心的逻辑上。

2. **Pre-trained LLM（创意引擎）**：使用冻结的 Codey（PaLM2 微调的代码模型）作为突变/交叉算子。LLM 不需要理解问题本身，只需作为"语法正确且偶尔有有趣想法"的程序来源。实验表明结果对 LLM 选择不敏感（StarCoder 也有效）。

3. **Evaluation（守门员）**：自动执行生成的程序并评分，不正确的程序（执行超时、产出无效）直接丢弃。这是对抗 LLM 幻觉的关键机制。

4. **Programs Database（岛屿模型）**：采用 island-based 进化策略维护多样化的程序种群。多个 island 独立进化，定期淘汰表现最差的一半 island 并用最佳 island 的程序重新 seed。island 内部按 signature（各输入上的得分元组）聚类，采样时偏好高分 cluster 和短程序。

5. **Best-shot Prompting**：从同一 island 采样 $k=2$ 个程序按分数排序构建 prompt（`priority_v0`, `priority_v1`），让 LLM 生成 `priority_v2`。多程序 prompt 使 LLM 能发现跨程序的模式并泛化。

---

## 四、实现细节

FunSearch 实现为分布式系统，包含三类 worker：

- **Programs Database**：存储和提供程序，实现 island 模型和采样逻辑
- **Samplers**：执行 LLM 推理，每个 prompt 生成多个样本以提高吞吐量
- **Evaluators**：执行程序并评分，运行在廉价 CPU 上

典型配置：15 个 sampler（需 GPU 加速推理）+ 150 个 CPU evaluator（5 台服务器，每台 32 个并行评估器）。三类 worker 异步通信。

**Island 进化策略细节**：
- 每 4 小时执行一次 island 重置：淘汰得分最低的 $m/2$ 个 island，从存活 island 中随机选一个的最高分程序作为 seed
- Cluster 采样使用 Boltzmann 选择，温度随 island 中程序数量线性衰减
- 程序内采样偏好较短的程序（负长度归一化后 softmax）

**总样本量**：约 $10^6$ 次 LLM 采样。

**代码规模**：FunSearch 的核心算法、代码操作工具和单线程实现已开源于 GitHub。

---

## 五、实验结果

### Cap Set 问题

在 $\mathbb{Z}_3^n$ 中寻找最大 cap set（无三向量和为零的集合）：

| 维度 $n$ | 3 | 4 | 5 | 6 | 7 | 8 |
|---------|---|---|---|---|---|---|
| 已知最优 | 9 | 20 | 45 | 112 | 236 | 496 |
| FunSearch | 9 | 20 | 45 | 112 | 236 | **512** |

- 8 维发现了 512 大小的 cap set，超越了之前 20 年来的最优记录 496
- 140 次实验中有 4 次找到 512-cap（成功率约 3%）
- 通过人工解读发现的 `priority` 函数，提取出 "reflections" 对称性，进而手工构造出显式的 512-cap

### Admissible Sets 与 Cap Set Capacity 下界

| 来源 | Admissible Set | Capacity 下界 |
|------|---------------|--------------|
| Calderbank & Fishburn, 1994 | $\mathcal{I}(90,89)$ | 2.2101 |
| Edel, 2004 | $\mathcal{I}(10,5)$ | 2.2173 |
| Tyrrell, 2022 | $\mathcal{I}(11,7)$ | 2.2180 |
| FunSearch | $\mathcal{I}(12,7)$ | 2.2184 |
| FunSearch | $\mathcal{I}(15,10)$ | 2.2194 |
| FunSearch | $\mathcal{A}(24,17)$ | **2.2202** |

- 将 cap set capacity 的下界从 2.2180 提升到 2.2202，是 20 年来最大的改进
- 通过解读代码发现新的对称性，进而定义 symmetric admissible sets，缩小搜索空间后找到更大维度的结果

### Online Bin Packing

| 算法 | OR1 | OR2 | OR3 | OR4 | Weibull 5k | Weibull 10k | Weibull 100k |
|------|-----|-----|-----|-----|-----------|------------|-------------|
| First Fit | 6.42% | 6.45% | 5.74% | 5.23% | 4.23% | 4.20% | 4.00% |
| Best Fit | 5.81% | 6.06% | 5.37% | 4.94% | 3.98% | 3.90% | 3.79% |
| FunSearch | **5.30%** | **4.19%** | **3.11%** | **2.47%** | **0.68%** | **0.32%** | **0.03%** |

（数值为超出 $L_2$ 下界的 excess bins 比例，越低越好）

- 在所有数据集上超越 First Fit 和 Best Fit
- 仅在 OR1 规模的实例上训练，但泛化到更大实例时性能差距更大
- Weibull 100k 实例上仅比下界多 0.03%
- 发现的启发式揭示了通用策略：不是总选最满的 bin，而是只在"紧密适配"时才放入最满的 bin

---

## 六、批判性分析

1. **Cap Set 成功率极低**：8 维 512-cap 的发现依赖 140 次独立实验，仅 4 次成功（~3%），这使得方法的实际可复现性存疑。论文承认了这一点但未深入分析失败模式——究竟是陷入局部最优还是搜索空间本身的困难？

2. **人工介入不可忽视**：最重要的突破（symmetric admissible sets）实际上依赖研究者手工解读代码、发现对称性、重新定义搜索空间。这不是纯粹的自动化发现，而是 human-in-the-loop 的迭代过程。论文在叙事上倾向淡化这一点。

3. **Bin Packing 基线偏弱**：仅对比 First Fit 和 Best Fit 这两种最基础的启发式。文献中存在大量改进的启发式（如 Harmonic、memory-augmented 方法），以及 RL-based 方法，均未纳入比较。声称"发现新算法"可能过于夸大。

4. **可扩展性声明不充分**：论文声称 FunSearch 比传统 solver 更可扩展，但对比实验仅在 Appendix 中简要提及，未给出公平的计算资源对比。15 个 GPU sampler + 150 个 CPU evaluator 的配置成本不低。

5. **LLM 的实际贡献不清晰**：论文承认 LLM "不使用太多问题上下文"，只是"偶尔有有趣想法的语法正确程序源"。那么 LLM 相比一个经过良好设计的随机代码生成器（如基于语法的 fuzzer）的边际贡献到底有多大？Appendix 中的 ablation 不够充分——虽然对比了 random mutation，但 random mutation 的设计空间本身很大。

6. **问题适用范围有限**：作者明确指出 FunSearch 目前只适用于有高效评估函数、丰富打分信号、且能提供 skeleton 的问题。这排除了大量重要的科学发现场景（如定理证明、需要二值判断的问题）。

---

## 七、AI Infra / MLSys 视角

1. **分布式异步进化架构**：FunSearch 的三类 worker（Database / Sampler / Evaluator）异步通信的架构设计值得 AI Infra 借鉴。特别是将昂贵的 LLM 推理（GPU）与廉价的评估（CPU）解耦，可以类比推理系统中的 prefill/decode 分离或 speculative decoding 的架构思路。

2. **LLM 作为代码搜索的 mutation operator**：这一范式可以直接迁移到 AI 系统的自动优化场景——例如自动搜索 CUDA kernel 实现、内存调度策略、通信拓扑等。关键要素是问题必须有自动化的评估函数（如 benchmark throughput / latency），这在 MLSys 中非常自然。

3. **Island 模型的多样性维护**：在 hyperparameter tuning 或 neural architecture search 中，避免搜索陷入局部最优是核心挑战。FunSearch 的 island-based 策略（定期淘汰+重新 seed）提供了一种轻量级的 exploration 机制。

4. **可操作的 Future Work 方向**：
   - 用 FunSearch 搜索 ML compiler 的 scheduling 策略（如 XLA、TVM 的 tile size / loop order）
   - 自动发现分布式训练的通信优化启发式（如 gradient compression、pipeline scheduling）
   - 搜索 KV cache eviction 策略——评估函数天然可用（cache hit rate / perplexity）

---

## 八、总结

FunSearch 提出了一种将预训练 LLM 与进化算法结合的程序搜索框架，通过在函数空间而非解空间中搜索，利用自动评估函数过滤 LLM 幻觉，在 cap set 问题上实现了 20 年来首次突破（8 维 512-cap），并在 online bin packing 上发现了优于经典启发式的新算法。其核心优势在于搜索结果是可解释的程序而非不透明的数值解，支持人机协作的迭代发现流程。主要局限在于成功率较低（需大量独立实验）、依赖人工设计 skeleton 和评估函数、以及适用范围受限于"易评估"类问题。
