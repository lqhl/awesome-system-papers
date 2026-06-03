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
---

# AlphaProof Nexus: Advancing Mathematics Research with AI-Driven Formal Proof Search (arXiv 2026)

> **一句话总结**：DeepMind 的 LLM 驱动的形式化证明搜索框架，结合 Gemini 3.1 Pro + Lean 编译器验证 + 进化算法，在 353 个开放 Erdős 问题中自主解决了 9 个（含 2 个悬而未决 56 年的问题），每个问题推理成本仅几百美元，同时证明了 44/492 个 OEIS 猜想，并在组合优化、代数几何、量子光学等领域的实际研究中部署出成果。令人惊讶的是，仅靠 LLM ↔ Lean 交替的基础 agent 也解决了全部 9 个 Erdős 问题，但在最难问题上成本更高。

## 问题

LLM 在数学推理上日益强大（如 [[AlphaProof-Nature25]]、Aletheia），但自然语言证明的不可靠性（幻觉、隐蔽逻辑错误）是其融入数学研究的根本障碍。形式化证明（在 Lean 等语言中生成机器可验的证明）是解决此问题的路径，但此前该方法主要局限在竞赛数学和人工辅助形式化，从未在大规模开放研究问题上被系统验证。

## 核心方法

AlphaProof Nexus 是一个让 LLM agent 与 Lean 编译器交互生成形式化证明的框架，定义了四种逐渐增强的 agent：

- **Agent (A) — Basic**：多个独立的 prover subagent 执行 Ralph loop——多轮 Gemini 3.1 Pro 推理循环 + search-and-replace 编辑工具 + Lean 编译反馈。每轮编辑后立即编译检查，episode 结束时将教训总结为注释进入下一轮。任一 subagent 找到 sorry-free 证明即终止全部。
- **Agent (B) — +AlphaProof**：在 (A) 基础上让 subagent 可调用 [[AlphaProof-Nature25]] 作为工具，填入 sketch 中缺失的证明步骤。AlphaProof 返回 proof / disproof / failure，分别直接替换 / 反馈给 prover / 提示。
- **Agent (C) — +Evolution**：引入进化算法（受 [[AlphaEvolve-arXiv25|AlphaEvolve]] 启发）。prover subagent 从共享 population database 采样 sketch，用 Gemini 3.0 Flash rater agent 对 sketch 做相对排名（清晰度 / 可行性 / 创新性），聚合成 Elo 评分后驱动 P-UCB 采样。关键创新是**用 LLM 相对评价替代数值 fitness**，解决了形式化证明「通过/不通过」二元信号无法做梯度化进化选择的问题。
- **Agent (D) — Full-featured**：同时具备 AlphaProof 调用和进化搜索能力。per-problem 跑 10 个并行 prover subagent + rater agent，配合 global goal cache（跨 sketch 复用已证/已否子目标）和 SafeVerify（防 axiom 注入等环境漏洞），是实际大规模探索的主力。

**vs [[AlphaEvolve-arXiv25|AlphaEvolve]]**：AlphaEvolve 优化可量化的数值 reward（代码运行速度、数学构造质量），目标是**发现程序/构造**；AlphaProof Nexus 面对的是**二元形式化验证**（proof 通过 or 不通过），目标是**发现证明**。两者的进化框架组件复用，但 fitness 机制根本不同。

**vs [[FunSearch-Nature24|FunSearch]]**：FunSearch 也是 LLM + evaluator 做进化搜索，但 evaluator 是程序运行结果；AlphaProof Nexus 的 evaluator 是 Lean 编译器——更强（零容错）但也更硬（无部分正确性的中间信号）。

**三层信号架构**：理解 agent 递增设计的关键不是「哪个更强」，而是框架如何在缺乏可计算 fitness 的场景下拼凑出驱动搜索的反馈信号：

| 层 | 信号 | 性质 | 成本 |
|---|---|---|---|
| Lean 编译错误 | 硬信号、粒度粗、不可被 agent 游戏化 | 免费 |
| [[AlphaProof-Nature25\|AlphaProof]] 分派 | 硬信号（proof / disproof / failed），可跨 sketch 缓存 | 贵（~$60/题） |
| LLM rater 主观排名 | 软信号、不可靠但填补了解析空间 | 便宜 |

Agent (A) 只用第一层就够了（Ralph loop 证明了编译错误反馈的多轮累积足以驱动搜索）；Agent (D) 在三层俱全后对最难问题获得额外增益——但不是因为进化搜索本身有魔力，而是 AlphaProof 分派的硬信号为进化框架的选择提供了可靠的差异化基础。Agent (C)（纯进化，无 AlphaProof）在所有题上都比 (A) 差，印证了**没有硬信号支撑时 LLM rater 引入的噪声超过收益**。

## 关键结果

### Agent 设计洞察

基础 agent (A) 解决了全部 9 个 Erdős 问题是在 **post-hoc 分析中发现的**，不是事先的设计选择。本文选 (D) 做大规模探索时，简单 agentic loop 在竞赛基准上表现不佳——也就是说，(A) 能解这些题是事后才知道的，不是事前可预测的。这个发现的实践启示是：**基础模型越强，先试最简单的 agentic loop，别一上来就建进化框架。**

Agent (D) 的优势集中在最难的 2/9 题（#125、#138，成本低 2-5×），而在其余 6/9 题上 (A) 更便宜或持平。Agent (C)（纯进化，无 AlphaProof）在所有题上都比 (A) 差——进化框架单独用甚至会拖后腿。AlphaProof 工具调用的增益体现在 #12(ii) 和 #125 上。小模型（Gemini Flash/Flash-Lite）和 AlphaProof standalone 均无法解决任何问题。

论文坦诚指出：「as LLM capabilities grow, the advantage of the full-featured agent may diminish.」

- **Erdős 问题**：Agent (D) 在 353 个已形式化的 Erdős 问题中自主解决 9 个，包括 #12(i)（Erdős-Sárközy 1970，关于无限集合的无除法约束构造，56 年未完全解决）和 #125（两个进制受限集合的和集的 density 问题，1996 年提出）；每个问题推理成本约几百美元
- **Agent 设计对比**：基础 agent (A) 惊人地也解决了全部 9 个问题，但在最难问题（#125、#138）上 Agent (D) 成本低 2-5×；AlphaProof 工具在 #12(ii) 和 #125 上显著提升效率；小模型（Gemini Flash/Flash-Lite）和 AlphaProof standalone 均无法解决任何问题
- **OEIS**：用 Gemini 自动形式化 492 个开放猜想后，Agent (D) 证明 44 个，经人工审核确认形式化正确且此前未被证明
- **优化理论**：证明了 Anchored GDA 的精确 O(1/k) 收敛速率，同时**自主发现了新的参数调度方案**（在 EVOLVE-VALUE 块内同步搜索算法参数和证明），结果优于前人工作
- **代数几何**：解决了一个约 15 年的开放问题——codimension 3、type 2 的 pure O-sequence 的 log-concavity，使用非平凡的重构和详细案例分析
- **图论**：证明了 graph reconstruction conjecture 的一个二分变体，证明了 1996 年 Graffiti 自动猜想系统提出的一个关于生成树最大叶子数的猜想
- **加性组合**：帮助解决 Ben Green 列表中的 #57 问题，Agent 找到了复值版本的浮点反例并形式化证明其为真反例
- **量子光学**：与 Mario Krenn 合作证明了多个关于单色量子图存在的猜想（4/6/10 个顶点的 GHZ 态可线性光学实现问题）
- **形式化纠错**：Agent 在 Erdős #125 和 #741(i) 中发现并修正了原问题 density 定义的歧义（自然密度 vs 下密度/上密度）
- **失败模式**：(1) 核心难点被 offload 到单一 sorry 的同义反复辅助引理中；(2) 声称某些引理是「已知文献结果」实为幻觉——凸显端到端形式验证的价值

## 开源状态

- ✅ **Lean 证明文件**：[alphaproof-nexus-results](https://github.com/google-deepmind/alphaproof-nexus-results) — 所有已证定理的 `.lean` 源码，可在本地 Lean 4 编译验证
- ✅ **部分自然语言证明**：同一仓库 + 独立 preprint（如优化理论的结果 [58]）
- ✅ **Prompts**：论文附录 Figures 6/7/8 给出了基础 agent、rater、prover 的 prompt 模板（condensed）
- ❌ **AlphaProof Nexus 框架代码**：Ralph loop、进化 pipeline、global goal cache 均未开源
- ❌ **AlphaProof 模型/代码**：Nature 2025 论文描述了方法但未发布
- ❌ **Gemini 3.1 Pro**：闭源 API

可验证但不可复现：任何人在本地下载 `.lean` 文件即可验证所有定理，但无法在别的开放问题上跑这套系统。

## 相关

- **相关概念**：LLM-guided evolution、formal verification、[[Lean]]、Ralph loop、Plackett-Luce rating、P-UCB、proof sketch、autoformalization
- **同类系统**：[[AlphaProof-Nature25]]、[[AlphaEvolve-arXiv25]]、[[FunSearch-Nature24]]、[[AI-Co-Mathematician-arXiv26]]
- **同主题**：[[Auto-Research]]
- **同会议**：arXiv 2026
