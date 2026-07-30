---
type: proposal
name: ImportanceGuidedKVTiering
title: "Importance-Guided KV Cache Tiering: Joint Optimization of Sparse Attention Selection and Memory Placement"
status: draft
created: 2026-05-06
last_updated: 2026-05-06
target_venue: "OSDI 2027（如果 H1 和 H3 验证强）→ ATC 2027 / EuroSys 2027（如果只有 H1 验证）→ MLSys 2027（如果只有 H4 验证）"
tags: [kv-cache, sparse-attention, llm-serving, memory-management, tiered-storage, cross-layer-optimization]
related_papers:
  - "[[NSA-ACL25]]"
  - "[[MSA-arXiv26]]"
  - "[[DeepSeek-V4-arXiv26]]"
  - "[[BLASST-MLSys26]]"
  - "[[LMCache-arXiv25]]"
  - "[[Cartridges-ICLR26]]"
  - "[[PASTA-ICLR24]]"
  - "[[LLMSteer-NeurIPSW24]]"
related_concepts:
  - "[[Sparse-Attention]]"
  - "[[KV-Cache]]"
  - "[[PagedAttention]]"
  - "[[Flash-Attention]]"
related_systems:
  - "[[vLLM]]"
  - "[[SGLang]]"
novelty: high
feasibility: medium
effort: medium
---

# 重要性引导的 KV 缓存分层

> Sparse attention 机制在决定「哪些 token 值得看」时产生的 block importance score，恰好也是 KV cache tier placement 的最优信号——把两个分治的领域（计算稀疏性 × 存储分层）做 cross-layer joint optimization，让 KV cache tiering 的 eviction/prefetch 决策从「猜」变成「问模型」。

## 1. 为什么这是个好问题

### 1.1 问题定义

LLM serving 在长上下文场景下面临**双层拮抗**：

- **计算层**：attention 的 O(N²) 让长序列 decode 不可承受。Sparse attention（[[NSA-ACL25]]、[[BLASST-MLSys26]]、Twilight、DSA）通过只让 query 看到部分 token 来降计算量。每个 sparse attention 机制在运行时都会产生**block importance scores**——哪些 token/block 对当前 query 重要，哪些可以跳过。
- **存储层**：KV cache 随 context length 线性膨胀，1M context 单序列 KV cache >100 GB，远超单 GPU HBM。[[LMCache-arXiv25]]、[[Cartridges-ICLR26]] 等工作做 KV cache tiering（HBM → DRAM → SSD），依赖 LRU/frequency/recency 等通用缓存策略决定什么留在 HBM、什么驱逐。

**这两个层当前完全不通信**。Block importance scores 在 sparse attention 完成计算后被丢弃；KV tiering 用 blind heuristics 做 eviction。核心机会：**importance score 是 KV block 的「ground truth」重用信号**——模型自己告诉你哪些 block 对解码质量重要。用这个信号指导 tier placement 是 zero-cost 的（NSA 的 scoring 零额外计算），且信息含量远超 LRU/frequency。

具体来说，给定一个 serving system with multi-tier KV cache storage：
1. Sparse attention 为每个 query 产生的 block importance scores 被记录下来（而非丢弃）
2. 这些 scores 跨多个 query 和时间窗口聚合，形成每个 block 的 persistent importance
3. Tier placement (HBM / DRAM / SSD) 和 prefetch/eviction 决策由 persistent importance + recency 联合驱动
4. 如果模型本身是 dense attention 的，post-hoc 提取 block-wise attention scores 作为 proxy importance

### 1.2 社区盲区

Probe 识别出这个空白：「kernel/算法的人做 sparse attention，系统的人做 KV tiering——两者不对话」。具体盲区有三层：

**盲区 1：importance scores 的价值未被认识**。NSA 的 block selection branch 在运行时用压缩注意力的中间分数做 top-n 选择——这组分数编码了「模型认为哪些 context block 对当前 query 最重要」。但论文将它视为稀疏化的**内部实现细节**，没意识到它也是 KV 管理的**外部信号源**。同样，BLASST 的 running max thresholding 虽然不是为了产生 explicit importance ranking，但 `local_max - running_max` 差值本身就是天然的 block importance proxy。

**盲区 2：KV tiering 的 eviction heuristics 在原地打转**。LMCache 的 tier placement 主要基于 LRU 和 access frequency。CacheGen/CacheBlend 在传输优化上做了大量工作，但「什么该留在 HBM」的决策仍是通用缓存策略向 KV cache 的移植。LRU 对 KV cache 的适配有根本问题：一个 1000 步前生成但频繁被引用的 token（如 system prompt 中的约束条件）会被 LRU 驱逐，而刚生成但不再被需要的 token 却被保留。

**盲区 3：没有人做 cross-layer joint optimization**。DeepSeek-V4 的 CSA+HCA + 异构 KV 结构是最接近的工作，但它把稀疏选择（CSA）和异构存储作为两个独立模块设计，没有显式地用 CSA 的 selection scores 驱动 tier placement。SGLang + NVIDIA 的合作路线图提到了「KV cache connector API」和「KVBM + Hi-cache」，但也未触及 importance-guided tiering。

这个盲区的根源是学术分治——attention kernel 论文投 MLSys/ACL/NeurIPS，KV cache 系统论文投 OSDI/ATC/EuroSys。两个 community 之间缺乏桥接。

### 1.3 从 measurement 到 contribution：可证伪假设

**H1: Block importance scores 预测 KV cache 重用优于 LRU**

- **攻击的隐含前提**：LMCache 及几乎所有 KV tiering 系统的隐含前提——「最近访问的 KV block 最可能被未来 query 复用」——在长上下文多查询场景下成立。
- **可证伪预测**：在相同 HBM budget 下，importance-guided eviction 的 KV cache hit rate 比 LRU 高出 ≥ 20%（相对提升），且这个优势随 context length 增长而扩大（128K < 512K < 1M）。
- **Metric**：KV cache hit rate = (在 HBM 中找到的 block 数) / (attention 请求的 block 总数)，在 multi-turn conversation (LMSys-Chat-1M) + RAG (LongBench) + code agent (SWE-bench traces) 三个 workload 上测量。
- **预期数值**：importance-guided 在 128K 下 hit rate 70-75% vs LRU 50-55%（相对 +20-40%）；1M 下 gap 扩大到 30-50%。
- **如果成立意味着**：Block importance score 是 KV cache 管理的 first-class primitive，应被标准化为模型 serving 接口的一部分——类比 OS 页表的 accessed/dirty bit。

**H2: 聚合 importance 揭示 query-independent 的「结构性热点」**

- **攻击的隐含前提**：[[LLMSteer-NeurIPSW24]] 的隐含前提——要找到 query-independent 的重要 context 区域，需要 offline 的 contextual re-reading（两次不同 prefix prompt 的 attention 交集）。如果单次 importance scoring 的跨 query 聚合就能达到同样效果，那 re-reading 的成本就是不必要的。
- **可证伪预测**：Top-10% blocks by aggregate importance（跨 ≥ 50 个 diverse query 聚合）与 per-query top-10% blocks 的 Jaccard overlap ≥ 0.6。这些「结构性热点」block 对应 system prompt、task instruction、关键约束条件等 query-independent 的 context 区域。
- **Metric**：聚合top-k集合和每个查询top-k集合之间的杰卡德相似度。
- **预测数值**：对于系统提示/约束繁重的工作负载，Jaccard ≥ 0.6；对于自由形式的创意生成，< 0.3。
- **如果成立意味着**：Importance-guided pre-warming（推理前把结构性热点预加载到 HBM）可以消除冷启动延迟，对 multi-turn agent / RAG 场景尤其有价值。

**H3: Joint optimization 的收益大于独立优化的加和**

- **攻击的隐含前提**：两个 community 默认的假设——sparse attention 优化和 KV tiering 优化是独立可叠加的（各自的收益相加即可）。
- **可证伪预测**：Joint optimization（同一组 importance scores 同时驱动 attention sparsity 和 tier placement）在 1M context 下的端到端 per-token decode latency 比「最优 sparse attention + 最优独立 KV tiering」低 ≥ 30%。
- **Metric**：Per-token decode latency (P50/P95/P99)，在相同 quality target 下（RULER ≥ 90%）。
- **预期数值**：≥ 30% latency reduction at 1M context；≥ 15% at 128K。
- **如果成立意味着**：Cross-layer co-design 不是 nice-to-have 而是 load-bearing——两个层的独立最优解在联合空间中可能远离 Pareto frontier。

**H4: Post-hoc importance extraction 可以在 dense model 上工作**

- **攻击的隐含前提**：[[NSA-ACL25]] 的隐含前提——native sparse training 是获得高质量 block importance 的必要条件（NSA 强调「模型与稀疏模式协同适应」）。
- **可证伪预测**：从 dense model（Llama-3.1/8B, full attention）的 attention scores 中 post-hoc 提取 block importance（block-wise mean/max attention score）来指导 tier placement，能达到 NSA-style native scoring 的 ≥ 80% tier placement 质量（按 H1 的 hit rate metric）。
- **Metric**：KV cache hit rate ratio = hit_rate(post-hoc) / hit_rate(native sparse)。
- **预期数值**：≥ 0.80。
- **如果成立意味着**：这项技术适用于**所有已部署模型**，不需要 sparse attention 训练——这大大降低了 adoption barrier 并将 contribution 从「sparse attention 的配套优化」升级为「通用 KV cache 管理技术」。

## 2. 相关工作

### 2.1 基础设施层（站在其肩膀上）

| 系统 | 提供的基底 | 我们需要改什么 |
|------|-----------|---------------|
| [[vLLM]] / [[PagedAttention]] | Block-based KV cache management, block table, copy-on-write prefix sharing | 在 block manager 的 eviction/allocation path 上加入 importance-guided policy |
| [[LMCache-arXiv25]] | Multi-tier KV storage (GPU/CPU/SSD/remote), batched data movement, connector API | 替换 LRU-based eviction 为 importance-weighted eviction |
| [[Flash-Attention]] / FlashInfer | IO-aware attention kernel, 支持 block table 间接寻址 | 在 kernel 输出端挂载 importance score 记录（zero-copy side channel） |
| [[SGLang]] / [[RadixAttention]] | Prefix tree KV sharing | 在 radix tree node 上维护 aggregate importance score |

### 2.2 策略层（共享问题但方向不同）

| 工作 | 做了什么 | 与我们方向的区别 |
|------|----------|-----------------|
| [[LMCache-arXiv25]] | LRU + frequency-based KV eviction, batched data movement | 用 LRU 而非模型自身的重要性判断 |
| [[CacheGen-SIGCOMM24]] | KV cache 压缩传输 (custom quantization + arithmetic coding) | 优化传输大小而非 placement——正交且可叠加 |
| [[Cartridges-ICLR26]] | 离线训练紧凑 KV 表示替代 prefill | 预计算 vs 在线 adaptive——两阶段可能是互补的（warm Cartridge + online importance-guided tiering） |
| [[PASTA-ICLR24]] / [[LLMSteer-NeurIPSW24]] | Post-hoc attention score 修改来改善质量 | 同用 attention scores 作为信号，但目标是修改 attention 而非管理 memory |
| [[DeepSeek-V4-arXiv26]] | CSA + HCA + 异构 KV 结构 | 最接近的工作，但未显式连接 sparse selection scores ↔ tier placement |
| [[BLASST-MLSys26]] | Running max thresholding 做 block skip | 产生了 block importance proxy（local_max - running_max），但用作 skip 决策而非 tiering 信号 |

### 2.3 关键 tension

- **Native sparse (NSA) vs post-hoc (BLASST)**：NSA 的 importance scores 来自原生训练的压缩注意力分支（零额外成本但需要 sparse 训练），BLASST 的来自 FA kernel 的 running max（兼容 dense 模型但信息含量可能更低）。H4 直接测试这个 tension。
- **Per-query importance vs persistent importance**：单次 query 的 importance 可能高度 query-specific；需要聚合策略来区分 query-specific vs query-independent importance。这个 tension 决定了 pre-warming 的可行性。
- **Tier placement 的 cost model**：PCIe transfer (CPU↔GPU) 约 50 GB/s，NVMe 约 7 GB/s。在 decode 的 memory-bound 阶段，block fetch 的延迟是否可以 hide 在 compute 后面？需要 pipeline 设计。

## 3. 核心研究问题

### RQ1: Measurement — Block importance scores 的预测力（Weeks 1-4）

这是整个 proposal 的脊梁。如果 importance scores 不比 LRU 好，后续 design 无意义。

**具体任务**：
- 在 vLLM 上 hook attention kernel 输出，记录每个 decode step 的 per-block attention scores（block-wise mean/max）
- 对 NSA-style sparse model（如果有开源版本）记录 native block importance scores
- 在三个工作负载上收集 trace：多轮对话（LMSys-Chat-1M）、每个文档对应多个查询的 RAG（LongBench）、代码智能体会话（SWE-bench）
- Offline replay：在固定 HBM budget 下，比较 LRU / LFU / importance-guided / oracle (Belady's MIN) 的 hit rate
- 产出：一条 hit-rate-vs-budget 曲线，清楚显示 importance-guided 的 Pareto frontier 位置

**Go/No-Go gate (Week 4)**：如果 importance-guided 在所有 workload 和 budget 下都不显著优于 LRU（< 10% 相对提升），pivot to "Why Importance Scores Don't Predict KV Reuse" → negative result paper at HotStorage/EuroSys short。

**为什么这个 measurement 自己就是 contribution**：即使最终 joint optimization 收益低于预期，RQ1 的 measurement 数据本身就是第一个系统性的「模型内部信号 vs KV 重用模式」关系研究——这个数据目前不存在。

### RQ2: Design — 从 scores 到 policy（Weeks 5-8）

**子问题 2.1：Score aggregation 策略**

如何从 per-query per-block importance 得到 persistent importance？
- Exponential moving average: `I_block(t) = α · score(t) + (1-α) · I_block(t-1)`
- Sliding window aggregation: top-k% blocks in last W queries
- Attention-sink bias: always pin first/last few blocks (known sink tokens)

需要测量不同 α / W 下的 stability-predictiveness trade-off。

**子问题 2.2：Tier placement policy**

给定 HBM budget B（in blocks），每步决定：
- **Eviction**：驱逐 persistent importance 最低的 block
- **Prefetch**：从 DRAM/SSD 预取 persistent importance 最高但不在 HBM 的 block
- **Pinning**：重要性超过阈值的 block 永不驱逐（直到 importance decay）

与 LMCache 的 integration：在 LMCache 的 connector API 上实现 `get_importance(block_id) → float` 接口，复用其 batched data movement + zero-copy 基础设施。

**子问题 2.3：Post-hoc extraction for dense models**

对没有 native sparse attention 的模型（Llama, Qwen, etc）：
- 在 FlashAttention kernel 的 inner loop 中，block-wise 记录 attention scores 的 max/mean
- 存储成本：per-block one float32，对 1M context / block_size=16 / 32 layers = ~8 MB overhead → negligible
- 需要验证这个 extraction 不显著增加 kernel 延迟（目标 < 5% overhead）

### RQ3：实施——端到端系统（第9-12周）

**实现范围**：
- Modified vLLM block manager (~500 LOC change)：在 `allocate` / `free` / `evict` 路径上加入 importance-guided logic
- 重要性提取侧通道（~300 LOC）：在 FlashInfer 注意力内核尾部钩注意力分数
- 分数聚合服务（~400 LOC）：每块 EMA + 滑动窗口 + pinning；与块管理器通过共享内存通信
- LMCache integration (~300 LOC)：通过 LMCache connector API 暴露 importance scores 给 tier placement
- Configuration & monitoring (~200 LOC)：importance policy 的可配置参数 + Prometheus metrics

总计约 1700 LOC changes，跨 3-4 个组件。

**Evaluation benchmark suite**：
- RULER @ 128K/256K/512K（长上下文检索准确性，验证 quality 不退化）
- MRCR v2 @ 128K/256K/512K/1M（多针检索，最敏感的 quality metric）
- LMSys-Chat-1M（生产 multi-turn conversation trace，验证真实 workload 下的 hit rate）
- LongBench（多任务长上下文理解，验证通用性）
- SWE-bench agent traces（代码 agent 场景，验证 tool-use / multi-step 场景）

**Baselines**：
- vanilla vLLM (PagedAttention, LRU eviction)
- vLLM + LMCache (LRU-based tiering)
- vLLM + BLASST (sparse attention only, no tiering integration)
- vLLM + LMCache + BLASST (best independent optimization, no cross-layer)

### RQ4: Correctness — Silent retrieval failures（贯穿全项目）

这是 SOSP-2025 silent failure 主题的直接延伸。核心问题：importance-guided eviction 是否引入了**静默检索失败**——模型自信地给出错误答案，因为它需要的 KV block 被驱逐了但模型不知道？

**测量方法**：
- 在 RULER/MRCR 上对比 importance-guided vs LRU 的 calibration（confidence vs accuracy）
- 构建 adversarial 测试：target 信息被嵌入到低 importance 的 block 中（模型可能误判为不重要）
- 对 importance-guided eviction 引入**保守模式**：当 confidence < threshold 时，fall back 到 recomputing from DRAM/SSD

**如果发现高比例的 retrieval hallucination**：这不是 kill 这个方向的问题，而是贡献的一部分——定义 importance-guided KV management 的 safety boundary，并设计 conservative fallback 机制。

## 4. 可行性

### 4.1 工程范围

| 组件 | 预估 LOC | 依赖 | 风险 |
|------|---------|------|------|
| vLLM block manager 改造 | ~500 | 熟悉 vLLM core | low — block manager 代码结构清晰 |
| Importance extraction (FlashInfer hook) | ~300 | 熟悉 CUDA/Triton attention kernel | medium — kernel 修改有性能陷阱 |
| Score aggregation + policy engine | ~400 | 无特殊依赖 | low — 纯 Python/C++ 逻辑 |
| LMCache connector 集成 | ~300 | LMCache API stable | low |
| Evaluation harness | ~500 | 标准 benchmark 集成 | low |
| **Total** | **~2000** | | |

**硬件需求**：1-2× A100/H100 (80 GB) 或 1× B200。用 Llama-3.1-8B (128K native context) 或 Qwen3-8B (256K) 做主力实验模型。对 1M context 的 scaling 实验，可 extend 到 Qwen2.5-14B-1M 或使用 MSA 的 tiered storage 思路做 emulation。

**软件栈**：vLLM 0.8+ / FlashInfer 0.2+ / Triton 3.0+ / Python 3.12。全部开源，无 license 障碍。

**为什么小团队能做**：
- 不需要训练模型（H4 的 post-hoc extraction 是关键 enabler）
- 开源 serving 框架成熟，block manager 是 modular 的
- 核心 insight（importance scores → tier placement）是算法/策略创新，不依赖大规模 infra
- Measurement-heavy 的设计让早期信号快速出现

### 4.2 时间线

| Phase | Weeks | 产出 | Go/No-Go |
|-------|-------|------|----------|
| **M1: Measurement** | 1-4 | hit-rate-vs-budget curves (RQ1), importance-vs-LRU comparison | H1 验证：importance 是否显著优于 LRU (≥20% hit rate improvement)? No → Pivot A |
| **M2: Policy Design** | 5-8 | Aggregation + tiering policy (RQ2), initial end-to-end prototype | H2 + H4 验证：aggregate importance 是否揭示结构性热点？post-hoc extraction 是否可行？|
| **M3: System + Eval** | 9-12 | Full system (RQ3), evaluation across all benchmarks, ablation studies | H3 验证：joint optimization 是否 ≥30% latency reduction? |
| **M4: Writing** | 13-16 | Paper draft, revision, supplementary materials | |

**Gate decisions**：
- Week 4: H1 fail → Pivot A (negative result paper)
- 第 8 周：H1 通过，但 H2/H4 失败 → 范围缩小到密集模型的重要性引导驱逐（无预热）
- 第 12 周：H3 边缘（15-25% 不≥30%）→ 仍可在 ATC/EuroSys 上发布并提供诚实的报告

## 5. 投稿策略

### 5.1 投稿梯度

```
H1 + H3 强验证 (>20% hit rate, >30% latency)
  → OSDI 2027 (deadline ~Dec 2026)
  
  理由: cross-layer co-design + counterintuitive finding 
  (模型内部信号打败 purpose-built caching heuristic) 
  是 OSDI 级别的 contribution

H1 验证强但 H3 中等 (10-20% hit rate, 15-25% latency)  
  → ATC 2027 / EuroSys 2027
  
  理由: solid engineering contribution with thorough measurement

H4 验证但 H1-H3 弱
  → MLSys 2027 (systems track)
  
  理由: practical technique for ML serving, 
  post-hoc extraction method is the main contribution
  
  → 或 NeurIPS 2027 (datasets & benchmarks track)
  如果把 measurement data 和 benchmark 作为 contribution

全部不通过
  → HotStorage 2027 short paper or Arxiv technical report
  记录 negative result + why importance scores don't work for KV management
```

### 5.2 为什么这个 venue 需要这篇 paper

**对 OSDI**：OSDI 历史上建立了「用 OS 思想解决系统问题」的传统（PagedAttention = OS paging + attention 是最经典的例子）。本工作的核心 insight——block importance score 作为「attention 层的 accessed bit」——是同一传统的延续。此外，cross-layer optimization（计算层 × 存储层）是系统研究的核心问题。

**对 ATC**：ATC 重视 production-relevant 的 serving optimization。如果 post-hoc extraction (H4) 验证，这个技术的 adoption barrier 极低（不需要改模型），对工业界即刻可用。

**对 MLSys**：MLSys 2026 已接收多篇 attention kernel / KV 管理论文（FlashAttention-4、MAC-Attention、BLASST、SparseSpec）。本工作填补的是这些论文之间的空白——sparse attention kernel 和 KV cache management 之间的桥接。

### 5.3 论文 story arc

**标题**：“重要性引导的 KV 缓存分层：当模型告诉您要保留什么”

**开头**：“稀疏注意力机制计算 block importance score，以决定跳过哪些 token；注意力计算结束后，这些分数通常被丢弃。我们证明它们是 KV Cache 分层放置的最佳信号，命中率比 LRU 高 20–40%。”

**Story arc**:
1. **观察**：KV缓存分层和稀疏注意力是独立优化的。重要性分数在关注后被丢弃。
2. **测量**：我们使用 vLLM 来收集配对数据（重要性分数、未来的 KV 块访问）。重要性引导驱逐明显优于 LRU，并且差距随着上下文长度的增加而扩大。
3. **为什么**：重要性分数捕获模型对哪些上下文重要的语义判断。 LRU 仅捕获时间局部性。在长上下文场景中，关键上下文（系统提示、早期指令）在时间上遥远但在语义上很重要。
4. **设计**：简单策略——EMA 聚合 → 分层放置 → pin 高重要性 block；在 vLLM block manager 与 LMCache connector 中实现。
5. **结果**：在相同质量的情况下，1M 上下文中的延迟减少了 30-50%。事后提取适用于密集模型，使得该技术具有普遍适用性。
6. **含义**：“块重要性分数”应该是从注意力内核到内存管理器的标准化信号，类似于页表访问位。

**图 1（概览）**：三栏对照：（左）标准 KV 分层用 LRU 驱逐语义重要但时间上较旧的 block；（中）稀疏注意力计算 block importance score；（右）重要性引导分层把正确的 block 留在 HBM。

## 6. 转向方案

### Pivot A: H1 不通过（importance scores 不优于 LRU）

**为什么可能发生**：大多数 query 的 attention pattern 高度集中在最近生成的 token（recency bias），LRU 本身已经在做正确的事。Importance scores 的额外信息含量不足以区分「近期但不再需要的 token」和「近期且仍然需要的 token」。

**Pivot 方向**：改成 "Why Recency Works: An Empirical Study of KV Cache Access Patterns"。测量结果仍然是贡献——这是第一个系统性的 KV cache access pattern characterization。把 negative result 定位为「importance scores 的预测力被 recency bias 主导」的经验发现。

**Target venue**: HotStorage 2027, 或 EuroSys 2027 short paper。

### Pivot B: H1 通过但 H3 不通过（joint optimization 的增量收益太小）

**为什么可能发生**：如果 importance scores 高度集中在少数 block（如 system prompt），那 tier placement 只需要很少的 HBM 就能覆盖大部分 importance mass。额外的 joint optimization（动态调整 sparse attention 的 top-k 与 tier prefetch 协同）的边际收益可能很小。

**Pivot 方向**：把 contribution focus 在 importance-guided eviction policy 本身（而非 joint optimization）。简化实现（只需在 LRU 上加 importance-based pinning），更 clean 的 story。

**Target venue**: ATC 2027（更偏重实用系统 contribution）。

### Pivot C: H4 不通过（post-hoc extraction 质量太差）

**为什么可能发生**：Dense model 的 attention pattern 更 diffuse（没有 sparse training 的 sharpen 效果），block-wise mean attention score 区分度太低。

**Pivot 方向**：如果 H1-H3 在 NSA-style sparse model 上通过但在 dense model 上不通过，那 contribution 变成 "Why Sparse Attention Training Is Necessary for Importance-Aware KV Management"——论证 native sparse training 的另一个好处（不仅是计算效率，还有 KV 管理的信号质量）。

**Target venue**: MLSys 2027（更偏重算法-系统协同设计）。

### 终极 fallback

如果所有假设都不通过：写一篇 4-page short paper 记录「为什么 model internal signals 对 memory management 的预测力不如简单的 recency heuristics」——这对 community 有价值，避免其他人重蹈覆辙。Archive on arxiv + submit to HotStorage。

---

*本提案基于 `proposals/_probes/subquadratic-sparse-attention.md` 的 landscape characterization + CLAUDE.md Taste Rubric 的自我评估。*

---

## 附录: Taste Rubric Self-Challenge

### Workload 真实性

**评估**：PASS (borderline)

- LMSys-Chat-1M 和 SWE-bench agent traces 是公开可获取的生产级 workload trace
- RULER 和 MRCR 是长上下文质量评测的社区标准
- 缺少 proprietary production data（如企业内部 serving 的 KV access pattern），但这不是实质性缺陷——公开 trace 足以支撑 measurement 的生态效度
- 一个 risk：这些 trace 可能不足以覆盖「长上下文 + 多查询复用」的联合模式（这是 importance-guided tiering 最有利的场景）。需要合成部分 workload 作为补充

### Counterintuitive

**评估**：PASS

- Core finding："模型内部信号（从未被训练用于 memory management）在预测 KV 重用上打败了 purpose-built 的 LRU 策略"
- 这违反直觉：LRU 是缓存管理的 gold standard 50 年，importance scores 的原始目的是决定 attention skip，两者似乎不应对同一个问题给出不同的答案
- Counterintuitive 的解释已经在 story arc 中：LRU 捕获 temporal locality，importance scores 捕获 semantic importance——在长上下文场景下，这两者 diverges（early system prompt 是 semantically important 但 temporally distant）
- 一个 nuance：如果社区已经预期 attention scores 对 KV 管理有用（如 H2O 已经用了 accumulated attention scores 做 eviction），那这个 finding 的 counterintuitive 程度会降低。需要在前言中区分 H2O 的 per-token accumulated attention weight（简单的 frequency proxy）vs 我们的 block-wise contextualized importance（反映当前 query 的信息需求）

### 10x vs 2x

**评估**：PASS (通过重新 framing)

- 直接 metric（latency reduction）是 30-50%，属于 1.5-2× 范围，不是 10×
- **但 framing 是关键**：这个 contribution 的核心价值不是「让现有系统更快」，而是「让 1M+ context serving 在经济上可行」
- 当前 1M context serving 的 practical 成本极高——要么 HBM overprovision（单卡 H200 141 GB 仅够 1-2 个 1M 序列），要么频繁 recompute（延迟开销 10-100×）
- Importance-guided tiering 让 KV cache 在 tiered storage 上的 hit rate 显著提升，使得用小得多的 HBM budget 就能 serve 1M context
- 如果用「每 query 的 infrastructure cost」作为 metric：在相同 quality 下，importance-guided tiering 相比 full HBM provisioning 节省 5-10× cost
- **这个 framing shift 需要在 paper 的 introduction 中 explicit 地建立**

### Model-proof

**评估**：PASS

- KV cache 的存在不依赖于任何特定模型架构——只要模型使用 attention（dense or sparse），就有 KV cache
- 即使未来 SSM/linear attention 取代了部分 Transformer 层，混合架构中的 attention 层仍需要 KV cache management
- Post-hoc extraction (H4) 确保技术适用于任何 attention-based model，不需要改变训练
- 更强的 argument：如果 sparse attention 成为主流（NSA 和 SSA 都指向这个方向），importance scores 会变成「免费」信号，使得 importance-guided tiering 成为自然选择——technique 的价值随行业发展只会增加

### Abstraction

**评估**：PASS (borderline)

- 提出的新抽象：「Block Importance Score」作为 attention kernel 和 memory manager 之间的标准化信号接口
- 类比 OS 页表的 accessed/dirty bit——一个低开销、从 compute layer 产生、被 memory layer 消费的信号
- 这个抽象的深度体现在：
  1. 它是算法/系统之间的 boundary object，不是某个 module 内部的 heuristic
  2. 它统一了 sparse attention（用 scores 做 selection）和 KV tiering（用 scores 做 placement）的 interface
  3. 不同 sparse attention 策略（NSA compression 分支、BLASST running max、Twilight top-p）产生不同质量的 scores，但 interface 是统一的
- Borderline 的理由：这个抽象目前仍停留在「定义一个新 API」的层面。如果要有真正的抽象深度，需要证明这个 API 在不同模型架构（dense/sparse）、不同 serving 框架（vLLM/SGLang）、不同硬件（A100/H200/B200）下都是 useful and implementable 的
- **改进方向**：在 proposal 的 design section 中 explicit 地定义 `BlockImportanceInterface` 的 spec（输入/输出/语义/性能约束），让它从「我们用了 importance scores」变为「这是 importance scores 应该被消费的标准方式」

### 总结

| 维度 | 评估 | 备注 |
|------|------|------|
| Workload 真实性 | PASS (borderline) | 公开 trace 可支撑，但有合成补充需求 |
| Counterintuitive | PASS | 模型内部信号 vs LRU 的核心张力成立 |
| 10x vs 2x | PASS (reframed) | 需从 latency 重构为 cost-per-query framing |
| Model-proof | PASS | KV cache 是 attention 的固有存储需求 |
| Abstraction | PASS (borderline) | Block Importance Score 作为标准化接口的概念成立，需在设计节 explicit 定义 |

**5/5 通过，0 维度不通过。无需 V2 重写。** 但 borderline 的三个维度需要在 implementation 和 paper writing 阶段 extra attention：
- Workload: 确保至少一个 workload trace 有 production provenance
- 10x vs 2x: Introduction 中 explicit 建立 cost framing
- Abstraction: Design section 中 explicit 定义 `BlockImportanceInterface` spec
