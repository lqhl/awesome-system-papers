---
type: paper
name: NeuroSymbolicProofSearch
full_title: Neuro-Symbolic Proof Generation for Scaling Systems Software Verification
authors: [Baoding He, Zenan Li, Wei Sun, Yuan Yao, Taolue Chen, Xiaoxing Ma, Zhendong Su]
venue: OSDI
year: 2026
tags: [formal-verification, theorem-proving, llm, isabelle, sel4]
source_pdf: "[[osdi26-he-baoding.pdf]]"
source_md: "[[osdi26-he-baoding]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向系统软件验证的神经符号证明生成（OSDI 2026）

> **原题**：Neuro-Symbolic Proof Generation for Scaling Systems Software Verification

> **一句话总结**：论文观察到 seL4 的证明失败主要来自领域引理幻觉和目标形状不匹配，因此让经过证明状态微调的 1.7B/7B LLM 逐步生成 Isabelle proof step，再用修复、反例过滤、best-first search 和 Sledgehammer 闭合子目标；在 FVELER 的验证、测试和 test-hard 集合上，Mistral-7B 达到 77.6%，但平均成功证明仍需 139.1 分钟。

## 问题与动机

交互式定理证明器（ITP）能给系统软件提供内核检查的正确性保证，但证明脚本的构造成本限制了大规模采用。论文以 seL4 为主要对象：其验证工程约有 20 person-years 的投入和超过 100K 行证明脚本，而最简单的抽象规格约 3K 行。本文只处理证明生成，不处理规格编写。

现有 LLM 方法通常生成完整证明，或只在小型数学题上进行 proof-step prediction。seL4 的 Isabelle/HOL 证明大量依赖 `wp` 等领域专用 tactic 和局部引理；表面上的 procedural proof script 还隐藏了中间 proof state。因此，训练数据少且信号不完整，FVEL 在 seL4 测试集上成功率低于 10%。

## 关键观察 / 隐含假设

- **观察 1：失败首先是知识落地问题。** 在验证集失败运行产生的 7.77M 次 tactic 尝试中，undefined fact、undefined method 和 undefined constant 合计占错误的 61.1%；tactic-inapplicable 占 17.9%（表 5）。
  - **依赖假设**：错误输出仍包含可用的 tactic 或引理线索，能够被规则重组或局部替换。
  - **可能失效场景**：若正确引理不在当前上下文，编辑距离和 MePo 只能找到形式相近而非语义正确的候选。
- **观察 2：证明状态空间会快速膨胀。** signed-overflow 示例有 8,445 个候选步骤，其中 44.2% 导向重复状态，剩余状态中 52.3% 存在反例。重复检测和 QuickCheck/Nitpick 能在搜索早期削减大量分支（§3.2.1）。
  - **依赖假设**：候选状态可被 Isabelle 的测试或有限模型搜索有效区分；反例信号足以作为“不可继续”的近似判断。
- **观察 3：失败多发生在长证明的后段。** 测试和 test-hard 的失败中，96% 至少到达深度 11，只有 3.7% 在深度 10 前停滞（表 6）。
  - **可能失效场景**：固定的候选数和搜索预算无法覆盖更长的证明链；残余目标若超出 Sledgehammer 能力，前面取得的进展不会转化为成功。

## 核心方法

系统从 Isabelle 的初始 proof state 开始，每次让微调后的 LLM 生成一个 proof step。每个候选会立即交给 Isabelle 执行，成功则得到新的状态，失败则进入 revision 阶段。单步生成把长证明拆成可验证的局部决策，也让模型直接看到假设、目标和 tactic 反馈。

Revision 模块处理两类常见错误。对于 tactic 错误，系统抽取候选步骤中的 premises，并与训练语料中最常用的 12 个 tactics 重组。对于 undefined fact，系统从当前候选 premises 中以编辑距离找近邻并替换，候选集合再由 MePo 限制为与目标最相关的 128 个事实。该设计直接回应了观察 1，但它是启发式修复，不是语义检索。

搜索采用 best-first tree search。QuickCheck 和 Nitpick 用于发现潜在反例，SolveDirect 的改造版本用于检测语义等价的重复 proof state；剩余状态按 LLM 逐步 log-probability 的累计分数排序，并用长度归一化 `L^α`（默认 α=1）减弱对短证明的偏好。每轮最多扩展 5 个状态，每个状态生成 128 个候选。

若树搜索在预算内未完成证明，系统选择得分最高的 16 个残余状态调用 Sledgehammer。Sledgehammer 使用 MeSh/MePo 选择最多 2,048 个 premises，并调用 Z3、CVC5、E、SPASS 和 Vampire，单次限时 60 秒。为支持这一流程，作者实现了新的 Isabelle REPL，暴露增量执行、proof-state 克隆/恢复、自动化工具和进程超时控制，并缓存大型 seL4 theory 的重复计算。

## 设计取舍

- **逐步搜索换取可验证性，牺牲搜索成本。** 每个 step 都由 Isabelle 内核检查，避免直接信任整段 LLM 输出；代价是每个候选都要启动或推进 prover，成功证明平均耗时 139.1 分钟。
- **启发式 revision 换取覆盖率，牺牲候选精度。** tactic-premise 重组和编辑距离替换能挽救“方向大致正确”的输出，但会产生大量误导候选。
- **小模型换取候选吞吐，牺牲长程规划。** Qwen3-1.7B 和 Mistral-7B 适合批量生成和打分，却难以稳定构造很长的 proof chain；论文将层次规划、子目标分解和更强模型协同留给后续工作。

## 实验与结果

- 在 FVELER seL4 的 validation、test 和 test-hard 集合（共 3,046 个仍有效 theorem）上，Mistral-7B 成功 2,167 个，成功率 77.6%；Qwen3-1.7B 成功率 70.4%，分别比最强基线 Sledgehammer 高 37.3 和 30.0 个百分点（表 1，§4.3.1）。
- 对 ground-truth proof 超过 10 行的 393 个 theorem，成功率仍约 20%；成功率随证明长度增加而下降（图 3）。
- 在完全未出现在训练集的 SysInitGroup 上，成功率为 67.6%（图 4），但该结果仍来自相同 Isabelle/seL4 生态。
- 全自动证明覆盖的原有 proof lines 为 6,235 行，占评测语料 36.2%；在提供人工 proof prefix 的协作实验中，平均 effort saving 为 79.8%（表 2、图 5）。这是按“能完成的 theorem 所对应脚本行数”和 prefix 比例计算，不等同于端到端工程工时减少。
- 58.4% 的成功证明在 10 分钟内完成，73.4% 在 30 分钟内完成，80.8% 在 2 小时内完成；平均值被少数超长任务拉高（§4.3.2）。
- 关闭 revision 时，原本没有有效步骤的 77 个困难 theorem 中仍有 24.7% 可被 revision 挽救；对有效步骤少于 5% 的 220 个 theorem，挽救率为 11.8%（§4.3.4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| proof-step 搜索比完整证明生成更适合 seL4 | Mistral-7B 77.6%，Sledgehammer 40.3%，FVEL 7.2%（表 1） | Isabelle/HOL、FVELER seL4、120 分钟预算 | 强 |
| 符号工具确实减少了无效搜索 | signed-overflow 中 44.2% 状态重复、52.3% 余下状态有反例（§3.2.1） | 单个示例；反例检测不直接提高总成功率 | 中 |
| 系统可减少人工 proof-script 工作 | 自动覆盖 36.2% proof lines，prefix 协作 effort saving 79.8%（表 2、图 5） | 使用 ground-truth proof prefix；不测真实专家交互 | 中 |
| 跨项目泛化存在，但可能受相近领域影响 | X86 Semantics 上比基线高 32.5%，四个额外 benchmark 平均相对提升 36.9%（图 7） | 3 个 AFP 项目和翻译后的 Code2Inv；仍以 Isabelle 为中心 | 中 |

## 批判性分析

### 论证链条

从错误统计到 revision、从状态爆炸到过滤和排序，设计与观察之间的对应关系清楚。77.6% 的结果说明组合系统有效，但不能把提升归因于某个组件：完整系统同时改变了模型、搜索、revision、过滤和 hammer。消融表支持“组件组合有帮助”，但论文没有给出各模块在相同计算成本下的完整贡献分解。

### 假设压力测试

训练集和 test-hard 按 session 划分，能检验一部分跨文件泛化；但所有核心实验仍依赖 Isabelle 的语言、库和 prover 工具。AFP 结果不能直接证明对 Rocq、Lean 或不同系统验证方法同样有效。将 counterexample 当作过滤依据也有风险：QuickCheck/Nitpick 的有限搜索未发现反例，不代表状态可证明。

更大的风险是预算和时间公平性。所有方法均设 120 分钟，但本文框架还进行大量 Isabelle 状态执行；“平均 139.1 分钟”与 120 分钟的评测限制之间需要结合不同统计口径理解。论文未报告每个 baseline 的 CPU/GPU 资源消耗、候选执行次数和单位成功证明成本，因此工程部署的性价比仍不清楚。

### 实验可信度

seL4 是系统级 ITP 的合适压力测试，test-hard 的独立 session 也比随机切分更有说服力。证明相似度随长度下降只能降低“直接记忆脚本”的可能性，不能排除预训练数据泄漏或共享 tactic 模式。人工协作实验把真实专家输入替换成正确的 ground-truth prefix，因而只能说明“给定可靠方向后的自动补全能力”，不能直接推断专家实际节省 79.8% 工时。

### 系统性缺陷

搜索的核心瓶颈仍是 lemma hallucination（错误的约 61.1%）和长程规划。每个候选都进入 Isabelle，导致并行资源、缓存一致性和进程隔离成为部署成本。论文实现了 theory cache 和超时控制，但未量化缓存命中率、内存开销、并发扩展性或失败恢复。Sledgehammer 作为最后闭合器仍依赖外部 ATP/SMT，虽然最终 proof 会回到 Isabelle 重构和检查，但调用成本和 solver 行为会影响可复现性。

## 局限与后续工作

- **长证明退化**：proof length 增大时成功率下降，且多数失败在较深搜索阶段耗尽预算（图 3、表 6）。可测量的后续方向是比较层次规划、子目标分解与当前单步搜索在相同 prover 调用预算下的成功率。
- **premise grounding 不足**：undefined fact 占主要错误来源。应在相同候选预算下比较编辑距离、MePo、结构化检索和学习式 premise ranking 的错误率与最终覆盖率。
- **成本尚未充分刻画**：平均成功证明耗时 139.1 分钟。需要报告每个 theorem 的 prover CPU 时间、GPU 时间、候选数、缓存命中率和单位成功成本。
- **跨 prover 泛化未知**：额外 benchmark 仍是 Isabelle 项目。应在 Rocq/Coq 或 Lean 的系统验证项目上复现 state-step 数据抽取、revision 和 kernel-checking 流程。

## 相关

- **相关概念**：[[Interactive Theorem Proving]]、[[Automated Theorem Proving]]、[[Proof Search]]、[[Formal Verification]]
- **同类系统**：[[seL4]]、[[Sledgehammer]]、[[FVEL]]、[[Selene]]
- **同会议**：[[OSDI-2026]]
