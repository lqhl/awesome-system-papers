---
type: paper
name: GEPA
full_title: "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning"
authors: [Lakshya A Agrawal, Shangyin Tan, Dilara Soylu, Noah Ziems, Rishi Khare, et al.]
venue: ICLR
year: 2026
tags: [prompt-optimization, evolutionary-search, reflection, compound-ai, sample-efficiency, domain/auto-research]
source_pdf: "[[iclr26-agrawal-gepa.pdf]]"
source_md: "[[iclr26-agrawal-gepa]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-12
---

# 反思式提示词演化可以胜过强化学习（ICLR 2026）

> **原题**：GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning

> **一句话总结**：GEPA 抓住复合 AI 系统的运行轨迹和评估器诊断本身就是高密度自然语言学习信号这一观察，以反思式 prompt 变异、按样例维护的 Pareto 候选选择和可选的系统感知合并替代权重更新；在 Qwen3-8B 的六项任务上平均比 24,000-rollout 的 GRPO 高 6 个百分点、最高高 19 个百分点，且达到最优结果所需 rollout 少 4–35 倍，但结论依赖可序列化轨迹、可靠反馈函数和固定模型已有的反思能力。

## 问题与动机

复合 AI 系统（compound AI system）把一个或多个 LLM 模块与检索、工具调用和控制流组合起来。常见适配方法是用 [[GRPO]] 等强化学习（reinforcement learning，RL）算法根据最终标量奖励更新模型权重，但一次 rollout 可能包含昂贵的模型、检索或代码执行调用，数万次采样因而成为现实瓶颈；闭源模型还根本不允许更新权重。

论文的关键反问是：既然系统的推理、工具调用、模块输入输出和评估器报错都能表示成语言，为何要先把它们压缩成一个标量，再从稀疏奖励估计梯度？作者提出 GEPA（Genetic-Pareto），让固定权重的 LLM 直接阅读这些轨迹，用自然语言归纳错误原因和任务规律，然后改写系统中各模块的 prompt。

其 claim 边界不是“prompt 优化普遍取代 RL”。正式实验覆盖六个推理、指令遵循、隐私委托与检索验证任务，以及 Qwen3-8B、GPT-4.1 Mini 两个目标模型；代码优化和对抗 prompt 搜索是推理时搜索的扩展案例。论文证明的是：在这些有训练/验证集、可自动评分且轨迹可读的复合系统上，语言空间搜索能以更少 rollout 得到更高的 held-out 分数。

## 关键观察 / 隐含假设

- **观察 1：标量奖励丢弃了最有用的诊断信息。** 执行轨迹包含各模块的推理与工具输出，评估轨迹还可能包含编译错误、失败 rubric 或人工解释；反思模型可利用它们做隐式 credit assignment，定位应改写哪个 prompt（§3）。
  - **依赖假设**：失败原因能被可靠地序列化，且反思模型能从少量轨迹归纳出可泛化规则，而不是只记住样例。
  - **可能失效场景**：只有黑盒标量奖励、反馈与真实目标错位、轨迹过长或隐藏状态主导结果时，语言反馈不再是高密度学习信号。
- **观察 2：总分最好的 prompt 未必包含所有可迁移策略。** 某些候选只在少数样例上领先，却可能代表尚未充分探索的有效方向；总是变异全局最佳候选会迅速陷入局部最优（§3.1、图 4）。
  - **依赖假设**：按样例的局部赢家确实反映互补策略，而不是评估噪声或偶然过拟合。
  - **证据强度**：中；固定 evolution harness 下，Pareto 选择的 Qwen3-8B 四任务 aggregate 提升为 12.44 个百分点，高于 greedy 的 6.05 和 beam search 的 5.11，但未报告多随机种子误差。
- **假设 1：固定模型已具备足够强的反思与指令遵循能力。** GEPA 不更新目标模型权重；收益来自模型先验被更好的 prompt 激活。论文也把“新模型更善于遵循和反思”作为纯指令优化反超 few-shot 优化的解释（§4、附录 H）。
  - **证据强度**：中；Qwen3-8B 与 GPT-4.1 Mini 都得到提升，且 Qwen 优化的 prompt 可迁移到 GPT-4.1 Mini，但只覆盖两个模型家族。
- **假设 2：验证集反复选择候选不会造成不可接受的自适应过拟合。** GEPA 用 `D_pareto` 逐候选评分并选择最终 program，且多数 rollout 都耗在验证上。
  - **可能失效场景**：验证集小、分布漂移强或迭代预算很大时，Pareto 前沿会放大样例级噪声；独立 test set 只证明本文配置下的泛化，不能消除更长期的 validation overfitting。

## 核心方法

GEPA 的候选是复合系统全部模块 prompt 的一个具体版本，目标模型权重始终冻结。优化从 seed program 开始，在 rollout 预算耗尽前重复“选父候选—采样训练 minibatch—生成变体—小批评估—若优于父候选则进入候选池并在 `D_pareto` 上评分”的循环（图 3、附录算法 1）。最终返回验证集 aggregate 最好的候选。

**反思式 prompt 变异（reflective prompt mutation）**先运行被选候选并记录每个模块的输入、输出和推理，再由反馈函数 `μ_f` 同时返回数值分数与文本诊断。反思 LM 读取当前 prompt、完整轨迹、分数和诊断，对成功/失败做模块级 credit assignment，并提出新指令；多模块系统按 round-robin 选择本轮更新的模块。这使一次变异能积累高层任务规律，而不是随机替换词句。

**按样例的 Pareto 候选选择**为每个训练实例记录历史最高分，保留至少在一个实例上并列最佳的候选，剪掉严格被支配者。采样候选时，概率按它领先的实例数量加权。这个“illumination”策略保留多条局部赢家 lineage，使搜索不会只围绕当前 aggregate 最优点反复微调。

**系统感知合并（system-aware merge）**是可选 crossover：从两条 lineage 中按模块挑选各自已经演化、可能互补的 prompt，组合成新系统，而不是把两段自然语言盲目拼接。它在 GPT-4.1 Mini 上常有增益，但固定的调用时机和预算分配会让 Qwen3-8B 退化，说明 merge 尚不是稳定的默认组件（附录 D.1、H）。

正式论文聚焦 prompt 和复合 [[LLM|LLM]] program 优化。后续 [[Optimize-Anything|optimize_anything]] 把同一“文本候选 + 评估器 + 可操作附加信息”思想包装成任意文本制品的声明式 API，但博客中的 agent、skill、SVG 等案例不属于本文六任务主实验，不能混作 ICLR 论文证据。

## 设计取舍

- **语言空间学习换取 rollout 效率**：GEPA 无需训练权重，适用于闭源模型且能消费丰富反馈；代价是上限受固定模型能力与 prompt 可控范围约束，不能学到 prompt 无法表达的新能力。
- **Pareto 多样性换取验证开销**：按样例保留赢家减少局部最优，但候选进入池后需要在 `D_pareto` 上广泛评分；论文明确指出多数 rollout 用于 candidate selection，而不是产生训练信号。
- **自动评估换取目标风险**：编译器、exact match 等评估器使搜索可审计；若 `μ_f` 来自 LLM judge 或有漏洞，反思模型也可能系统性优化错误目标。
- **边界条件**：它最适合 rollout 昂贵、反馈文本丰富、候选能用 prompt 表达、train/validation 分布稳定的任务；对只有长期延迟奖励、不可观测环境状态或强 distribution shift 的任务会变脆。

## 实验与结果

- **对 GRPO 的主结果**：Qwen3-8B 六任务上，GEPA aggregate 从 baseline 45.23 提到 54.85，GRPO 为 48.91；GEPA 平均比 GRPO 高约 6 个百分点、5/6 任务获胜，最大差距 19 个百分点，并以 4–35 倍更少 rollout 达到各自最优 test performance（表 1、§4）。
- **rollout 口径**：GRPO 每任务固定 24,000 次；GEPA 各任务总预算为 1,839–7,051 次，其中多数用于验证选择。若只算产生反思学习信号的 train rollout，达到最优结果需要 79–737 次；因此“35 倍”同时受 candidate-selection 记账方式影响（表 1、§4）。
- **对 prompt optimizer 的结果**：GPT-4.1 Mini 六任务 aggregate，baseline 53.03、MIPROv2 58.67、TextGrad 59.14、GEPA 65.22、GEPA+Merge 66.36；GEPA+Merge 相对 baseline 提升 13.33 个百分点，是 MIPROv2 5.64 个百分点提升的两倍以上（表 2）。
- **跨模型迁移**：在 Qwen3-8B 上优化、未经修改直接用于 GPT-4.1 Mini 的 prompt，aggregate 为 62.03，相对 baseline 提升 9.00 个百分点，超过直接在 GPT-4.1 Mini 上优化的 MIPROv2、TextGrad 和 Trace（表 2）。
- **选择策略消融**：Qwen3-8B 四任务、相同 evolution harness 下，Pareto 选择提升 12.44 个百分点；greedy best-candidate 与 beam search 分别只提升 6.05 和 5.11（表 3、图 4）。
- **推理时代码搜索**：GPT-4o 上，NPUEval 的平均 NPU vector utilization 从 sequential refinement 的 4.25% 提到 30.52%；KernelBench 中快于 [[PyTorch|PyTorch]] baseline 的任务比例从接近 0 提到超过 20%，但这里只是扩展实验，不能支持通用代码优化结论（§5、附录 E）。
- **对抗搜索**：GPT-5 Mini 的 AIME-2025 pass@1 被通用干扰指令从 76% 降到 10%，说明同一机制也能搜索稳定破坏系统的 prompt（§5、附录 F）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 反思式 prompt 演化能用更少 rollout 超过 GRPO | 表 1、§4：六任务平均高约 6 个百分点，最多高 19 个百分点，达到最优结果少 4–35 倍 rollout | Qwen3-8B；六个可自动评分任务；GRPO 24,000 rollout，主要用 [[LoRA\|LoRA]] | 中 |
| GEPA 超过领先 prompt optimizers | 表 2：GPT-4.1 Mini aggregate 65.22，MIPROv2 58.67、TextGrad 59.14、Trace 56.30 | 单次正式配置；六任务；预算与 MIPROv2 对齐误差最多 10.15% | 强 |
| 按样例 Pareto 选择优于 greedy/beam | 表 3、图 4：aggregate gain 12.44 vs. 6.05/5.11 | Qwen3-8B 四任务；同一 harness；未给多 seed 方差 | 中 |
| 优化的 prompt 可跨模型迁移 | 表 2：Qwen 优化 prompt 在 GPT-4.1 Mini 上带来 +9.00 aggregate gain | 只验证 Qwen3-8B → GPT-4.1 Mini 一个方向 | 中 |
| GEPA 可作为硬件代码的推理时搜索器 | §5、附录 E：NPUEval 4.25% → 30.52% vector utilization；KernelBench 过 baseline 比例接近 0 → 超过 20% | GPT-4o；两个 kernel benchmark；`D_val = D_train`，不测未见任务泛化 | 弱 |

## 批判性分析

### 论证链条

“轨迹含丰富语言信号 → 反思可做 credit assignment → 少量 rollout 产生大幅改进”的链条在主实验中基本闭合：不仅最终分数超过 GRPO，Pareto 选择消融也解释了搜索为什么不易停在局部最优。最薄弱的一跳是把性能差异归因于“语言比梯度是更丰富的学习媒介”；GEPA 同时改变了参数空间、模型先验、搜索器和可见反馈，实验不能隔离究竟是自然语言反馈、预训练知识还是 prompt 空间更容易搜索。

标题中的 “can outperform reinforcement learning” 是存在性判断，正文证据足以支持；若读成普遍优越则会越界。GRPO 需要训练 Qwen3-8B，而 GEPA 的反思 LM 自身也消耗调用，rollout 数并不是完整的 FLOP、美元成本或 wall-clock 对比。附录给出反思调用数和费用，但没有把两类优化器统一成端到端资源曲线。

### 假设压力测试

GEPA 强依赖反馈函数。编译错误或逐项 rubric 具有直接因果含义时，反思接近可读的近似梯度；只有 noisy LLM judge 或最终成败时，模型可能根据偶然相关性改写 prompt。按样例 Pareto 前沿还会优先保留极端局部赢家，若单样例分数方差大，这种多样性机制可能退化成噪声放大器。

跨模型结果只覆盖从 Qwen3-8B 到 GPT-4.1 Mini，尚不能说明跨模型代际、开源/闭源家族和弱到强/强到弱双向迁移都稳定。Merge 在 GPT-4.1 Mini 有效、在 Qwen3-8B 反而退化，已经展示搜索超参数并非 model-proof。

### 实验可信度

六任务跨数学、检索、指令遵循和隐私委托，且采用独立 test set，证据比单 benchmark 强；MIPROv2、TextGrad、Trace 和 GRPO 都是相关强基线。论文也披露预算对齐与 GRPO 配置，完整 prompt 和搜索树放在附录，审计性较好。

不足是主表没有随机种子均值、标准差或显著性检验；进化搜索与 LLM 采样都具有随机性，单次 best candidate 容易高估期望收益。作者手调 GRPO 的部分超参数，同时 GEPA 的反思模型与目标模型组合、proposal token 成本和验证集反复使用也会影响公平性。Qwen 表中 GEPA 在 AIME-2025 低于 GRPO，GEPA+Merge 在 IFBench 明显低于 baseline，说明收益并非逐任务稳定。

### 系统性缺陷

论文未讨论生产环境中的 prompt 版本治理、回滚、评估器漂移与安全审计。优化后指令可能很长且包含从训练轨迹归纳出的特殊规则；虽然通常比 MIPROv2 few-shot prompt 短，仍需检查敏感数据是否被写入 prompt、规则冲突是否导致尾部失败，以及下游模型升级后是否需要重跑搜索。

## 局限与后续工作

- **局限 1**：主结果只覆盖两个目标模型、六个自动评分任务，不能外推到开放式科研判断、人类偏好或长期交互环境。
- **局限 2**：rollout 效率不是统一计算效率；未来应报告总模型 token、反思 LM 调用、训练 FLOP、美元成本和 wall-clock 的 Pareto 曲线。
- **局限 3**：缺少多随机种子统计；应在固定总 token 预算下至少运行 5 个 seed，报告每任务均值、方差和最差分位数。
- **局限 4**：验证集承担按样例 Pareto 选择，存在自适应过拟合风险；应加入搜索过程从不访问的二级 holdout，并随迭代数测量 generalization gap。
- **后续工作 1**：构造只给标量、给 noisy 文本、给真实编译/测试诊断三档反馈，在相同候选选择器下量化反馈信息量与样本效率的因果关系。
- **后续工作 2**：让 merge 调用时机由 lineage 差异和候选互补度触发，在 Qwen3-8B 与 GPT-4.1 Mini 上检验是否消除固定策略导致的退化。
- **后续工作 3**：在模型升级、数据分布漂移和评估器版本变化后重放相同 prompt，测量性能衰减、回滚成本与重新优化预算。

## 相关

- **相关实体**：[[Optimize-Anything]]
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[BES-arXiv26]]
- **相关主题**：[[Auto-Research]]
- **同会议**：[[ICLR-2026]]
