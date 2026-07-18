---
type: proposal
name: ElasticMoEP2P
title: "ElasticMoE: Expert-Level Elasticity for Multi-Node MoE Decode Serving via P2P RDMA"
status: archived
created: 2026-04-05
last_updated: 2026-04-05
target_venue: "OSDI/SOSP → MLSys（已确认 novelty 空间被 CRAFT MLSys'26 压缩，归档）"
tags: [LLM-Serving, MoE, Expert-Parallelism, Elastic-Scaling, P2P-RDMA]
related_papers:
  - "[[CRAFT-MLSys26]]"
  - "[[Libra-ICLR26]]"
  - "[[BlitzScale-OSDI25]]"
  - "[[Aegaeon-SOSP25]]"
  - "[[FlexiCache-MLSys26]]"
  - "[[MorphServe-MLSys26]]"
  - "[[BLASST-MLSys26]]"
  - "[[Quake-OSDI25]]"
  - "[[Matrix-MLSys26]]"
related_concepts:
  - "[[MoE]]"
  - "[[KV-Cache]]"
  - "[[Disaggregation]]"
related_systems:
  - "[[vLLM]]"
  - "[[SGLang]]"
novelty: medium
feasibility: low
effort: high
deprecation_reason: >
  CRAFT (MLSys'26) 占据了 fine-grained per-layer expert replica allocation 叙事位；
  组合性 novelty 不足以支撑 OSDI/SOSP；
  venue 错配（控制器/优化问题 vs 系统抽象问题）；
  Phase 0 三层假设风险过高。
---

# ElasticMoE: Expert-Level Elasticity for Multi-Node MoE Decode Serving

> ⚠️ **ARCHIVED（2026-04-05）**：从旧 `ideas/` 目录通过 git log 恢复，原状态 deprecated。

## Deprecation 原因

在 MLSys 2026 论文调研后，确认本 idea 的 novelty 空间已被压缩到难以支撑目标 venue 的程度。**核心问题是顶部 venue 错配，底部被前沿工作吃掉**。

### 1. 核心贡献被 CRAFT（MLSys'26）覆盖

[[CRAFT-MLSys26]] 直接占据了"fine-grained per-layer expert replica allocation with cost model"的叙事位：
- MCKP-based 非均匀副本分配（非均匀性贡献被吃）
- Per-layer benefit estimation（layerwise 差异化贡献被吃）
- 相比 EPLB 副本数减少 7-8x（SOTA 基准提高）
- CRAFT 可"免费"扩展为 periodic re-planning，进一步压缩动态方案的差异化窗口

### 2. 组合性 novelty 不足以支撑 OSDI/SOSP

ElasticMoE 的每个机制都是已有技术的移植或组合：
- Replication → CRAFT（静态）+ Libra（per-layer）
- Consolidation / Migration → INET4AI 的 swap 对偶
- Estimate-Verify-Commit → Quake 的直接移植
- Stability classification → FlexiCache 方法论移植
- 去中心化 Controller → 30 年前的 gossip 技术
- P2P RDMA → pplx-garden 提供

**没有单一"新抽象"或"新系统哲学"** 来支撑 OSDI/SOSP。审稿人的公正评价会是："combination of known techniques applied to MoE, no surprising finding"。

### 3. Venue 错配

本 idea 本质上是**控制器/优化问题**，不是系统抽象问题：
- 给定实时 load + stability prior → 输出 expert placement decisions
- 这是 MLSys/SIGMETRICS 的 profile，不是 OSDI/SOSP 的 profile

MLSys 2027 虽然可投，但面临三重阻力：
- CRAFT 作者在 PC 中，novelty bar 极高
- 需要 32+ GPU 多节点实验（学术实验室门槛）
- 依赖三个未验证假设（imbalance 严重度、memory-bound 状态、stability 跨 trace 一致性）全部成立

### 4. Phase 0 的三层假设风险过高

本方案立足于三个必须全部成立的经验假设：
- 假设 1：decode 阶段 MoE 负载不均严重（P99 imbalance > 2×）
- 假设 2：负载不均可转化为延迟差异（GEMM compute-bound）
- 假设 3：expert 负载分布有可跨 trace 复现的异质性

任一假设失败整个方案崩盘。这种"研究前置验证成本高 + 多假设连乘风险"的结构不适合作为主攻方向。

---

## 可重用的 artifacts（如未来相关方向）

本文档中有两个仍有价值的独立方法论贡献，**可剥离用于其他方向**：

1. **Drift-injection benchmark**：MoE LB 的 drift-aware 评估方法论，可作为 workshop paper 单独发表
2. **Expert stability classification**：FlexiCache 方法论到 MoE expert 的移植，可作为 measurement paper 的核心发现

如果未来要 pivot 到 MoE serving 方向，可考虑：
- **Expert-as-a-Service 架构**：把 expert 建模为独立部署的无状态微服务，提出新的 serving 抽象（OSDI-worthy 但需 18-24 个月）
- **纯 expert-level auto-scaling**：专注流量突发下的 expert 冷启动 + 快速扩容，与 BLITZSCALE 互补
- **MoE serving 的存算解耦**：expert 权重池与 compute 池解耦架构

---

## 历史版本（保留供参考）

以下是 deprecation 前的完整方案，保留以备将来参考或部分 artifacts 复用。

---

> **一句话定位**：在 disaggregated serving 的 decode 池中，以 expert 为资源粒度（而非 GPU 实例粒度），基于 P2P RDMA 实现事件驱动的复制/合并/迁移/扩缩，在零模型质量损失下显著改善多节点 MoE decode 的尾延迟。

---

## 一、已解决与未解决：研究空白的重新校准

### 1.1 已解决的问题

| 问题 | 已有方案 | 状态 |
|---|---|---|
| MoE all-to-all 通信效率 | DeepEP（NVLink+IBGDA）、pplx-garden/TransferEngine（P2P RDMA） | 成熟 |
| Padding 浪费 | pplx-garden P2P scatter（精确发送）、MegaBlocks（block-sparse） | 成熟 |
| 通信-计算重叠 | ScheMoE、DeepEP hook、pplx-garden 两阶段 dispatch | 成熟 |
| **静态 expert replica 分配** | **[[CRAFT-MLSys26]]（MLSys'26）**：MCKP-based per-layer replica budget，相比 EPLB 副本数减少 7-8x | **新，已解决** |
| **Prefill 单节点 LB** | [[Libra-ICLR26]]（ICLR'26）：speculative gating + Two-Stage Execution，8×H200 上 +19.2% 吞吐 | 已解决 |
| LB 搬运代价建模 | Latency-Optimal LB（INET4AI'25）：migration cost 感知 heuristic，搬运量 -57% | workshop 级 |
| 单机 expert offloading | [[KTransformers]]、MoE-Infinity、Pre-gated MoE | 活跃研究 |
| 实例级弹性扩缩 | [[BlitzScale-OSDI25]]（OSDI'25）：layer-granularity live scaling | 已解决 |
| Token 级自动扩缩 | [[Aegaeon-SOSP25]]（SOSP'25）：per-token slack budget，97% 扩缩延迟削减 | 已解决 |

### 1.2 未解决的问题

| 问题 | 当前最佳状态 | 为什么难 |
|---|---|---|
| **Decode 阶段多节点 MoE LB** | Libra 单节点 prefill only；CRAFT 静态不响应运行时 | 小 batch 下 MoE_local 窗口不足、跨节点 IB 带宽比 NVLink 低 18x |
| **运行时 expert 负载漂移响应** | CRAFT 一次性离线，Libra 每层重做，EPLB 每 1000 iter | 需在 ms-级时间预算内完成触发-决策-执行 |
| **Expert-level consolidation** | 无 | 需要跨节点协调合并决策，避开跨 GPU 权重迁移的关键路径 |
| **Expert-level auto-scaling** | 实例级有（BLITZSCALE、Aegaeon），expert 级无 | 需要 expert 粒度的通信、调度、SLO 记账 |
| **pplx-garden EP>64 的 proxy 瓶颈** | 论文明确 flag | 单 CPU proxy 线程 per GPU，enqueue 开销 O(EP) |
| **Drift-aware LB 评估方法论** | 无——所有工作用静态 trace | 需要构造 drift-injection benchmark 才能暴露静态方案的失效 |

### 1.3 现状地图的根本变化

**CRAFT 改变了 novelty 格局。** 一年前的版本把 Libra 当作主要对手，但 CRAFT 直接把"cost-aware per-layer expert replica allocation"这一子领域占据。ElasticMoE 必须在**三个正交维度**上与 CRAFT 区分，缺一不可：

1. **时间维度**：CRAFT 是一次性静态（offline profile → deploy），ElasticMoE 是持续自适应（event-driven cross-step）
2. **操作维度**：CRAFT 只做 replication，ElasticMoE 做 replication + consolidation + migration + scaling
3. **场景维度**：CRAFT 的 MCKP 假设 uniform 硬件和 stationary 负载，ElasticMoE 针对 workload drift 和多节点异构带宽

---

## 二、核心研究问题与定位

### 2.1 核心问题

> **在 disaggregated serving 的 decode 池中，面对 workload drift 和多节点异构带宽，能否以 expert 为资源粒度实现事件驱动的弹性调度（复制/合并/迁移/扩缩），在零模型质量损失下将多节点 MoE decode 的 P99 latency 降低 X%，且对 workload drift 的恢复时间比静态方案（CRAFT/EPLB）快 K 倍？**

两个可量化、可证伪的 claim：

- **Claim 1（性能）**：在平稳负载下，ElasticMoE 的稳态性能应至少匹配 CRAFT；在多节点场景（>2 节点）下应优于 CRAFT
- **Claim 2（鲁棒性）**：在 workload drift 下，ElasticMoE 的 imbalance recovery time 应显著短于 CRAFT/EPLB，且 SLO 违规率降低

### 2.2 为什么聚焦 decode + 多节点

**Decode 是 agentic 时代的端到端延迟主导。**

Prefix caching 削减了 agentic 场景的 prefill：长 system prompt、工具定义、对话历史高度重复，cache 命中后 prefill 近乎免费。典型 agentic 请求 90% prefix cache 命中率下，prefill 从 10ms 降至 ~1ms，而 decode 50ms 不变——decode 占比从 83% 上升到 98%。**Prefix cache 越有效，decode 越是"剩下的、无法被 cache 优化掉的"瓶颈**，这正是 ElasticMoE 的主战场。

**多节点是真实部署的必然。**

DeepSeek-V3 256 experts、Kimi-K2 等模型在单节点 8 GPU 上无法完整 EP 部署，必须跨节点。Libra 的单节点 NVSwitch 假设（900GB/s）在跨节点 IB（50GB/s）下完全失效——18x 带宽差异意味着 expert 权重迁移代价从 ~50µs 放大到 ~1ms。

**Expert-level auto-scaling 是实例级扩缩的自然演化。**

BLITZSCALE（OSDI'25）证明了 layer-granularity live scaling 的可行性；Aegaeon（SOSP'25）把自动扩缩做到 token-level。**下一个自然维度是 expert-level**：流量突发时不是复制整个模型实例，而是复制被压垮的 hot expert。Expert 级扩缩的基本单元（50MB 权重）比实例级（50GB 模型）小 1000x，响应速度和资源效率都更高。

### 2.3 P2P RDMA 为何是 enabling technology

| 需求 | Collective (NCCL/All2All) | P2P (pplx-garden TransferEngine) |
|---|---|---|
| 运行时改变 expert 位置 | ❌ 需重建通信组 | ✅ 动态成员管理 |
| Token 按需发送 | ❌ 对称缓冲区 | ✅ per-token scatter（WRITEIMM） |
| 异构 expert 容量 | ❌ 所有 rank 同结构 | ✅ 每个 rank 独立 |
| ms 级 expert 权重传输 | ❌ 需全局同步 | ✅ 直接 P2P WRITE + IMMCOUNTER |
| 分层通信感知（NVLink vs IB） | ❌ topology-blind | ✅ 可按物理路径分流 |

但必须直面一个现实限制：**pplx-garden 的 CPU proxy 在 EP≥64 时成为瓶颈**（enqueue 工作量 O(EP)/dispatch，单线程 per GPU）。ElasticMoE 的 consolidation 机制恰好能缓解这个问题——通过压缩 active expert 数量减少 per-dispatch 的 peer count。

---

## 三、系统设计：ElasticMoE

### 3.1 部署架构

ElasticMoE 定位为 **disaggregated serving 下的 decode pool 优化**，基于 SGLang 实现。

**为什么必须 disaggregated**：non-disaggregated 模式下，同一 GPU 的同一次 MoE forward 混合了 prefill 和 decode tokens。Expert placement 是 GPU 级状态，无法让 prefill 走一套 placement、decode 走另一套。这不是额外限制——SGLang、DistServe 都论证了 PD disaggregation 在大规模 MoE 上是当前工业趋势。

```
Prefill Pool (节点 1-2)              Decode Pool (节点 3-8, ElasticMoE)
┌──────────────────────┐            ┌─────────────────────────────────┐
│ SGLang + Libra/CRAFT │            │ ┌─────────────────────────────┐ │
│ Placement: 静态 EP    │   KV       │ │  Decentralized Controllers   │ │
│ Comm: AllGather/All2All│  Cache    │ │  (一个 per-node, gossip 同步)│ │
│ 完全不修改             │  ────►    │ │  基于 per-expert token 计数  │ │
└──────────────────────┘            │ │  → Estimate-Verify-Commit    │ │
                                    │ └─────────────────────────────┘ │
                                    │                                  │
                                    │ Expert Worker Pool                │
                                    │ Comm: pplx-garden P2P RDMA        │
                                    │ Placement: 跨 step 持久化 + 动态  │
                                    └─────────────────────────────────┘
```

**实现路径**：
1. Prefill worker 完全不动，用 SGLang 原生 EP（或集成 CRAFT 作为静态 baseline）
2. Fork decode worker 的 MoE execution 路径：
   - dispatch/combine 替换为 pplx-garden P2P
   - 加入 persistent placement manager（维护跨 step 的 expert→GPU 映射）
   - Routing table 存 GPU constant memory，dispatch 时查表
3. **去中心化 Controller**：每节点运行一个 Controller，通过 gossip 同步 placement 状态，避免中心化 orchestrator 在 >64 GPU 时的瓶颈（借鉴 [[Matrix-MLSys26|Matrix]] 的 P2P 编排思想）

### 3.2 四个核心机制

#### 机制 1：自强化信号的负载感知（Self-Reinforcing Load Monitor）

**方法论模式**：借鉴 [[BLASST-MLSys26]] 的"重用计算中已有的状态"范式——零额外开销。

**信号来源**：pplx-garden 的 dispatch 阶段已经计算了 per-expert token count（routing metadata exchange）。Controller 直接订阅这些计数，无需额外收集。

**关键指标**（三层聚合）：
- Per-step：per-expert token count
- Per-window（100 step）：imbalance ratio (max/mean)、expert popularity rank
- Per-epoch（每 N 分钟）：**expert stability class**（见机制 2）

**错误预算触发器（借鉴 HELIOS 的 CBC 模式）**：维护 `imbalance_breach_counter`，当连续 B 个 step 的 imbalance > θ 时触发决策，而非每个 step 都决策。这把决策频率从 per-step（ms 级）降到 event-driven（秒级），避免在 decode 关键路径上做昂贵决策。

#### 机制 2：Expert 稳定性分类（Offline-Characterized Stability Profile）

**方法论模式**：借鉴 [[FlexiCache-MLSys26]] 的"model-inherent property characterization"——把模型的内禀特征转化为部署时的决策资产。

**核心假设**（Phase 0 必须验证）：MoE 模型的 expert 负载分布具有跨 trace 稳定的、可预先刻画的**异质性**。某些 expert 持续热（"stable hot"），某些周期性热（"bursty hot"），某些始终冷（"stable cold"）。

**离线刻画**（每次模型部署前做一次，~1 小时）：
1. 在多个代表性 trace（ShareGPT、LMSYS-Chat-1M、agentic workload）上记录每层每 expert 的访问频率
2. 计算每个 expert 的：
   - **Popularity**：trace 均值下的访问频率 rank
   - **Stability**：跨 trace 的 rank 相关性（Spearman ρ）
   - **Burstiness**：时间序列自相关系数
3. 分为四类：`stable_hot`（持续热且跨 trace 一致）、`bursty_hot`（高方差、短期爆发）、`neutral`、`stable_cold`

**在线使用**：
- `stable_hot` experts → 部署时即预先 replication（无需等触发）
- `bursty_hot` experts → 保留 replication headroom，触发时快速扩容
- `stable_cold` experts → 候选 consolidation 目标
- `neutral` experts → 标准 EP 布局

**这是对 FlexiCache 方法论的直接移植**，但应用对象从 attention head 换成 MoE expert。同样地，跨 trace 一致性是关键论证——Phase 0 必须证明 stability class 跨 trace 稳定（类比 FlexiCache 报告的 0.83 跨任务重叠）。

#### 机制 3：三种弹性操作 + Estimate-Verify-Commit

**方法论模式**：借鉴 [[Quake-OSDI25]] 的"cost-model-driven incremental maintenance + estimate-verify-commit"——每次调整都有 monotone improvement 保证。

**三种操作**：

**(a) Replication（复制热 expert）**
- 触发条件：expert E_hot 的 sliding-window token rate > 2× mean，且该 expert 的 `bursty_hot` 状态或错误预算超阈
- 目标 GPU：有空闲容量且通信距离最近（优先 intra-node、其次 intra-NVSwitch、最后 inter-node）
- 迁移机制：P2P RDMA WRITE（~50MB，400Gbps IB 下 2-5ms 含 overhead）
- Routing table 原子更新：新副本上线后 token 按负载比例分流（GPU constant memory 中 atomic pointer swap）
- **Expert 权重是只读的，无一致性协议需求**

**(b) Consolidation（合并冷 expert）**
- 触发条件：多个 expert 持续落在 `stable_cold` 类，且每 step token rate < 1
- 合并策略：将同层冷 expert 迁移到同一 GPU，释放出空 GPU 用于热 expert 扩容
- **Consolidation 是 ElasticMoE 独占的机制**——CRAFT/Libra/EPLB/INET4AI 都不做

**(c) Migration（迁移 expert）**
- 触发条件：某 expert 的跨节点通信量占该节点总通信量的 X%，且目标节点有容量
- 成本建模（吸收 INET4AI 的 insight）：
  ```
  Cost(migration) = sizeof(expert) / bandwidth(src→dst)
                  + downtime × expected_tokens_per_step × token_penalty
  ```
- 与 Replication 的区别：Migration 是移动（src GPU 释放权重），Replication 是复制（src GPU 保留权重）

**Estimate-Verify-Commit 协议**：
```
1. Estimate: 预测调整后的 imbalance ratio 改善 ΔI
2. Verify: 用 sliding window 内的历史 routing 数据离线重放调整后的 placement
3. Commit: 仅当 ΔI > τ 且 comm cost < budget 时执行
4. Rollback: 执行后 N 个 window 若 imbalance 未改善，回滚
```

**这个协议提供 monotone improvement 保证**，是对 EPLB 的一个清晰升级（EPLB 没有这个保证，可能做出让情况更糟的决策）。

#### 机制 4：通信感知路由（Communication-Aware Routing）

**分层策略**：

**(a) Replica-Aware Routing（零质量损失，核心 claim）**：
当 expert E 有多个副本 {R1, R2, ..., Rk} 时，按以下优先级选择副本：
1. 负载最低的副本
2. 若负载相近，选通信距离最近的副本（intra-GPU > intra-node > inter-node）

数学上同一 expert 的不同副本**输出等价**。Phase 0 必须测量 batched GEMM 在不同 batch 组合下的浮点差异，确认"零质量损失"实际差异 < noise threshold（预期 < 1e-5）。

**(b) Soft Load Balancing（可选 tradeoff，非核心 claim）**：
当 expert E 的 affinity score 与第 K+1 expert 差距 < ε 时，允许选择第 K+1 expert 以缓解负载。作为 quality-latency tradeoff knob 单独 evaluate。

**(c) Node-Locality Bias（可选 tradeoff）**：
Top-K 选择中为本节点 expert 加小 bonus。DeepSeek-V3 的 node-limited routing 是这个思想的硬编码版，ElasticMoE 提供 soft 版本。

**分层定位**：(a) 是核心（零/近零质量损失），(b)(c) 是可选 knob。Evaluation 分别报告各层贡献。

### 3.3 去中心化 Controller 设计

**动机**：中心 Controller 在 >64 GPU 时可能成为瓶颈，而 pplx-garden 的 proxy 已经是瓶颈——再叠加一个中心决策点会加剧。

**设计**：
- 每个节点运行一个 local Controller
- Local Controller 基于本节点 per-expert token 计数做本地 proposal
- 通过 gossip 协议（每秒一次）与其他节点同步：`{node_id, expert_id → load}`
- 全局决策通过分布式 consensus：提议节点广播 proposal，其他节点用相同 cost model 计算，投票或静默接受
- Routing table 版本号机制：每次更新生成新版本，不同 GPU 可能短暂不一致，通过 IMMCOUNTER 检测并重试

**借鉴 [[Matrix-MLSys26|Matrix]] 的 stateless + message-passing 设计**：Controller 本身无状态，状态完全由 gossip 消息承载。

---

## 四、与现有工作的深度对比

### 4.1 vs. CRAFT（MLSys 2026）— **首要对比对象**

[[CRAFT-MLSys26]] 是与 ElasticMoE 最接近的工作，必须清晰差异化。

| 维度 | CRAFT | ElasticMoE |
|---|---|---|
| **时间尺度** | 一次性 offline MCKP（~10s 启动时）+ 可选周期性重做（未评估） | Event-driven 跨 step 调整（秒级） |
| **触发机制** | 无触发——启动即部署 | Error budget counter + stability class 驱动 |
| **操作集** | Replication only（非均匀分配） | Replication + **Consolidation** + **Migration** |
| **负载假设** | Stationary（trace 代表性） | Non-stationary（drift-aware） |
| **硬件假设** | Uniform per-GPU capacity | 异构带宽感知（intra-node/inter-node 分层） |
| **Prefill/Decode** | 单一 plan 用于两者 | 仅 decode（与 CRAFT 可组合） |
| **规模** | 6-12 节点 × 8 A100 | 4-8 节点 × 8 H100（EP=32/64） |
| **monotone guarantee** | 无 | Estimate-Verify-Commit |

**核心论证**：

> CRAFT 通过离线 MCKP 求解了"给定 stationary trace，如何最优分配 replica budget"的问题，但它假设负载分布在部署后不变。**真实生产 serving 的流量分布会随用户群、时间、热点话题漂移**——例如 agentic workload 中 tool-calling 请求的比例波动会改变 expert 负载模式。ElasticMoE 面向这类 non-stationary 场景，且通过 Consolidation 和 Migration 两种 CRAFT 不具备的操作实现了更完整的资源调度能力。

**可预见的审稿人质疑与回应**：

**Q1**：*"CRAFT 声称可以周期性重跑（论文提到但未评估），这和你们有什么区别？"*

回应：(a) 周期性重做一次 MCKP 耗时 ~10s，在 serving 场景下意味着 ~10s 的 serving pause 或 shadow-mode 切换延迟；(b) MCKP 每次重做产生的是全新 plan，不考虑与当前 placement 的 delta，导致不必要的权重搬运（INET4AI 揭示的问题）；(c) ElasticMoE 的 incremental adjustment（改一两个 expert）+ Estimate-Verify-Commit 协议能在 ms 级完成调整，且保证 monotone improvement。Phase 2 必须包含"CRAFT periodic re-planning"作为 baseline，用实际数据说明这一点。

**Q2**：*"你们的 stability classification 和 CRAFT 的 offline profiling 有什么本质区别？"*

回应：CRAFT 的 offline profile 产出一个静态 replica plan；ElasticMoE 的 stability classification 产出**运行时决策的先验知识**——stable_hot experts 触发时立即扩容不犹豫、stable_cold experts 安全合并、bursty_hot experts 保留 headroom。Classification 本身不决定 placement，而是指导运行时决策的置信度。这两者是互补关系（可以在 CRAFT 的 static plan 上叠加 ElasticMoE 的运行时调整）。

### 4.2 vs. Libra（ICLR 2026）

Libra 的 Two-Stage Execution 依赖**大 MoE_local 计算窗口**来隐藏 token sharding + CPU planner 开销。

**失效机制**：
- Decode 典型 batch 128 tokens，单层 MoE 计算 ~1ms；Libra 的 CPU planner ~0.5ms + 权重双缓冲复制 ~0.5ms，在 decode 窗口内无法隐藏
- Libra 每层重新决定 placement，decode 80 层累积开销 ~80ms/request，不可接受
- Libra 的 AllGather dispatch 在 decode 小 batch 下效率低于 P2P

**速度-准确性对比**：

| 维度 | Libra | ElasticMoE |
|---|---|---|
| 决策位置 | CPU per-layer（prefill 下被 overlap） | 去中心化 per-second（off critical path） |
| 通信层 | AllGather（collective） | P2P RDMA（pplx-garden） |
| Replication 持久性 | 逻辑双缓冲（per-layer 重置） | 物理持久化（跨 step 保持） |
| 多节点支持 | ❌ 单节点 NVSwitch | ✅ 多节点 IB |

**Libra 的 speculative gating 能否迁移到 decode？** 预测原语（用 h_ℓ 预测 g_{ℓ+1}）本身 workload-agnostic，准确性应可迁移。但 Libra 把预测用于**每层重规划**，而 decode 关键路径无法承受这种开销。**ElasticMoE 可以选择性吸收 speculative gating**：用于在 error-budget breach 后**加速决策的 estimate 阶段**——而非替代 event-driven 架构。这是一个可以单独 ablation 的可选增强。

### 4.3 vs. Latency-Optimal LB（INET4AI'25）

| 维度 | INET4AI Heuristic | ElasticMoE |
|---|---|---|
| 均衡操作 | Expert swap only | Replication + Consolidation + Migration |
| 搬运代价建模 | Weighted Hamming + 线性代价 | 吸收其模型，扩展到多节点分层带宽 |
| 触发机制 | 周期性（每 10 iter） | Event-driven（error budget） |
| 通信层 | Collective | P2P RDMA（搬运代价降低 ~20x） |

**直接吸收的 insight**：INET4AI 的"搬运代价是主要瓶颈"正是 ElasticMoE 用 P2P RDMA 的核心论据——单 expert ~50MB 的搬运在 400Gbps IB 下 2-5ms，比 collective 方案低一个数量级。这 enables 更激进的 event-driven 调整。

### 4.4 vs. DeepEP / pplx-garden

pplx-garden 是通信基础设施，不做 placement 决策。**ElasticMoE 构建在 pplx-garden 之上**，关系类似 Spark 构建在 HDFS 之上。

**ElasticMoE 对 pplx-garden 的反向贡献**：Consolidation 机制缓解了 pplx-garden 的 EP=64 proxy 瓶颈——通过压缩 active expert 数量减少每次 dispatch 的 peer count。

**DeepEP 的 NVLink 优化（token dedup、partial sum）在 ElasticMoE 中的地位**：DeepEP 的 prefill 优化在 decode 场景价值受限；且 agentic 时代 prefix caching 削弱 prefill 占比——ElasticMoE 的 decode 定位恰好绕开了这个差距。

### 4.5 vs. BLITZSCALE / Aegaeon（实例级扩缩）

| 维度 | BLITZSCALE / Aegaeon | ElasticMoE |
|---|---|---|
| 扩缩粒度 | 模型实例（整个模型） | 单个 expert |
| 资源单位 | GPU 组（整机或 TP 组） | 单 GPU 的显存片段（~50MB） |
| 触发延迟 | 秒级 | 毫秒级 |
| 适用场景 | 流量 10x 突发（整模型扩容） | 流量分布漂移（热 expert 扩容） |

**互补定位**：BLITZSCALE/Aegaeon 应对"总 QPS 突增"，ElasticMoE 应对"QPS 分布形态变化"。实际部署中两层应并存：外层用 BLITZSCALE 增减模型实例，内层用 ElasticMoE 调整 expert 分布。可以在 evaluation 中展示**组合使用的协同效果**。

### 4.6 vs. FlexiCache / MorphServe（运行时适应）

这两个工作启发了 ElasticMoE 的方法论，但对象不同（attention head / layer quantization vs MoE expert）。ElasticMoE 把这些方法论模式**首次系统地应用到 MoE expert 调度**。

---

## 五、可行性与风险分析

### 5.1 强可行性信号

1. **Expert 权重只读**：replication 是 trivial（memcpy），无一致性协议
2. **Expert 很小**：DeepSeek-V3 单 expert ~50MB，400Gbps IB 下 2-5ms 搬运
3. **pplx-garden 提供完整通信原语**：WRITEIMM、IMMCOUNTER、dynamic membership
4. **自强化信号**：per-expert token count 已在 dispatch 中计算
5. **决策频率低**：event-driven，每秒级一次（vs. Libra per-layer）

### 5.2 关键风险与缓解

| 风险 | 严重度 | 缓解 |
|---|---|---|
| **Decode 负载不均是否足够严重** | 高 | Phase 0 实证：若 P99 imbalance < 1.5，放弃 |
| **小 batch GEMM 是否 compute-bound** | 高 | Phase 0 micro-benchmark；若 memory-bound，pivot 到"减少通信量"叙事 |
| **Workload drift 是否真实存在** | 中 | Phase 0 drift-injection + 真实 trace 分析（agentic workload 的分布变化） |
| **Stability classification 的跨 trace 一致性** | 高 | Phase 0 实证（类比 FlexiCache 的 0.83 跨任务重叠） |
| **CRAFT 增加周期性重做后是否仍差于 ElasticMoE** | 中 | Phase 2 实现 CRAFT periodic baseline，用实际数据对比 |
| **去中心化 Controller 的一致性** | 中 | Routing table 版本号 + IMMCOUNTER 检测不一致 |
| **pplx-garden EP=64 proxy 瓶颈** | 中 | Consolidation 缓解；大规模实验需验证 |
| **实验规模（32-64 GPU）** | 高 | 申请 NVIDIA academic program / 云；备选降级到 16-32 GPU |

### 5.3 三层关键假设（Phase 0 必须逐一验证）

**假设 1**：decode 阶段 MoE 负载不均足够严重（P99 imbalance > 2×）

**假设 2**：负载不均可转化为可观测延迟差异（GEMM 在 decode token count 范围 compute-bound）

**假设 3**：expert 负载分布有可跨 trace 复现的异质性（stability classification 有意义）

**三者全部成立才能立足**：
- 假设 1 不成立 → 放弃方向
- 假设 2 不成立 → pivot 到"减少通信量"或转向 prefill
- 假设 3 不成立 → 退化为纯反应式系统，失去 FlexiCache 式的方法论贡献

---

## 六、实验规划

### Phase 0：负载特征分析 + 稳定性刻画（4 周）

**核心目标**：验证三个关键假设；构建 stability classification 方法论

**实验 A：Imbalance 特征分析**
- 模型：Mixtral 8×22B、DeepSeek-V3-Lite（256 experts, EP=32）、Qwen3-MoE
- Trace：ShareGPT、LMSYS-Chat-1M、**自构造 agentic trace**（tool-calling、多轮对话、长 context）
- 指标：per-step imbalance ratio 分布、per-layer imbalance 差异、P99/P50 比
- **Node-limited vs non-node-limited 模型对比**：DeepSeek-V3 的 node-limited routing vs Mixtral 无限制

**实验 B：Expert GEMM Micro-Benchmark（关键）**
- 目标：确认 decode token count 范围（1-32）是否 compute-bound
- 度量：不同 token count 下的 GEMM latency 变化率
- 决策点：若 16-token vs 4-token 延迟差异 < 20%（memory-bound regime），pivot 方案

**实验 C：Stability Classification（关键方法论贡献）**
- 测量每个 expert 的 popularity/stability/burstiness
- 计算跨 trace 的 Spearman rank correlation
- **目标：stability class 跨 trace 一致性 > 0.7**（类比 FlexiCache 的 0.83）
- 分析：stable_hot/bursty_hot/neutral/stable_cold 的比例与层分布

**实验 D：Drift-Injection Benchmark（新方法论贡献）**
- 构造合成 drift trace：混合多个 trace，在时间轴上按比例切换
- 测量静态方案（CRAFT/EPLB）在 drift 下的 imbalance recovery time
- 为 Phase 2 的对比实验建立 baseline 基准
- **这个 benchmark 本身是一个发表贡献**——现有工作都用静态 trace 评估

**实验 E：Libra Two-Stage 在 decode 下的失效分析**
- 模拟 Libra Two-Stage Execution 在 decode（batch 8-128）下的行为
- 测量 MoE_local 窗口时间 vs CPU planner + 权重复制开销
- 目标：实证数据说明"Libra 为何不适合 decode"

**Phase 0 决策门**：
- 若假设 1 不成立 → 放弃方向
- 若假设 2 不成立 → 重新定位（转向 prefill 或改变 story）
- 若假设 3 不成立 → 去掉 stability classification，退化为纯反应式
- 三个都成立 → 继续 Phase 1

### Phase 1：Expert Replication + Stability Prior 原型（5 周）

**目标**：验证 replication 机制，集成 stability classification

**实现**：
1. Load monitor（自强化信号，复用 pplx-garden routing metadata）
2. Error budget trigger（HELIOS CBC 模式）
3. Weight copy via P2P RDMA
4. Routing table atomic update（GPU constant memory）
5. Stability class 集成（启动时加载 offline classification）

**评估**：
- Setup：2-4 节点 × 8 H100（16-32 GPU），Mixtral + DeepSeek-V3-Lite
- **关键 baseline**：
  - CRAFT（static offline plan）
  - CRAFT + periodic re-planning（每 60s 重跑）
  - EPLB
  - Libra（改造为 decode 模式）
  - pplx-garden static EP
- 指标：P99/P50 decode latency、throughput、SLO 违规率、replication overhead（显存、频率）

### Phase 2：完整系统（Consolidation + Migration + Drift）（8 周）

**目标**：三种操作完整实现 + drift-aware 评估

**实现**：
1. Consolidation（合并冷 expert）
2. Migration（跨节点迁移）
3. Estimate-Verify-Commit 协议
4. 去中心化 Controller + gossip 同步
5. 与 SGLang continuous batching scheduler 集成

**评估**：
- Setup：4-8 节点 × 8 H100（32-64 GPU），DeepSeek-V3 full scale
- **真实 workload + drift-injection 两类评估**
- **Ablation**：
  - Replication only（= 手写版 CRAFT dynamic）
  - + Consolidation
  - + Migration
  - + Stability prior
  - + Decentralized controller（vs 中心化）
- 指标：P99 latency、drift recovery time、SLO 违规率、GPU 利用率、跨节点通信量

### Phase 3：论文撰写（4 周）

---

## 七、论文定位与贡献

### 7.1 核心 Claim

> MoE 推理 decode 阶段的 expert 负载分布呈现**既异质又漂移**的特性：跨 trace 存在稳定的 expert stability class（FlexiCache-style 的 model-inherent property），但 workload drift 导致静态方案（CRAFT/EPLB）性能退化。ElasticMoE 提出**基于 stability prior 的事件驱动弹性调度**——在 P2P RDMA 基础上实现 replication、consolidation、migration 三种 expert 级操作，通过 Estimate-Verify-Commit 协议保证 monotone improvement，在 drift-injection benchmark 上 imbalance recovery 比 CRAFT 快 K 倍，多节点 decode P99 latency 降低 X%。

### 7.2 对标论文模式

| 论文 | 核心 insight | ElasticMoE 的类比 |
|---|---|---|
| [[CRAFT-MLSys26]] (MLSys'26) | Per-layer replica budget（static） | Per-expert elasticity（dynamic + multiple ops） |
| [[FlexiCache-MLSys26]] (MLSys'26) | Head stability 作为 model-inherent property | Expert stability classification |
| [[MorphServe-MLSys26]] (MLSys'26) | 离线优先级 + 运行时查表 | Stability class 指导运行时决策 |
| [[BLASST-MLSys26]] (MLSys'26) | 重用已有计算状态做决策 | 复用 pplx-garden routing metadata |
| [[Quake-OSDI25]] (OSDI'25) | Cost-model + estimate-verify-commit | Expert placement adjustment 协议 |
| [[BlitzScale-OSDI25]] (OSDI'25) | Layer-granular live scaling | Expert-granular live scaling |
| Latency-Opt LB (INET4AI) | 搬运代价建模 | P2P RDMA 吸收并压低搬运代价 |
| [[Matrix-MLSys26]] (MLSys'26) | P2P 去中心化编排 | 去中心化 Controller + gossip |

### 7.3 贡献列表

1. **Drift-injection benchmark + 失效分析**：首个 MoE LB 的 drift-aware 评估方法论；实证量化 CRAFT/EPLB 在 non-stationary 负载下的退化
2. **Expert stability classification**：基于 FlexiCache 方法论的首次应用到 MoE expert；跨 trace 稳定性实证
3. **Expert-level elasticity（四维操作）**：Replication + Consolidation + Migration + Auto-scaling（Consolidation 与 Auto-scaling 首次）
4. **Estimate-Verify-Commit for expert placement**：monotone improvement 保证（EPLB、CRAFT 均无此保证）
5. **去中心化 Controller 设计**：解决 >64 GPU 规模下的 orchestration 瓶颈
6. **端到端多节点 MoE decode 系统**：基于 pplx-garden + SGLang，32-64 GPU、DeepSeek-V3 scale 验证

### 7.4 论文结构

1. **Motivation**：(a) agentic 时代 decode 占比主导；(b) workload drift 真实存在的实证；(c) 静态方案（CRAFT）在 drift 下退化；(d) Libra 在 decode 失效
2. **Expert Load Characterization**：stability classification 方法与跨 trace 验证
3. **Design**：四种弹性操作 + Estimate-Verify-Commit 协议 + 去中心化 Controller
4. **Implementation**：pplx-garden + SGLang 多节点集成
5. **Evaluation**：Mixtral + DeepSeek-V3，静态 + drift-injection，vs CRAFT/Libra/EPLB/BLITZSCALE
6. **Analysis**：Ablation + scaling + 稳定性分析

---

## 八、诚实的 OSDI/SOSP 可发表性评估

### 8.1 优势

1. **问题重要且被验证**：MoE 是当下主流架构，decode 是 agentic 时代的延迟主导
2. **三个维度的清晰差异化**：时间尺度（静态 vs 动态）× 操作集（4 vs 1）× 场景（drift vs stationary）
3. **新方法论贡献**：drift-injection benchmark + expert stability classification 是独立于系统实现的方法论创新
4. **monotone guarantee**：EVC 协议是 EPLB 的清晰升级
5. **去中心化架构**：解决真实 scaling 问题，且有 Matrix 等先例支持
6. **与 CRAFT 互补而非替代**：可以叠加运行，evaluation 中可展示组合效应

### 8.2 风险

1. **Phase 0 三层假设**：任一失败整个方案崩盘
2. **CRAFT + periodic re-planning 可能已足够**：必须用实验数据否决这个 baseline
3. **Drift 的真实性**：需要找到真实生产 trace 证明 drift 存在（可能需要与工业界合作）
4. **实验规模**：32-64 GPU 对学术实验室有挑战
5. **Stability classification 的泛化性**：如果不同模型的 stability 表现不同，方法论的普适性受质疑

### 8.3 与"工程优化"的界限

**Q1**：*"CRAFT + periodic re-planning 不就够了？"*

回应：(a) MCKP 每次 ~10s 求解，不支持 ms 级响应；(b) 全量重规划引入不必要的权重搬运（INET4AI 指出的问题）；(c) CRAFT 只有 replication，缺 consolidation/migration；(d) 无 monotone guarantee。Phase 2 必须实现这个 baseline 并用数据说服审稿人。

**Q2**：*"Stability classification 只是 offline profile，没什么深度。"*

回应：(a) 这是 FlexiCache 方法论的首次 MoE 应用，跨 trace 一致性的实证本身是贡献；(b) stability class 不是 placement 决策，而是决策的 prior——两者可分离评估；(c) drift-injection benchmark 让 classification 的价值可量化。

**Q3**：*"去中心化 Controller 在 64 GPU 下必要吗？"*

回应：(a) pplx-garden 论文明确 flag EP>64 的 proxy 瓶颈，中心 Controller 会加剧；(b) 中心化 vs 去中心化在 evaluation 中作为 ablation 对比；(c) 未来 EP=128/256 的趋势下去中心化是必然。

### 8.4 总体判断

| 维度 | 评分 | 说明 |
|---|---|---|
| 问题重要性 | ⭐⭐⭐⭐⭐ | MoE + decode + agentic 都是热点 |
| 新颖性 | ⭐⭐⭐⭐ | 单个机制不新，但四个操作 + stability prior + EVC + 去中心化的**组合**无人做过 |
| 技术深度 | ⭐⭐⭐⭐ | EVC 协议、去中心化 gossip、stability classification 都有足够深度 |
| 方法论贡献 | ⭐⭐⭐⭐ | Drift-injection benchmark + stability classification 可独立发表 |
| 评估说服力（假设 Phase 0 成功） | ⭐⭐⭐⭐⭐ | 真实 + drift workload × 5 个 baseline × ablation |
| 可行性 | ⭐⭐⭐ | 基础设施成熟，但需 32-64 GPU |

**结论**：相比一年前的版本，CRAFT 的出现要求 novelty bar 进一步抬高，但也为 ElasticMoE 提供了**更清晰的对照系**。新定位的核心是把"dynamic"和"elasticity"作为差异化主轴——不再是"做 replication"（CRAFT 已做），而是**"在 drift 下做 replication + consolidation + migration + auto-scaling，且保证 monotone improvement"**。

### 8.5 备选降级路径

若 Phase 0 部分失败：
- **假设 1 失败**（imbalance 不严重）：放弃方向
- **假设 2 失败**（memory-bound）：pivot 到"减少跨节点通信"叙事，转向 migration-centric
- **假设 3 失败**（stability 跨 trace 不一致）：去掉 FlexiCache-style 方法论贡献，退化为反应式系统
- **drift 不显著**：聚焦 auto-scaling 场景（流量突发下的弹性扩缩，BLITZSCALE expert-level 版）
- **若整体未达 OSDI 水准**：降级为 MLSys workshop（drift-injection benchmark + stability classification 单独成文）或 EuroSys
- **若工程价值显著但 novelty 不足**：贡献回 pplx-garden / SGLang 作为开源 feature
