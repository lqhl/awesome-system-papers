# Elastic MoE Serving with P2P RDMA

---

## 一、现状地图：谁做了什么，什么没人做

### 已解决的问题

| 问题 | 已有方案 | 状态 |
|------|---------|------|
| MoE all-to-all 通信效率 | DeepEP（NVLink 优化）、[pplx-garden TransferEngine](../reports/ai-infra/2510.27656v1.md)（P2P RDMA） | 成熟 |
| 集体通信的 padding 浪费 | pplx-garden P2P scatter（精确发送）、MegaBlocks（block-sparse）、X-MoE | 已有多种方案 |
| 通信-计算重叠 | ScheMoE、DeepEP hook mechanism、pplx-garden send/recv 分离 | 已有方案 |
| 边缘/单机 expert offloading | [KTransformers](../reports/sosp-2025/3731569.3764843.md)（Expert Deferral）、MoE-Infinity、Pre-gated MoE | 活跃研究 |

### 未解决的问题（研究空白）

| 问题 | 当前状态 | 为什么难 |
|------|---------|---------|
| **推理时 expert 负载不均** | 训练时靠 auxiliary loss 平衡，推理时无控制手段 | 推理时 routing 由模型决定，不能随意改 |
| **动态 expert placement** | 所有系统用静态 EP（每 GPU 固定 N/EP 个 expert） | 集体通信要求固定拓扑，不支持运行时调整 |
| **Expert 级弹性扩缩** | 只有实例级扩缩（[BLITZSCALE](../reports/osdi-2025/osdi25-zhang-dingyan.md)），没有 expert 级 | 需要 expert 粒度的通信和调度 |
| **跨节点 expert 数量 > 64 的可扩展性** | DeepEP/pplx 都在 64 GPU 后性能下降 | proxy 线程开销、routing 元数据交换成本 |

### pplx-garden 已经解决了什么

[pplx-garden](../reports/ai-infra/2510.27656v1.md) 的 P2P MoE kernel **已经消除了 padding 浪费**——它用 point-to-point scatter 替代 collective all-to-all，每个 token 直接发送给目标 expert，不需要预分配对称缓冲区。

但 pplx-garden **把 expert placement 当作静态输入**。它不决定哪个 expert 在哪个 GPU 上，也不做运行时负载均衡。它只是一个（很好的）通信层。

---

## 二、核心研究问题

> **在 MoE 推理 serving 中，能否利用 P2P 通信的灵活性实现 expert 级别的动态负载均衡和弹性调度，从而在极小或零模型质量损失的前提下大幅降低尾延迟？**

### 为什么这个问题重要

**推理时的 expert 负载不均是一个真实且严重的问题：**

1. **Mixtral 实测数据**（HuggingFace blog）：深层（layer 15, 31）的 expert 选择呈现强烈的 temporal locality，连续 token 高概率选同一批 expert，导致部分 expert 过载
2. **DeepSeek-V3 的设计约束**：将 256 experts 限制到最多 4 节点路由，正是因为跨节点通信代价太大——但这牺牲了路由灵活性
3. **尾延迟放大**：MoE 的每一步延迟由**最慢的 expert** 决定。如果一个 expert 收到 3× 平均 token 数，所有其他 GPU 都在等它

**量化影响**（估算）：

DeepSeek-V3 config：256 experts, top-8, EP=64, batch=128 tokens

- 均匀分布：每 expert 收到 128×8/256 = 4 tokens
- 实际分布（Zipf-like）：热门 expert 可能收到 12-16 tokens，冷门 expert 0-1 tokens
- 最慢 expert 的 GEMM 时间 ∝ token 数，因此 4× 的不均衡 → step 延迟增加 ~4×
- 每层的 expert 计算约 50-100µs → 不均衡导致额外 150-300µs/层

**⚠️ 注意：上述累积估算需要打折。** Mixtral 的实测数据显示 temporal locality 主要集中在深层（layer 15, 31 等），并非所有层都同时出现严重不均。假设 80 层中约 20-30 层出现显著不均（imbalance > 2×），实际累积额外延迟约 3-9ms，而非 12-24ms。仍然显著，但需要 Phase 0 的实证数据来精确量化。

**⚠️ 另一个关键不确定性：decode 阶段小 batch GEMM 是否 compute-bound？** 当单个 expert 只收到 4-16 个 token 时，GEMM 可能是 memory-bound 而非 compute-bound，此时 token 数差异未必线性转化为延迟差异。kernel launch overhead 可能淹没 compute skew。Phase 0 必须包含 micro-benchmark 验证这一点（见实验规划）。

### 为什么 P2P 通信是 enabling technology

| 需求 | Collective (NCCL) | P2P ([pplx-garden](../reports/ai-infra/2510.27656v1.md)) |
|------|-------------------|-------------------|
| 运行时改变 expert 位置 | ❌ 需重建通信组 | ✅ 动态成员管理 |
| 向新 replica 发送 token | ❌ 需全局同步 | ✅ 直接 P2P WRITE |
| 按需发送（无 padding） | ❌ 对称缓冲区 | ✅ per-token scatter |
| 异构 expert 容量 | ❌ 所有 rank 同结构 | ✅ 每个 rank 独立 |

---

## 三、系统设计：ElasticMoE

### 架构总览

```
┌─────────────────────────────────────────────────────┐
│                   ElasticMoE Controller              │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Load     │  │ Placement│  │ Routing           │  │
│  │ Monitor  │→ │ Optimizer│→ │ Table Publisher    │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└─────────────┬───────────────────────┬───────────────┘
              │ placement decisions    │ routing tables
              ▼                        ▼
┌─────────────────────┐  ┌─────────────────────────┐
│ Expert Worker Pool   │  │ Inference Engine         │
│ ┌───┐ ┌───┐ ┌───┐  │  │ (vLLM/SGLang)           │
│ │E0 │ │E1 │ │E0'│  │  │ - Router intercept      │
│ │   │ │   │ │rep│  │  │ - P2P dispatch/combine   │
│ └───┘ └───┘ └───┘  │  │ - pplx-garden backend    │
│    GPU 0   GPU 1    │  └─────────────────────────┘
└─────────────────────┘
```

### 三个核心机制

#### 机制 1：Runtime Expert Load Monitoring

**做什么**：实时追踪每个 expert 每秒收到的 token 数。

**怎么做**：
- pplx-garden 的 dispatch 阶段已经计算了 per-expert token count（routing metadata exchange 阶段）
- 零额外开销地收集这些计数，按滑动窗口（如 100 个 step）统计每个 expert 的 load 分布
- 计算 load imbalance ratio = max_load / mean_load

**关键指标**：
- Per-expert token rate（tokens/step）
- Load variance across experts on same GPU
- Cross-node communication volume

**复杂度**：低。只是统计已有信息，不引入新的通信。

#### 机制 2：Adaptive Expert Placement

**做什么**：当 load imbalance 超过阈值时，调整 expert 到 GPU 的映射。

**三种操作**：

**a) Expert Replication（复制热 expert）**

当 expert E_hot 持续过载时：
1. 选择一个有空闲容量的 GPU（可能在另一节点）
2. 通过 P2P RDMA 将 E_hot 的权重传输到目标 GPU（~50MB for DeepSeek-V3 单 expert，400Gbps 理论带宽下 ~1ms，**实际受 RDMA setup overhead 和 PCIe 竞争影响可能 2-5ms**；批量复制多个 expert 时需考虑带宽竞争）
3. 更新 routing table：发往 E_hot 的 token 按比例分流到两个副本
4. **不需要停止推理服务**——新副本上线后 routing table 原子更新

为什么推理时 replication 很简单：**expert 权重是只读的**。不需要同步写入、不需要一致性协议。两个副本完全独立地处理各自的 token，combine 阶段收集两份输出做加权平均即可。

**b) Expert Consolidation（合并冷 expert）**

当多个 expert 持续空闲（每 step < 1 token）时：
1. 将它们合并到同一 GPU（如果显存允许）
2. 释放空出的 GPU 用于其他 expert 的 replication 或其他模型
3. 通过 P2P 通信将合并后的新位置广播给所有节点

**c) Expert Migration（迁移 expert）**

当某节点的跨节点通信量过大时：
1. 将该节点上频繁与远端通信的 expert 迁移到靠近其 token 来源的节点
2. 减少跨节点 RDMA 流量

**Placement 决策算法**：

借鉴 [Quake](../reports/osdi-2025/osdi25-mohoney.md)（OSDI'25）的代价模型思想：

```
Cost(placement P) = Σ_e [token_rate(e) × (compute_cost(e, gpu(e)) + comm_cost(e, P))]
```

其中：
- `compute_cost` = expert GEMM 时间，与 token 数正相关
- `comm_cost` = token 到 expert 的 RDMA 传输成本，本地为 0，跨节点为 f(bandwidth, latency)

目标：最小化 max-GPU cost（因为 step 延迟由最慢 GPU 决定）。

这是一个 **online bin-packing with migration** 问题，可用贪心启发式求近似解：每隔 K 个 step 检查一次，只在 imbalance ratio > θ 时触发调整。

#### 机制 3：Communication-Aware Token Routing

**做什么**：在模型 router 的 top-K 选择结果中，考虑通信成本做微调。

**关键约束**：不能改变模型的 routing 决策（影响质量），只能在**等价选择**中择优。

**具体策略**：

**a) Replica-Aware Routing（零质量损失）**：当 expert E 有多个副本时，选择负载最低或通信距离最近的副本。数学上同一 expert 的不同副本是等价的。**注意**：不同 batch 组合下 batched GEMM 的浮点误差可能有微小差异，需要实验验证"零质量损失"的 claim（预期差异在噪声范围内，但需要数据支撑）。

**b) Soft Load Balancing（微小质量损失，optional）**：当 expert E 的 affinity score 与第 K+1 个 expert 非常接近（差距 < ε）时，如果 E 的当前队列更长，可以选择第 K+1 个 expert。这**修改了模型的 routing 决策**，引入微小的质量损失换取更好的负载均衡。ε 可调。作为 optional 的 quality-latency tradeoff 提供，不包含在核心 claim 中。

**c) Node-Locality Bias（微小质量损失，optional）**：在 top-K 选择中，为本节点的 expert 加一个小的 bonus（如 +0.01 × affinity），减少跨节点通信。这同样**修改了 routing 决策**。DeepSeek-V3 的 node-limited routing 是这个思想的硬编码版本；我们用 soft bias 实现更灵活的版本。同样作为 optional 提供。

**分层定位**：机制 3a 是核心（零/近零质量损失），3b 和 3c 是可选的 quality-latency tradeoff knob，在 evaluation 中分别测量其影响。

---

## 四、与现有工作的深度对比

### vs. DeepEP

| 维度 | DeepEP | ElasticMoE |
|------|--------|------------|
| 通信原语 | NCCL-like + NVLink 优化 | [pplx-garden](../reports/ai-infra/2510.27656v1.md) P2P RDMA |
| Expert placement | 静态（训练时确定，不变） | 动态（运行时自适应） |
| 负载均衡 | 依赖训练时的 aux-loss | 运行时 replication + routing |
| NVLink 优化 | ✅ token dedup + partial sum | ❌（需要实现，见下文） |
| 弹性 | ❌ 固定 EP degree | ✅ expert 级弹性 |
| 硬件兼容 | 仅 InfiniBand | InfiniBand + AWS EFA |

**诚实承认的差距**：DeepEP 的 NVLink 优化（跨 rank token dedup、partial sum）在 prefill 场景下优势巨大。ElasticMoE 的 P2P 方案在 prefill 时无法做这种优化（因为不知道同节点其他 rank 要发的 token 是否相同）。因此 ElasticMoE 主攻 **decode 场景**，prefill 可 fallback 到 DeepEP。

**DeepSeek-V3 node-limited routing 的影响**：DeepSeek-V3 在模型层面已经限制每个 token 最多路由到 4 个节点，这大幅减少了跨节点通信。这意味着：
- ElasticMoE 的跨节点 expert migration 收益被削弱——模型本身已经做了 locality-aware routing
- ElasticMoE 的主要价值转向**节点内的 expert 负载均衡**和**热 expert 的节点内 replication**
- 对于没有 node-limited routing 的模型（如 Mixtral），ElasticMoE 的跨节点优化收益更大
- Phase 0 需要分别测量 node-limited 和 non-node-limited 模型的负载特征

### vs. FlexMoE / HetuMoE

| 维度 | FlexMoE / HetuMoE | ElasticMoE |
|------|-------------------|------------|
| 目标场景 | 训练 | **推理 serving** |
| 调整粒度 | EP degree（全局统一） | 单个 expert 的 placement |
| 调整频率 | 每 epoch / 手动 | 每秒级自动调整 |
| 通信层 | NCCL | [pplx-garden](../reports/ai-infra/2510.27656v1.md) P2P |

训练和推理的关键区别：训练时可以 drop token（梯度噪声可容忍），推理时不能 drop（影响用户结果）。训练的负载均衡主要靠改 routing，推理的负载均衡必须靠改 placement（不能改模型行为）。

### vs. [KTransformers](../reports/sosp-2025/3731569.3764843.md)（SOSP'25）

KTransformers 做的是 **computation offloading**（expert 在 CPU 上计算）。ElasticMoE 做的是 **communication optimization**（expert 在 GPU 上，但动态调整位置）。两者面向不同部署场景：KTransformers 适用于单机/边缘，ElasticMoE 适用于数据中心多机。

**需要注意的概念重叠**：KTransformers 的 Expert Deferral（将冷 expert 推迟/offload）与 ElasticMoE 的 Expert Consolidation 在动机上高度相似——都是识别冷 expert 并节省资源。关键区别在于：
- KTransformers 将冷 expert 从 GPU offload 到 CPU，目标是减少 GPU 显存占用
- ElasticMoE 将冷 expert 合并到同一 GPU，目标是释放 GPU 用于热 expert replication，优化的是**延迟**而非显存
- KTransformers 是单机视角，ElasticMoE 是分布式多机视角，需要跨节点协调

论文中需要明确讨论这一区别，避免审稿人质疑 novelty。

---

## 五、可行性与风险分析

### 强可行性信号

1. **Expert 权重是只读的**：推理时 expert 不更新权重，replication 是 trivial 的（memcpy 即可），不需要一致性协议
2. **Expert 很小**：DeepSeek-V3 单个 expert ~50MB（7168 × 2048 × 2 bytes × 2 matrices），400Gbps 理论带宽下 ~1ms（实际 2-5ms，受 RDMA overhead 和 PCIe 竞争影响，仍然很快）
3. **[pplx-garden](../reports/ai-infra/2510.27656v1.md) 已提供全部通信原语**：P2P WRITE、dynamic membership、multi-NIC aggregation
4. **Placement 调整频率低**：不需要每个 step 调整，每秒调整一次就够（100 个 step 的统计窗口）

### 关键风险

| 风险 | 严重程度 | 缓解方案 |
|------|---------|---------|
| **推理时负载不均是否真的严重？** | 高 | 必须先跑实验量化。如果 imbalance ratio < 1.5，收益太小不值得做 |
| **负载不均能否转化为延迟差异？** | 高 | Decode 小 batch GEMM 可能是 memory-bound，token count 差异不等于延迟差异。Phase 0 micro-benchmark 验证 |
| **Replication 增加显存开销** | 中 | 单 expert 50MB，复制 10 个 hot expert = 500MB，占 H100 80GB 的 < 1% |
| **Routing table 更新延迟** | 中 | 原子 pointer swap，ns 级；table 在 GPU constant memory 中，广播成本可忽略 |
| **Placement 决策质量** | 中 | 贪心启发式在 online bin-packing 上已有理论保证（2-competitive） |
| **Prefill 场景无法与 DeepEP 竞争** | 高 | 明确定位为 decode-focused 系统；prefill 使用 DeepEP 或 pplx-garden 原有方案 |
| **实验需要 16-64 GPU** | 高 | 必须有 4-8 节点集群。可申请 NVIDIA academic program 或使用云 |

### 最大不确定性：两个层级的验证

这是整个方案的 **make-or-break** 假设，必须在 Phase 0 验证。注意这是**两层**假设，缺一不可：

**假设 1：推理时 expert 负载不均是否足够严重？**

验证方法：
1. 在 vLLM 中跑 DeepSeek-V3 或 Mixtral 推理，记录每个 step 每个 expert 的 token count
2. 使用 ShareGPT 真实对话 trace 作为输入
3. 计算 per-step imbalance ratio 和 per-expert token count 分布
4. 如果 P99 imbalance ratio > 2.0，假设 1 成立

**假设 2：负载不均能否转化为可观测的 wall-clock 延迟差异？**

验证方法：
1. Micro-benchmark 单个 expert 在不同 token count 下的 GEMM latency
2. 如果 4 tokens vs 16 tokens 的延迟差异显著（>30%），假设 2 成立
3. 如果 GEMM 在该范围内是 memory-bound（差异 <20%），则 imbalance ratio 再高也无法转化为延迟收益

**预期结果**（基于 Mixtral 的已有分析）：深层 expert 的 temporal locality 很强，imbalance ratio 在某些层可能达到 3-5×。但需要用真实 serving trace 而非 benchmark 验证，且需要 micro-benchmark 确认延迟可转化性。

---

## 六、实验规划

### Phase 0: 负载特征分析 + Micro-Benchmark（3 周）

**目标**：验证两个核心假设——(1) 推理时 expert 负载不均是否足够严重；(2) 负载不均是否能转化为可观测的延迟差异

**实验 A：负载特征分析**
- 模型：Mixtral 8×22B（8 experts，容易部署和分析）+ DeepSeek-V3-Lite 或 Qwen-MoE（256 experts）
- Trace：ShareGPT、LMSYS-Chat-1M、Perplexity 公开 query logs（如有）
- 在 vLLM 中插桩 MoE routing 层，记录每个 decode step 的 per-expert token count
- 分析指标：
  - Per-step imbalance ratio（max/mean）分布
  - Token count 的 temporal autocorrelation（连续 step 间 expert 选择的相关性）
  - Cross-layer expert co-occurrence（同一 token 在不同层选相同 expert 的概率）
  - **Per-layer imbalance 分布**：区分哪些层严重、哪些层轻微，避免全层累积的过度估算
  - **Node-limited vs non-node-limited 模型对比**：分别测量两类模型的负载特征差异

**实验 B：Expert GEMM Micro-Benchmark（关键！）**
- 在目标 GPU（H100/A100）上，测量单个 expert 在不同 token count（1, 2, 4, 8, 16, 32）下的 GEMM latency
- 使用 DeepSeek-V3 的 expert 维度（7168 × 2048）
- 目标：确认在 decode 场景的典型 token count 范围内，GEMM 是 **compute-bound 还是 memory-bound**
- 如果 4 tokens vs 16 tokens 的延迟差异 < 20%（memory-bound regime），则 expert replication 对延迟的改善有限，需要重新评估方案价值

**关键决策点**：
- 如果 P99 imbalance ratio < 1.5，放弃此方向
- 如果 imbalance ratio > 2× 但 micro-benchmark 显示 GEMM 在该 token count 范围内是 memory-bound（延迟差异 < 20%），需降级为 "减少通信量" 而非 "减少计算延迟" 的故事，或考虑转向 prefill 场景（prefill 的 token count 更大，更容易 compute-bound）

### Phase 1: Expert Replication 原型（4 周）

**目标**：验证 expert replication 对尾延迟的改善

**实验设置**：
- 2-4 节点，每节点 8 GPU（16-32 GPU total）
- Mixtral 8×22B with EP=8
- pplx-garden 作为通信后端

**实现**：
1. Load monitor：收集 per-expert token count（从 dispatch routing metadata）
2. Replication trigger：当 expert 的 token rate > 2× mean 持续 100 步时触发
3. Weight copy：通过 P2P RDMA WRITE 复制 expert 权重到目标 GPU（~1ms）
4. Routing table update：原子更新 GPU memory 中的 expert→GPU 映射
5. Dispatch 修改：查 routing table 做 replica-aware load balancing

**评估**：
- vs. static EP (DeepEP/pplx-garden)：P99 decode latency
- vs. token dropping：精度对比（perplexity, MMLU）
- Replication overhead：显存增量，replication 触发频率

### Phase 2: 完整系统 + 大规模评估（6-8 周）

**目标**：完整的 ElasticMoE 系统 + DeepSeek-V3 scale 评估

**实现**：
1. Expert consolidation（合并冷 expert）
2. Communication-aware routing（soft load balancing, node-locality bias）
3. 与 vLLM continuous batching scheduler 集成
4. 集成 [BLITZSCALE](../reports/osdi-2025/osdi25-zhang-dingyan.md) 式的 live expert migration

**评估**：
- 4-8 节点（32-64 GPU），DeepSeek-V3 配置（256 experts, EP=64）
- 真实 serving trace，varying request rate（突发流量）
- 端到端指标：TTFT, TPOT, throughput, GPU utilization
- vs. DeepEP static EP, vs. vLLM default MoE, vs. Tutel
- Ablation：只 replication / 只 routing / 只 consolidation / 全部组合

### Phase 3: 论文撰写（4 周）

---

## 七、论文定位与贡献

### 核心 Claim

> MoE 推理 serving 中，expert 负载不均是尾延迟的主要来源。利用 P2P 通信的灵活性，ElasticMoE 首次实现了运行时 expert 级弹性调度——动态复制热 expert、合并冷 expert、通信感知路由——在零或极小模型质量损失的前提下将 P99 decode latency 降低 X%。

### 对标论文

| 论文 | 会议 | 核心 insight | ElasticMoE 的类比 |
|------|------|-------------|------------------|
| DistServe | OSDI'24 | Prefill/decode 应分离 | MoE expert 应弹性放置 |
| [Quake](../reports/osdi-2025/osdi25-mohoney.md) | OSDI'25 | 向量索引应自适应维护 | Expert placement 应自适应调整 |
| [BLITZSCALE](../reports/osdi-2025/osdi25-zhang-dingyan.md) | OSDI'25 | 模型加载可逐层 live | Expert 迁移可在线完成 |
| [Skybridge](../reports/osdi-2025/osdi25-lyerly.md) | OSDI'25 | 弱化局部保证以强化全局 | 允许 expert 不均匀分布以优化全局延迟 |

### 贡献列表

1. **首次量化了 MoE 推理时 expert 负载不均的严重程度**（empirical study, Phase 0 的数据）
2. **Expert replication/consolidation/migration 的在线算法**，基于代价模型的 placement 优化
3. **Communication-aware routing**：在不损失模型质量的前提下减少跨节点通信
4. **端到端系统实现**：基于 [pplx-garden](../reports/ai-infra/2510.27656v1.md) P2P RDMA + vLLM，支持 256-expert scale

### 论文结构

1. **Motivation**：量化推理时 expert 负载不均（Phase 0 数据）→ 尾延迟瓶颈
2. **Background**：MoE 通信模型、P2P vs collective、pplx-garden 能力
3. **Design**：Load monitor + Placement optimizer + Communication-aware routing
4. **Implementation**：基于 pplx-garden + vLLM 的系统实现
5. **Evaluation**：Mixtral + DeepSeek-V3 config，真实 trace，端到端对比
6. **Analysis**：各机制的贡献分解、开销分析、极端场景

---

## 八、诚实的 OSDI/SOSP 可发表性评估

### 优势

1. **问题真实且重要**：MoE 是当前 LLM 的主流架构（DeepSeek-V3/R1, Mixtral, Qwen-MoE），推理效率直接影响成本
2. **核心 insight 非 trivial**：expert placement 应该是动态的而非静态的，这与当前所有 production 系统的假设相反
3. **完整的系统故事**：从问题发现（负载不均量化）→ 方案设计（三个机制）→ 系统实现 → 端到端评估
4. **站在 [pplx-garden](../reports/ai-infra/2510.27656v1.md) 肩膀上**：P2P 通信层已经解决，研究聚焦在上层调度策略
5. **评估故事可以很强**：如果 Phase 0 验证了负载不均严重（imbalance > 2×），P99 延迟改善可以很显著

### 风险

1. **如果负载不均不严重**（Phase 0 失败），整个方案没有立足点。这是最大风险。
2. **DeepEP 在 prefill 上的 NVLink 优化是硬优势**，ElasticMoE 在 prefill 上无法竞争，必须明确定位为 decode-focused
3. **实验规模**：需要 32-64 GPU，对学术实验室有挑战。但比训练论文（通常需要数百 GPU）低一个量级
4. **[pplx-garden](../reports/ai-infra/2510.27656v1.md) 的 64-GPU scaling 限制**：proxy thread 瓶颈可能影响大规模评估

### 与"工程优化"的界限

审稿人可能质疑：*"这只是在 [pplx-garden](../reports/ai-infra/2510.27656v1.md) 上加了一层调度策略。"*

**回应**：
- Phase 0 的 empirical study 本身就是贡献（首次量化 MoE 推理时负载不均）
- Expert replication 在推理场景的 trivial 特性（只读权重→无需一致性）是一个 insight
- Communication-aware routing 涉及 quality-latency tradeoff 的系统性分析
- 整体设计是 "MoE 推理的资源管理应从实例级下沉到 expert 级" 这一新抽象

### 总体判断

| 维度 | 评分 | 说明 |
|------|------|------|
| 问题重要性 | ⭐⭐⭐⭐⭐ | MoE 推理效率是当下最热点问题之一 |
| 新颖性 | ⭐⭐⭐⭐ | 动态 expert placement + P2P 是新组合；但各组件独立不新 |
| 技术深度 | ⭐⭐⭐ | 调度算法 + 系统集成，但无根本性的新原语 |
| 评估说服力（如果 Phase 0 成功） | ⭐⭐⭐⭐ | 端到端真实 workload + 大规模 MoE 模型 |
| 可行性 | ⭐⭐⭐⭐ | 基于成熟开源组件，但需 32-64 GPU |

**结论：有机会冲 OSDI/SOSP，但成功与否取决于 Phase 0 的实证数据。** 如果推理时的 expert 负载不均确实严重（imbalance > 2×），这是一篇有竞争力的系统论文。如果不均不严重，应果断转向。

### 备选降级路径

如果 Phase 0 显示负载不均不够严重：
- **降级为 workshop paper**（MLSys workshop, EuroSys workshop）：报告 "MoE 推理时的 expert 负载特征分析"
- **转向弹性扩缩**：用 P2P RDMA 做 expert 级别的弹性扩缩容（需求变化时增减 expert 副本），不依赖负载不均假设
- **贡献给开源社区**：将 pplx-garden MoE kernel 集成到 vLLM/SGLang 作为工程贡献
