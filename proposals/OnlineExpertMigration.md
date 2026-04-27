---
type: proposal
name: OnlineExpertMigration
title: 在线 MoE expert 迁移——continuous 与 per-iter 之间的精确 trade-off
status: draft
category: mlsys
verdict: pending
created: 2026-04-27
last_updated: 2026-04-27
tags: [moe, expert-parallelism, load-balancing, llm-serving, rdma, p2p]
related_papers: ["[[CRAFT-MLSys26]]", "[[Libra-arXiv26]]", "[[LatencyOptimal-MoELB-INET4AI25]]", "[[FluxMoE-arXiv26]]", "[[FarSkip-Collective-MLSys26]]", "[[MoEBlaze-MLSys26]]", "[[FP8FlowMoE-MLSys26]]", "[[EventTensor-MLSys26]]", "[[LayeredPrefill-MLSys26]]", "[[TransferEngine-MLSys26]]", "[[NEST-MLSys26]]", "[[DeepSeek-V4-arXiv26]]"]
related_concepts: ["[[MoE]]", "[[Expert-Parallelism]]", "[[Load-Balancing]]", "[[KV-Cache]]", "[[RDMA]]", "[[Disaggregation]]"]
related_systems: ["[[vLLM]]", "[[SGLang]]"]
novelty: medium
feasibility: high
effort: long
---

# 在线 MoE expert 迁移——continuous 与 per-iter 之间的精确 trade-off

> **TL;DR**:[[MoE]] expert 重分配的设计空间已分化成 periodic batch / per-iter on-critical-path([LLEP](https://arxiv.org/abs/2601.17111))/ per-pass non-blocking([[Libra-arXiv26|Libra]])几个粒度。本提案在该频谱上抢占未被占据的格点:**跨 iter 后台带宽摊销迁移 + 与 dispatch critical-path 解耦的 IMMCOUNTER routing-table hot-swap + decentralized gossip**。利用 [[TransferEngine-MLSys26|TransferEngine]] 的 IMMCOUNTER 在空闲 P2P 带宽窗口内推送 hot expert 到 under-loaded GPU,接收方完整收到才把该 expert 加入 routable set。目标:在 hotness drift 频率高的 trace 上 end-to-end MoE 延迟比 [LLEP](https://arxiv.org/abs/2601.17111) ≥ 10%、比 [[LatencyOptimal-MoELB-INET4AI25]] ≥ 15%,迁移期 TPOT P95 退化 < 3%,在 1-2 × 8 H100 上用 DeepSeek-V2-Lite-16B / Qwen3-30B-A3B / DeepSeek-V3 蒸馏版验证。需 6 周以上工程 + 形式化验证 + 多模型多 trace 对比。

## Idea

**问题动机**。[[MoE]] inference 的 expert load imbalance 已被多篇工作深耕,但迁移机制在 2025-2026 已经分化成几个粒度,每个粒度有自己的 sweet spot:

| 粒度 | 代表 | 何时迁 | 是否 critical-path | planner |
|---|---|---|---|---|
| **periodic batch** | EPLB / [[CRAFT-MLSys26\|CRAFT]] / [[LatencyOptimal-MoELB-INET4AI25]] / [SYMI](https://arxiv.org/abs/2504.19925)(训练) | 每 N(~500–1000) iter | swap 时 stop-the-world | centralized ILP / heuristic |
| **per-iter on-CP** | [LLEP](https://arxiv.org/abs/2601.17111)(2026-01,推理 + 后训练) | 每 iter 检测 imbalance > 阈值 | 是,挂在 dispatch 路径上 | centralized LLA(每 iter 一次) |
| **per-pass non-blocking** | [[Libra-arXiv26\|Libra]](2026,SGLang)| 每个 forward pass | 否,藏在 MoE_local 计算窗口 | per-layer locality plan |
| **per-event** | [SGLang Elastic EP](https://www.lmsys.org/blog/2026-03-25-eep-partial-failure-tolerance/)(2026-03,fault recovery)| 节点失败时 | 否,但是冷重映射 | EP layer manager |

矛盾在于:periodic batch 在分布稳定时摊销最优,但 [[LatencyOptimal-MoELB-INET4AI25]] 量化指出 EPLB 单次要搬 13036 个 expert(即使经 ILP 优化也仍要 2440 个),LB 频率上限只能到每 500 iter ~ 2×/秒;LLEP per-iter on-CP 反应快但每 iter 都把迁移代价吃在 dispatch 路径上,在 hotness drift 持续高频的场景下会**饱和 critical-path 带宽**;per-pass non-blocking 需要 70-90% 准确的预测器,且 scope 限于 next-layer。一个**未被占据的格点**:在 drift 频率超过 LLEP per-iter 反应能力时,把迁移决策**从 critical-path 解耦到后台机会主义带宽窗口**,牺牲单次反应速度换持续吞吐稳定。

**核心方法**。提出 **continuous expert reassignment**:把迁移决策从 dispatch critical-path 解耦,放到后台机会主义带宽窗口里,通过 IMMCOUNTER 通知 + lock-free routing table 实现热切换。

- **后台机会主义迁移**:运行时持续监测 (a) expert 实际命中率 / GPU 占用,(b) [[Libra-arXiv26|Libra]] 风格的 next-layer routing 投机,(c) cross-layer correlation(类 [PreScope](https://arxiv.org/abs/2509.23638) 观察)。当某 GPU 间 P2P 链路在当前 layer 计算窗口内有空闲带宽时,后台流式推送 1-2 个候选 hot expert 副本到 under-loaded GPU。**不阻塞 forward pass,与 dispatch 路径无依赖**。这是与 LLEP 的关键差异:LLEP 一旦 imbalance > λ 就在 dispatch 上强制迁移,本提案"无空闲带宽则推迟"
- **IMMCOUNTER-based routing-table hot-swap**:接收方 GPU 通过 [[TransferEngine-MLSys26|TransferEngine]] 的 IMMCOUNTER 检测某个 expert shard 已**完整**到达,**才**把该 expert 加进自己的 routable set;router 端在每 iteration 末尾读最新 routable view,**没有跨 GPU 同步,没有 stop-the-world**。借鉴 [[LayeredPrefill-MLSys26]] 的 layer-group 调度思路,在 layer 边界天然有 router refresh 点
- **带宽摊销**:把单次 13036-expert 的批量迁移摊到几千个 iter 的零碎窗口里。每 iter 只搬 0-3 个 expert,迁移带宽峰值不超过 [[Expert-Parallelism|EP]] 通信峰值的 10%
- **decentralized P2P 拓扑**:不需要 [[CRAFT-MLSys26|CRAFT]] / [[LatencyOptimal-MoELB-INET4AI25]] 的全局 ILP 规划器,也不像 LLEP 每 iter 算全局 LLA 计划;每 GPU 维护一个本地 expert routing table,通过周期 broadcast(SWIM-style gossip)收敛全局视图
- **与 hotness predictor 解耦**:迁移机制不绑定具体预测算法。可插拔接 [[Libra-arXiv26|Libra]] 的 speculative gating(70-90% accuracy)、[Pre-Attention](https://arxiv.org/abs/2511.10676) 的 93-97% accuracy、[PreScope](https://arxiv.org/abs/2509.23638) 的 cross-layer correlation、或简单的滑动窗口统计,做对比
- **与 SGLang Elastic EP 抽象正交化**:SGLang 上游已 ship 运行时 expert remap(为 fault recovery)。本提案不重造抽象,而是把 EEP 的 trigger 从"node failure"扩展为"hotness drift",共用同一套 expert remap 数据结构;两个 trigger 通过 `drift trigger | failure trigger` 区分

**预期收益**(M1 micro-benchmark 校准前为 hypothesis):
- 在 hotness drift 频率高的 trace 上,end-to-end MoE 延迟比 [LLEP](https://arxiv.org/abs/2601.17111) ≥ 10%、比 [[LatencyOptimal-MoELB-INET4AI25]] ≥ 15%
- 迁移期 TPOT P95 退化 < 3%(LLEP critical-path 迁移在频繁 drift 下退化更大,这是 differentiator)
- 实质生效迁移次数(routable set 实际改动)≥ 50× / 秒,在 token throughput 1-3K tokens/s 的运行点上
- 跨 vendor:同一二进制在 ConnectX-7 和 EFA 上 work(继承 [[TransferEngine-MLSys26|TransferEngine]],或可由 [UCCL-EP](https://arxiv.org/pdf/2512.19849) 替代)

## 相关工作(仓库内)

### MoE LB / 迁移直接对比

- [[CRAFT-MLSys26]] — 静态 per-layer benefit + MCKP 分配 replica 预算,**配置时一次性决策**,运行时不再迁移。本提案补"运行时动态迁移"
- [[LatencyOptimal-MoELB-INET4AI25]] — periodic batch 代表:ILP + heuristic 优化迁移代价,EPLB 13036 → 2440 expert 搬运、12.5% MoE 延迟降。论文实验在 8 × AMD MI300 上,本提案 H100 复现需要确认硬件平台差异(MI300 HBM3 vs H100 HBM3,Infinity Fabric vs NVLink 拓扑差异)。LB 频率上限 ~ 每 500 iter,这是"周期 batch"假设的固有限制
- [[Libra-arXiv26|Libra]] — speculative gating 70-90% 准确预测下一层 expert,Two-Stage Locality-Aware Execution。**已用 PyTorch SymmetricMemory 做 P2P expert 拷贝、double-buffer 隐藏在 MoE_local 计算窗口里**——属 per-pass non-blocking 的代表。本提案直接复用其 speculation 信号作为预测器候选,但迁移机制是 *跨 iter 摊销* 而非 *per-pass 即时*

### MoE expert 资源管理(非迁移类)

- [[FluxMoE-arXiv26]] — expert paging 在**单卡内** GPU↔CPU swap,改 residency 但不改 host GPU 归属。和本提案正交,可叠加
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — 改架构让 all-to-all 与计算重叠,本提案的"机会主义带宽利用"思路类似但不改架构
- [[MoEBlaze-MLSys26|MoEBlaze]] — token routing buffer 免物化,训练侧;与推理侧迁移正交
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — FP8 dataflow 减 cast,与 expert placement 正交但减 expert weight 体积有协同(迁移更便宜)
- [[NEST-MLSys26|NEST]] — level-wise 7 维并行联合优化,offline 决策
- [[EventTensor-MLSys26|EventTensor]] — megakernel 的 event tensor 抽象,**可借**:expert ready 通知本质上就是 event,IMMCOUNTER → Event Tensor 是天然映射

### 通信底座 / 调度协同

- [[TransferEngine-MLSys26]] — **直接底座**:IMMCOUNTER 完成通知 + paged WRITE + UVM watcher,vendor-neutral 跨 ConnectX-7/EFA。论文已把 KvCache transfer / RL 权重更新 / **MoE dispatch/combine** 列为三大生产场景。本提案的 novel 应用是把 IMMCOUNTER 用于 expert routing **table** 的 lock-free publish/subscribe(routable set 元数据流),与 dispatch/combine 的 token 流通信路径解耦
- [[LayeredPrefill-MLSys26]] — layer-group 调度,本提案的 router refresh 点天然落在 layer-group 边界
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1.6T-Pro / 284B-Flash + FP4 expert 量化 + **√Softplus affinity routing**(V4 把 affinity 激活从 V3 的 sigmoid 改为 sqrt-softplus)+ MegaMoE 是开源 fine-grained EP 的 fused 内核名(非模型名)。验证场景之一(Lite/蒸馏版本可在 8 卡跑);FP4 量化让 expert 体积缩小 ~10×,迁移成本下降,需评估是否会稀释 continuous 摊销的卖点

## 相关工作(外部)

MoE 调度是 2025-2026 最拥挤的赛道之一,必须诚实标注:

### 直接 baseline 与机制层近邻

- **Nguyen et al. (Jan 2026)** [LLEP / Least-Loaded Expert Parallelism](https://arxiv.org/abs/2601.17111),Salesforce — **最直接竞品**:推理 + 后训练侧 *per-iteration* 在 dispatch 路径上做 expert 权重 + token P2P 转移,gpt-oss-120b 1.9× 端到端 / 单层 5–6× 加速,**已开源** [`SalesforceAIResearch/LeastLoadedEP`](https://github.com/SalesforceAIResearch/LeastLoadedEP)。本提案的差异是 *跨 iter 后台摊销 + 与 dispatch 解耦 + decentralized*,在 hotness drift 高频场景下 LLEP 持续占用 critical-path 带宽,本提案"无空闲带宽则不迁"是 differentiator
- **Pan et al. (Apr 2025)** [SYMI / Adaptive Expert Replication for MoE Training](https://arxiv.org/abs/2504.19925) — **训练侧**,decouple expert params 与 optimizer state,per-iteration right-size 资源以避免 migration 开销。思路相似(continuous adjustment),但训练场景 + 不依赖 P2P RDMA primitive
- **Zhao et al. (Oct 2025)** [HybridEP](https://arxiv.org/abs/2510.19470) — 训练 + cross-DC 场景,异步通信器把 expert migration 与 compute overlap;同样属"机制层 continuous"但 scope 错开(训练 cross-DC vs 推理 intra-DC)
- **SGLang Team (Mar 2026)** [Elastic EP in SGLang](https://www.lmsys.org/blog/2026-03-25-eep-partial-failure-tolerance/) — 上游 SGLang 已 ship 运行时 expert-to-GPU 重映射(为 fault tolerance 设计)。**本提案与其代码路径正交化复用**:trigger 从"node failure"扩展为"hotness drift",共用 expert remap 抽象
- **UCCL-EP** [arXiv 2512.19849](https://arxiv.org/pdf/2512.19849)(Dec 2025) — Portable EP 通信库,EFA 上比 SOTA 快 2.1×,与 [[TransferEngine-MLSys26|TransferEngine]] 是 vendor-neutral 通信底座的同期竞品。底座可二选一,降低 R4 风险

### 预测 / prefetch 类(本提案 consumer 不是 contributor)

- **Wang et al. (Jun 2025)** [MoE-GPS](https://arxiv.org/abs/2506.07366) — 量化不同 prediction 策略对 LB 性能的影响,**只指导预测器选型,不做迁移**。可借其 distribution-only prediction 思路
- **Zhao et al. (Sep 2025)** [PreScope](https://arxiv.org/abs/2509.23638) — cross-layer routing correlation 驱动 prefetch,**单卡 prefetch 不迁移 host**。本提案 layer-group 路由刷新点借鉴其 cross-layer 观察
- **Liu et al. (Nov 2025)** [Pre-Attention Expert Prediction](https://arxiv.org/abs/2511.10676) — 93-97% pre-attention prediction accuracy(DeepSeek V2 Lite 93%、Qwen3-30B 95%、Phi-mini-MoE 98%),**仍是 prefetch 不是 migration**
- **Cao et al. (Oct 2024)** [ExpertFlow](https://arxiv.org/html/2410.17954v2) — RPP + token scheduler + cache engine,但 cache 在本地 GPU,不跨 GPU 迁移 host
- **Zhao et al. (Sep 2025)** [DuoServe-MoE](https://arxiv.org/html/2509.07379v2) — 区分 prefill/decode phase 的 prefetch,与本提案正交

### 其他(scope / 路线不同)

- **Gandhi et al. (Oct 2025)** [Rewiring Experts on the Fly](https://arxiv.org/abs/2510.14853) — 在线调整 routing weight(模型行为侧),不动 expert 物理 placement,与本提案正交
- **Zhang et al. (Aug 2025)** [Prism: Edge Inference for Distributed MoE](https://arxiv.org/html/2508.12851v4) — edge / 跨服务器 placement,scope 不同;周期性 placement re-evaluation 思路类似
- **Sun et al. (Mar 2026)** [Semantic Parallelism / Speculative MoE Pre-scheduling](https://arxiv.org/abs/2503.04398) — speculative token + expert pre-scheduling,与 Libra 路线类似
- **He et al. (Oct 2024)** [Aurora: Optimizing MoE Inference Time](https://arxiv.org/html/2410.17043v1) — 联合 colocation + GPU assignment + comm scheduling,**offline 求解**

## Novelty 评估

- **新颖点**(三轴**联合**才构成 delta,任何一条单独都不算 novel):
  - **continuous-vs-per-iter trade-off 的精确刻画**:LLEP 是 per-iter critical-path、本提案是跨 iter background。给定 hotness drift 频率 f 与 P2P 带宽 B,这两者存在 break-even 曲线;本提案的端到端贡献是**给出该曲线**,并证明在高频 drift 区域 background continuous 严格占优
  - **IMMCOUNTER 用作 routable-set publish/subscribe channel**:[[TransferEngine-MLSys26|TransferEngine]] 已把 IMMCOUNTER 用于 KV transfer / RL 权重 / MoE dispatch/combine。本提案首次把 IMMCOUNTER 做成 expert *routable set* 的 publish/subscribe channel——这是元数据流类型(routing table 自身,不是 token 流)的新应用,与 dispatch/combine 通信路径解耦
  - **decentralized 架构**:[[CRAFT-MLSys26|CRAFT]] / [[LatencyOptimal-MoELB-INET4AI25]] / LLEP 都需要某种全局 view(ILP / heuristic / LLA);本提案的 gossip-based load monitoring 是真 delta,但 gossip 实际开销(N=128/256 expert × L=60 layer × P=64 GPU)需在 M3 量化
  - **predictor 与迁移机制解耦**:migration controller 不绑定特定预测算法,可作为 [[Libra-arXiv26|Libra]] / [PreScope](https://arxiv.org/abs/2509.23638) / [Pre-Attention](https://arxiv.org/abs/2511.10676) / 滑动窗口的可插拔下游
- **不新颖处**:
  - "expert 在 GPU 间动态分配" 已被 LLEP / Libra-P2P 实现,本提案不发明
  - "热度预测" 已被 Libra / PreScope / Pre-Attention 充分研究,本提案是 consumer
  - "P2P RDMA 跨 vendor" 是 [[TransferEngine-MLSys26|TransferEngine]] / UCCL-EP 的贡献,本提案是 consumer
  - "运行时 expert 重映射" 已被 SGLang EEP 实现(虽 trigger 是 fault recovery)
- **总体判断**:**low–medium 边界**。MoE LB 是 2025-2026 最拥挤赛道,核心 abstraction 已被反复打磨;LLEP / Libra 已分别在 per-iter 与 per-pass 占住格点。本提案在跨 iter background 的格点有真 niche,但学术叙事必须是"机制层精确化"而非"机制层 first"。
  
  现实可投稿目标:**NSDI / EuroSys 优先,OSDI 需要三个条件全部达成**:(a) end-to-end vs LLEP ≥ 10% **且** vs [[LatencyOptimal-MoELB-INET4AI25]] ≥ 15%;(b) 必须在 LLEP 做不出来的高频 drift 场景上展示压倒性优势;(c) IMMCOUNTER hot-swap 机制可证明正确(无路由 race condition)。三条都达不到则降为 EuroSys / HPDC。

## 可行性评估

- **核心组件**:
  - **Per-GPU expert routing table + IMMCOUNTER hot-swap**(~3 周):lock-free 数据结构,wait-free reader,IMMCOUNTER-driven publisher
  - **Hotness monitor + gossip**(~1 周):每 GPU 滑动窗口 expert hit 计数 + 周期 SWIM-style gossip
  - **Migration controller**(~3 周):机会主义带宽 detector + 候选 expert 选择(marginal benefit / per-expert utility)+ 节流策略
  - **Hotness predictor 适配层**(~1 周):统一 IO 接口,可插 [[Libra-arXiv26|Libra]] / PreScope-like / Pre-Attention / 滑动窗口
  - **路由表读 / 写一致性证明**(~1 周):TLA+ spec 验证 IMMCOUNTER hot-swap 在 router 视角无 stale read,无 expert 不可达
  - **LLEP / Libra-P2P / LatencyOptimal-MoELB baseline 接入**(~2 周):必接,正面对比是 paper 立得住的关键
  - **Eval pipeline**(~2 周):多 trace 对比 + ablation
  - **小计**:13 周(若团队 ≤ 2 人,可去 TLA+ 形式化省 1 周;若放弃跨节点拓扑实验,可再省 1 周)
- **可复用代码**:
  - [[SGLang]] v0.4.10+ 作为 host([[CRAFT-MLSys26|CRAFT]] / [[Libra-arXiv26|Libra]] 都在 SGLang 上,baseline 直接对齐),或 [[vLLM]]
  - SGLang Elastic EP 的 expert remap 抽象:复用其 `expert_parallel_layer` 数据结构,trigger 扩展即可
  - [[TransferEngine-MLSys26|TransferEngine]] 的 IMMCOUNTER 实现(若 pplx-garden 未开源则用 NIXL / DeepEP-RDMA / [UCCL-EP](https://arxiv.org/pdf/2512.19849) 替代)
  - LLEP 已开源(Salesforce):[`SalesforceAIResearch/LeastLoadedEP`](https://github.com/SalesforceAIResearch/LeastLoadedEP)直接 baseline
  - EPLB(DeepSeek 开源)+ [[CRAFT-MLSys26|CRAFT]] 代码(若开源)+ [[LatencyOptimal-MoELB-INET4AI25]] heuristic(论文伪代码可重实现)
  - Hotness trace:OpenOrca / MBXP / GSM8K / ShareGPT
- **数据 / 算力**:
  - **硬件**:1 × 8 H100 跑 DeepSeek-V2-Lite-16B + Qwen3-30B-A3B(单节点 EP=8);2 × 8 H200 跑 DeepSeek-V3-671B 蒸馏版(若有);3 节点跑跨节点 EP 拓扑
  - **模型**:DeepSeek-V2-Lite (16B / 64 experts,top-6),Qwen3-30B-A3B (128 experts,top-8),GLM-4.5-Mini(若可获得),DeepSeek-V3 (8 卡 sub-cluster)
  - **trace**:OpenOrca / MBXP / GSM8K + 自合成的高频 drift trace(多租户混合 ShareGPT + SWE-Bench + MBPP+)
- **关键风险**:
  - **R1: 路由表 hot-swap 的正确性**(M2 验证)— 在 router 读、迁移完成、IMMCOUNTER 通知三者交错下不能漏 token 也不能 double-route。Mitigation:M2 阶段 deterministic 测试 + TLA+ 验证 invariant
  - **R2: 与 LLEP / [[LatencyOptimal-MoELB-INET4AI25]] 的数字差距**(M3 验证)— 若 vs LLEP < 5% 或 vs LatencyOptimal-MoELB < 12%,投 OSDI/SOSP 太薄。Mitigation:M3 末必须双门槛达标(vs LLEP ≥ 10% **且** vs LatencyOptimal-MoELB ≥ 15%);否则转 NSDI/EuroSys 叙事,改写"continuous-vs-per-iter trade-off"为主卖点
  - **R3: Hotness drift 的 trace 可得性**— [[LatencyOptimal-MoELB-INET4AI25]] 自己的 trace 不一定开源。Mitigation:用公开 dataset 合成 drift,先邮件作者询问是否分享 trace
  - **R4: TransferEngine IMMCOUNTER 接口在 SGLang/vLLM 集成成本**— 没开源就要用 NIXL / UCCL-EP 替代,可能损失部分性能特性。Mitigation:M1 micro-benchmark 验证 IMMCOUNTER 关键性能,再决定是否必须用 pplx-garden
  - **R5: 与 prefetch 类工作的边界(Pre-Attention / PreScope)**— 评审会问"你和 prefetch 的差异"。Mitigation:eval 必须明确区分"prefetch 命中"vs"migration 收益"两块,把 host migration 单独的贡献分离出来
  - **R6: 与 LLEP 的差异化**— LLEP 是 per-iter on-critical-path 的 P2P 权重 + token 转移,且开源 + 5-6× 单层加速。Mitigation:eval 必须 (a) 接 LLEP 作 baseline,(b) 拆出"per-iter on-critical-path"vs"continuous background"的延迟对比,(c) 在 hotness drift 频率高的 trace 上证明 LLEP 在每 iter 都触发迁移会饱和带宽,本提案的摊销策略反而占优
  - **R7: 与 SGLang Elastic EP 代码路径冲突**— SGLang 上游已 ship 运行时 expert remap(为 fault recovery)。Mitigation:M1 阶段读 SGLang `expert_parallel_layer` 实现,把本提案的 hot routing table 与 EEP 的故障重映射逻辑做成同一抽象的两个 trigger(`drift trigger | failure trigger`),复用同一套 routing-table publish/subscribe
- **总体判断**:**high**。所有组件在已发表工作里有先例;硬件需求小;trace 公开可获;主要工程量在 controller、正确性证明、LLEP / EEP 代码路径正交化。**effort: long**(13 周左右,3-5 人小团队)。

## 实现规划

### M1 — Baseline 复现 + 通信底座 + Micro-benchmark(~3 周)

- 在 [[SGLang]] v0.4.10 + DeepSeek-V2-Lite (8 × H100, EP=8) 上跑通 baseline;复现 [[LatencyOptimal-MoELB-INET4AI25]] heuristic LB 与 EPLB
- 接入 LLEP 开源代码作 baseline;复现 gpt-oss-20b 上 ~1.4× 加速(±5% 容差)
- 在 [[Libra-arXiv26|Libra]] 公开代码或自实现一份 speculative gating 预测器
- 集成 [[TransferEngine-MLSys26|TransferEngine]] 或 NIXL / UCCL-EP,验证两 GPU 间 paged WRITE + IMMCOUNTER 通知端到端可用
- 读 SGLang `expert_parallel_layer` 源码,确认与本提案的 routing-table 抽象的正交化路径
- **Micro-benchmark**(必做):IMMCOUNTER 通知到 GPU 上的实际延迟、单 expert 迁移 wall time、gossip 广播开销;用真实数字替换 hypothesized 数字
- **验证标准**:
  - LatencyOptimal-MoELB 数字复现(±5% 容差)
  - LLEP 数字复现(±5% 容差)
  - IMMCOUNTER 通知到 GPU 上 < 5 µs(若不达标则调整 controller 设计或换底座)
- **Go/no-go gate**:micro-benchmark 数字若严重偏离 hypothesis(如 IMMCOUNTER > 50 µs)→ 重新设计 controller,或 pivot 到更保守的 swap 协议

### M2 — Lock-free routing table + 单 expert hot-swap(~3 周)

- 实现 per-GPU local routing table,IMMCOUNTER-driven publisher,wait-free reader
- 复用 SGLang `expert_parallel_layer` 抽象,扩展 `drift trigger | failure trigger` 双路径
- 实现"单 expert 从 GPU A 迁到 GPU B"端到端协议:启动 → 后台传输 → IMMCOUNTER complete → routing table swap → 老副本释放
- 用 deterministic test + TLA+ spec 验证无路由 race condition
- **验证标准**:
  - 在 in-flight decode 期间(Llama 风格 dense baseline 模拟 MoE token 流)迁移单个 expert 不丢 token、不重复 route
  - 迁移期 TPOT 退化 P95 < 3%
- **Go/no-go gate**:若 TLA+ 找出无法解决的 race condition → pivot 到 stop-the-world 但更便宜的 swap 协议

### M3 — Continuous migration controller + 多预测器对比 + 正面对比 LLEP(~3 周)

- 实现 hotness monitor + gossip + opportunistic 带宽 detector + migration controller
- 接入 4 种 hotness predictor:[[Libra-arXiv26|Libra]] speculative gating / 滑动窗口统计 / [PreScope](https://arxiv.org/abs/2509.23638) cross-layer correlation / [Pre-Attention](https://arxiv.org/abs/2511.10676)
- 在 OpenOrca/MBXP/GSM8K + 合成高频 drift trace 上端到端 eval,baseline 含 **LLEP / [[LatencyOptimal-MoELB-INET4AI25]] / EPLB / no-LB**
- **验证标准**(双门槛):在 ≥ 2 个 trace 上 end-to-end MoE latency
  - **vs LLEP ≥ 10%**(critical-path on-CP vs background 摊销)
  - **vs [[LatencyOptimal-MoELB-INET4AI25]] ≥ 15%**(periodic batch baseline)
  - 实质生效迁移 ≥ 50× / 秒(在 token throughput 1-3K tokens/s 的运行点上)
  - 迁移期 TPOT P95 退化 < 3%
- **Go/no-go gate**:vs LatencyOptimal-MoELB < 12% **或** vs LLEP < 5% → pivot 到 NSDI/EuroSys "continuous-vs-per-iter trade-off" 叙事(机制层精确化)

### M4 — 完整 eval + ablation + 跨模型验证(~3 周)

- 模型扩展:加 Qwen3-30B-A3B、DeepSeek-V3-Lite(若有)、跨节点拓扑(2 × 8 H200)
- Ablation:(a) 不同 predictor 的影响;(b) IMMCOUNTER hot-swap vs 显式同步 swap 的延迟差;(c) gossip 频率;(d) 仅 prefetch vs prefetch + migration 的拆分;(e) **不同 hotness drift 频率下 vs LLEP 的曲线(确认 break-even point)**
- 与 [[CRAFT-MLSys26|CRAFT]]、[[Libra-arXiv26|Libra]]、[LLEP](https://arxiv.org/abs/2601.17111)、[[FluxMoE-arXiv26]] 在各自合适场景做对比
- **验证标准**:
  - 至少 3 个模型 × 3 个 trace 上一致优于 baseline
  - ablation 显示每个组件贡献 ≥ 5%
  - decentralized gossip vs centralized planner 在大规模(64 GPU 模拟)上 scalability 优势可量化
  - **给出 vs LLEP 的 break-even 曲线**(在哪种 drift 频率以上 background 击败 critical-path)——这是 paper 的核心定量贡献

> **Go/No-Go gates 总览**:
> - M1 末:micro-benchmark 数字若严重偏离 hypothesis → 重新设计 controller 或换底座
> - M2 末:正确性证明失败 → pivot 到更保守的 swap 协议
> - M3 末:vs LLEP < 5% 或 vs LatencyOptimal-MoELB < 12% → pivot OSDI → NSDI/EuroSys

## 开放问题

- **预测精度与迁移收益的关系**:[[Libra-arXiv26|Libra]] 70-90% accuracy 够吗?[Pre-Attention](https://arxiv.org/abs/2511.10676) 的 93-97% 是否能让迁移决策"基本无误"?有没有 prediction accuracy 的关键阈值?
- **continuous vs per-iter 的 break-even**:在哪种 hotness drift 频率以上 background continuous 击败 LLEP 的 per-iter critical-path?这是 paper 的核心定量贡献,也是 OSDI 投稿成败的关键
- **跨节点 vs 节点内 P2P 的性价比**:节点内 NVLink 200 GB/s,跨节点 RDMA 50-100 GB/s;迁移决策是否需要 topology-aware?
- **[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 的 FP4 expert 量化怎么影响迁移收益**:expert 体积大幅缩小,迁移成本下降 ~10×,可能让 batch swap 与 per-iter on-CP 都变便宜——本提案的"continuous"卖点会不会因此被稀释?需在 V4 量化模型上重测
- **Hotness predictor 的训练成本**:speculative gating 需要每层多算一次,对 prefill 是不是另一种 overhead?在 LM 推理 token-bound 场景下值不值?
- **与 [[LiveSessionMigration]] 的关系**:那个 proposal 的 session migration 与本提案的 expert migration 是否应该共用一套 controller?expert 是 weight 不是 state,但热度漂移会牵引 session placement——两者应该融合还是解耦?(参考 `proposals/LiveSessionMigration.md`)
- **决定上 OSDI 还是 NSDI/EuroSys**:novelty 在机制层精确化(continuous-vs-per-iter trade-off + decentralized + decoupled hot-swap)而非问题层;若 P2P 协议成分主导,NSDI 更对口;若数字 + niche 立得住,OSDI 仍有可能

## 参考

- 内部相关:[[MoE]]、[[Expert-Parallelism]]、[[Load-Balancing]]、[[KV-Cache]]、[[RDMA]]、[[Disaggregation]]、[[CRAFT-MLSys26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[Libra-arXiv26]]、[[FluxMoE-arXiv26]]、[[TransferEngine-MLSys26]]、[[MLSys-2026]]
- 外部链接(已在「相关工作(外部)」展开):LLEP / SYMI / HybridEP / SGLang Elastic EP / UCCL-EP / Pre-Attention / PreScope / MoE-GPS / ExpertFlow / DuoServe-MoE / Rewiring Experts / Prism / Aurora / Semantic Parallelism
- 兄弟 proposal:`proposals/LiveSessionMigration.md`
