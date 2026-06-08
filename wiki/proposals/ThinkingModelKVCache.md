---
type: proposal
name: ThinkingModelKVCache
title: "When KV Cache Heuristics Break: Rethinking Tiering for Thinking-Model Inference"
status: draft
created: 2026-04-30
last_updated: 2026-04-30
target_venue: "OSDI 2027 / SOSP 2027"
tags: [kv-cache, thinking-models, chain-of-thought, llm-inference, tiered-storage, page-migration]
related_papers:
  - "[[vLLM-SOSP23]]"
  - "[[LMCache-arXiv25]]"
  - "[[FlexiCache-MLSys26]]"
  - "[[DiffKV-SOSP25]]"
  - "[[CacheGen-SIGCOMM24]]"
  - "[[CacheBlend-EuroSys25]]"
related_concepts:
  - "[[KV-Cache]]"
  - "[[PagedAttention]]"
related_systems:
  - "[[vLLM]]"
novelty: high
feasibility: medium
effort: medium
---

# When KV Cache Heuristics Break: Rethinking Tiering for Thinking-Model Inference

> **一句话 idea**：所有现有 KV cache tiering/compression 工作（TTKV、FlexiCache、DiffKV、LMCache）都在 normal decode 上评测——但 **thinking model**（R1、QwQ、o1）的 Chain-of-Thought trace 是另一个世界：CoT 长度可达 input 的 10-50×，模型反复回看之前的推理步骤，attention pattern 是**语义驱动的跳跃式访问**而非时序局域。我们 hypothesize 并计划验证：**现有的 recency/stability/attention-score 三类 heuristic 在这个 workload 下全部翻车**。然后基于 measurement insight 设计 thinking-aware 的 KV cache 管理策略。

---

## 1. 为什么 thinking model 是现有 KV cache 研究的盲区

### 1.1 一个被忽略的 workload shift

过去两年所有重要的 KV cache 系统工作——从 [[vLLM-SOSP23|vLLM]] 的 PagedAttention 到 [[FlexiCache-MLSys26|FlexiCache]] 的 head stability 到 [[DiffKV-SOSP25|DiffKV]] 的四维压缩到 [[LMCache-arXiv25|LMCache]] 的多 tier 存储——都在同一类 workload 上评测：**normal chat / RAG / summarization**。这些场景的特征是 decode 长度不超过 input 的 2-3×，attention 主要集中在最近 token（sliding window locality），prefix 复用相对可预测。

但 2025-2026 年，serving 的重心正在从 normal chat 转向 **thinking model**（推理模型）：

- DeepSeek-R1、QwQ-32B、o1/o3 系列在 LLM serving 流量中的占比快速上升
- 这些模型在给出最终答案前会生成 **超长 Chain-of-Thought（CoT）trace**——10K-100K+ tokens 的「思考过程」
- CoT 的 KV cache 增长速度远超 normal decode：一个 1K prompt 可能触发 50K token 的 CoT，生成 **300-500× 于 prompt 的 KV page**

这是 LLM serving 历史上第一次出现 **decode KV cache >> prefill KV cache** 的情况。所有现有工作假定 prefill KV 占大头——这个假定对 thinking model 完全不成立。

### 1.2 为什么 CoT 的访问模式是质变，不是量变

不只在于「序列更长」。CoT trace 有本质不同的 attention 访问模式：

| | Normal decode | Thinking model CoT |
|---|---|---|
| 访问局部性 | 强 temporal locality（sliding window + attention sink） | 弱——模型随时跳回 20K+ token 前的推理步骤 |
| 重要 token 的定义 | attention score 高（当前 query 偏好） | **语义 milestone**（中间结论、逻辑转折、假设-验证点） |
| Reuse 规律 | 可预测的衰减 | 跳跃式、bursty——那些「milestone」token 的 KV 被反复回看几十次 |
| Attention head 行为 | stable head 的 top-K 跨 step 稳定（FlexiCache） | **故意不稳定**——thinking 过程是 controlled exploration，head pattern 随推理阶段切换 |
| KV 增长速度 | 线性（每 step 一个 token） | 仍然线性，但总长度大一个量级 → 总 KV 体积爆炸 |

### 1.3 已有的唯一数据点：DiffKV 的 thinking model 评测

[[DiffKV-SOSP25|DiffKV]] 是为数不多在 thinking model 上评测的 KV 压缩工作——它报告了对 QwQ-32B、R1-Distill-Qwen-14B 等模型的压缩效果。但 DiffKV 的评测聚焦 **compression ratio vs accuracy**，完全没有分析 **thinking model 的 KV page access pattern 是什么样的**。它只是把压缩算法套到了新 workload 上，没问「这个 workload 是否让某些假设不再成立」。

**目前没有任何工作对 thinking model 做过 KV page reuse 的 measurement。** 这是一个巨大的空白——因为如果 access pattern 完全不同，那 tiering policy 的出发点就得推倒重来。

---

## 2. 核心假设：三个 heuristic 在 CoT 下全部翻车

我们提出三个可证伪的假设。它们分别攻击三类主流的 tiering heuristic——recency、stability、attention score——并预测在 thinking model 场景下这些 heuristic 系统性地失败。

### H1: Temporal recency 的 recall 崩塌到接近随机

**攻击对象**：TTKV (arXiv 2604.19769) 的 temporal recency heuristic——「最近访问的 KV page 就是最可能被再次访问的」。

**直觉**：Normal decode 中 attention 有强 sliding window locality，recency 是自然的好 heuristic。但 CoT trace 中模型反复回看远处——当它在 step 30K 时需要验证一个在 step 5K 做的假设，recency 完全抓不到。

**可证伪预测**：在 CoT trace 上，temporal recency 的 5-step-ahead page reuse recall 应该显著低于 normal decode（预期：normal decode >80%，CoT <30%）。在 decode length > 10K 的区间，recency recall 应趋近 random selection。

### H2: Unstable attention head 是 tiering 错误的重灾区——但它们是 thinking 的关键

**攻击对象**：[[FlexiCache-MLSys26|FlexiCache]] 的 head stability heuristic——「stable head 的 KV 可以 offload，unstable head 全驻 GPU」。

**直觉**：FlexiCache 在 normal decode 上发现 bottom 25% unstable head 跨任务高度重合（overlap 0.83），因此可以 offline profiling 一次。但 thinking 过程中，attention head 的「不稳定」可能是 **功能性的**——不同推理阶段（理解问题 → 探索假设 → 验证 → 输出结论）会激活不同的 head pattern。如果 evict 了一个在当前阶段看起来不重要但在验证阶段会反复回看的 page，伤害远超 normal decode。

**可证伪预测**：FlexiCache-style stability profiling 在 CoT trace 上的 RCO 应显著低于 normal decode。unstable head 中被 temporal recency 错误 evict（但 5 步内被重新访问）的比例应 > stable head 的 3× 以上。更重要的是——这些被错误 evict 的 page 在 downstream accuracy 上的影响应该比 normal decode 大得多（因为 thinking 中的错误会级联）。

### H3: Attention score 是红鲱鱼——CoT 里重要的不是「当前最关注的」而是「逻辑链上的里程碑」

**攻击对象**：[[DiffKV-SOSP25|DiffKV]] 的 attention score heuristic——「高 attention score 的 token 值得更多存储资源」。

**直觉**：DiffKV 按 attention score 给 token 分配精度预算。这在 normal QA 中合理——当前 query 关注的就是重要的。但在 CoT 中，「当前 step 最关注的 token」往往是思考链条上最新加入的片段，但「未来 step 会反复回看的 token」是那些构成推理骨架的 **语义 milestone**——关键假设、中间结论、推导分叉点。两者不是一回事。

**可证伪预测**：用 DiffKV top-20% attention score 作为「应驻留 HBM」的标记，在 CoT trace 上的 10-step-ahead reuse recall 应不优于 random selection +10% 以内。而如果手动标注 CoT 中的「语义 milestone」token（如 AIME 数学题的各步推导结论），这些 token 的 KV page reuse count 应远高于 attention-score top-20% 的子集。

### 为什么这三个假设组成一个有力的 narrative

它们不是孤立的——H1 说「时序信号没用」、H2 说「跨 head 稳定性没用」、H3 说「重要性信号没用」。如果 ≥2 个被验证，结论是清晰的：**thinking model 的 KV cache 管理需要全新的设计原则，不能靠修修补补 normal-decode 那套 heuristic**。

如果 0 个被验证——那说明现有 heuristic 的泛化能力比我们想的强，这本身也是一个有价值的 measurement finding，但 novelty ceiling 低很多。

---

## 3. 研究问题

### RQ1: Thinking-Model KV Page Access Characterization

**目标**：证伪 H1-H3。

**实验设计**：

- 模型：Qwen2.5-7B-Instruct、Llama-3.1-8B-Instruct + R1-Distill 变体（thinking model）；对照组用非 thinking 版本（normal decode）
- Trace：AIME 2024（数学推理）、GPQA（科学推理）、BIG-Bench Hard reasoning 子集——这些会触发真实的 multi-step reasoning
- 用 [[vLLM-SOSP23|vLLM]] 做 inference，instrument block table access path 记录每个 KV page 的访问时间戳、所在 (layer, head)、decoding step
- 对每次访问记录对应的 token 的 attention score（来自正常 decode kernel 的计算）

**H1 测试**：对每个 trace，按 decode step 分段（$[0, 1K), [1K, 5K), [5K, 20K), [20K+]$），每段内计算 temporal recency 的 recall@k。Cross-validate 跨模型。

**H2 测试**：用 FlexiCache 的方法 compute per-head RCO over CoT trace。对比同一模型在 normal trace 上的 RCO。对 unstable head 的 page 计算 false eviction rate。

**H3 测试**：对 CoT trace 中 attention score top-20% token 的 KV page，计算其平均 reuse count（5-step window 内被访问次数）。与 random sampled page 做 t-test。额外：在 AIME trace 上手工标注一组「milestone token」（各步推导的关键表达式），单独分析它们的 reuse pattern。

**产出**：
- CoT trace 的 KV page reuse distance distribution（vs normal decode 的对照）
- 三个假设的证伪结论 + significance
- CoT KV access 的 taxonomy：milestone-driven vs recency-driven 的页面分布
- 对 tiering policy 设计的 direct implication

**Go/no-go**：≥1 假设被强验证（p < 0.01 + effect size 大）→ OSDI track。0 假设 → 写 measurement short paper 或并入 MLSys scope。

### RQ2: Thinking-Aware Tiering Policy

**目标**：基于 RQ1 的 insight 设计适合 thinking model 的 KV cache 管理策略。

**设计原则**（取决于 RQ1 结果，以下为假设 RQ1 验证 ≥1 个假设成立后的设计方向）：

1. **不使用 recency**：如果 H1 被验证，temporal recency 不作为 tiering signal。转而使用 **semantic milestone detection**——学习识别 CoT trace 中高 reuse 概率的 token 位置（如：包含特定 pattern 的 token、attention score 虽然当前不高但处于关键层中段的 token）
2. **Per-phase tiering**：如果 H2 被验证（stability 信号在 CoT 中不可靠），改为 **per-phase profiling**——将 CoT trace 按隐式语义阶段分割（exploration → verification → conclusion），在每个 phase 内独立计算 head activity pattern
3. **不对称压缩**：如果 H3 被验证（attention score 不是好的重要性信号），那迁移到冷 tier 时不应该 uniform 降精度——应该优先保留那些被 H3 标记为「milestone-like」的 page（即使它们的 attention score 不高）

**具体策略**（具体选择取决于 RQ1 实际结果）：
- 用 lightweight feature（token position、layer depth、head index、attention entropy、logit diff of predicted next token）训练一个简单的 binary classifier 预测「这个 page 在 10 步内会被再次访问吗？」
- 对比这个 prediction-based policy vs recency vs stability vs random vs oracle
- 关键 metric：throughput @ fixed accuracy（thinking model 对 accuracy 极其敏感——CoT 中的错误会级联放大）

**方法**：
- Python event simulator 回放 RQ1 的 CoT trace
- 仿真多 tier（HBM / DRAM / remote SSD）配置下的 hit rate 和 fetch latency
- 最终在 vLLM + LMCache 上实现最有潜力的 policy 做端到端验证

### RQ3: Milestone-Driven Prefetch for Remote Tiers

**目标**：利用 RQ1 发现的 milestone reuse pattern 做 remote KV page 的 prefetch。

如果 H3 被验证——attention score 不是好的importance signal，但存在可识别的 milestone token——那我们可以做 **milestone-triggered prefetch**：一旦 detect 到当前 step 正在访问某个 milestone token 的 KV，提前从远程 tier 预取与该 milestone 语义相关的其他 page（如：同一 reasoning step 的所有 token、或同一层的邻近 head）。

**对比 baseline**：recency-based prefetch（TTKV-style）、no prefetch、oracle prefetch。

**方法**：在 fabric-lib 上用 IMMCOUNTER 做 async fetch completion，测量 prefetch accuracy 和 decode stall reduction。

### RQ4: Correctness Under Tiered CoT

**问题**：thinking model 的 CoT 是敏感链路——一个 KV page 的 bit error 可能导致后续推理全部走偏。跨 tier 迁移引入的延迟和潜在 corruption 需要更强的 correctness guarantee。

**方向**：
- per-page CRC-32C checksum on RDMA transfer（连接 SOSP-2025 silent failure 主线）
- 如果 page migration 延迟超出某个阈值（导致 decode stall），fallback 到 recompute（重跑该 page 对应 token 的 attention）——保证 determinism
- versioned page table for multi-replica scenarios

---

## 4. 可行性

### 4.1 为什么这个方向适合个人/小团队

- **不需要训模型**：直接拿开源 thinking model（R1-Distill-Qwen-7B/14B、QwQ-32B）和 normal model（Llama-3.1-8B/70B）跑推理 trace
- **核心工作 = measurement**：最大的 contribution 来自 RQ1 的测量发现
- **工程量可控**：vLLM instrumentation ~400 LoC，simulator ~800 LoC，policy plugin ~1200 LoC——总计 ~3.5K LoC
- **站在巨人肩膀上**：LMCache 做 storage backend、fabric-lib 做传输、vLLM 做推理——我们只做 policy 层

### 4.2 时间线（~15 周）

| Phase | 内容 | 时间 | Go/No-Go |
|-------|------|------|----------|
| M1: CoT Trace Collection + Hypothesis Testing | 3 models × 3 reasoning benchmarks, 收集 KV page access trace, 证伪 H1-H3 | 3 周 | ≥1 假设验证 → OSDI track |
| M2: Policy Design + Simulator | 基于 M1 insight 设计 thinking-aware policy, 仿真器对比 ≥5 种策略 | 3 周 | Prediction vs best heuristic ≥15% hit rate gain |
| M3: Milestone Prefetch (RDMA) | fabric-lib microbench + milestone-triggered prefetch 可行性 | 2 周 | Prefetch accuracy > 50% vs random |
| M4: vLLM + LMCache Integration | 实现 top policy + prefetch in vLLM plugin | 3 周 | Output exact-match verified |
| M5: End-to-End Eval | Thinking model benchmark (AIME, GPQA, BBH) vs baselines | 2 周 | Throughput ≥1.5× @ same accuracy |
| M6: Writing | Paper | 2 周 | — |

### 4.3 关键风险

| 风险 | 缓解 |
|------|------|
| 三个假设全被推翻 | 写成 measurement paper ——「出乎意料地，existing heuristics 在 CoT 上仍然 work」——也有 insight 但没有 OSDI-level novelty。target MLSys |
| Thinking model 在 vLLM 上 OOM（CoT 太长，单 GPU 不够） | 用 tensor parallelism（2 GPU / model）或 Qwen2.5-1.5B 等小模型做 proof-of-concept，大模型 trace 在 A100 80GB 上跑 |
| CoT trace 不公开（thinking model 的 production trace 难以获取） | 用 AIME/GPQA 等标准 benchmark 自己跑 CoT trace——虽然不是 production，但是 well-defined 且社区认可 |
| R1-Distill 变体 vs original model 的 access pattern 差异 | 设对照组：同一 backbone（如 Qwen2.5-7B）的 thinking 版 vs non-thinking 版——确保差异来自 reasoning 过程而非模型 architecture |

---

## 5. 为什么这是 OSDI-level 的 idea

### 5.1 它有一个 counterintuitive finding 作为脊梁

OSDI/SOSP 不接受「我们做了更好的 policy」——它要的是 **surprising insight that changes how people think about the problem**。这篇工作的核心赌注是：**thinking model 的 KV cache access pattern 与 normal decode 有本质不同，而社区完全没有意识到——还在用 normal decode 上调试出来的 heuristic 去套 thinking workload**。

如果 H1-H3 中 ≥1 个被强验证，paper 的 narrative arc 是：

> "The community has built sophisticated KV cache tiering systems (TTKV, FlexiCache, DiffKV, LMCache) assuming recency, stability, and attention-score heuristics. But on thinking models — the fastest-growing serving workload — these heuristics systematically fail. Here's why, and here's what to do instead."

这和 [[Jenga-SOSP25|Jenga]] 的 arc 类似：Jenga 发现 PagedAttention 在异构 attention 下浪费 79.6% 内存（counterintuitive finding），然后设计 LCM slab allocator（fix）。

### 5.2 Timing 完美

- Thinking model 是 2025-2026 最大的 LLM inference trend，但在 **system venue（OSDI/SOSP/MLSys）** 上还没有任何工作专门研究过 thinking model 的 KV cache 管理
- DiffKV 是唯一在 thinking model 上评测的，但它只做 compression，不做 measurement
- 到 OSDI 2027 截稿（~2026 年底），这个空白大概率已经被填——**现在动手正好**

### 5.3 Problem-forward

不是「我们有个很酷的 idea 叫 prediction-driven tiering」，而是「这里有个真实的 problem——thinking model 的 KV cache 爆炸，且没人知道怎么在 thinking workload 上做 tiering——我们来测量、理解和解决它」。

---

## 6. 论文 story

**Title**: *Thinking Aloud, Caching Differently: Why KV Cache Heuristics Fail on Reasoning Models — and What to Do About It*

1. **Motivation (0.5p)**：Thinking model 的 CoT trace 是 KV cache 管理的全新挑战——decode KV >> prefill KV，且访问模式是 semantic milestone-driven 而非 recency-driven
2. **Measurement of the Gap (2p)**：三个假设的证伪实验——H1: recency 崩了，H2: stability 不适用，H3: attention score 是红鲱鱼。数据 + significance + 可视化
3. **Why It Matters (0.5p)**：不正确的 tiering 不只是性能问题——CoT 中错误 evict 一个 milestone page 会导致 downstream 推理全部走偏。这是 correctness 问题
4. **Design (1.5p)**：基于 measurement insight 的 thinking-aware tiering + milestone-triggered prefetch
5. **Evaluation (1p)**：AIME / GPQA / BBH reasoning benchmark 上的 throughput-latency-accuracy tradeoff vs vLLM / TTKV / FlexiCache
6. **Implication (0.5p)**：这个思路不只适用于 KV cache——thinking model 的 bursty、semantic-driven access pattern 可能对 MoE routing、PD disaggregation 调度、甚至 hardware memory hierarchy design 都有影响

---

*本提案从原始方向（general KV cache tiering policy）pivot 到 thinking-model-specific KV cache management，因为后者 (a) 问题更尖锐——existing heuristics 有清晰的 failure mode，(b) 时机更好——尚未被社区覆盖，(c) 贡献更干净——measurement reveals counterintuitive finding → design fixes it。*
