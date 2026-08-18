---
type: paper
name: PASTA
full_title: "Tell Your Model Where to Attend: Post-hoc Attention Steering for LLMs"
authors: [Qingru Zhang, Chandan Singh, Liyuan Liu, Xiaodong Liu, Bin Yu, Jianfeng Gao, Tuo Zhao]
venue: ICLR
year: 2024
tags: [attention-steering, llm-inference, prompting, model-profiling, inference-time-control, area/ai-infra]
source_pdf: "[[iclr24-zhang-pasta.pdf]]"
source_md: "[[iclr24-zhang-pasta]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PASTA：告诉模型该关注哪里——LLM 的事后注意力引导（ICLR 2024）

> **原题**：Tell Your Model Where to Attend: Post-hoc Attention Steering for LLMs

> **一句话总结**：PASTA 的核心观察是普通 prompt 标记很难让基础 LLM 稳定关注用户指定 span，但少数 [[Attention|attention]] head 可以被 post-hoc 重加权来放大这些 span；它通过一次性 multi-task head profiling 选择 steering heads，在不改参数的情况下让 LLaMA-7B 四类任务平均分从 few-shot 的 73.45 提升到 95.46，不过依赖用户或数据管道准确给出重点 span，并要求推理栈暴露可修改的 per-head attention score。

## 问题与动机

这篇论文要解决的不是一般意义上的 instruction tuning，而是一个更窄的交互接口问题：用户已经知道 prompt 中哪些内容最重要，但模型不能像人类读加粗、斜体文本那样稳定利用这些强调信号。作者把这个问题放在三类场景里：复杂输出格式或改写指令、长 context 中的关键信息、context 与模型参数记忆冲突时的新事实。

现有方法要么只依赖纯文本 prompt，要么用 few-shot demonstration 间接说明任务。前者的问题是 markdown 星号、引号等 marker 本身是弱信号，模型可能把它当普通 token；后者虽然常常有效，但会增加 prompt 长度，并且 few-shot 示例选择带来高方差。PASTA 的目标是在推理时直接干预 attention，让用户指定 span 在模型内部真的获得更高权重。

这个问题对系统层也有意义：如果 attention score 或 [[KV-Cache]] 里的内容可以被当成可操作对象，那么「模型如何读 context」就不只是 prompt engineering，而变成 inference pipeline 的一个控制面。不过 PASTA 本文主要是算法原型，系统成本、optimized kernel 兼容性和 serving SLO 还没有被充分测量。

## 关键观察 / 隐含假设

- **观察 1：显式文本 marker 不能可靠传达 emphasis。** 论文在 LLaMA-7B 和 GPT-J 上比较 zero-shot、星号/引号标记、few-shot 与 PASTA；LLaMA-7B 上 marked prompting 的平均分低于 zero-shot，GPT-J 上 marked prompting 也经常退化，说明「把重点 span 包起来」不是足够强的控制机制。
  - **依赖假设**：被测模型没有在类似强调标记上学到稳定的操作语义；用户标记本身不会被模型自然解释成高优先级控制指令。
  - **可能失效场景**：更强的 instruction-tuned / markdown-heavy / UI-specialized 模型可能已经能利用显式标记；这时 PASTA 的相对收益会下降。
- **观察 2：只有少数 attention head 适合被 steering。** Figure 2 与 Appendix B.3 显示，steer all heads 往往比 zero-shot 更差，steer 单层或单 head 的结果跨 layer/head 波动很大；multi-task profiling 选出的 heads 明显更稳。
  - **依赖假设**：head 的功能分化足够稳定，能通过少量任务 profile 出「可被用于强调用户 span」的 head set，并泛化到未见任务。
  - **可能失效场景**：模型架构、训练配方、GQA/MQA、long-context attention 机制或 instruction tuning 改变后，head profile 可能需要重新估计；论文只在 GPT-J、LLaMA-7B、附录的 LLaMA-13B / Vicuna-7B 上给证据。
- **观察 3：适量 steering 存在质量-服从度 tradeoff。** Figure 3 显示 steered head 数增加时，JSON format accuracy 和 pronoun-changing accuracy 上升，但 JSON prediction accuracy 与 fluency 会下降；alpha 设为 0 也会让性能退化。
  - **依赖假设**：用户关心的不只是形式服从，还包括保留 context 中的事实内容与生成质量；因此不能无脑增强所有 highlighted tokens。
  - **可能失效场景**：如果任务只关心格式或硬约束，过强 steering 可能看起来有利；如果任务需要全局语义整合，过强 steering 会把非 highlighted context 压得太低。
- **假设 1：重点 span 可以被外部可靠指定。**
  - **证据强度**：中。四个评测任务里 highlighted span 都很清楚：JSON / Pronouns 强调最后 instruction，CounterFact 强调 new fact，BiasBios 强调首句职业信息。但这更像 curated benchmark，而不是开放式真实对话。
- **假设 2：推理系统可以承担 per-head attention score 访问与修改。**
  - **证据强度**：弱到中。论文用 PyTorch / HuggingFace 在 V100 和 A6000 上实现，但没有报告 latency、memory、throughput，也没有讨论 [[Flash-Attention|FlashAttention]]、paged KV 管理或 prefix cache 命中路径里的实现代价。

## 核心方法

PASTA 输入一个 prompt `x`、用户指定的 highlighted token 集合 `G`，以及一次性选出的 steering head set `H`。对每个被选中的 layer/head，它不修改模型参数，而是在 attention probability 上做投影：highlighted token 保持原 attention，非 highlighted token 乘以 `alpha` 后重新归一化。直观上，这等价于把 highlighted token 的相对 attention 放大约 `1 / alpha`，但通过 downweight 其他 token 来做，数值上更稳定。

作者选择乘法缩放而不是给 highlighted token 加常数，是因为乘法保留 highlighted tokens 之间原本的 attention 差异。这个选择很关键：PASTA 不是把用户 span 内所有 token 均匀抬高，而是在 span 内继续尊重模型已有的局部偏好，只改变「span 内」与「span 外」之间的相对尺度。

第二个组件是 multi-task model profiling。PASTA 从多个涉及用户强调的任务中各取小训练集，逐个 head 单独应用 steering 并评估表现；每个任务得到一个 head ranking，然后默认取多个任务 top-k heads 的交集作为模型级 profile。这个 profile 只需对一个 LLM 做一次，之后可用于未见任务。论文也比较了 task-specific、union、intersection 三种策略：task-specific 有时更强，但需要每个新任务重新选择；intersection 是默认的任务泛化折中。

实验里 `alpha` 固定为 0.01。LLaMA-7B 的 `k` 在 300、400、500 中交叉验证，对应最终约 25、53、86 个 steered heads；GPT-J 选择 250、275、300、350，对应约 52、72、111、153 个 heads。Appendix A.2 给出的最终任务配置里，LLaMA-7B 在 JSON Formatting 上 steer 53 个 heads，在 Pronouns Changing、BiasBios、CounterFact 上 steer 86 个 heads。

## 设计取舍

- **不改权重 vs 改推理内核**：PASTA 避免 finetuning、LoRA 或 [[Model-Editing|model editing]] 的训练成本，但把复杂度转移到 inference-time attention intervention；如果 serving stack 不 materialize attention matrix，工程成本会显著上升。
- **用户可控性 vs span 标注负担**：方法给用户一个直接的「告诉模型看哪里」接口，但默认 highlighted span 已经存在且正确。真实 RAG、agent memory、多轮对话里，重要 span 可能需要自动识别。
- **模型级 profile vs 任务最优 profile**：intersection heads 支持未见任务，task-specific heads 常常更强；这是泛化与任务性能的典型交换。
- **服从强调 vs 保留上下文**：steer 太少效果弱，steer 太多会损伤 prediction accuracy 或 fluency。PASTA 的控制旋钮不是单调免费的。
- **简单公式 vs 安全边界**：任何被用户标记的 span 都会被增强；论文没有讨论恶意 instruction、错误事实、prompt injection 或不同用户之间的权限隔离。

## 实验与结果

**准确率指标与基线**：任务 score、JSON format/prediction accuracy；`vs.` zero-shot、few-shot 与不同 PASTA profile，限定为 LLaMA-7B/GPT-J-6B 的四项任务和固定 highlighted span（§5）。

**结果**：LLaMA-7B multi-task accuracy score 为 **95.46%**，zero-shot/few-shot 分别为 **67.29%/73.45%**（§5.1，Table 1）。

- **设置**：模型是 GPT-J-6B 和 LLaMA-7B；任务覆盖 JSON Formatting、Pronouns Changing、BiasBios、CounterFact；每个任务 1000 train、1000 valid、5000 test；生成使用 greedy search。
- **LLaMA-7B 主结果**：multi-task PASTA 平均分 95.46，高于 zero-shot 67.29 和 few-shot 73.45；task-agnostic PASTA 平均分 85.89，说明不使用目标任务 profile 也有明显收益。
- **Instruction following**：LLaMA-7B JSON Formatting 上 multi-task PASTA 达到 96.64 format accuracy / 85.09 prediction accuracy，高于 few-shot 的 84.85 / 73.58；Pronouns Changing 达到 96.42 accuracy / 95.84 all-changed accuracy，高于 zero-shot 的 71.84 / 66.28。
- **Context use / knowledge conflict**：LLaMA-7B BiasBios accuracy 从 zero-shot 87.36 提升到 95.28；CounterFact 从 zero-shot 58.50 / 52.03 提升到 99.60 / 99.57。
- **GPT-J 结果更不均匀**：multi-task PASTA 平均分 85.22，但 JSON Formatting 出现「格式很高、内容较低」的现象；默认 intersection heads 给出 91.50 format accuracy / 18.63 prediction accuracy，而 task-specific heads 在 Table 5 中达到 85.71 / 79.39。这支持了 head selection 是关键瓶颈，而不是公式本身总能安全泛化。
- **Prompt sensitivity**：在 JSON / Pronouns 的 original、shortened、rephrased instruction 上，PASTA 对所有 prompt variant 都提升 zero-shot；平均分例如 original 从 47.9 到 83.5，shortened 从 39.3 到 76.0，rephrased 从 67.1 到 86.9。
- **Head profiling ablation**：steer all heads 会退化，steer whole layer 或 single head 方差很大；profiled heads 是主要贡献来源。head 数量增加提升任务服从度，但会牺牲 JSON prediction accuracy 或 fluency。
- **更多模型**：附录报告 LLaMA-13B 上 PASTA 平均分 96.71，高于 zero-shot 56.05 和 few-shot 64.41；Vicuna-7B 实验暗示 LLaMA-7B profile 可迁移到 instruction-tuned 变体，但不同 head selection 策略仍有明显差异。
- **生成质量**：附录用 fluency 和 consistency 检查生成质量。LLaMA-7B 上 PASTA 与 zero-shot fluency 接近，例如 CounterFact fluency 4.89 vs 4.96，同时 consistency 从 11.64 提升到 19.29。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| PASTA reweights attention heads without changing weights | non-highlighted attention multiplied by α=0.01 (§3) | GPT-J-6B/LLaMA-7B, attention scores required | high |
| LLaMA multi-task score exceeds prompting on four tasks | 95.46 vs zero-shot 67.29 and few-shot 73.45 (Table 1) | four tasks, LLaMA-7B, greedy decoding | high |
| JSON format and prediction need separate interpretation | 96.64/85.09 vs 84.85/73.58 few-shot (Table 1) | LLaMA-7B JSON task | high |
| Context/new-fact results rely on highlighted span | BiasBios 95.28 vs 87.36; CounterFact ES/PS 99.60/99.57 vs 58.50/52.03 (Table 1) | fixed spans, no automatic span selection | high |
| Intersection profile trades format for content | GPT-J JSON 91.50/18.63 vs task-specific 85.71/79.39 (Table 5) | JSON F.Acc/P.Acc only | high |

## 批判性分析

### 论证链条

PASTA 的核心链条基本闭合：marked prompting 弱，说明显式 marker 不是可靠控制接口；all-head steering 退化，说明需要选择性干预；profiled heads 在四类任务上显著提升，说明某些 attention heads 的确可以作为 inference-time control surface。最强的证据是 profiling ablation，因为它排除了「只要把 highlighted token 放大就行」这种过度简化解释。

但论文标题里的「让模型读懂强调」比实验证明的内容更宽。实验真正证明的是：当外部已经给出正确 span 时，selected-head attention reweighting 可以改善若干构造任务。它没有证明模型能自己理解自然 UI 中的强调，也没有证明用户随手标注的 span 在开放任务里可靠。

### 假设压力测试

最脆的假设是 span availability。JSON 和 Pronouns 的 highlighted span 是最后一句 instruction，BiasBios 是首句，CounterFact 是 new fact；这些都是规则可得的 benchmark 结构。真实 RAG 里 relevant evidence 可能分散在多个段落，agent 对话里重要事实会随时间变化，用户也可能高亮错误内容。PASTA 本身不判断 span 是否可信。

第二个压力点是模型与架构迁移。GPT-J 的 JSON prediction anomaly 已经说明同一个 selection strategy 可能把「形式服从」和「内容正确」解耦。对使用 GQA/MQA、sliding-window attention、long-context RoPE scaling 或 MoE routing 的模型，head profile 的稳定性需要重新测量。

第三个压力点是 serving compatibility。PASTA 是 query-dependent：每个请求的 highlighted span 可能不同，steered attention 也随请求改变。这和 [[Prefix-Caching]] / shared context cache 的「一次 prefill，多次复用」目标天然有张力，后续 [[LLMSteer-NeurIPSW24|LLMSteer]] 正是沿着这个缺口把 steering 变成 query-independent。

### 实验可信度

四个任务覆盖了 instruction following、long context distraction 和 knowledge conflict，面比单一 benchmark 更好；5000 test size 也比很多 proof-of-concept 更扎实。few-shot variance、prompt rephrasing、head-count / alpha ablation 都是有价值的压力测试。

不足是 baseline 主要是 prompting 家族，没有和更强的 instruction-tuned chat models、tool-use prompts、constrained decoding、retrieval reranking 或现代 attention steering 变体充分比较。论文的 LLaMA-7B / GPT-J 设定适合验证机制，但不足以直接推出「生产 LLM interface 应该这么做」。

### 系统性缺陷

论文未报告 PASTA 的在线 latency、GPU memory、kernel fusion 影响或 batching 影响。对标准 PyTorch attention，修改 attention probability 很直接；对 FlashAttention 类 fused kernel，attention probabilities 通常不会完整 materialize，token/head-specific reweighting 可能需要额外 mask、kernel 分支或 fallback path。

PASTA 也没有讨论可观测性和调试。若模型输出变好或变坏，系统需要知道是 span 标错、head profile 不适配、alpha 太强、还是下游 decoding 问题。论文的 profile 是离线选择结果，但没有提供生产中监控 profile drift 的机制。

安全方面，PASTA 把用户 emphasis 直接变成模型内部权重增强。若 emphasis 来自不可信网页、检索文档或攻击者输入，这可能放大 prompt injection；若 emphasis 来自可信用户，它又可能帮助覆盖模型旧知识。这两种情况需要权限模型区分，论文未覆盖。

## 局限与后续工作

- **局限 1：span selection 被简化。** 当前评测里 highlighted span 基本由任务模板给定；需要测试自动 span detection、用户噪声标注和多 span 冲突时的鲁棒性。
- **局限 2：系统开销缺失。** Future work 应该在 HuggingFace eager attention、FlashAttention、paged attention 和 prefix-caching serving 路径上分别测 latency、throughput、batching 和 memory overhead。
- **局限 3：profile 泛化证据有限。** 需要跨 LLaMA 2/3、Mistral、GQA/MQA、MoE、long-context model 验证 head profile 是否稳定，以及 profile drift 是否可监控。
- **Future work 1：把 steering 与 cache 生命周期解耦。** 验证能否像 [[LLMSteer-NeurIPSW24|LLMSteer]] 那样把重要 token metadata 离线化，使 attention steering 与 [[KV-Cache]] reuse 兼容。
- **Future work 2：建立质量-服从度 Pareto 曲线。** 对 head 数、alpha、decoding strategy 做系统 sweep，用 format accuracy、factual accuracy、fluency、latency 同时建模，而不是单独调一个任务分数。
- **Future work 3：安全边界。** 区分用户可信 emphasis、检索文档 emphasis 和攻击者 emphasis，测 PASTA 是否会提高 prompt injection 成功率。
- **Future work 4：机制解释。** 对被选中的 heads 做 token-level attribution，判断它们是否真的编码 instruction/new fact/职业首句，还是只是 benchmark-specific shortcut。

## 相关

- **相关概念**：[[Attention]]、[[KV-Cache]]、[[Prefix-Caching]]、[[Prompting]]、[[Model-Editing]]、[[LoRA]]
- **同类系统 / 后继工作**：AutoPASTA、[[LLMSteer-NeurIPSW24|LLMSteer]]、[[Cartridges-ICLR26|Cartridges]]
- **同会议**：[[ICLR-2024]]
- **源码与原文**：[[iclr24-zhang-pasta]]、[[iclr24-zhang-pasta.pdf]]
