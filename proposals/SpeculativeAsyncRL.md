---
type: proposal
name: SpeculativeAsyncRL
title: 给 async RL 加一层 fix-ante staleness 契约——投机梯度 + KL-bounded reconciliation 的可证明上界
status: draft
category: ml-algorithm
verdict: pending
created: 2026-04-27
last_updated: 2026-04-27
tags: [rl, rlhf, async-training, speculative, staleness-bound, llm]
related_papers: ["[[Belfast-OSDI25]]", "[[HetRL-MLSys26]]", "[[DAS-MLSys26]]", "[[TransferEngine-MLSys26]]"]
related_concepts: ["[[Speculative-Decoding]]"]
related_systems: []
novelty: low
feasibility: medium
effort: medium
---

# 给 async RL 加一层 fix-ante staleness 契约——投机梯度 + KL-bounded reconciliation 的可证明上界

> **TL;DR**:async RL post-training 红海里现有工作(AReaL / ROLL Flash / StreamRL / TBA)对 staleness 都是**经验处理**——实测 K-step off-policy 还能收敛就用,没有"最坏情况下保证什么"的契约语义。借鉴 [[Belfast-OSDI25|SpecLog]] 的 fix-ante ordering,本提案给异步 RL 训练加一层显式契约:**预先承诺版本窗口 K + 投机梯度在 shadow 参数累积 + 单步 KL 越 ε 阈值就 rollback**,产出**第一个对 async RL 给出 closed-form 单步 staleness 上界的 framework**。一级卖点是理论保证,二级卖点是任何不退化的速度收益。投稿主目标是 NeurIPS / ICML(算法 + 理论),M3 末若速度也有可观增量(对标 ROLL Flash / TBA 不退化)再考虑系统会议二投。

## Idea

### 问题动机

RL post-training 已是 LLM 推理与对齐的核心手段,wall-clock 性能瓶颈集中在 rollout 与训练之间的同步。近 18 个月一批工作把这条 critical path 往**异步 + off-policy** 方向推:

- [Asynchronous RLHF (Noukhovitch et al., Oct 2024)](https://arxiv.org/abs/2410.18252) — Llama 3.1 8B 比同步快 ~40%、Rho 1B 在 GSM8k 上快 ~70%,主要靠"用旧权重 rollout、用新权重训练"的 off-policy 容忍;
- [TBA (Bartoldson et al., Mar 2025; v2 Dec 2025)](https://arxiv.org/abs/2503.18929) — 解耦 exploration / learning,4× 或更多 speedup 同时保精度,容忍很大 asynchrony;
- [ROLL Flash (Lu et al., Oct 2025)](https://arxiv.org/abs/2510.11345) — 工业 framework,RLVR 2.24× / agentic 2.72×;
- [StreamRL (Zhong et al., Apr 2025)](https://arxiv.org/abs/2504.15930) / [AsyncFlow (Han et al., Jul 2025)](https://arxiv.org/abs/2507.01663) / [AReaL (Fu et al., May 2025)](https://arxiv.org/abs/2505.24298) — pipeline / streaming / disaggregation 路线;
- [Stabilizing RL (Zheng et al., Dec 2025)](https://arxiv.org/abs/2512.01374) — 给 staleness 提供**理论形式化**:token-level 优化 sequence-level reward 的条件,off-policy 时 IS clipping + Routing Replay 是有效手段。

**这条线缺一块**:虽然实测各家都能收敛,但 staleness 处理是**事后**的——经验上 K-step off-policy 还能跑就用。**没有人在 step 开始前就承诺一个版本预算并给出"被 commit 的 step T 与 fully-sync ideal 的距离上界"**。Stabilizing RL 给了形式化但侧重 IS / clipping 的事后修正,不是 fix-ante。

[[Belfast-OSDI25|Belfast / SpecLog]](OSDI 2025) 在 shared log 域提供了一种相邻范式:**预先承诺全局位置 + 速度推进 + 极少数 misspeculation 时回滚**——精确性来自"事先约定"而非"事后协调"。能不能把这个思路套进 async RL,把"用了多大 staleness"也变成事先承诺?

### 三件事

1. **Fix-ante 版本预算**。trainer 在 step T 开始前广播一个 contract:"step T 接受的 rollout 必须由版本号 ∈ [V−K, V] 的权重生成,K 由 KL 漂移率在线估计"。Rollout worker 收到 contract 后自查持有的权重版本是否在窗口内,不在就先 sync 再生成。**预算预先承诺,非事后审计**——这是 fix-ante 的核心。

2. **投机梯度应用**。rollout worker 的样本陆续到达 trainer,**不必凑齐 batch**。每个样本到达就立即在一个 shadow 参数副本上跑 forward + backward,把梯度累加到 shadow。trainer 不等 batch 完整,而是按节拍(每 N ms 或每 M 样本)对 shadow 做一次 try-commit,检查 shadow 与契约 policy 的距离 KL(shadow ‖ π_T) ≤ ε。检查通过则 commit shadow → policy,否则 rollback shadow,继续累。**shadow 始终指参数副本,投机始终指 commit 时机**——两个概念不混用。

3. **KL-bounded reconciliation**。reconciliation 的正确性 token 是**单步 KL**:Belfast 用"actual cut == predicted cut",本提案用"shadow 与契约 policy 在 ε 球内"。每个 rollout 携带其源权重版本号,版本超出 contract 窗口直接丢弃(算 misspeculation)。系统的"正确性"等价于:任意被 commit 的 step T 的权重 π_T 满足

   ‖π_T − π_T^{ideal}‖_KL ≤ δ(K, ε)

   其中 δ 是 K 与 ε 的 closed-form,与 reward / advantage 估计的有界性挂钩。**这个 bound 是本提案的 first-order contribution**。

### 一级卖点:可证明 staleness 上界

| 工作 | staleness 处理 | 形式化层级 | 是否 fix-ante |
|---|---|---|---|
| Asynchronous RLHF | 经验 off-policy + DPO 鲁棒性观察 | 实证 | 否 |
| AReaL | workload balancing + staleness-enhanced PPO | 算法变体 | 否 |
| ROLL Flash / StreamRL / AsyncFlow | pipeline / streaming 优化 | 系统 | 否 |
| TBA | trajectory balance loss(off-policy 友好) | 算法 | 否 |
| Stabilizing RL | IS clipping + Routing Replay,事后稳定化 | 理论 + 实证 | **否(事后)** |
| **本提案** | fix-ante K-window contract + KL-bounded rollback | **理论 closed-form** | **是** |

唯一一行 fix-ante。这是从"经验性 off-policy"到"契约性 off-policy"的范式偏移。

### 二级卖点(若有):速度

速度不是主卖点,因为 ROLL Flash / TBA / StreamRL 已经 2-4× 同步基线,**继续在速度赛道与之竞争胜算低**。本提案对速度的诚实预期:

- **绝对目标 aspirational**:在与 ROLL Flash / TBA 相同硬件 + 模型规模下,wall-clock **不退化**(可 ±10%);若 K 调到激进档,**有可能**比同步 baseline 多挤 10-30%;
- **决定性数字**:"再快多少"由 M2 末的 preliminary measurement 决定,proposal 不预先承诺具体数字。

> 注:撤回早先草稿"比 Asynchronous RLHF 再快 ≥ 25%"的具体目标。理由:无 preliminary 支撑;且 Asynchronous RLHF 已被多篇晚出工作 superseded,作为对标过弱。

### 与正交工作叠加(复利)

- **Rollout 内 speculation**:[[DAS-MLSys26|DAS]](per-problem suffix tree)/ [SPEC-RL (Liu et al., Sep 2025)](https://arxiv.org/abs/2509.23232) / [RhymeRL (He et al., Aug 2025)](https://arxiv.org/abs/2508.18588) — 解决 rollout 内生成,与本提案的 rollout-train 同步层正交;
- **快速权重同步**:[[TransferEngine-MLSys26|TransferEngine]] 万亿参数 1.3 s — 7B-14B 规模下权重 sync 应 << 1 s,不构成本提案 contract 频繁切换的瓶颈;
- **异构调度**:[[HetRL-MLSys26|HetRL]] 在异构 GPU 上 3.17× 平均加速,与本提案在调度层正交。

## 相关工作(仓库内)

### Speculative-then-reconcile 思路源头

- [[Belfast-OSDI25|Belfast / SpecLog]] — **直接灵感来源**:fix-ante ordering + speculative delivery + 极少数 misspeculation 时回滚。本提案是把同思路从 shared log 搬到 async RL training。差异:Belfast 的 misspeculation 极少(几乎所有 cut 都准),本提案的 misspeculation(KL 越 ε)率会显著更高,δ(K, ε) bound 必须把 misspeculation 频率内化到证明中

### RL 训练与 rollout 加速

- [[HetRL-MLSys26]] — 异构 GPU 集群上的 partition / assignment 搜索,3.17× 平均吞吐。与本提案正交,可叠加
- [[DAS-MLSys26]] — RL rollout 阶段的 distribution-aware speculative decoding,per-problem suffix tree drafter,rollout 时间降 50%。与本提案正交(rollout 内 vs rollout-train 间)

### 通信底座

- [[TransferEngine-MLSys26]] — 万亿参数 1.3 s 权重同步。本提案的 contract 频繁切换需要快速 P2P weight sync;7B-14B 规模下权重远小于万亿,sync 时间充裕

## 相关工作(外部)

近 18 个月 async RL / speculative rollout 是顶级红海:

- Noukhovitch et al. (Oct 2024 → ICLR 2025) [Asynchronous RLHF: Faster and More Efficient Off-Policy RL for Language Models](https://arxiv.org/abs/2410.18252) — 早期但已被多篇晚出工作 superseded 的弱 baseline;Llama 3.1 8B ~40% / Rho 1B GSM8k ~70%;**经验性 staleness,无 fix-ante 契约**
- Bartoldson et al. (Mar 2025, v2 Dec 2025) [Trajectory Balance with Asynchrony (TBA)](https://arxiv.org/abs/2503.18929) — **重要 prior**:解耦 exploration / learning,**4× 或更多 speedup 同时保精度**。trajectory balance 损失(off-policy 友好)。本提案与 TBA framing 区分:TBA 是损失函数级 off-policy 容忍,本提案是 step 级 fix-ante 契约;两者可正交叠加
- Zhong et al. (Apr 2025) [StreamRL: Scalable, Heterogeneous, and Elastic RL for LLMs](https://arxiv.org/abs/2504.15930) — disaggregated stream generation + output-length ranker,2.66× 吞吐。聚焦 pipeline bubble,不动 staleness
- Fu et al. (May 2025) [AReaL: Large-Scale Asynchronous RL System for Language Reasoning](https://arxiv.org/abs/2505.24298) — workload balancing 控 staleness + staleness-enhanced PPO 变体。经验 / 启发式 staleness,无 fix-ante 契约
- Han et al. (Jul 2025) [AsyncFlow: An Asynchronous Streaming RL Framework](https://arxiv.org/abs/2507.01663) — TransferQueue 中央数据管理,1.59× 平均吞吐。架构层面优化,不触及 staleness 语义
- Wang et al. (Aug 2025) [SeamlessFlow: Trainer–Agent Isolation for Bubble-Free Pipelines](https://arxiv.org/abs/2508.11553) — tag scheduling 消 bubble。pipeline 优化,不动 staleness
- He et al. (Aug 2025) [RhymeRL: HistoSpec + HistoPipe](https://arxiv.org/abs/2508.18588) — 历史 rollout token sequence 相似性做 draft + 调度,2.6× 提升。rollout 内 speculation,与本提案正交
- Zhou et al. (Sep 2025) [APRIL: Active Partial Rollouts in RL](https://arxiv.org/abs/2509.18521) — long-tail 主动停止 rollout,平均 22.5%(最高 44%)吞吐 + 平均 2.1pt 精度提升。与本提案正交
- Gao et al. (Sep 2025) [RollPacker: Mitigating Long-Tail Rollouts](https://arxiv.org/abs/2509.21009) — tail batching + elastic parallelism,2.03–2.56× 端到端时间 reduction(对 veRL)。同步 RL 路线,与本提案正交
- Liu et al. (Sep 2025) [SPEC-RL: Accelerating On-Policy RL with Speculative Rollouts](https://arxiv.org/abs/2509.23232) — **同名 / 思路相邻**。把 prior trajectory segment 当 speculative prefix,draft-and-verify 验证,2-3× rollout 加速。**对 rollout 内做 speculation,本提案对 rollout-train 同步做 speculation——不同层级**
- Lu et al. (Oct 2025) [ROLL Flash: Accelerating RLVR and Agentic Training with Asynchrony](https://arxiv.org/abs/2510.11345) — 工业 framework,RLVR 2.24× / agentic 2.72×。staleness 经验化(同 AReaL 类)
- Qin et al. (Nov 2025) [Seer: Online Context Learning for Fast Synchronous LLM RL](https://arxiv.org/abs/2511.14617) — 同步 RL 优化路线,2.04× rollout 提升
- Zheng et al. (Dec 2025) [Stabilizing RL with LLMs: Formulation and Practices](https://arxiv.org/abs/2512.01374) — **最关键的近邻 prior**:对 staleness 给出**理论形式化**(token-level / sequence-level 关系),off-policy 需 IS clipping + Routing Replay。30B MoE 验证。本提案与之区分:Stabilizing RL 是**事后稳定化**(IS / clipping 修正已发生的 off-policyness),本提案是**事前承诺**(K-window contract + 越界 drop);两者互补——本提案的 fix-ante bound 可给 Stabilizing RL 的 IS 提供 sharper window
- Ye et al. (Apr 2026) [TensorHub: Scalable and Elastic Weight Transfer for LLM RL Training](https://arxiv.org/abs/2604.09107) — Reference-Oriented Storage,跨数据中心 19× GPU stall 改善。本提案的 contract 切换可 consume

## Novelty 评估

- **新颖点**:
  - **Fix-ante 契约 + closed-form δ(K, ε)**:据上表,本提案是当前唯一一行"事前承诺 + 可证明上界"。Stabilizing RL 已有理论形式化但属事后稳定化;TBA 已 4× 加速但属损失函数级 off-policy 容忍。**delta 在"step 级 fix-ante + 单步 closed-form bound"**
  - **正交叠加性**:对 [[DAS-MLSys26]] / [SPEC-RL](https://arxiv.org/abs/2509.23232) / [[HetRL-MLSys26]] / [[TransferEngine-MLSys26]] 都正交,可叠加获得复利
- **不新颖处**:
  - "Async RL 是好东西"已被 Asynchronous RLHF / TBA / ROLL Flash 充分证明
  - "Speculative rollout"已被 [SPEC-RL](https://arxiv.org/abs/2509.23232) / [[DAS-MLSys26]] / [RhymeRL](https://arxiv.org/abs/2508.18588) 占领
  - "快速权重同步"已被 [[TransferEngine-MLSys26|TransferEngine]] / [TensorHub](https://arxiv.org/abs/2604.09107) 解决
  - "off-policy 收敛性"在 RL 理论侧有大量先例(IS、PPO clip、GAE、TBA、Stabilizing RL)
- **总体判断**:**low**(诚实)。Async RL post-training 是 2025-2026 最拥挤的赛道之一,18 个月里 12+ 篇 arXiv,4 个工业级 framework。本提案的 delta 集中在"fix-ante + closed-form bound 的算法 + 理论侧",**唯一窄缝**是 prior work 都没在 step 开始前承诺版本预算并证明 closed-form bound。
  - **若 Stabilizing RL 的后续工作已在做 fix-ante**(可能性中等)→ delta 进一步收窄甚至消失
  - **若 closed-form bound 在标准 GRPO 假设下证不下来或太松**(常见风险)→ 退化为"实证 staleness 控制器",novelty flipped 到 negative
- **Venue 选择**:
  - **主投 NeurIPS / ICML**(算法 + 理论侧):卖理论保证 + 实证收敛
  - **二投 EuroSys / ATC**(系统侧):仅当 M3 末速度增量也可观时
  - **不投 OSDI / SOSP / MLSys**:速度叙事过于拥挤,本提案的"再快多少"不预设具体数字

## 可行性评估

- **核心组件**:
  - **Closed-form δ(K, ε) 推导(~4-6 周)**:在 GRPO 标准假设下(reward bounded、advantage 有界、policy 平滑)证明 KL(π_T ‖ π_T^{ideal}) ≤ f(K, ε, advantage_bound, lipschitz)。可能要参考 Stabilizing RL 的 token-level 形式化思路;若纸面证不下来,fall back 到 TLA+ + Coq 形式化
  - **Contract 广播协议(~1 周)**:trainer 周期发布版本窗口 + ε 阈值 + batch ID
  - **Rollout worker 自查 + drop(~1 周)**:接收 contract 后版本不符自动 sync 或 drop
  - **Shadow 参数 + try-commit(~3 周)**:shadow 与主参数双副本,每 N 样本 try-commit + KL 检查 + rollback。考虑 LoRA 风格低秩 shadow 减 memory
  - **KL 监控与 K 自适应(~2 周)**:在线估计 KL 漂移率,自动调 K 与 ε
  - **集成 [[TransferEngine-MLSys26|TransferEngine]] 或 NIXL(~1 周)**:快速 weight sync + IMMCOUNTER 完成通知
  - **Eval pipeline(~2 周)**:wall-clock 测量 + 收敛曲线 + benchmark
- **可复用代码**:
  - [verl](https://github.com/volcengine/verl) 或 [OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) 作为 host
  - [Asynchronous RLHF 开源](https://github.com/mnoukhov/async_rlhf) 作为弱 baseline,**重点对标 ROLL Flash / TBA**(若开源)而非 Asynchronous RLHF
  - [SPEC-RL](https://arxiv.org/abs/2509.23232) / [[DAS-MLSys26|DAS]] 代码叠加 rollout 内加速
  - [[TransferEngine-MLSys26|TransferEngine]] 或 NIXL 作为通信层
  - 数据集:GSM8K、MATH-500、HumanEval(若做 code RLVR,需要 unit test verifier)、UltraFeedback(若做 RLHF)
- **数据 / 算力**:
  - **硬件**:1 × 8 H100 跑 Qwen3-7B colocated GRPO;2 × 8 H100 disaggregated rollout-train;3 × 8 H100 完整 ablation
  - **模型**:Qwen3-7B-Base、Qwen3-14B-Base、可选 Llama-3.1-8B
  - **数据**:GSM8K (RLVR)、MATH-500、可选 HumanEval (code RLVR)
- **关键风险**:
  - **R1: closed-form bound 证不下来或太松**(M1 验证)— 若纸面 closed-form 在 GRPO 标准假设下做不出严格 bound,或得到的 bound 太宽以致实测 KL 永远在 bound 内 100%(没区分力),idea 主卖点崩塌。**Mitigation**:M1 末若 bound 失败,pivot 到"实证 staleness 控制器 + 严格 ablation",novelty 降级为 minor delta,evidence 加强;早期决策点
  - **R2: 投机梯度 rollback 频繁反噬**(M2 验证)— 若 KL 越界率 > 30%,shadow 重算成本抵消速度收益。**Mitigation**:LoRA 低秩 shadow + 自适应 ε(把 ε 也作为元控制器学)
  - **R3: 与 TBA / Stabilizing RL 实证对比掉点**(M3) — 若本提案在收敛精度上 < TBA,即便理论好看也难发。**Mitigation**:M3 必须报告 GSM8K + MATH-500 完整收敛曲线对比 TBA 与 Stabilizing RL,精度差距必须 ≤ 1pt
  - **R4: novelty 进一步被 scoop**(持续监控) — Stabilizing RL 后续 / TBA 后续可能在做 fix-ante。**Mitigation**:每月一次 arXiv search,M2 末重做 prior-work survey
  - **R5: 同步 vs 异步只是简化叙事**(framing) — prior work 实际是连续谱(同步、轻度 off-policy、激进 off-policy、loss-level off-policy 容忍)。**Mitigation**:proposal / 投稿稿严格使用"事前 vs 事后"区分,而非"同步 vs 异步"
- **总体判断**:**medium**(由 high 下调)。R1 是真实风险——closed-form bound 在 RL 标准假设下能否给出 sharp 形式无先例可借,若失败则主卖点崩塌。所有工程组件本身高可行(verl / OpenRLHF / TransferEngine 都 mature),但**理论组件成败决定整体可行性**。3-5 人 8-14 周,其中 4-6 周是理论。

## 实现规划

### M1 — 理论 + Baseline 复现(~4 周)

- 在 verl + Qwen3-7B 上跑通 GRPO 同步 baseline
- 复现 [Asynchronous RLHF](https://arxiv.org/abs/2410.18252)(弱 baseline)与开源版 TBA / ROLL Flash(强 baseline,若开源)
- **理论组件**:在 GRPO 标准假设下推导 closed-form δ(K, ε) bound;对照 [Stabilizing RL](https://arxiv.org/abs/2512.01374) 的 token-level 形式化框架
- 集成 [[TransferEngine-MLSys26|TransferEngine]] 或 NIXL 做权重 sync,profile 同步开销
- 实现 contract 广播 + rollout worker drop
- **验证标准**:
  - 同步 GRPO 在 GSM8K 上收敛 ≥ 80% accuracy(参照公开数字)
  - 异步弱 baseline (Asynchronous RLHF) 比同步快 ≥ 30%
  - **closed-form δ(K, ε) bound 在纸面成立**;若失败则 R1 mitigation 启动
- **Go/no-go gate**:R1 触发 → 立即决策(pivot 实证路线 vs archive)。复现 baseline 失败 → 切换到 OpenRLHF。理论失败但工程成功 → 降级为系统会议路线(EuroSys / ATC)

### M2 — 投机梯度 + KL rollback 工程实现(~3 周)

- shadow 参数(全量 / LoRA 双方案对比)+ try-commit 机制
- KL 监控 + 触发 rollback;自适应 K / ε 控制器
- 与 contract 系统集成
- **首份 preliminary measurement**:wall-clock 与 commit/rollback ratio
- **验证标准**:
  - 在 GSM8K 上 commit / rollback ratio ≥ 5:1(rollback 不太频繁)
  - **实测单步 KL 落在 closed-form bound 内**(若 100% 在 bound 内但 bound 显然过松 → R1 风险升级)
  - wall-clock 不退化于同步 baseline ±10%
- **Go/no-go gate**:rollback 率 > 30% 或 KL 监测发散 → 调 ε 或 pivot 到 contract-only 简化版(无投机梯度,只有 K-window drop)

### M3 — 完整 eval + 收敛性 + 跨模型(~3 周)

- 模型扩 Qwen3-14B、Llama-3.1-8B
- benchmark:GSM8K + MATH-500 +(可选)HumanEval
- ablation:contract 有/无、shadow 全量/LoRA、不同 K 不同 ε、与 [SPEC-RL](https://arxiv.org/abs/2509.23232) / [[DAS-MLSys26]] 叠加测复利
- **强 baseline 直接对比**:TBA(若开源,否则用 trajectory balance 损失复刻)+ Stabilizing RL 风格 IS clipping
- **验证标准**:
  - 收敛精度差距 ≤ 1pt 对比 TBA / Stabilizing RL
  - closed-form δ 上界与实测 KL 吻合,**且 bound 紧到能区分 K=4 vs K=16**(否则证明 too loose)
  - wall-clock 无退化(±10% 对同步基线);若再快 ≥ 15% 视为 bonus
- **Go/no-go gate**:精度掉 ≥ 2pt 或 bound 过松无法分辨 K → archive 或转写"为什么 fix-ante 难搬到 ML training"的 negative-result paper

### M4 — 论文化(~2 周)

- 主稿:**算法 + 理论故事**,投 NeurIPS / ICML(deadline 决定先后),focus 在 closed-form bound + 实证不退化
- 二投备稿(条件):若 M3 末 wall-clock 也有 ≥ 15-25% 收益,改写系统层故事(EuroSys / ATC / ICLR systems track)

> **统一阈值约定**:全文统一 wall-clock 区间 — `[0, 不退化-10%)` = archive;`[不退化±10%, +15%)` = 算法会议主路;`[+15%, +25%)` = 算法 + 系统二投;`[+25%, ∞)` = 加速度 strong claim 重写。

## 开放问题

- **K 的 Pareto**:K=1(几乎同步)、K=10(中度 off-policy)、K=∞(完全异步)在 wall-clock vs 收敛精度的 Pareto 上是什么形状?是否有自适应 K 最优策略?(注:这与 Idea 节"δ(K, ε) 可证明"不矛盾——bound 给出 worst-case,Pareto 是 average-case 经验形状)
- **Bound 的紧度**:closed-form δ 在 GRPO 标准假设下能多紧?能否区分 K=4 与 K=16?若 bound 过松无区分力,理论卖点失效
- **shadow 参数 vs 主参数**:能否直接在主参数上 commit + rollback?LoRA shadow 是否足够?完整双副本 memory 翻倍可接受吗?
- **KL 之外的 reconciliation token**:reward 信号本身、advantage 估计、PPO clip 触发率,哪个对"misspeculation"更敏感?
- **与 Stabilizing RL 的协同**:本提案 fix-ante bound 能否给 Stabilizing RL 的 IS clipping 提供 sharper window?这是潜在合作方向而非竞争
- **是否值得做的元判断**:novelty 评估 low、R1 是 binary risk,且 sister proposal(`proposals/LiveSessionMigration.md`、`proposals/OnlineExpertMigration.md`)命中率更高。本提案适合作为低优先级备选,或与算法 + 理论侧研究者合作

## 参考

- 内部相关:[[Speculative-Decoding]]、[[Belfast-OSDI25]]、[[HetRL-MLSys26]]、[[DAS-MLSys26]]、[[TransferEngine-MLSys26]]、[[OSDI-2025]]、[[MLSys-2026]]
- 外部链接(已在「相关工作(外部)」展开):Asynchronous RLHF / TBA / StreamRL / AReaL / AsyncFlow / SeamlessFlow / RhymeRL / SPEC-RL / APRIL / RollPacker / ROLL Flash / Seer / Stabilizing RL / TensorHub
- 兄弟 proposal:`proposals/LiveSessionMigration.md`、`proposals/OnlineExpertMigration.md`
