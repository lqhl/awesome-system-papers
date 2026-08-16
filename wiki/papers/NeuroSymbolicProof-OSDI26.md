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
last_reviewed: 2026-08-14
---

# 用神经—符号方法扩展系统软件证明生成（OSDI 2026）

> **原题**：Neuro-Symbolic Proof Generation for Scaling Systems Software Verification

> **一句话总结**：论文把 seL4 的人工 Isabelle proof replay 成 181,887 个“当前 proof state → 下一步”样本，用微调小模型提出 tactic、用 Isabelle 执行和修复、用 QuickCheck/Nitpick/等价检查剪枝，最后让 Sledgehammer 收尾；按表 1 的作者口径，Mistral-7B 版本成功率为 77.6%，而 Hammer 是 40.3%，但论文给出的各 split 成功数、百分比、“still valid”总数、失败数和 120 分钟上限彼此不能完全复算，结论应以表内口径而不是一个自洽的统一分母来理解。

## 问题与动机

高保证系统的软件实现通常只有几千到几万行，但规格、refinement 和安全性质的证明脚本可能大一个数量级。seL4 约 10K 行 C 和 3K 行 abstract specification，对应超过 100K 行 Isabelle proof，累计投入约 20 person-years。这里的瓶颈不只是写 theorem statement，而是反复观察 proof state、选择项目专用 lemma/tactic、执行一步、理解新的 subgoal，再继续写下一步（§1–§2）。

通用大模型可以认出 Isabelle 语法和 seL4 背景，却很容易把 `wp` 用在错误的 goal shape 上，或引用当前 context 中根本不存在的 lemma。论文图 1 让 Gemini 3 Pro 和 GPT-5.1 在禁用 web search 的条件下证明一个三步 seL4 theorem；两者都用了看似相关的 tactic，仍因未完成 goal 或 undefined fact 失败。已有 FVEL 直接生成整段 proof，在 1,077 个 test theorem 上也只有个位数成功率。

根本困难是，系统验证的证明往往是程序式的。proof script 的表面文本没有直接写出每步之后 Isabelle 内部生成的 hypotheses 和 goals；而这些中间状态才决定下一条 tactic 是否适用。seL4 可供训练的 theorem 只有约 20K 量级，直接学习“statement → whole proof”既浪费每个 proof 内部的多步监督，也让一次 hallucination 破坏整段输出。

论文因此把任务改成 theorem-prover-in-the-loop 的逐步搜索：小模型只负责提出下一步候选，Isabelle 决定候选是否真的改变了 proof state，符号工具删除重复或存在反例的分支，搜索器再继续扩展较有希望的状态。最终输出仍是普通 Isabelle proof script，可信基（trusted base）没有变成 LLM。

## 关键观察 / 隐含假设

- **观察 1：一条 n-step 人工 proof 不只是一个样本，而是 n 个带精确语义状态的监督样本。** replay 人工脚本即可收集每一步之前的 proof state 与下一步 tactic，训练数据从 26,081 个 theorem 扩成 181,887 个 state–step pair，平均每 theorem 约 7 对（§3.1、§4.2）。
  - **依赖假设**：过去 proof trajectory 的局部 tactic/lemma 分布能代表新 theorem；重放时取得的 state 没有丢失必要 session context。
  - **可能失效场景**：新 subsystem 使用未见 abstraction、需要先发明 invariant/中间 lemma，或正确策略要牺牲短期模型概率才能在很多步之后收敛。
- **观察 2：[[LLM|LLM]] 的错误候选仍包含可修复信号。** 错 tactic 往往引用了合适 premise，错 premise 又常与正确名字接近；保留一半结构、替换另一半，比重新采样更容易得到可执行 step（§3.1.2）。
  - **依赖假设**：正确 tactic 位于训练集中最常见的 12 个之一，正确 premise 能在 MePo 选出的 128 个 fact 中用 edit distance 找到。
  - **可能失效场景**：语义相近但名字不同、overload/type context 关键、需要冷门 tactic，或 hallucinated lemma 不是简单拼写错误。
- **观察 3：很多搜索分支可在昂贵扩展前由符号工具排除。** 在 `sofl_test` 示例的 8,445 个候选 step 中，44.2% 导向重复 proof state；剩余状态里又有 52.3% 被 QuickCheck/Nitpick 找到 counterexample（§3.2.1）。
  - **依赖假设**：counterexample 对当前切片后的 obligation 是真的，双向 SolveDirect 足以识别语义重复，工具 timeout 不会被误当作反例。
  - **可能失效场景**：proof-state extraction 丢了 assumption 时，反例反映 benchmark 构造错误；高阶、不可执行或无限结构又可能让 QuickCheck/Nitpick很弱。
- **观察 4：小模型的概率适合做搜索 proposal 和排序，proof correctness 仍交给 kernel。** Qwen3-1.7B 在作者口径下也达到 70.4%，而未微调的 Qwen/Mistral 即使有 tree search 也只有 0.1%/0.0%（表 1、表 4）。
  - **依赖假设**：模型概率与“最终可完成”相关；用平均 log probability 排序不会长期偏爱语法常见但战略错误的路径。
  - **可能失效场景**：长证明需要低概率的结构性跳转，局部高概率路径会在深处耗尽预算。
- **假设 1：ground-truth proof 的行数可以代表人工工作量。** 论文以成功 theorem 对应的人类 proof line 数计算 36.2% coverage，再用精确人类 prefix 模拟 79.8% effort saving。
  - **证据强度**：弱。proof line 的难度差异很大，生成的脚本也可能比人工脚本长；实验没有真实开发者、review 或后续维护。
- **假设 2：同一 seL4 ecosystem 内未见 session 足以表示泛化。** test-hard 隔离了 SysInit、SysInitExamples、LibTest session，但仍共享 Isabelle、seL4 依赖和 lemma vocabulary。
  - **证据强度**：中。四个额外项目提供更强的外部检查，但最不同的 Code2Inv 成功率只有 22.6%。

## 核心方法

作者先实现新的 Isabelle REPL。它建立在 scala-isabelle 和 Py4J 上，由 Python 读取 theory/context、逐步执行 tactic、clone/restore proof state，并调用 Sledgehammer、Nitpick、QuickCheck 等 Isabelle 工具。与 PISA 相比，它支持更新的 Isabelle 和更多 ML-level API。大型 theory 的 dependency compile 很慢，例如 CRefine 中一次 step 可超过一分钟；REPL 因而缓存已经执行的无关 theorem，避免每次分支都从头重放（§4.1）。

训练时，系统在 REPL 中逐条 replay 人工 proof。每执行一步，就把执行前的 hypotheses/goals 与人工 next step 保存为一个训练对。作者分别对 Qwen3-1.7B 和 Mistral-7B 做 full-parameter SFT：3 epochs、global batch 16、bfloat16、learning rate `1e-5`、cosine decay、warmup 0.1，并用 [[DeepSpeed|DeepSpeed]] [[ZeRO|ZeRO-2]]。模型只预测一个 next step，不生成内部 thinking（§3.1.1、§4.2）。

推理是 length-normalized best-first tree search（图 2、算法 1）：

1. 一个 node 保存 Isabelle proof state、到达它的 proof prefix 和累计模型分数。每轮最多选 5 个高分 state，每个 state 以 temperature 1.0、top-p 0.95 生成 128 个候选 step，最大输出 2,048 tokens。
2. Isabelle 实际执行每个候选。完成所有 subgoal 就返回 kernel-accepted proof；报错的 step 进入 revision，成功但未结束的 step 生成新 node。
3. tactic repair 保留候选引用的 premise，与训练 corpus 中最常用的 12 个 tactic 重组。premise repair 只处理 undefined fact：先由 MePo 从 library 取 128 个相关 fact，再按 edit distance 选最接近的 3 个名字替换。
4. QuickCheck 对可执行部分做随机测试，Nitpick 把高阶公式转成有限关系模型寻找反例；发现反例就剪枝。系统还把两个 proof state 形式化成 theorem，用改造后的 SolveDirect 双向检查，删除可互相推出的重复状态。
5. 剩余 node 的 score 是沿路径的 log probability 之和除以 `L^α`，默认 `α=1`，即缓和长 proof 因概率连乘受到的惩罚。搜索始终优先扩展高分未访问 node。

如果 tree search 没完成 theorem，系统取树中最高分的 16 个 residual state 交给 Sledgehammer。每个调用先由 MeSh（MePo + MaSh）选 2,048 个 premise，再让 Z3、CVC5、E、SPASS、Vampire 尝试 60 秒；外部 solver 成功后仍需重建 Isabelle proof。Hammer 只在树搜索末尾调用，避免每个 node 都支付昂贵 ATP/SMT 成本（§3.3、§4.2）。

这一流程只生成 proof。theorem/specification 是否表达了正确系统需求、C 程序到 Isabelle model 的抽取是否正确、还需要哪些 invariant，都在系统边界之外。对于它成功返回的脚本，每一步由 Isabelle kernel 检查，因此 LLM hallucination 最多浪费搜索，不会直接把错误 proof 当作已证明。

## 设计取舍

- **逐步验证换大搜索量**：错误不能穿过 Isabelle kernel，但每轮最多可产生 5×128 个原始候选，revision 又会扩增；validation failure 上累计 7.77M tactic attempts。
- **局部状态换长程计划**：prompt 短、训练样本多，也满足局部可检查；代价是模型不显式决定中间 lemma、case split 结构或多步 invariant strategy。
- **规则修复换搜索偏置**：常见 tactic 和名字相似 premise 能便宜救回候选，却可能产生大量语法合法但语义不合适的组合。
- **counterexample pruning 换适用域限制**：找到反例时剪枝很有价值；找不到不代表可证明，而且可执行 fragment、finite model 和 state slicing 会影响信号质量。
- **末尾 Hammer 换互补能力**：tree search 可先把大 goal 化简，再让 ATP 关闭叶子；但 Hammer 对 241 个 validation residual failure 一个也没完成，说明它不是可靠的兜底。
- **domain SFT 换迁移与更新成本**：模型学会 seL4/Isabelle 特有 tactic 和 lemma；library 重构、session 变化或换 prover 后要重新 replay、训练和校准。
- **kernel soundness 换 proof quality 未保证**：29-step 机器 proof 可以替代人工一行 composite tactic，逻辑上正确，但可读性、稳定性和长期维护成本可能更差。

## 实验与结果

- FVELER 共 29,125 个 seL4 theorem：train/validation/test/test-hard 分别是 26,081/1,115/1,077/852。前三个是随机划分；test-hard 来自训练中没有的 SysInit、SysInitExamples、LibTest session。训练集 replay 得到 181,887 个 state–step pair。机器是 AMD EPYC 9654 96-core 与 6 张未注明型号的“high-end GPU”；论文称所有方法 time limit 均为 120 分钟（§4.2）。
- 表 1 按论文口径报告：Selene 5.6%、FVEL 7.8%、Auto 5.9%、Hammer 40.3%，Qwen3 版本 70.4%，Mistral 版本 77.6%；后者在 Val/Test/TsHd 是 79.8%/89.0%/69.8%，比 Hammer 的总值高 37.3 个百分点。正文又说 Mistral 成功 2,167 个，即 788/811/568。可是这些 count 除以表内 split rate 推出的分母之和约 2,713，2,167/2,713 约为 79.9%，不是 77.6%；若除以三个原始 split 的 3,044 个 theorem 则是 71.2%。论文没有定义“still valid”的各 split 分母，也没有解释这组差异（§4.3.1、表 1）。
- 按 ground-truth proof length 分组，Mistral 对一行 proof 约 96%，长度增加后下降；对 393 个超过 10 行的 theorem 仍约 20%。按 session 分类，test-hard 中完全未用于训练的 SysInitGroup 为 67.6%。这说明系统不只复现单行 tactic，但 proof line 只是难度 proxy，且 unseen session 仍依赖共同的 seL4 library（图 3–4）。
- 成功 theorem 对应的人类 proof 共 6,235 行，占评测 corpus 的 36.2%；Hammer 是 2,581 行、15.0%。AI–human 模拟把 ground-truth proof 的前 `σ` 比例原样交给系统，pass rate 从 0% prefix 的 77.61% 升到 90% prefix 的 86.03%，按论文公式得到 79.8%“effort saving”。同一节又称成功 proof 平均耗时 139.1 分钟，58.4% 在 10 分钟内、73.4% 在 30 分钟内、80.8% 在 2 小时内；139.1 分钟平均值超过前文“所有方法 120 分钟”上限，论文没有说明它是聚合 GPU time、并行 worker 累加还是另一套 timeout（§4.3.2、表 2、图 5）。
- 四个额外 benchmark 上，Mistral 版本分别达到 X86 Semantics 65.1%（86 theorem）、IEEE Floating Point 58.0%（188）、SATSolverVerification 55.1%（564）、Code2Inv 22.6%（399）；对应最强 baseline 为 32.6%、48.4%、48.0%、12.8%。X86 与 seL4 接近，后两项偏 SMT-friendly，Code2Inv 需要把 loop invariant 翻译成 Isabelle，所以这些结果说明有迁移能力，但离“广泛系统验证自动化”仍有距离（§4.3.3、图 7）。
- 200-theorem ablation 中，DeepSeek v3.2 从直接生成 5.5% 提升到 tree search 12.5%、再加 [[RAG|RAG]] 33.0%、再加 Hammer 52.0%，而 trained LLM + tree + Hammer 是 70.0%；API tree search 平均约 4.1 美元/theorem。hammer-free 对照中，base Mistral/Qwen 是 0.0%/0.1%，SFT 后为 59.8%/57.1%。对起初没有任何有效 step 的 77 个难题，revision 救回 24.7%；对 valid-step ratio 少于 5% 的 220 个，救回 11.8%。不过 counterexample filtering 平均找到 1.3 个反例/theorem，作者明确说它“不直接提高 overall success rate”，因此表 3 不能单独证明每个组件都必不可少（§4.3.4、表 3–4）。failure analysis 还报告 692 个未解 theorem（241/199/252），与 2,167 个成功合计 2,859，仍无法和表 1 分母统一；validation 的 7.77M attempts 中 69.8% 是 kernel error，error 内 undefined fact 占 60.1%、tactic inapplicable 占 17.9%。test+hard 的 451 个失败里，96.3% 深度至少 11；241 个 validation failure 中 23 个出现真实 counterexample，且最终 Sledgehammer 一个也没关闭（§5.2、表 5–6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| state–step SFT 加交互式搜索显著优于 neural 与 Hammer baseline | 表 1：作者口径 Mistral 77.6%，FVEL 7.8%，Hammer 40.3% | seL4/FVELER；count、rate 与有效分母不能完全复算 | 中 |
| domain fine-tuning 是候选质量的主要来源 | 表 4：hammer-free base 0.0%/0.1%，SFT 59.8%/57.1% | 相同 tree-search 配置；只测 Qwen/Mistral | 强 |
| 对未见 session 和外部 project 有部分泛化 | SysInitGroup 67.6%；四个外部集 22.6%–65.1% | 共用 Isabelle；X86 相近，多个集 hammer-friendly | 中 |
| 自动 proof 可减少约 79.8% 人工工作 | exact-prefix 模拟与论文定义的 `η` | 非 user study；把 proof line 等同 effort，不含 review/maintenance | 弱 |
| 返回 proof 的逻辑正确性不依赖 LLM 可信度 | 每一步由 Isabelle 执行，外部 solver 结果也要重建 kernel proof | 只保证给定 formal theorem；不保证 specification/model 正确 | 强 |

## 批判性分析

### 论证链条

论文最有说服力的想法不是“LLM 会证明 seL4”，而是把 ITP 内部状态重新变成训练和搜索接口。procedural proof 的语义藏在中间 goal，这一观察直接导出 state–step replay；模型容易 hallucinate，又直接导出 kernel execution、revision 和 symbolic filtering。Table 4 清楚显示，没有 domain SFT，tree search 几乎无候选可用。这条 observation → mechanism → ablation 链是完整的。

但“scaling systems software verification”是比实验更宽的标题。系统从一个已经存在、可编译的 theorem 和成熟 lemma/tactic library 开始，只减少 proof construction 的一部分成本。specification、abstraction、invariant discovery、C-to-model correspondence 与 proof maintenance 仍由专家承担。seL4 的 20 person-years 不能直接按 77.6% theorem success 或 79.8% line metric折算。

### 假设压力测试

当前 ranking 把局部模型概率当成长期可完成性的 proxy。短 proof 中这通常有效；超过 10 行后约 20% 的成功率，以及大多数失败在深度 31 以后耗尽，显示搜索不是“找不到第一步”，而是在后期缺少计划。一个需要先发明 auxiliary lemma、选择不常见 induction 或暂时把 goal 变复杂的证明，很可能被平均 log-probability 排到后面。revision 只在 tactic 名和 premise 名附近搜索，也不能补足这种战略缺口。

数据切分同样需要压力测试。validation/test 是随机 theorem split，同一 theory/session 内相邻 theorem 会共享 imports、局部 fact 和 proof pattern；test-hard 隔离 session 更好，但仍依赖 seL4 foundation。生成 proof 与 ground truth 的 sequence/Jaccard similarity 较低，只说明脚本表面不同，不能排除 pretrained model 见过 public seL4，或通过相邻 theorem 学到几乎同一 lemma 组合。外部 benchmark 缓解了这一点，但 Code2Inv 的 22.6% 也揭示了域变化后的落差。

### 实验可信度

评测的优点是规模大，并报告 length、session、external project、ablation、成功案例和两层 failure analysis。Isabelle kernel 使“成功”有清楚的判定，不依赖人工评分。尤其是 7.77M failed tactic 和 451 个 failed run 的 breakdown，揭示 undefined premise 与 late-search collapse，而不只给最终百分比。

最大问题是核心汇总数字不能闭合。表 1 百分比、2,167/1,965/1,124 等成功数、原始 3,044 个 evaluation theorem、“still valid”措辞和 692 个失败不能导出同一个 denominator；论文也未给 per-split valid count。类似地，120 分钟统一 cap 与 139.1 分钟成功平均值相冲突。它们不太可能同时表示单 theorem 的同一种 wall-clock measure。在作者澄清前，适合引用“表 1 报告 77.6%”和各表原值，不适合自行声称一个精确的总体成功/失败概率或平均时延。

compute fairness 也不透明。硬件只写“六张高端 GPU”，没有型号、训练时长、inference batching、每 theorem GPU-hour、Isabelle CPU saturation 或成功 proof 的能耗。Selene、FVEL、Auto、Hammer 与 fine-tuned search 使用的模型、候选数和 compute path 不同；同一 wall-clock cap 并不能保证同等算力。只有 API ablation 给了约 4.1 美元/theorem，full local system 没有对应成本。

### 系统性缺陷

failure log 显示 undefined fact 单项占 kernel error 的 60.1%，说明模型仍没有被 context 严格约束。把候选限制为当前可见 premise、先预测 lemma ID 再解码 tactic，可能比生成后按 edit distance 修复更直接。与此同时，Sledgehammer 对所有 241 个 validation residual failure 都无能为力，表明“tree 简化后 Hammer 收尾”只覆盖某些成功 case，不能当普遍 fallback。

23 个 validation failure 出现 counterexample，作者推测是 benchmark 切 state 时丢了必要 assumption。这不是纯粹的框架失败，却说明数据生成管线也需要 formal validation：如果 evaluation obligation 本身不可证明，success denominator 和 failure attribution 都会被污染。最后，kernel-valid 不等于维护友好。案例中机器用 29 步替代人类一条 composite tactic；library 更新后，这种低层脚本可能更容易 break，也可能让 reviewer 花更多时间理解。

## 局限与后续工作

- **局限 1**：只生成已经给定的 Isabelle theorem proof，不生成 specification、invariant，也不验证程序到 formal model 的映射。
- **局限 2**：主要训练和评测来自 seL4；随机 split 有 library-level leakage 风险，test-hard 也未脱离同一 ecosystem。
- **局限 3**：长 proof 成功率明显下降，失败大多在较深位置耗尽搜索，当前没有显式高层 plan 或 auxiliary-lemma generation。
- **局限 4**：论文的 success count/rate/failure denominator 与 time-limit/mean-time 报告不一致，阻碍精确复现和系统比较。
- **局限 5**：GPU 型号、训练成本、full-system per-theorem cost、throughput 和能耗没有报告。
- **局限 6**：79.8% 是 exact-human-prefix 与 proof-line proxy 的模拟，不是专家 user study；不含 proof review、重构和长期维护。
- **局限 7**：目前只验证 Isabelle/HOL；换 Lean、Rocq 或其他项目级 tactic ecosystem 是否有效未知。
- **后续工作 1**：公开每个 split 的原始数、有效 theorem 数、成功/失败数、timeout 与 wall/GPU time，提供能逐行复算的 manifest。
- **后续工作 2**：在训练/测试之间做 theory、session、repository 和时间切分，并加入完全私有或发布日期晚于 pretraining 的项目，分层测泛化。
- **后续工作 3**：把 premise 选择变成 context-constrained decoding，目标是同时降低 undefined-fact 比例、总 tactic attempts 和 time-to-proof。
- **后续工作 4**：训练 value/planning model 预测剩余 proof distance，允许提出 auxiliary lemma，并在相同 compute budget 下单独报告长度超过 10 行的成功率。
- **后续工作 5**：让 seL4 专家比较从零手写、AI completion 和 whole-proof review 的真实 wall time、修改次数、可读性与 library upgrade 后 breakage。
- **后续工作 6**：把 proof-state extraction 加入 assumption-preservation check，先剔除可被 QuickCheck/Nitpick 反例证明为无效的 benchmark obligation。

## 相关

- **相关概念**：交互式定理证明、proof-state search、premise selection、神经—符号推理、形式化验证
- **相关系统与数据集**：seL4、Isabelle/HOL、Sledgehammer、FVELER、Selene、Code2Inv
- **同会议**：[[OSDI-2026]]
