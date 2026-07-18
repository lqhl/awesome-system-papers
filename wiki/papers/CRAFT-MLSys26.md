---
type: paper
name: CRAFT
full_title: "CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations"
authors: [Adrian Zhao, Zhenkun Cai, Zhenyu Song, Lingfan Yu, Haozheng Fan, Jun Wu, Yida Wang, Nandita Vijaykumar]
venue: MLSys
year: 2026
tags: [moe, expert-parallelism, load-balancing, llm-serving, expert-replication]
source_pdf: "[[17e62166fc8586dfa4d1bc0e1742c08b.pdf]]"
source_md: "[[17e62166fc8586dfa4d1bc0e1742c08b]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations (MLSys 2026)

> **一句话总结**：在 [[MoE]] + [[Expert-Parallelism]] 部署中，均匀 expert replication（EPLB）因 per-layer 收益差异大且 balancedness 随 replica 数 sublinear 递减而严重过度复制、挤占 [[KV-Cache]]；CRAFT 用离线 load replay 估计 per-layer replication benefit，再以 MCKP 动态规划在显存预算内做 layerwise 分配，在 DeepSeek-R1-671B / Kimi-K2-1000B 上 vs EPLB 平均 goodput **1.14×**（最高 **1.2×**），replica 数少 **7.25–7.5×**，初始化开销约 **10 s**、推理零额外开销。

## 问题与动机

大规模 [[MoE]] LLM 推理普遍采用 [[Expert-Parallelism]]（EP）：专家权重分片到多 GPU，token 经 all-to-all dispatch/combine 路由到对应 expert。Router 的 top-K 选择与输入 token 的 Zipfian 分布使少数 **hot expert** 承担远超平均的 token load，造成 GPU 级负载不均——冷卡空转、热卡成为瓶颈，all-to-all 流量也高度偏斜。Expert placement 通过 hot/cold 共置缓解不均，但在单层内少数 expert 主导绝大部分 load（高 skew）时，placement 无法消除峰值。

**Expert replication** 复制 hot expert 权重、把 token 分散到多个副本，是 [[SGLang]]、[[vLLM]]、TensorRT-LLM、DeepSpeed-MoE 等框架中广泛采用的第二层手段。业界主流 **EPLB**（Expert Parallelism Load Balancer）采用 **uniform replication**：每 GPU 每层预留 1 个 replica slot，在 60 层 MoE、千亿参数模型上 replica 总数达 `L × D`，显存开销巨大。大规模 serving 本就受参数与 [[KV-Cache]] 双重挤压，过度 replication 会缩小 batch 与并发上限，反而拉低吞吐。

论文的核心 claim 是：现有 replication 方案在 **memory–balancedness trade-off** 上严重次优——大量 replica 边际收益极小，而高 skew 层仍 replica 不足。CRAFT 提出 **cost-aware、per-layer 粒度** 的 replica 分配，在固定 replication 显存预算下最大化负载均衡收益，并无缝替换 EPLB，无需重训或改模型。

## 关键观察 / 隐含假设

- **观察 1：各 MoE 层对 replication 的收益差异极大，可粗分为 high-skew（replication-effective）与 low-skew（replication-ineffective）两类。** 以 Kimi-K2 @8 节点为例，layer 20 的 peak-to-mean load 仅约 2.5×，placement 后 balancedness 已高；layer 51 最热 expert 负载 >27× 平均、top-2 expert 占约 20% 总 load，placement 无法削峰，replication 显著改善 balancedness（Fig. 3–4）。Fig. 6 显示 layer 20 几乎不受益，而 layer 11/12/51 的 plateau 点分别为 1/8/16 replicas。
  - **依赖假设**：离线 profiling 的 expert load 分布能代表线上推理；各层 skew 模式在 profiling 窗口内相对稳定。
  - **可能失效场景**：prompt 分布剧变（新语言、工具调用、多模态）、routing 策略更新、或 tenant 混合导致 per-layer skew 重排时，离线 benefit 矩阵会过时；shared expert、expert grouping（如 GraceMoE）改变 load 形态。

- **观察 2：Balancedness 随 per-layer replica 数 sublinear 增长，超过约 16 replicas/layer 后收益可忽略，但 uniform replication 仍按 `L×D` 分配。** Fig. 5 显示各配置下 replica 翻倍超过 16 后 aggregated balancedness 几乎平坦，却双倍占用 expert 显存。EPLB 在 Kimi-K2 @64 GPU 上配置 60 replicas/GPU（每层每层 1 个），远超有效区间。
  - **依赖假设**：balancedness（avg load / max load）与端到端 goodput 强相关；KV cache 缩减带来的并发损失可用 goodput knee point 量化。
  - **可能失效场景**：decode 阶段 batch 很小、collective latency 主导时，balancedness 改善对 ITL 影响有限（论文 Appendix C 显示 ITL 与 BASE/EPLB 相当，但 prefill-heavy 场景才是主战场）；expert sharding 等替代并行策略改变瓶颈定义。

- **观察 3：集群规模增大时 placement-only baseline 恶化，replication 相对价值上升。** 6→12 节点时每 GPU 持有 expert 数减少，hot/cold 共置机会变少，baseline balancedness 下降（Fig. 3）。KA 配置在 6 节点已较均衡，12 节点时 placement 失效、replication 成为必要手段。
  - **依赖假设**：模型规模固定、仅扩 GPU 数；EP 分片策略不变。
  - **可能失效场景**：随集群扩大同时增加 DP rank 与 batch，或采用 disaggregated prefill/decode 改变 token 分布；跨节点 expert 放置优化（ExFlow、MoETuner）可能部分替代 replication 需求。

- 观察 4：过度 replication 会通过压缩 KV cache 直接伤害 goodput，小集群上 EPLB 甚至慢于无 replication baseline。 K\*6 上 EPLB 使 KV cache 减少 75%，goodput 低于 BASE（Fig. 9）；D\*8/K\*12 分别减 19% / 24%。CRA 在 far fewer replicas 下保留大部分 balancedness gain。
  - **依赖假设**：KV cache 容量是 goodput 的 binding constraint；replica 与 KV 争用同一 GPU HBM。
  - **可能失效场景**：[[Disaggregation]]、CPU/offload KV、或极大 batch 使 compute 而非 memory 成为瓶颈时，replication 的 KV 代价权重下降。

- **假设 1：离线 expert load 分布（3000 batch、随机采样 profiling 序列）可泛化到评测流量，且 profiling 序列与评测输入不重叠即可避免泄漏。**
  - **证据强度**：中。论文明确排除 profiling 序列出评测集，但仅 4 个数据集、固定 4096+256 长度，未测 production trace 漂移或 periodic rebalancing 闭环效果。

- **假设 2：per-layer replication benefit 可近似为独立可加，用 MCKP（每层选一个 replica count）即可逼近全局最优。**
  - **证据强度**：中。动态规划在 replay 上验证有效，但未与穷举或在线 adaptive replication（SwiftMoE 类）对比；层间 routing 相关性未建模。

## 核心方法

CRAFT 是端到端 **benefit-driven replica allocation** 框架，直接替换 EPLB，分三阶段：

**1. Per-layer replication benefit 估计（离线）**
对每层在 `K = log₂D + 1` 个 base-2 几何级数 replica count 上，replay 离线 load 分布 `W`（shape `B×L×E`），用与 EPLB 类似的 greedy placement 计算 balancedness gain，得到收益矩阵 `T`。Placement-only baseline 作为零 replica 参照。初始化约 **10 s**，可与 periodic rebalancing 重叠到 CPU。

**2. Replication factor R 选择**
`r = R × D` 为总 replica 预算。用户可手动设 R 满足显存约束；或 CRAFT 自动选 **per-replica balancedness gain 最高** 的 R，避开边际递减区（对应 Fig. 5 拐点）。实验显示 **R=8** 在多数配置下 goodput 最优。

**3. MCKP 最优 per-layer 分配**
在总容量 `C = r` 约束下，每层从 `{0} ∪ R` 选一个 replica count，最大化 `Σ T[r][ℓ]`。问题为 Multiple-Choice Knapsack，NP-hard 但 `L、D、K` 小，动态规划 `O(L·C·K)` 可解。高 skew 层分到更多 replica，已均衡层分到 0。

**4. Capacity-aware expert assignment & placement**
Per-layer replica 数不均时，需保证各 GPU **expert capacity 一致**（否则 DP rank 内 KV cache 大小不一致、最大并发由最小 cache 决定）。贪心策略：Primary——新 replica 分给当前 expert 数最少的 GPU（保证 `r` 为 `D` 的倍数时最终各卡容量齐）；Secondary——并列时 **interleaved** 跨 node 分配以平衡节点级容量。最后对每层执行标准 greedy placement（最 loaded expert → least loaded device），与 EPLB 一致但尊重 per-GPU capacity 上界。

无需修改 router 或训练；集成于 **SGLang v0.4.8**，替换 EPLB 模块。与 topology-aware placement（ExFlow、Occult）、expert grouping（GraceMoE）正交，可替换 greedy placement 步骤。

## 设计取舍

- **离线规划 vs 在线 adaptive replication**：赢得可预测的显存预算与零推理开销，代价是 workload 漂移时需 re-profiling / periodic rebalancing；论文提及在线重平衡但未作为主实验路径。
- **Per-layer 粒度 vs per-expert 粒度**：layer 级分配降低优化维度、使 MCKP 可解，但同一层内多个 hot expert 无法差异化复制次数；EPLB 的 uniform per-layer 已比 per-expert 粗，CRAFT 在 layer 维精细、层内仍靠 placement 分流。
- **Balancedness 代理目标 vs 端到端 latency**：优化 balancedness gain 而非直接优化 TTFT/goodput，依赖观察 4 的相关性；省去在线试错，但代理目标在 decode-heavy 或网络 bound 场景可能偏离。
- **整除约束 `r = R×D`**：简化 KV cache 对齐与实现，但可能略浪费 replica slot；作者认为 `R=1` 时开销仍可接受。
- **边界条件**：在 **大规模 EP MoE + 高 skew workload + KV 紧张** 下最优雅；低 skew 数据集上 replication 本身收益有限，CRAFT 相对 BASE 约 **1.14×**、相对 EPLB **1.02×** 仅微幅领先。小集群（6 节点）KV 极紧时 EPLB 灾难性退化，CRAFT 优势最大。

## 实验与结果

**设置**：AWS p4de.24xlarge（8× A100-80GB/节点，NVLink + EFA P2P）；CUDA 12.8 / NCCL 2.26.2；SGLang v0.4.8 + DP + TP-attention + EP。模型：DeepSeek-R1-671B（58 MoE 层、256 experts）、Kimi-K2-1000B（60 MoE 层、384 experts），top-8 routing，bfloat16。Workload：FinePDFs（德 E、日 J）、LAMBADA L、RedPajama arxiv A；输入 4096、输出 256 tokens。集群 6/8/12 节点。Baseline：BASE（placement only）、EPLB（每 GPU 每层 1 replica）、CRA8（CRAFT，R=8）。

- **Goodput**（8 节点）：vs EPLB 平均 **1.14×**，最高 **1.2×**；DeepSeek **1.15×**（最高 1.2×），Kimi **1.12×**（最高 1.17×）。CRA8 使用 replica 数为 EPLB 的 **1/7.25**（D）和 **1/7.5**（K）。
- **TTFT**：CRA8 vs BASE 平均降 **29%**（最高 58%），与 EPLB（30%，最高 59%）接近。
- **数据集 skew**：高 skew（E/J）CRA8 vs BASE **1.42×** goodput；低 skew（L/A）**1.14×**。EPLB 在高/低 skew 分别为 **1.24×** / **1.02×**。
- **小集群**：6 节点 EPLB goodput 平均比 BASE 低 **46%**；CRA8 仍比 BASE 高 **1.14×**，KV cache 仅减 **6%**（vs EPLB **75%**）。
- **扩展性**：6→8 节点 CRA8 goodput 平均 **1.65×**，8→12 **1.6×**，优于 EPLB。
- **R sweep**：过小 R 负载不均未解，过大 R KV 压缩抵消收益；R=8 在多数配置最优（Appendix B）。
- **开销**：推理零额外开销；ITL 与 BASE/EPLB 相当（Appendix C）。初始化 benefit 估计约 **10 s**。

## Critical Analysis

### 论证链条

链条结构为：**测量** uniform replication 的 sublinear balancedness 收益与 per-layer skew 差异（§3.2–3.3）→ **机制** 过度 replica 挤占 KV cache、小集群上 goodput 可低于 baseline（§5.3）→ **设计** 用离线 replay + MCKP 在预算内把 replica 倾斜到 high-benefit 层 + capacity-aware 分配保 KV 对齐（§4）→ **结果** 更少 replica 达到相近 balancedness，goodput/TTFT 全面优于 EPLB。

最强证据是 Fig. 5/6/9 将 **balancedness–memory trade-off** 与 **goodput knee point** 联立，解释为何 EPLB 在 K\*6 反而慢于 BASE。最弱环节是把 offline balancedness gain 最大化直接等同于 serving 最优，中间依赖「balancedness ↔ prefill 效率 ↔ goodput」链条，decode 路径验证较薄。

### 假设压力测试

**Workload**：4 个文本数据集、固定长度；未覆盖 agent 多轮、代码生成、多模态或极端长尾 prompt。若线上 skew 随时间漂移，静态 MCKP 解需 periodic rebalancing——论文一笔带过，未量化漂移多快会使 benefit 矩阵失效。

**硬件/规模**：仅 A100 + AWS p4de；未测 H100/B200、不同 NVLink/EFA 拓扑，或 expert sharding 混合 EP。万亿参数模型已大，但仍是 6–12 节点；超大规模 pod 的 placement 与 all-to-all 成本可能改变 replica 最优策略。

**部署**：假设 co-located prefill+decode、mixed chunked prefill（chunk 4096）。与 [[Disaggregation]]、[[Prefix-Caching]]、speculative decoding 的组合未测。Amazon 作者背景暗示生产动机，但评测仍是学术 trace + Poisson 式 batch 负载。

**模型**：仅 2 个 top-8 MoE LLM；shared expert、不同 K 值、训练期 adaptive replication 的迁移性未验证。

### 实验可信度

优点：baseline EPLB 是业界事实标准；指标覆盖 goodput（knee point）、TTFT、ITL、balancedness、KV 占用；多集群规模与多数据集；profiling/eval 输入分离。

限制：**无** expert-placement-only SOTA（ExFlow、MoETuner、Occult）或 expert sharding（Balmau et al.）作强 baseline；**无** 在线 workload 漂移实验；goodput 定义依赖 TTFT knee，对 ITL/TBT SLO 产品约束的覆盖不足。R=8 是事后选取的最优操作点，跨模型自动选 R 的鲁棒性仅在 Appendix B 部分展示。

### 系统性缺陷

- **Workload 适应性**：核心依赖离线 profiling；冷启动、tenant 切换、模型热更新后的 replan 频率与成本，论文未系统讨论。
- **尾延迟与公平性**：聚焦 goodput knee 与 mean TTFT，未深入 p99 TTFT/TBT 或跨请求公平性；replication 改变 all-to-all 模式对 tail 的影响未隔离。
- **可观测性与运维**：per-layer 异构 replica 计划使调试「哪层、哪卡 hotspot」更复杂；论文未讨论。
- **故障恢复**：GPU 掉线或 expert 重映射时 CRAFT plan 如何增量更新，论文未讨论。
- **正确性**：replication 不改变语义，但 placement 错误会导致 silent wrong routing；论文假设 greedy placement 正确性继承 EPLB。

## 局限与 Future Work

- **局限 1**：评测限于 2 个 MoE LLM、4 个数据集、6–12 节点 A100 集群；未覆盖 disaggregation、多租户 production trace、在线 routing 漂移。
- **局限 2**：优化目标是 offline balancedness gain 而非直接端到端 latency；decode-heavy 或网络-bound 场景外推需谨慎。
- **局限 3**：与 topology-aware placement、expert grouping、expert sharding 的联合优化仅停留在 related work 层面，未实验量化。
- **局限 4**：Periodic rebalancing、profiling 开销与 workload 变化速率的闭环行为未作为主结果。

- **Future work 1**：在 production trace 上测量 expert load 漂移半衰期，对比「静态 CRAFT plan」vs periodic re-profiling 的 goodput–overhead Pareto。
- **Future work 2**：将 CRAFT per-layer replication 与 ExFlow/MoETuner 类 placement IP 或 GraceMoE grouping **联合求解**，量化通信量减少是否进一步放大 replication 收益。
- **Future work 3**：在 H100/B200、更大集群与 [[Disaggregation]] 部署下复现 KV–replica trade-off，验证 R 自动选择与 balancedness 代理是否仍成立。
- **Future work 4**：细粒度到 per-expert replication（在层内 skew 极高时）是否能在可控 MCKP 规模下 beat layerwise 分配。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[KV-Cache]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、[[Tensor-Parallelism]]、[[Disaggregation]]
- **同类系统**：[[SGLang]]、[[vLLM]]、EPLB、ExFlow、MoETuner、GraceMoE、FasterMoE、SwiftMoE
- **同会议**：[[MLSys-2026]]、[[MoEBlaze-MLSys26]]、[[LayeredPrefill-MLSys26]]、[[MixLLM-MLSys26]]
- **对比**：CRAFT 与 [[LayeredPrefill-MLSys26]] 同属 MoE serving 内存压力主题，但前者优化 **EP 负载均衡下的 expert replica 预算**，后者优化 **chunked prefill 导致的 expert 重复加载**；与 [[MoEBlaze-MLSys26]]（训练侧 activation/routing buffer）互补，均指向 MoE memory wall
