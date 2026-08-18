---
type: paper
name: ICL-EF
full_title: "Can AI Scientist Agents Learn from Lab-in-the-Loop Feedback? Evidence from Iterative Perturbation Discovery"
authors: [Gilles Wainrib, Barbara Bodinier, Haitem Dakhli, Josep Monserrat, Almudena Espin Perez, Sabrina Carpentier, Roberta Codato, John Klein]
venue: ICML
year: 2026
tags: [auto-research, experimental-design, in-context-learning, perturbation-discovery, benchmark, domain/auto-research]
source_pdf: "[[icml26-wainrib-lab-loop-feedback.pdf]]"
source_md: "[[icml26-wainrib-lab-loop-feedback]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 科研智能体能否从实验反馈中学习？（ICML 2026）

> **原题**：Can AI Scientist Agents Learn from Lab-in-the-Loop Feedback? Evidence from Iterative Perturbation Discovery

> **一句话总结**：论文用 JUMP Cell Painting 的预计算 p-value 模拟 800 条十轮基因扰动 campaign，以随机置换反馈为反事实控制；Claude Sonnet 4.6 的 ICL-EF 从 zero-shot 的 20.4 个平均命中提高到 29.3，带表型指纹与假设寄存器的 ICBR-EF 达 31.4，但这些“发现”都是约 8,000 个已测基因的离线重检索，不是实际 lab-in-the-loop 或新湿实验（§3–§6，表 1，图 2、5）。

## 问题与动机

使用 [[LLM]] 选择下一批实验时，性能改善可能来自两种完全不同的能力：模型从新实验结果中更新了策略，或模型只是从预训练知识中持续提取相关基因。先前工作发现，把反馈标签随机打乱后性能几乎不变，因而质疑 LLM 是否真的能做面向实验设计的上下文学习（in-context learning, ICL）。

本文把问题缩成可控的顺序选择实验。在 JUMP Cell Painting CRISPR 子集中，每个 target feature 有约 8,000 个基因 knockout 和已计算好的显著性；智能体每轮选 100 个未测基因，查表得到 p-value，十轮后以累计唯一 hit 数计分。随机反馈条件保留每批 hit rate 和 prompt 长度，却在批内打乱 gene–outcome 对应，从而隔离“读取真实反馈内容”与“更长上下文唤醒先验”两种解释（§3.1–3.3）。

题目中的 “Lab-in-the-Loop” 需要严格限定：本文没有调用实验室、仪器或新样本。所谓实验是对公开数据中预计算结果的顺序揭示；验证器是 `p < 0.05` 的确定性查表。它提供的是反馈驱动实验选择的强反事实证据，而非湿实验闭环或开放世界科学发现。

## 关键观察 / 隐含假设

- **观察 1：真实标签结构，而非单纯 prompt 变长，驱动 Sonnet 4.6 的提升。** Random Feedback 平均 18.4 个 hit，低于 zero-shot 的 20.4；ICL-EF 为 29.3，较 Random Feedback 多 10.9，ICBR-EF 为 31.4，多 13.0，二者校正后 `p = 0.003`（§4.6，图 5）。
  - **依赖假设**：批内置换保留了除 gene–outcome 关系外的关键 prompt 属性；跨 iteration 置换可能检验不同的时间顺序混杂，论文未覆盖。
  - **可能失效场景**：真实实验有噪声、延迟、批效应与缺失值，错误反馈可能比本文干净二值标签造成更强的错误固着。

- **观察 2：模型能力阈值决定反馈能否转化为有效行动。** 同一架构和 prompt 下，Sonnet 4.5 的 ICL-EF 只比 zero-shot 多 1.7 个 hit，99% CI 跨 0；Sonnet 4.6 多 8.9，99% CI 为 `[4.50, 15.33]`。对应的 out-of-library proposal 从 45.3% 降到 9.1%（§4.4，表 1、表 5）。
  - **依赖假设**：模型升级的主要可观测机制是 instruction following 改善，但版本同时改变知识、推理和长上下文处理，不能把因果效应只归于 hallucination。
  - **可能失效场景**：候选库不明确、命名不规范或工具能自动约束 action space 时，基因名 hallucination 可能不再是主要瓶颈。

- **观察 3：可利用的家族结构使 ICL 收益高度异质。** ICBR-EF 相对 random 在 F70、F80、F10 上为 6.0、5.1、3.2 倍，难特征 F90 也为 4.1 倍；反馈方法跨 feature 的方差高于 zero-shot，说明它既能放大有效 family lead，也能放大错误固着（§4.3，图 3）。
  - **依赖假设**：十个 feature 跨越的“难度谱”足够代表其他表型；feature 选择方法与预先可见信息没有造成有利筛选。

- **假设 1：命中数量是实验设计质量的充分指标。**
  - **证据强度**：**中**。二值 hit 给出客观、可重复奖励，却忽略效应量、机制多样性、毒性、实验成本和 false discovery control。

- **假设 2：JUMP 中的相关结构能代理真实实验可学习性。**
  - **证据强度**：**弱到中**。公开数据规模大，但本文直接揭示预计算 p-value，没有 plate noise、失败实验或实验时间，环境对 ICL 特别友好。

## 核心方法

每条 campaign 固定十轮，每轮选择 100 个基因，共揭示 1,000/约 8,000 个候选；十个 target feature 的随机 hit rate 约为 1–2%。八个条件各运行十个 replica，合计 800 条 campaign：Random、GP-UCB、Sonnet 4.5 的 zero-shot/ICL-EF，以及 Sonnet 4.6 的 zero-shot/Random Feedback/ICL-EF/ICBR-EF（§3.1，表 1）。

**Zero-shot** 每轮只看 target description、已测/未测基因列表，不看结果。它持续从染色质、核转运、转录等先验类别中选候选，为“静态预训练知识”提供直接基线（附录 A）。

**ICL-EF** 额外读取所有历史 gene、hit/miss 和 target p-value。脚手架还统计成功基因的前四个字母，给出出现最频繁的五个 prefix，引导模型围绕 protein complex、family 和 pathway 做 exploitation，同时要求保留一部分 exploration（§3.2、附录 B）。这不是纯粹“把原始反馈放进上下文”：人工设计的 prefix extractor 已编码“命名相似表示功能相关”的归纳偏置。

**ICBR-EF** 再为近期 8 个 hit、4 个 miss 提供共扰动 CellProfiler feature，并汇总 hit 中最常见的五个共显著表型。模型维护 JSON 假设寄存器，为机制假设标记 confidence 与 Active/Weakened/Abandoned/New 状态；下一轮完整替换寄存器（§3.2、附录 C）。它把历史结果上方增加了一层显式理论状态，但该理论本身没有外部机制 verifier。

**Random Feedback** 使用与 ICL-EF 相同的 prompt 和框架，只在每个 batch 内置换 hit/miss 标签。统计推断先在每个 feature 内平均十次 replica，再以十个 feature 为推断单位做精确双侧 sign-flip permutation，并对全部方法对应用 Benjamini–Hochberg 校正；附录另给 99% hierarchical bootstrap CI（§3.4）。

## 设计取舍

- **预计算查表换取强控制**：所有策略看到同一候选库和确定性结果，便于反事实比较；代价是不存在实验噪声、样本制备、排队和失败恢复。
- **完整历史换取上下文成本**：十轮 campaign 平均消耗约 410,000 input token；更长实验会触及固定 context window，且每次 session 结束后学习完全消失。
- **Prefix exploitation 换取偏差**：家族命名能快速开采 hit，却可能过度偏向易识别的 family，牺牲机制多样性和真正跨 pathway 的探索。
- **假设寄存器换取可审计性**：ICBR-EF 能显式保留、削弱和关闭假设；其额外收益仅 2.1 个 hit，99% hierarchical CI 的边界触及 0，复杂状态管理的回报并不稳固。
- **边界条件**：最适合候选集合封闭、反馈快速可靠、同家族 outcome 高相关的批量筛选；对反馈稀疏、延迟或每次实验成本不同的场景不能直接外推。

## 实验与结果

- Sonnet 4.6 的 zero-shot、ICL-EF、ICBR-EF 平均分别发现 20.4、29.3、31.4 个 hit；Random 为 11.0，GP-UCB 为 19.5，Random Feedback 为 18.4（§4.1，表 1）。
- 相对 zero-shot，ICL-EF 增加 8.9 个 hit（约 43.6%），ICBR-EF 增加 11.0 个（约 53.9%）；相对 Random，ICBR-EF 增加约 185%。论文摘要的 53.4% 对应 best feedback strategy 的量级，不应误读成所有 ICL variant 的统一收益。
- ICL-EF 与 ICBR-EF 均优于 GP-UCB，校正后 `p = 0.003`；但作者明确称 STRING-only kernel 是保守 baseline，更丰富的表达、Gene Ontology 或 learned embedding 可能缩小差距（§3.3、§4.1）。
- Sonnet 4.5 的 zero-shot/ICL-EF 为 20.1/21.8，即表格差 1.7；摘要和表 1 caption 又写成 +0.8，正文内部存在数值口径矛盾。无论用哪个口径，99% CI 都跨 0，结论仍是“不显著”（§4.4，表 1、表 5）。
- Sonnet 4.5 ICL-EF 的 out-of-library proposal 为 45.3%，测试槽位 39–50% 由随机 fallback 填充；Sonnet 4.6 降到 9.1% 和 3–11%。所谓 hallucination 多为真实生物基因，但不在 JUMP 候选库（§4.4，图 4）。
- Random Feedback 较 zero-shot 少 2.0 个 hit，`p = 0.15`；在 6/10 feature 为负，并在 F70/F80/F90 等稀疏结构任务上少 30–40%，说明错误标签会主动误导探索（§4.6，图 5）。
- 每条十轮 campaign 调用 LLM 十次，平均约 410,000 input、19,000 output token；API 成本为 zero-shot 1.41 美元、ICL-EF 1.46 美元、ICBR-EF 1.77 美元。600 条 LLM campaign 约 900 美元，未计数据生成或真实实验成本（§6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Sonnet 4.6 会利用真实实验反馈改善下一轮选择 | §4.6，图 5：ICL-EF 比 Random Feedback 多 10.9 个 hit，`p = 0.003` | 10 个 JUMP feature、每条件 10 replica、预计算二值反馈 | 强 |
| 更丰富的表型反馈与显式假设状态进一步提高命中 | §4.1，表 1：ICBR-EF 31.4 vs ICL-EF 29.3，校正 permutation `p = 0.006` | 99% hierarchical CI 边界为 0；单 assay、单模型版本 | 中 |
| ICL 效果依赖模型能力 | §4.4，表 1、表 5：4.5 的差异不显著，4.6 为 +8.9 且 CI 排除 0 | 仅两个相邻 proprietary model；升级同时改变多种能力 | 中 |
| 错误反馈会系统性损害实验选择 | §4.6：Random Feedback 平均低 2.0，困难 feature 低 30–40% | 批内标签置换；整体差异未显著 | 中 |
| 本文验证的是离线反馈学习而非湿实验发现 | §3.1、§6：结果来自 JUMP 已计算 p-value；作者承认无 batch/noise/delay | 公开 Cell Painting CRISPR 数据；无新实验 | 强 |

## 批判性分析

### 论证链条

“真实反馈比置换反馈好”是本文最强的因果证据。Random Feedback 保留了 prompt 结构和边际 hit rate，且错误内容会让性能变差，因此难以用“上下文更长只是唤醒先验”解释 Sonnet 4.6 的提升。逐轮 learning curve 继续拉开，也与累计反馈利用一致。

但论文证明的是 action selection 发生适应，不是模型发现了正确生物机制。ICL-EF 大量依靠 gene prefix 和已知 complex 关系；ICBR-EF 的假设寄存器由模型自写、没有独立机制标签。把每个 p-value hit 称为 discovery 会放大证据等级：这些 outcome 在原始 JUMP 实验中早已存在，只是对当前 agent 暂时隐藏。

### 假设压力测试

真实实验中的 false positive、plate effect 和 batch drift 会破坏“一个 hit → 开采整个 family”的策略。Random Feedback 已显示错误 lead 能让模型固着，正说明本文收益可能对反馈质量非常敏感。若每轮只返回延迟几天后的 noisy effect size，完整上下文和 prefix shortcut 的优势可能显著下降。

公开 JUMP 数据还存在预训练污染。Random Feedback 能证明模型利用了本轮反馈内容，却不能判断 zero-shot 的 20.4 个 hit 中多少来自见过同一数据或论文；也不能证明反馈后提出的邻近基因不是把静态关联重新排序。

### 实验可信度

十个 feature、十次 replica、反事实反馈和 feature-level permutation 比单次 retrospective demo 强得多。作者没有把 replica 当作独立 feature 扩大样本量，并报告多重比较校正和 hierarchical CI，这是优点。

局限在于 benchmark 只用一种 assay、两版 Claude，且 GP-UCB 被刻意设成保守 baseline，论文也没有直接比较先前主张更稳健的 LLMNN。表 1 caption/摘要对 Sonnet 4.5 效应写 +0.8，表格与正文为 +1.7；“所有 10 feature 显著”与正文对 ICL-EF “7/10 显著”的叙述也需谨慎区分 variant。

### 系统性缺陷

- **候选约束**：即使 prompt 提供完整未测列表，Sonnet 4.5 仍有 45.3% proposal 越界，必须靠随机 fallback 才填满 batch。
- **状态长度**：历史列表不断增长，十轮已约 41 万 input token；真实长程 campaign 需要检索、压缩和遗忘策略。
- **停止与安全**：系统固定十轮、固定 1,000 个实验，没有样本效率停止规则、毒性约束或实验成本差异。
- **机制可信度**：假设 register 只有自然语言自洽性，没有因果扰动、专家复核或独立 assay 验证。
- **实验执行缺席**：所有 outcome 都是查表，论文没有测试 lab scheduler、机器人、质量控制或失败恢复。

## 局限与后续工作

- **局限 1**：公开 JUMP 单一 assay 和两个 Claude 版本，外部有效性与 model-proof 性都有限。
- **局限 2**：预计算、干净、即时二值反馈比真实实验更容易；未覆盖噪声、延迟、batch effect 和失败实验。
- **局限 3**：hit count 偏向可密集开采的 gene family，不评价机制新颖性、效应量或多样性。
- **局限 4**：没有 LLMNN 或更强 kernel/embedding Bayesian optimization 的同环境比较。
- **后续工作 1**：按预注册噪声率和 1–3 轮延迟扰动 feedback，测量 ICL 收益、错误固着率和恢复时间。
- **后续工作 2**：在新 assay 或时间切分的未公开 perturbation 上 blind test，再由真实实验复测 top candidate，报告 hit precision 与 false discovery rate。
- **后续工作 3**：用 action mask 彻底禁止库外基因，再比较 4.5/4.6，以分离 instruction-following 与反馈推理能力。
- **后续工作 4**：在等 API token 与等实验预算下加入 LLMNN、丰富 GP kernel 和 learned acquisition baseline。

## 相关

- **相关概念**：[[LLM]]、上下文学习、顺序实验设计、贝叶斯优化、Cell Painting
- **同类系统与基准**：[[HeurekaBench-ICLR26]]、[[DDR-Bench-ICML26]]、[[CausalGame-ICML26]]
- **相关主题**：[[Auto-Research]]
- **同会议**：ICML 2026
