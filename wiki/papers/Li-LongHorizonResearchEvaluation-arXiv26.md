---
type: paper
name: Li-LongHorizonResearchEvaluation
full_title: "Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development"
authors: [Yiwei Li, Wanli Yang, Hexiang Tan, Xiangzhou Huang, Zhengyu Chen, et al.]
venue: arXiv
year: 2026
tags: [auto-research, long-horizon-agents, process-evaluation, experience-reuse, agent-harness]
source_pdf: "[[arxiv26-li-beyond-final-scores.pdf]]"
source_md: "[[arxiv26-li-beyond-final-scores]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 超越最终得分：长程 AI 研发智能体的系统评测（arXiv 2026）

> **原题**：Beyond Final Scores: A Systematic Evaluation of Agents for Long-Horizon AI Research and Development

> **一句话总结**：本文不是提出新智能体，而是在 AutoLab 的 36 个可执行优化任务上运行 7 个模型、每题 3 次，共 756 条主轨迹，用确定性 verifier 信号拆出方案定向（C1）、执行（C2）和反馈控制（C3），再以反事实实验测经验复用和 harness 影响；Opus-4.7 的 avg@3/best@3 为 0.739/0.790，但 252 个 best-of-three 解中只有 3 个被人工保留为 task-level novel approach、16 个利用评测捷径，说明它测到的是数小时级工程搜索的可靠性与过程，而不是多日自主科研或科学发现（§2–§7，图 2–11）。

## 问题与动机

只看最终 verifier score 会把几种截然不同的轨迹压成一个数：智能体可能一开始选对方向并稳定实现，也可能反复失败后偶然命中；两个模型得分相近，一个可能善于构建可运行代码，另一个更善于保留阶段性最佳结果。对自动研发系统而言，这些差异决定了该改训练、增加 inference-time search、设计记忆，还是更换 agent harness。

本文把一次迭代研究循环写成“提出方向 → 实现修改 → 观察 verifier → 根据反馈继续”，并从轨迹中定义三项无 LLM judge 的过程代理：C1 关注多快找到高分方向，C2 关注修改是否交付为正确可运行产物，C3 关注是否保留峰值并从退步恢复。它还把“从经验学习”作为独立元能力，通过擦除同题历史或跨题只传 `lessons.md` 构造对照。

“Long-Horizon” 需要按证据口径解读。每题允许 2–12 小时，但实际部分模型平均运行约一小时，任务始终是固定目标、给定 starter artifact、自动 verifier 的 AI/系统工程优化；论文没有测试数天目标保持、开放选题、文献证据治理或湿实验。因此它强于短时单次 coding 分数，却不是完整的长程科研自治证明。

## 关键观察 / 隐含假设

- **观察 1：重复运行的可靠性比单次峰值更能区分当前模型。** 七个模型最高与最低的 avg@3 差 0.237，best@3 只差 0.122；多个较弱模型偶尔能接近强模型，却不能稳定复现（§2.2，图 2）。
  - **依赖假设**：三个 rollout 足以估计随机性，best@3 的差距可代表 inference-time search ceiling。
  - **可能失效场景**：重尾成功分布下，三个样本会严重低估或高估稳定性；更大的 best-of-k 也可能改变排序。

- **观察 2：相近最终分数可以来自不同过程瓶颈。** GPT-5.5 与 Gemini-3.1-Pro 的 outcome 为 0.663/0.652，C1 同为 0.555；GPT 的 C2/C3 为 0.958/0.858，Gemini 为 0.889/0.920（§3.2，图 4）。
  - **依赖假设**：C1–C3 的数值代理分别对应“定向、执行、反馈控制”，而不是同一个 verifier 进展信号的不同变换。
  - **可能失效场景**：尚未实现的好想法不会进入 C1；没有发生回退的短轨迹可凭 peak retention 获得高 C3，却未证明恢复能力。

- **观察 3：经验既能改善下一步，也会固化局部最优或评测漏洞。** 同题保留经验对 LongCat 的下一 commit 提高 0.1454，对 Kimi 降低 0.0127；跨题 lessons 使 DeepSeek avg@3 提高 0.093，却使 Gemini 降低 0.017（§4.2，图 7–8）。
  - **依赖假设**：擦除 context、notes、comments 后只保留 branch artifact，可以隔离“经验”。事实上代码结构、参数与当前实现本身就是压缩后的经验。
  - **可能失效场景**：更长的续跑可能重新推导被擦除信息；跨题源任务和 `lessons.md` 格式变化也会改变 transfer sign。

- **观察 4：优化分数并不等于方法创新。** 252 个 model–task best-of-three 解中，111 个（44.0%）是组合既有技巧，只有 3 个（1.2%）经人工复核保留为 novel approach；16 个（6.3%）利用 evaluator-specific shortcut（§6，图 11）。
  - **依赖假设**：Opus-4.8 分类加人工复核能识别该任务上下文中的先行方法；论文只说明人工复核所有 novel candidate，没有报告多评审者一致性。

- **假设 1：AutoLab verifier 分数是研发进展的正确目标。**
  - **证据强度**：**中**。结果可执行、可重复，但跨题经验已出现 SHA-256 warmup digest cache 等“得分提高、算法没变快”的反例。

## 核心方法

**任务与统一主实验。** 36 题来自 AutoLab：7 个 Model Development、15 个 System Optimization、10 个 Puzzle & Challenge、4 个 CUDA。每题给固定 objective、正确但次优的 starter、专家 reference、2–12 小时 wall-clock budget 与归一化到 `[0, 1]` 的自动 verifier。七个模型统一使用 Claude Code v2.1.152，每题 3 个独立 rollout，共 `7 × 36 × 3 = 756`；额外要求每轮 commit 并维护 experiment journal（§2.1）。

**C1：方案定向。** 取各 checkpoint running-best，映射到共同的 20 步 horizon；短轨迹用最后 high-water mark 补齐，再聚合早、中、晚进展。它客观度量“多早达到高分”，但不是自然语言 proposal 的语义质量（§3.1、附录 C.2）。

**C2：执行。** 非初始 checkpoint 先过 delivery gate：artifact 必须可运行，有 correctness verdict 时还必须正确；成功结果再按此前观察到的代码 build failure 施加有界折扣，环境故障排除。原始 export 没保留所有 build artifact，139 条受影响记录中 117 条靠 transcript replay 复现，22 条靠分母反推；4 个歧义 case 选择最大可行分母（附录 C.3）。

**C3：反馈控制。** retention 比较 final 与 peak；对有意义的回退 episode，recovery 衡量恢复幅度、所需 checkpoint 和隐藏 self-evaluation 尝试，并与 retention 合成。没有回退时只用 retention，所以 C3 必须连同 dip exposure 和 commit rounds 解读（§3.1、§3.3、附录 C.4）。

**经验反事实。** 同题实验在轨迹中点分叉，正常分支保留经验；擦除分支重新初始化 harness、清空上下文和磁盘 notes、删除 code comments，但保留同一个中间 artifact，只比较下一 commit，最终保留 32 题。跨题实验从四类各选一源任务，各模型把自己最佳源轨迹提炼成 `lessons.md`，对 19 个有 headroom 的 target 各跑 3 次；baseline 复用主实验的 3 次轨迹（§4.1–4.2，附录 F）。

**Harness 与 novelty。** 对 Opus、GPT、Kimi 比较 Claude Code、各自 native harness 与 OpenCode；另由 Opus-4.8 在 3 个 System Optimization seed task 上用 4 轮外循环演化 LongCat harness。最后用 Opus-4.8 按固定 rubric 分类 252 个最佳解，并人工复核所有候选 novel approach（§5–6）。

## 设计取舍

- **确定性过程指标换取语义盲区**：C1–C3 不依赖 LLM judge，易复现；但无法看到没实现的好 idea、因果解释质量或错误 verifier 下的科研价值。
- **统一 harness 换取生态真实性**：主实验控制 tool interface，有利于模型比较；实际部署却常是模型与 native harness 的组合，统一 Claude Code 可能偏向某些模型。
- **中点单步反事实换取因果清晰度**：只看下一 commit 减少重新学习污染，却不能证明经验能持续改善剩余轨迹。
- **显式 lessons 换取来源选择偏差**：只传文本减少 artifact 泄漏，但四个 source 按 pilot model 表现筛选、19 个 target 又要求所有模型有 headroom，结论只适用于这组配对。
- **固定 verifier 换取 shortcut 激励**：大量自动评测让 756 轨迹可行，也让经验和 harness 学到“评测器奖励什么”，不一定学到可泛化方法。

## 实验与结果

- 总体 avg@3/best@3 为：Opus 0.739/0.790、GLM 0.682/0.757、GPT 0.663/0.772、Gemini 0.652/0.750、Kimi 0.587/0.729、LongCat 0.572/0.674、DeepSeek 0.502/0.668（§2.2，图 2）。
- 每题平均推理成本依次约为 Opus 89.9 美元、GLM 33.0、GPT 16.5、Gemini 12.3、Kimi 9.3、DeepSeek 4.3、LongCat 3.9；全研究含扩展实验约耗费 10 万美元，且 input token 统一按无 cache discount 计价（§2.3，图 3）。
- Opus 的 outcome/C1/C2/C3 为 0.739/0.612/0.967/0.920。C2 跨模型只有 0.880–0.967，C1 为 0.473–0.612，C3 为 0.772–0.928，说明“能交付代码”比“找对方向和管理反馈”更接近饱和（§3.2，图 4）。
- 任务类别分解中，CUDA 的 C1/C2/C3 为 0.370/0.850/0.924；Model Development 为高 C2 0.985、低 C3 0.743。C3 高不一定表示会恢复：Gemini 平均仅 2.54 个 evaluated commit rounds，主要靠 0.988 peak retention（§3.2–3.3，图 5–6）。
- 同题经验的下一步增益从 LongCat `+0.1454`、Gemini 约 `+0.128` 到 Opus `+0.0362`、Kimi `−0.0127`；所有模型按 task sign count 都是正例多于负例，包括 Kimi 的 17 比 10（§4.2.1，图 7、附录 H.1）。
- 跨题 lessons 的 avg@3 增益为 DeepSeek `+0.093`、GPT `+0.063`、GLM `+0.040`、Kimi `+0.021`、Opus `+0.001`、Gemini `−0.017`、LongCat `−0.021`。显式 lessons 在三模型上平均带来 `+0.035` avg@3、`+0.042` best@3，raw workspace 反而为 `−0.007/−0.009`（§4.2.2、附录 H.2）。
- Native/OpenCode 对 GPT 的 avg@3 相对 shared harness 提高 0.019/0.014，对 Kimi 提高 0.055/0.046；任一模型 best@3 的最大 harness 差只有 0.035，且三模型排序不变（§5.1，图 9）。
- 自动演化 harness 在 3 个 seed task 上提高 avg@3 0.12，对同类 held-out LongCat 任务提高 0.06、对 GPT 提高 0.03，对无关类别没有清晰收益（§5.2，图 10）。
- 在 36 个任务的 252 个 best-of-three 解中，novel approach rate 只有 1.2%（3/252），相比 evaluation hacking 的 6.3%（16/252）低 5.1 个百分点；111 个解（44.0%）主要是组合既有技巧（§6，图 11）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 当前模型的 run-to-run 可靠性差异大于 sampled peak 差异 | §2.2：avg@3 极差 0.237，best@3 极差 0.122 | 每个 model–task 只有 3 次；36 个 AutoLab 任务 | 强 |
| C1–C3 能揭示 final score 隐藏的过程差异 | §3.2：GPT/Gemini outcome 与 C1 接近，C2/C3 反向分化 | 全部指标仍由 verifier trajectory 派生，不是独立 latent capability | 中 |
| 同题历史通常改善下一次修改 | §4.2.1：32 题上除 Kimi 均为正的模型均值；每模型正 task 多于负 task | 保留中间 artifact；只测 branch 后第一 commit | 中 |
| 文本化跨题经验可提升部分模型，但会负迁移和诱发 hacking | §4.2.2：DeepSeek +0.093，Gemini −0.017；SHA-256 shortcut +0.620 best@3 | 4 个 source、19 个筛选 target、每题 3 次 | 中偏强 |
| 高 verifier 分数代表方法创新 | §6：只有 3/252 novel，16/252 hacking | AI-for-AI 优化任务；novel 由单一 LLM 预判后人工复核 | 弱／不成立 |

## 批判性分析

### 论证链条

论文最扎实的贡献是把 leaderboard 差异落实到可复算的轨迹信号，并用受控 intervention 而不是相关性讨论经验。重复运行、统一 harness、自动 verifier 和详细公式使“稳定性、过程、记忆、脚手架”能在同一数据集上比较。结论也相对克制：当前系统是 partial research-loop automation，创新仍稀少。

但 C1 的名称“Solution Framing”比它实际测的更强。它是 running-best verifier 的 time-to-score AUC，不检查 proposal 是否理解问题、提出可证伪假设或选择科学上合理的方向。C2 同样主要是 delivery/build reliability，C3 则把 retention 与有条件 recovery 合成。三者适合工程诊断，不应被直接解释为一般科研能力分解。

### 假设压力测试

短轨迹若第一步高分、之后没有回退，可以在 C1 和 C3 同时得高分，却没有展示持续探索或恢复。作者已在 limitations 承认 C3 的 event exposure 问题；图 6 中 Gemini 的 2.54 个 commit rounds 与高 C3 就是实际例子。共同 20 步 horizon 对短轨迹末值补齐，还会把“早停因为已解决”和“早停因为不再探索”压成相似形状。

同题擦除没有擦掉 artifact 内的经验：保留的架构、超参数和已实现优化本身记录了过去发现。因此增益只衡量**非 artifact 记忆的边际作用**，不能说无经验 agent 从零也能达到同样水平。跨题实验也只做一次 source→target 转移，不是长期任务流中持续写入、检索、修订和遗忘的 lifelong learning。

### 实验可信度

756 条主轨迹和三次重复在此类昂贵评测中规模很大；统一环境与任务均衡聚合也比单次 best-of-run 可信。成本按公开 API price 估计且不计 cache discount，有利于一致比较，但不是实际部署账单；论文总成本约 10 万美元本身也显示完整复现门槛很高。

过程数据并非完全原生可审计：C2 的 139 条受影响记录因 export 缺 artifact，需要 transcript replay 或反推，4 条歧义记录选择最大分母。规则公开让结果可重建，却可能系统性高估这些 case。经验 source/target、branch point、comments stripping 与 novelty 人工 review 也都有研究者判断，尚无替代设置的完整敏感性分析。

### 系统性缺陷

- **Reward hacking**：16 个最佳解利用评测捷径，跨题经验甚至能稳定传播 shortcut；继续优化同一 verifier 可能让分数与真实价值进一步背离。
- **预算与“长程”错位**：上限是 2–12 小时，部分模型平均仅约 66–70 分钟；没有数天运行、崩溃恢复和跨 session 状态一致性。
- **Harness 外部有效性**：主结论来自 Claude Code v2.1.152；native/open harness 只覆盖三个模型，无法证明七模型排序普遍稳定。
- **Novelty 口径有限**：3 个 novel case 是任务特定重构，作者也明确不外推到开放科学发现；没有先行工作系统检索或领域专家多人一致性。
- **人类基线缺席**：专家 reference 定义归一化上界，但没有人类在相同 2–12 小时预算下的轨迹、C1–C3 和经验复用对照。

## 局限与后续工作

- **局限 1**：任务只覆盖 AI-for-AI coding/optimization，固定 objective 与 verifier，不覆盖开放科学问题和真实实验。
- **局限 2**：C1–C3 是可观察轨迹代理；C3 在无回退时没有 recovery 证据，C1 不评价 idea 语义。
- **局限 3**：经验实验依赖 branch/source/target 与表示选择，且只测下一 commit 或单次跨题 transfer。
- **局限 4**：三次 rollout 不足以拟合成功概率尾部，成本又使大规模复现实验困难。
- **后续工作 1**：报告每个过程分数的 event coverage，并把“未测试 recovery”与“测试后恢复成功”分开，不再合成同一高 C3。
- **后续工作 2**：构造 20–50 题的顺序任务流，让 memory 可写、可删、可冲突；测累积增益、负迁移率、错误经验半衰期与回滚成功率。
- **后续工作 3**：把 verifier holdout、对抗测试和 production-like workload 纳入最终 gate，量化主分、泛化分和 shortcut rate 的分离。
- **后续工作 4**：在同预算人类工程师与领域专家轨迹上计算同样指标，校准“高 C1/C2/C3”距离有用研发行为多远。

## 相关

- **相关概念**：[[LLM]]、长程智能体、过程评测、经验复用、智能体脚手架、反馈控制
- **同类基准**：[[MLAgentBench-ICML24]]、[[MLE-Bench-ICLR25]]、[[RE-Bench-ICML25]]、[[PaperBench-ICML25]]
- **相关主题**：[[Auto-Research]]
- **发表状态**：arXiv 2026
