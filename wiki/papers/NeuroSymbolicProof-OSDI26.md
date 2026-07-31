---
type: paper
name: NeuroSymbolicProof
full_title: "Neuro-Symbolic Proof Generation for Scaling Systems Software Verification"
authors: [Baoding He, Zenan Li, Wei Sun, Yuan Yao, Taolue Chen, Xiaoxing Ma, Zhendong Su]
venue: OSDI
year: 2026
tags: [formal-verification, theorem-proving, llm, sel4, neuro-symbolic]
source_pdf: "[[osdi26-he-baoding.pdf]]"
source_md: "[[osdi26-he-baoding]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向系统软件验证的神经—符号证明生成（OSDI 2026）

> **原题**：Neuro-Symbolic Proof Generation for Scaling Systems Software Verification

> **一句话总结**：论文观察到系统验证 proof script 的真正推理信号藏在 Isabelle 中间 proof state，而非表面文本，于是将人类证明拆为 state→step 数据，结合 fine-tuned LLM 的 best-first search、规则修复、QuickCheck/Nitpick pruning 和 Sledgehammer closure；FVEL seL4 上成功率达 77.6%，比最强 baseline 高 37.3 个百分点。

## 问题与动机

[[seL4]] 约 10K 行 C，却需要超过 100K 行 Isabelle proof、约 20 person-years。现成 LLM 即使认识 theorem context，也会误用 `wp` 等 domain tactic 或 hallucinate lemma；FVEL 对 1,077 个 test theorem 的 fine-tuned Mistral/Llama baseline 成功率仍低于 10%。

系统 proof 多为 procedural tactic script：每一步之后 ITP 产生的 hypothesis/goal 才体现语义。直接训练 whole-proof generation 不仅数据只有约 20K theorem，也丢失中间监督。论文因此将 proof generation 变为 theorem-prover-in-the-loop 的 step search，而非一次性文本补全。

## 关键观察 / 隐含假设

- **观察 1：一个 n-step 人类 proof 可提供 n 个 `(proof state, next step)` 样本。** 细粒度 REPL 既扩大训练数据，也允许 inference 每步由 Isabelle 检查（§3、4.1）。
  - **依赖假设**：历史 human trajectory 足以覆盖新 theorem 的局部 tactic distribution。
  - **可能失效场景**：新 module 缺少相似 premise/tactic，或正确 proof 需长程策略而局部最可能 step 会走入死路。
- **观察 2：[[LLM|LLM]] 候选中存在大量可由 symbolic tool 低成本排除的无效分支。** 示例 8,445 steps 中 44.2% 生成 duplicate state，剩余又有 52.3% 可找到 counterexample（§3.2）。
  - **依赖假设**：QuickCheck/Nitpick timeout 或找不到 counterexample 不会被误当成可证明，ranking 仍能筛出好 state。
- **观察 3：小模型经 domain fine-tuning 后足以提供候选，ITP 负责 correctness。** Qwen3-1.7B 也达 70.4%，base model+tree search 几乎为零（表 1、4）。
  - **依赖假设**：evaluation theorem 与训练 library 的 API/lemma distribution 相近；unseen session 只部分检验跨域。
- **假设 1：proof success/ground-truth line coverage 可近似人类 effort savings。**
  - **证据强度**：弱；79.8% 来自“给定 proof prefix 后系统能补全”的模拟，不是开发者 longitudinal study。

## 核心方法

作者实现 Isabelle REPL，暴露当前 goal/hypothesis、执行 tactic、counterexample tool 和 local automation。每个 node 是 proof state；fine-tuned Mistral-7B 或 Qwen3-1.7B 提议多个 next step，规则 revision 修复 syntax、lemma/tactic variant 或无进展建议，再让 Isabelle kernel 执行，只有合法 transition 进入树（图 2）。

filter 先合并 duplicate state，并运行 QuickCheck/Nitpick 丢弃有 counterexample 的 obligation；剩余 state 按累计 LLM log-probability 做 best-first expansion。预算耗尽或搜索停滞时，在 residual goal 上调用 Sledgehammer 检索 local lemma 并尝试 closure。最终 proof 每一步都由 [[Isabelle-HOL]] kernel 检验，因此模型不能绕过 soundness base。

训练集从现有 seL4 proof replay 中提取 state-step pair；评测使用 FVEL validation/test/test-hard，另以 AFP 的 X86 Semantics、IEEE Floating Point、SATSolverVerification 和 Code2Inv 检查迁移。

## 设计取舍

- **kernel-checked correctness 换巨大 search cost**：成功 proof 平均 139.1 分钟，失败 validation 累积 7.77M tactic attempts。
- **局部 best-first 换长程规划缺失**：短/中 proof 效果强，超过 10 行成功率约 20%，96% failure 已走到深度 11 后才耗尽预算。
- **domain fine-tuning 换维护成本**：library/tactic 演化后需重新 replay 和训练。
- **symbolic pruning 换 tool bias**：QuickCheck/Nitpick 对可执行 fragment 更有效，Sledgehammer 对最后 residual goal 未必有用。
- **边界条件**：有成熟 proof corpus、可交互 ITP 和 domain tactic 的项目适合；新规范、长 horizon 或 missing assumption 的 theorem 会变脆。

## 实验与结果

- FVEL still-valid validation/test/test-hard 上，Mistral-7B 完成 2,167 theorem（788/811/568），总成功率 77.6%，比 Sledgehammer 高 37.3 个百分点；Qwen3-1.7B 为 70.4%（表 1）。
- proof 超过 10 行的 393 个 theorem 仍约 20% 成功；完全训练未见的 SysInitGroup 成功率 67.6%（图 3–4）。
- 自动完成 theorem 对应 ground-truth proof 的 6,235 行，即 line coverage 36.2%；prefix-completion 模拟得到平均 effort reduction 79.8%（表 2、图 5）。
- 成功 proof 平均 139.1 分钟，但 58.4% 在 10 分钟内、73.4% 在 30 分钟内、80.8% 在 2 小时内（§4.3.2）。
- additional Isabelle/Code2Inv benchmark 上均超过 baseline；X86 Semantics 高 32.5 个百分点，其余 hammer-friendly 项平均相对提升 36.9%（图 7）。
- failure tactic 中 69.8% kernel error；lemma hallucination 占 61.1%、goal-shape mismatch 占 17.9%。96% search failure 到达深度至少 11 后耗尽 128-attempt budget（表 5–6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| neuro-symbolic search 大幅提高 seL4 proof coverage | 表 1：77.6%，高 Sledgehammer 37.3pp | FVEL still-valid splits、两种 fine-tuned model | 强 |
| 方法不只解决单行 trivial proof | 图 3：超过 10 行仍约 20% | proof line count 只是难度 proxy | 中 |
| 对未见 session 有一定泛化 | 图 4：SysInitGroup 67.6% | 同一 seL4 ecosystem、Isabelle tactic/library 高度共享 | 中 |
| 可显著减少人工 proof text | 表 2/图 5：36.2% line coverage、模拟 79.8% reduction | prefix-completion simulation，无真实 user study | 弱 |

## 批判性分析

### 论证链条

把隐含 proof state 变成显式 supervision，再让 symbolic checker 过滤 LLM，这是很自然且证据充分的设计。ablation 表明 fine-tuning、tree search、revision 与 hammer 各有贡献。标题中的“scaling verification”主要指自动补 proof；formal specification、invariant discovery 与 code-model correspondence 仍由人承担。

### 假设压力测试

新 subsystem 若没有历史 lemma/tactic，fine-tuned likelihood 会系统性偏离；test-hard 的 SysInit 仍共享 seL4 foundation，不能代表跨 prover/项目迁移。长 proof 需要先选 invariant 或中间 lemma，best-first local step 很可能在深处 collapse。benchmark state slicing 还可能丢 assumption；validation failure 中 9.5% 有真实 counterexample，说明一部分任务本身不可证。

### 实验可信度

FVEL 规模大、同时与 neural/Auto/Sledgehammer 比较，并报告 proof-length/session/generalization/ablation/failure，覆盖全面。公开 proof 可能被 pretrained model 见过；作者以 generated-vs-ground-truth similarity 低来反驳 memorization，但低 similarity 不能完全排除 library-level leakage。大量算力/时间成本未归一为每个成功 proof 的 GPU-hour/美元。

### 系统性缺陷

平均 139 分钟会限制 IDE feedback；7.77M failed tactics 给 Isabelle server、logging 和 scheduling 带来运维成本。61.1% hallucinated premise 说明没有强 grounding；Sledgehammer 在 241 个 validation residual failure 上一个也没关闭。生成 proof 虽 kernel-correct，可能可读性差、依赖脆弱 lemma 或难以维护。

## 局限与后续工作

- **局限 1**：只自动化 proof construction，不生成 specification/invariant，也不验证原始 C 与 model 的抽取过程。
- **局限 2**：长 proof 成功率和 search latency 仍不足，跨 Isabelle 之外 ITP 未验证。
- **后续工作 1**：加入 premise-grounded constrained decoding，以 hallucination rate、valid-step ratio 和 time-to-proof 测量改善。
- **后续工作 2**：训练 value/planning model预测 residual proof distance，在相同 128-attempt budget 下比较超过 10 行 theorem 成功率。
- **后续工作 3**：开展 expert study，比较从零手写、AI prefix completion 与 whole-proof review 的 wall time、修改次数和长期 maintenance breakage。

## 相关

- **相关概念**：[[Formal-Verification]]、[[Interactive-Theorem-Proving]]、[[Neuro-Symbolic-AI]]、[[Proof-Search]]
- **同类系统**：[[seL4]]、[[Isabelle-HOL]]、[[Sledgehammer]]、[[FVEL]]、[[Selene]]
- **同会议**：[[OSDI-2026]]
