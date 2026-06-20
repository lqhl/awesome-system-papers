---
type: paper
name: BOA
full_title: "Toward Principled LLM Safety Testing: Solving the Jailbreak Oracle Problem"
authors: [Shuyi Lin, Anshuman Suri, Alina Oprea, Cheng Tan]
venue: MLSys
year: 2026
tags: [llm-safety, jailbreak, red-team, search, evaluation]
source_pdf: "[[66f041e16a60928b05a7e228a89c3799.pdf]]"
source_md: "[[66f041e16a60928b05a7e228a89c3799]]"
---

# Toward Principled LLM Safety Testing: Solving the Jailbreak Oracle Problem (MLSys 2026)

> **一句话总结**：形式化 jailbreak oracle 问题（给定 ⟨M,D,p,J,τ⟩ 判定是否存在 likelihood ≥ τ 的 harmful 响应），并实现 BOA 两阶段搜索（BFS 随机采样 + DFS priority search + hybrid sampling）；在 ϵ=10⁻⁴ 下 Vicuna-7B JDR 达 **95.31%**，揭示解码策略微调即可 catastrophic 削弱对齐、greedy 评测低估部署风险约 **1.5–3.5×**，且 alignment 既 shallow 又 narrow。

## 问题与动机

LLM 安全评测长期 ad hoc：改 prompt 测 attack success rate、多用 greedy decoding，无法回答部署中的核心问题——**给定模型 M、prompt p、解码策略 D，是否存在 harmful 响应 r 使 J(p,r)=1 且 Pr_D(r|M,p) > τ？** 作者将此形式化为 **jailbreak oracle problem**，把安全评估从「哪种 attack 更强」转向「模型在这些条件下有多安全」。

采样解码下搜索空间指数爆炸（top-k=10、20 token 即 10²⁰ 路径），穷举不可行；纯随机采样又只覆盖高概率 refusal 路径。现有 jailbreak benchmark（JailbreakBench、HarmBench）与 attack 工作（GCG、TAP、AdvPrefix）大多在 greedy 或启发式采样下评测，忽略 generation distribution 的系统性探索，导致 pre-deployment 评估与线上 sampling-based serving 脱节。

## 关键观察 / 隐含假设

- **观察 1**：部分 adversarial prompt 的 jailbreak 位于模型自然高概率区域，少量随机采样即可命中；其余需探索低概率路径。
  - **依赖假设**：评测 prompt 集（JO-Bench 128 条）覆盖真实 red-team 语义多样性；refusal 与 compliance 在 token 树上有可区分模式。
  - **可能失效场景**：multi-turn 渐进式 jailbreak、或 refusal 与 harmful content 在概率上高度纠缠的 prompt。
- **观察 2**：安全对齐集中在生成前几 token 的高概率 refusal 路径上（alignment shallow）；同时大量 **低概率旁路** 可绕过 guardrail（alignment narrow）。
  - **依赖假设**：前 n_align=20 token 的均匀采样足以跳出 refusal basin；Qi et al. 等「shallow alignment」结论可迁移到被测 8 模型。
  - **可能失效场景**：深层 circuit-level 对齐、或 refusal 分布在长前缀才显现的模型。
- **观察 3**：解码策略对 vulnerability profile 影响远大于 attack prompt 微调——top-k 强制考虑 k 个候选，JDR 可稳定 **>90%**；top-p 则反映概率质量是否集中在 refusal 上。部分 prompt 在 default decoding 下「安全」，换任意其他 decoding 即被攻破（Llama-3.1-8B 上 **30/128**）。
  - **依赖假设**：RLHF/alignment 训练与评测共用相同 default decoding，造成 overfitting。
  - **可能失效场景**：训练时已做多 decoding 增强的模型；或 serving 栈固定单一 decoding 且与评测一致。
- **假设 1**：二元 judger J 可扩展为 partial generation 的细粒度 scorer Ĵ，且 Qwen2.5-3B-Instruct FP16 足够驱动 priority search。
  - **证据强度**：**中**——judger ablation 在 Llama-2-7B 上 70% JDR vs word-filter 35%，但全 pipeline 高度依赖 judger 质量与 prompt 设计。
- **假设 2**：相对 likelihood 阈值 τ(n)=ϵ·L_n(M,p,D) 比绝对概率阈值更公平，ϵ=10⁻⁴（约每 10⁴ 次生成出现一次）代表可部署风险。
  - **证据强度**：**中**——ϵ 从 1 到 10⁻⁸ JDR 单调变化，但「可接受风险」仍是 policy 选择，论文未与真实 incident rate 校准。

## 核心方法

**问题形式化**：给定 judger J、用户参数 ϵ，用 n-token response likelihood L_n 定义相对阈值 τ(n)。Oracle 返回 **Sat**（附带 witness 响应 r̂）或 **Unsat**（在 likelihood budget 内穷尽搜索的证据）；**Timeout** 为 provisional。验证结构不对称：Sat 可证漏洞，Unsat/Timeout 不能证全局安全。

**BOA 两阶段搜索**（Algorithm 1）：
1. **Phase 1 — Random Sampling**：n_sample=10 次按标准解码策略 D 完整采样；若 J(p,s)=1 且 log-prob ≥ log τ(|s|) 立即返回。
2. **Phase 2 — Priority Search**：DFS + priority queue，按 scoring function f 探索 token 树；前 n_align=20 token **均匀采样**候选（避开高概率 refusal），之后按模型概率采样；lookahead m=200、n=10 条候选，Ĵ 打分后取平均作为优先级。

**Judger 栈**：轻量 refusal filter（模式匹配 + 短 LLM refusal 判断，处理 refuse-then-comply）→ 细粒度 Ĵ（Qwen2.5-3B-Instruct）。**系统实现**：batch decode（可插拔 [[vLLM]]/HuggingFace）、fast approximate top-p（仅扫 top-512 token）、judger buffer 批处理、response cache 复用前缀重叠路径。全套优化使 phase 2  judged sequences 从 ~992 提升到 ~9726/ prompt（约 **10×**）。

开源：https://github.com/shuyilinn/BOA

## 设计取舍

- **取舍 1：两阶段 BFS→DFS vs 纯采样/纯 beam search**——随机采样覆盖「容易 jailbreak」；priority search 在固定 token budget 下系统性探索低概率路径。牺牲全局完备性，换可在一个 prompt 上 600s timeout 内产出可操作结论。
- **取舍 2：hybrid uniform+model sampling vs 纯 model / 纯 uniform**——前 20 token 均匀采样牺牲 coherence 早期路径，换取跳出 refusal；之后恢复模型分布保生成质量。n_align 保守偏大，不同模型需调参。
- **取舍 3：LLM judger 细粒度打分 vs 纯二元 J**——Ĵ 调用昂贵，靠 refusal filter + cache + batch 摊销；仍构成搜索吞吐主瓶颈。
- **边界条件**：单轮生成、固定 timeout（10 min/prompt、H100）；Sat 结论强，Unsat/Timeout 仅 bounded evidence；多轮对话、动态 system prompt 未覆盖。

## 实验与结果

- **JO-Bench**：JailbreakBench + HarmBench chemical-biological，128 prompts、11 harm categories；8 模型（Vicuna-7B 至 Qwen2.5-72B AWQ），默认 decoding + ϵ=10⁻⁴。
- **JDR（主结果）**：Vicuna-7B **95.31%**；Gemma-3 **34.38%**；Llama-3.1-8B **24.22%**；Qwen-3 **21.09%**；Llama-2 **7.03%**。JDR 随 search time 单调上升。
- **vs baselines**：BOA 全面高于 naive sampling 与 beam search；Qwen-3、Qwen-2.5-72B 等提升约 **50%** JDR。
- **解码策略（Llama-3.1-8B）**：top-k（k∈{5,10,20}）JDR **>90%**；top-p 显著更低；温度 T∈{0.6,1.0} 亦有明显差异。
- **ϵ 敏感性**：Llama-3.1-8B 在 ϵ=1/10⁻⁴/10⁻⁸ 上 JDR 为 **12.50% / 24.22% / 31.25%**；高 ϵ 仍能找到 jailbreak，说明 greedy/heuristic 评测不足。
- **Attack 重评（ϵ=10⁻⁴）**：AdvPrefix+GCG on Llama-3.1 greedy **25%** → BOA **39.06%**（~1.5×）；TAP on Qwen-3 greedy **13.28%** → BOA **46.88%**（~3.5×）。
- **Defense**：LAT 默认 **0%** JDR，top-k k=5 仅 **2.34%**。
- **Timeout**：Llama-3.1-8B **69.53%** vs 70B **41.41%**——8B 分支因子更大、refusal 更长，固定预算下更难穷尽。

## Critical Analysis

### 论证链条

observation（高/低概率 jailbreak 分区、shallow+narrow alignment、decoding overfitting）→ 设计（两阶段搜索 + hybrid sampling + Ĵ 引导）→ 结果（高 JDR、解码敏感、greedy 低估）链条整体闭合。较强环节：**Sat witness + 系统化 exploration** 直接挑战「attack failed under greedy」叙事。较弱环节：把 JDR 与「部署不安全」等同——需 judger 与人类意图对齐，且 Timeout 占比高时负向结论弱。

### 假设压力测试

- **Judger 单点依赖**：默认 Zhu et al. nuanced judger + Qwen2.5-3B；换 judger 或 harm 定义，JDR 与 witness 可比性存疑。论文有 judger ablation 但仅在 Llama-2-7B 开发集。
- **ϵ 与部署量纲**：10⁻⁴ 与「日均 query 量」的映射是启发式，未用 production trace 验证 incident 频率。
- **600s timeout**：大模型、宽 top-k 树、长 refusal 时 Unsat 可能只是「没搜完」；论文诚实区分 exhaustive vs timeout，但读者易误读为「安全认证」。
- **单轮限制**：真实 jailbreak 常 multi-turn；论文明确 leave as future work，当前 oracle 不覆盖主要攻击面之一。

### 实验可信度

- **Benchmark**：JO-Bench 语义多样性好，但 128 prompts 相对工业 red-team 规模偏小；8 模型覆盖主流开源族，缺闭源 API 模型。
- **Baselines 公平性**：naive sampling / beam search 与 BOA 共享 token budget，合理；但未与 Best-of-N serving 栈、或专用 red-team 工具（Tree of Attacks 等）在相同 ϵ 下端到端对比。
- **Defense 评估**：LAT 仅单点，难泛化到 circuit breaker、constitutional classifier 等。
- **系统 ablation 充分**：refusal judger、approx top-p、batch judger、cache 逐步贡献清晰（Table 4）。

### 系统性缺陷

- **成本与规模化**：每 prompt 10 min H100 + 多次 LLM judger 调用，全量 benchmark 成本高；论文未讨论 parallel telescopic search 的工程落地与成本模型。
- **Serving 集成**：依赖外部 decoding 框架，但未评测与在线 [[Continuous-Batching]]、dynamic batch 下的交互；fast top-p 近似在极端 p 下正确性边界未形式化。
- **可观测性与合规**：oracle 输出 witness harmful content 的存储、审计、人工复核流程——**论文未讨论**。
- **运维**：judger 模型版本、prompt 模板变更对历史 JDR 可比性的影响未建立 baseline registry。

## 局限与 Future Work

- **局限 1**：单轮 generation；multi-turn 需建模对话状态与用户侧策略，搜索空间进一步膨胀。
- **局限 2**：BOA 是 **falsification tool**，Timeout/Unsat 只给 coverage guarantee，非形式化 safety proof。
- **局限 3**：高 Timeout 率（尤其 8B）使「未发现 jailbreak」结论在固定预算下统计效力不足。
- **Future work 1**：在 production query volume 与 harm incident 数据上校准 ϵ，建立 risk-informed deployment threshold，而非固定 10⁻⁴。
- **Future work 2**：multi-turn oracle + 与 alignment 训练 loop 集成（用 oracle 发现的 low-prob path 作 adversarial training data），验证能否同时拓宽 shallow 与 narrow alignment。
- **Future work 3**：测量 decoding-strategy overfitting 的因果链——在 RLHF 阶段刻意多样化 D，看 BOA JDR 是否对 decoding 扰动更鲁棒。

## 相关

- **相关概念**：LLM-Safety、Jailbreak、Alignment、Red-Teaming、Speculative-Decoding（对比：BOA 探索 generation 空间而非 draft-verify）
- **同类系统/基准**：JailbreakBench、HarmBench、GCG、TAP、AdvPrefix、LAT（Latent Adversarial Training）
- **同会议**：[[MLSys-2026]]
- **对比**：greedy attack eval vs distribution-aware oracle；top-p（概率质量）vs top-k（旁路存在性）安全画像