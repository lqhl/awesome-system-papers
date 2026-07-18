---
type: paper
name: AlphaProofNexus
full_title: "Advancing Mathematics Research with AI-Driven Formal Proof Search"
authors: [George Tsoukalas, Anton Kovsharov, Sergey Shirobokov, Anja Surina, Moritz Firsching, et al.]
venue: arXiv
year: 2026
tags: [formal-proof, theorem-proving, lean, llm-agent, auto-research, evolutionary-search]
source_pdf: "[[arxiv26-tsoukalas-lean-formal-proof.pdf]]"
source_md: "[[arxiv26-tsoukalas-lean-formal-proof]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# Advancing Mathematics Research with AI-Driven Formal Proof Search (arXiv 2026)

> **一句话总结**：DeepMind 提出 AlphaProof Nexus，用 Gemini 3.1 Pro 与 [[Lean]] compiler feedback 搜索形式化证明；full-featured Agent (D) 在 353 个 Erdős formalizations 中解决 9 个，OEIS pipeline 从 492 次 formalization attempts 得到 44 个经人工审核的 accepted proofs；post-hoc 的 Basic Agent (A) 也复现全部 9 题，而 D 仅在 Fig. 3 的 #125/#138 上便宜 2–5×（§3、§5，Table 1，Fig. 3）。

## 问题与动机

LLM 在数学推理上进展迅速（如 Aletheia、[[AI-Co-Mathematician-arXiv26]]），但自然语言证明的幻觉与隐蔽逻辑错误使其难以直接进入数学研究流程：未审查的中间步骤错误会级联，人工审阅成本极高。形式化证明（在 [[Lean]] 等 proof assistant 中生成机器可验代码）是常见缓解路径——[[AlphaProof-Nature25]] 已在 IMO 级竞赛数学上证明 RL 驱动搜索的可行性，但此前成功主要集中在竞赛题与**人类主导、AI 辅助**的自然语言论证形式化（如 sphere packing 8 维），**从未在开放研究级问题上做过大规模、端到端的自主证明搜索评估**。

论文核心 claim 是：以 Lean 为媒介的 LLM agent 不仅能验证已知结果，还能**自主发现新证明**，且 agent 架构选择（简单 Ralph loop vs 进化 + 专用 prover 工具）对成本与成功率有可量化影响。作者用 Formal Conjectures 仓库中 353 个 Erdős 问题、492 个 OEIS 猜想，以及组合、优化、图论、代数几何、量子光学等协作课题做系统验证。

## 关键观察 / 隐含假设

- **观察 1**：Lean 编译器错误信息足以在多轮 agent loop 中把 LLM 推理「锚定」到类型安全的证明 sketch 上，即便没有数值 fitness 也能渐进消去 `sorry`。
  - **依赖假设**：目标定理已被正确形式化，且 Mathlib 等库对问题域足够成熟；prover 使用 frontier 模型（Gemini 3.1 Pro）。
  - **可能失效场景**：需要大量新定义/新理论的领域、形式化本身有误、或问题无法分解为 Mathlib 可表达的子目标时，编译反馈粒度太粗，loop 会停滞或 offload 难点到幻觉引理。

- **观察 2**：形式化证明评估是**二元信号**（编译通过且 sorry-free vs 否），与 [[AlphaEvolve-arXiv25]] / [[FunSearch-Nature24]] 的连续数值 reward 不同；直接用进化算法会面临 fitness landscape 不连续的问题。
  - **依赖假设**：可用廉价 LLM rater（Gemini 3.0 Flash）对**不完整** sketch 做相对排名，且排名与最终可证性有一定相关性。
  - **可能失效场景**：Agent (C)（纯进化、无 [[AlphaProof-Nature25]]）在所有 9 个已解 Erdős 题上均差于 (A)，说明**仅靠软信号时 rater 噪声可能超过收益**；硬信号（AlphaProof 子目标 proof/disproof）才是进化框架有效的关键支撑。

- **观察 3**：开放数学问题的可解性高度不均——对 353 题统一跑满预算后仅 9 题成功，说明「先广搜再找 tractable 题」本身是大额算力投资，单题几百美元的成本不能代表发现过程的边际成本。
  - **依赖假设**：研究者愿意预先投入全库扫描成本；每题 3000 episodes 上限足以覆盖可解题的搜索深度。
  - **可能失效场景**：更难 Erdős 题或需新理论的问题在预算内成功率趋近零；报告的单题成本未含 AlphaProof 调用（约 $60/题）及全库失败尝试的摊销。

- **假设 1**：Gemini 3.1 Pro 的数学推理能力已达到「研究级子目标分解 + tactic 合成」门槛，小模型（Flash / Flash-Lite）与 AlphaProof standalone tree search 均无法解任何评估题。
  - **证据强度**：**强**——论文在同一 9 题集上做了直接对比，小模型与 standalone 系统 solve rate 为 0。

## 核心方法

**AlphaProof Nexus** 是连接 frontier LLM 与 Lean 编译器的 agent 框架。输入为带 `sorry` 的 proof sketch（含 EVOLVE-BLOCK / EVOLVE-VALUE 标记限定可改区域），输出为 sorry-free 的完整证明。

四种递增强度的 agent：

- **Agent (A) — Basic**：多个无共享状态的 prover subagent 并行执行 Ralph loop——Gemini 3.1 Pro 多轮推理 + `search_replace` 编辑 + 每步 Lean 编译反馈；episode 结束若仍有 `sorry`，将教训写入注释进入下一轮。任一 subagent 成功即终止全部。验证阶段用 SafeVerify 防 axiom 注入等环境漏洞。
- **Agent (B) — +AlphaProof**：在 (A) 上增加对 [[AlphaProof-Nature25]] 的工具调用，对 sketch 中子目标返回 proof / disproof / failure，分别替换进 sketch 或反馈给 prover。
- **Agent (C) — +Evolution**：受 [[AlphaEvolve-arXiv25]] 启发，prover 从共享 population database 按 P-UCB 采样父 sketch；Gemini 3.0 Flash rater 对 7 个 sketch 做 Plackett-Luce 排名（清晰度、可行性、新颖性），Gibbs 采样得 Elo 分数驱动选择。核心创新是用 **LLM 相对评价替代可计算 fitness**。
- **Agent (D) — Full-featured**：(B)+(C)；10 个并行 prover + rater，global goal cache（跨 sketch 复用已证/已否子目标的 deep hash），每 episode 最多 5 次 AlphaProof 查询、90 次 search-replace；Lean v4.27 + Pantograph 在 Docker sandbox 中编译。

与 [[AlphaEvolve-arXiv25]] 的根本差异：后者优化可量化 reward（程序性能、构造质量），目标是**发现程序**；AlphaProof Nexus 面对的是**二元形式化验证**，目标是**发现证明**。与 [[FunSearch-Nature24]] 相比，evaluator 从程序运行结果变为 Lean 编译器——更强（零容错）也更硬（无部分正确性中间信号）。

**三层反馈信号**是理解架构递增的关键：

| 层 | 信号 | 性质 | 相对成本 |
|---|---|---|---|
| Lean 编译 | 硬信号、粒度粗 | 不可被 agent 直接游戏化 | 低 |
| [[AlphaProof-Nature25]] 分派 | proof / disproof / failed，可缓存 | 硬信号 | 高（约 $60/题，27.5 TPU·h） |
| LLM rater 排名 | 软信号 | 填补二元评估的信息空白 | 中低 |

## 设计取舍

- **取舍 1 — 简单 loop vs 重型 agent**：(A) 工程复杂度低、无 population 状态；(D) 在 Fig. 3 所示六题中的 #125、#138 上成本低 2–5×，在其余四题上约只有 (A) 一半的 cost efficiency。该比较是对 D 已解九题的 post-hoc evaluation，Fig. 3 只展示六题（§5，Fig. 3；全部九题见 Appendix Fig. 10）。
- **取舍 2 — AlphaProof 算力分配**：优先 LLM inference，AlphaProof 仅用 low-compute tree search（非 TTRL），每子目标 400 simulations + RPC 超时。换取更低 per-query 成本，但 standalone 模式无法单独解题。
- **取舍 3 — 可复现性 vs 能力上限**：Gemini 3.1 Pro、AlphaProof 模型、Nexus 框架代码均未开源；仅 Lean 证明与部分 prompt 公开。定理可本地验证，**系统行为不可复现**。
- **边界条件**：在 Mathlib 成熟的组合、数论、凸优化等领域表现最好；需大量新理论或形式化薄弱领域仍大多失败；EVOLVE-VALUE 块使 agent 可同时搜索算法参数与证明（Anchored GDA 案例），但依赖用户正确标记可进化区域。

## 实验与结果

- **Erdős 问题**：Agent (D) 对 Formal Conjectures 中 353 题各跑至多 3000 episodes，**9/353** 自主解决；含 #12(i)（1970 年 Erdős–Sárközy，56 年未决）与 #125（1996 年 base-3/4 和集 density 问题）；单题推理成本约几百美元；专家验证 Lean 陈述忠实于原猜想。
- **Agent 架构对比（9 个已解题）**：(A) 在 post-hoc 分析中同样解出全部 9 题；(D) 在 #125、#138 上成本低 2–5×，但该优势不普遍。(B)/(D) 图示成本不含 AlphaProof inference，后者约 27.5 TPU-hours、$60/problem；A/B 用 100 个单 subagent attempts，C/D 用 10 个十-subagent attempts，variance 不完全可比（§5，Fig. 3；Appendix Fig. 10）。
- **OEIS**：Gemini 自动形式化 492 个开放猜想，要求先证 test lemmas 防 misformalization；**44** 个经人工审核为正确形式化且此前未证明。
- **领域部署**：Anchored GDA 精确 O(1/k) 收敛率并自主发现新参数调度；代数几何 pure O-sequence log-concavity（15 年开放问题）；图重构猜想二分变体、Graffiti 1996 生成树叶子界；Green 列表 #57 浮点反例形式化；量子光学 GHZ 态存在性（4/6/10 顶点）等。
- **失败模式**：核心难点被 offload 到单一 `sorry` 的同义反复引理；声称「文献已知」的引理实为幻觉——显式 prompt 无法完全消除。
- **小模型 / standalone**：Gemini 3.0 Flash、3.1 Flash-Lite 版 (A) 与 AlphaProof standalone tree search 在评估题上 solve rate 均为 0。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Agent D 在 Formal Conjectures 的 353 个 Erdős formalizations 中解决 9 个 | §3, Table 1; Appendix §B.2 | early-Feb-2026 corpus；最多 3000 episodes/problem；experts 检查 statement fidelity | strong |
| Basic Agent A 在 post-hoc set 上复现全部 9 个成功 | §1, §5, Fig. 3; Appendix Fig. 10 | 只含 D 已解问题；A/B 与 C/D attempt design 不同 | medium |
| OEIS pipeline 从 492 attempts 得到 44 个 accepted proofs | §3 OEIS; Appendix §B.2 | Gemini 从 2649 open conjectures 选 500；8 个 upgrade 后排除；manual review | strong |
| Small-model A 与 standalone AlphaProof 在所测九题上均解出 0 题 | §5 after Fig. 3 | selected nine-problem post-hoc set；未跑 full 353 sweep | medium |
| B/D 图示成本遗漏约 $60/problem 的 AlphaProof compute | §5, Fig. 3 caption | v6e TPUs；约 27.5 TPU-hours/problem；不含全库失败搜索摊销 | strong |

## Critical Analysis

### 论证链条

作者从「形式化验证消除幻觉」→「agent + Lean 可搜索证明」→「大规模开放问题结果」的链条总体闭合：每个成功证明都有公开 Lean 源码，比纯自然语言 AI 证明更易独立核验。薄弱环节在于把 **9/353 Erdős 成功率**外推为「形式化证明搜索已成为数学研究工具」——97% 失败率说明方法仍高度选择性；协作课题（优化、量子光学等）成功案例多为**人机协作**而非完全自主，与 claim 的「autonomous」之间存在粒度差异。Agent 对比实验仅对已解题做 post-hoc 分析，未对全库做前瞻式架构选择验证，「(A) 足够」的结论带有时序后见之明偏差。

### 假设压力测试

- **形式化正确性**：9 个 Erdős 解经团队专家验证，但 OEIS 44/492 仍依赖人工审核子集；autoformalization 错误是系统性风险（论文用 test lemmas 缓解，未消除）。
- **LLM 能力外推**：当前结果绑定 Gemini 3.1 Pro；论文自己展示小模型完全失败，说明**非 frontier 模型下方法可能整体不工作**。
- **成本假设**：「几百美元/题」不含全库扫描摊销与 AlphaProof；AlphaProof 另需约 $60/题。最难题上 (D) 省钱，简单题上 (A) 更省——不存在单一最优架构。
- **领域迁移**：代数几何 8 题仅解 2 个开放问题；多数 Erdős 题仍不可达——Mathlib 成熟度是隐含门槛，论文在 Discussion 中部分承认。

### 实验可信度

- **Benchmark 代表性**：Erdős + OEIS 是极佳的开放问题基准，但偏向可 Lean 形式化的组合/数论；与 Aletheia 等自然语言路线在部分 Erdős 题上的重叠使「形式化独有优势」需更细比较（论文在 supplementary 讨论了 related work，主文略简）。
- **Baseline 公平性**：与 (A) 对比时 (C)/(D) 仅 10 attempts/problem 且无方差估计，(A)/(B) 有 100 attempts 可画 Pareto 曲线——设计合理但统计功效不对称；未与 Aristotle、Goedel-Prover 等最新形式化 prover 在相同 9 题上 head-to-head。
- **Ablation 支撑设计分解**：(A)→(B)→(C)→(D) 递进清晰，且 (C) 差于 (A) 有力证明「无硬信号的进化有害」，是全文最有洞察的 ablation。
- **Metric 覆盖**：报告 solve rate、USD 成本、wall-clock；未系统度量证明长度、人工审查时间节省、或 misformalization 检出率。

### 系统性缺陷

- **框架与模型封闭**：Nexus pipeline、AlphaProof 权重、Gemini API 均不可复现；开源仅 `.lean` 结果与 condensed prompt。
- **搜索方差**：per-problem 成本方差高；论文未讨论 tail latency 或 SLA 式「给定预算内保证成功率」。
- **安全与隔离**：Docker + SafeVerify 设计合理，但论文未讨论 multi-tenant 或恶意 sketch 风险（单团队内部使用场景）。
- **运维复杂度**：(D) 需 asyncio 控制器、population DB、Elo Gibbs 采样、global cache、RPC 批处理——工程成本显著高于 (A)，论文未量化人力维护开销。
- **可观测性**：论文未讨论生产级 tracing、失败归因 dashboard 或预算熔断策略。

## 局限与 Future Work

- **局限 1**：353 题中 97% 失败；agent 继承 LLM 偏见与高方差，边界刻画不足。
- **局限 2**：全库探索成本未在 headline 数字中体现；成功高度依赖 Mathlib 覆盖与问题可分解性。
- **局限 3**：框架代码与 AlphaProof 未开源，社区无法在其他开放问题上复现搜索过程。
- **Future work 1**：在固定算力预算下前瞻式比较 (A) vs (D) 的**期望成本**，而非仅对已解题 post-hoc——需预注册问题集与 stopping rule。
- **Future work 2**：量化 autoformalization 错误率与 test lemma 覆盖率的关系，建立「形式化质量 → 证明搜索成功率」的 measurement。
- **Future work 3**：将 TTRL 模式 AlphaProof 与 LLM inference 做动态算力分配，测试在最难子目标上的边际收益是否 justify 额外 TPU 成本。

## 相关

- **相关概念**：formal verification、proof sketch、autoformalization、Ralph loop、P-UCB、Plackett-Luce rating、LLM-guided evolution
- **同类系统**：[[AlphaProof-Nature25]]、[[AlphaEvolve-arXiv25]]、[[FunSearch-Nature24]]、[[AI-Co-Mathematician-arXiv26]]、[[Auto-Research-arXiv25]]
- **同主题**：[[Auto-Research]]
- **对比**：形式化自主发现 vs 自然语言证明 + 事后形式化（Aristotle / Gauss 路线）；进化搜索在二元验证 vs 数值 reward 场景下的 fitness 设计
