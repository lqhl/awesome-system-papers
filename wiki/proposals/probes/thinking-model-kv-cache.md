---
type: probe
topic: "Thinking model (CoT) KV cache management"
created: 2026-04-30
probed_papers:
  - "[[vLLM-SOSP23]]"
  - "[[Jenga-SOSP25]]"
  - "[[FlexiCache-MLSys26]]"
  - "[[DiffKV-SOSP25]]"
  - "[[LMCache-arXiv25]]"
  - "[[CacheGen-SIGCOMM24]]"
  - "[[CacheBlend-EuroSys25]]"
  - "[[fabric-lib-MLSys26]]"
  - "[[Cartridges-ICLR26]]"
  - "[[LLMSteer-NeurIPSW24]]"
  - "[[PASTA-ICLR24]]"
  - "[[FluxMoE-arXiv26]]"
  - "[[MSA-arXiv26]]"
  - "[[AttnRes-arXiv26]]"
  - "[[Libra-arXiv26]]"
  - "[[LatencyOptimal-MoELB-INET4AI25]]"
  - "[[DeepSeek-V4-arXiv26]]"
---

# 调研：思维模型的 KV Cache 管理

> Thinking model（R1、QwQ、o1 系列）的超长 Chain-of-Thought trace 对 KV cache 管理提出全新挑战——decode KV >> prefill KV，attention 访问模式从时序局域变为 semantic milestone-driven。社区所有现有 KV cache tiering/compression 工作都在 normal decode 上评测，**零 coverage**。

## Landscape

### KV Cache 管理基础设施

| 工作 | 做了什么 | 没做什么 | 隐含假设 |
|------|----------|----------|----------|
| [[vLLM-SOSP23\|vLLM]] | PagedAttention：KV cache 分页管理 + on-demand 分配 | 只在单 GPU 内，不做跨 tier 迁移 | KV page 大小均匀，所有层 attention 结构一致 |
| [[LMCache-arXiv25\|LMCache]] | Full-stack KV cache 层：GPU/CPU/SSD/remote multi-tier + batch data movement + modular connector | 不做 tiering policy——什么时候把哪个 page 搬到哪个 tier | Prefix identity 是主要的复用模式 |
| [[CacheGen-SIGCOMM24\|CacheGen]] | KV 编码为 compact bitstream（3.5-4.3×）+ adaptive streaming | 不做 tiering decision，只做传输优化 | KV 压缩的 accuracy overhead 可接受 |
| [[CacheBlend-EuroSys25\|CacheBlend]] | 多 chunk selective KV recompute（<15% token）+ pipeline fetch | 只针对 RAG prefix 场景，不做 intra-sequence tiering | Cross-attention 集中在少数 token 上 |
| [[fabric-lib-MLSys26\|fabric-lib]] | 跨厂商 P2P RDMA 库（IMMCOUNTER + GDRCopy） | 不做上层调度/缓存策略 | Reliable-but-unordered delivery 是 ConnectX 和 EFA 的交集 |

### KV 缓存分层/压缩/卸载

| 工作 | 做了什么 | 没做什么 | 隐含假设 |
|------|----------|----------|----------|
| TTKV (arXiv 2604.19769) | HBM+DRAM temporal-tiered KV cache，用 temporal recency | 只有 2 tier，不做跨节点，不做 thinking model | **最近访问的 page 就是最可能被再次访问的** |
| [[FlexiCache-MLSys26\|FlexiCache]] | Per-head temporal stability：stable head offload to host | 只 2 tier，stability profiling 在 normal decode 上做 | **Attention head 的 top-K stability 是 model-intrinsic，跨 task 不变** |
| [[DiffKV-SOSP25\|DiffKV]] | 四维差异化压缩（K≠V、token 重要性、per-head 稀疏） | 只做压缩不做 tiering；唯一在 thinking model 上评测的 KV 工作，但只测 compression ratio vs accuracy | **Attention score 反映 token 的相对重要性，高 score token 值得更多存储资源** |
| [[Cartridges-ICLR26\|Cartridges]] | Self-study 离线训练替代 prefill 生成 KV cache（38.6× 压缩） | 针对 static document corpus，不做 dynamic conversation/CoT | Context 是静态文档，可提前训练 |
| Kareto (arXiv 2603.08739) | 多目标静态 tier 容量配置 | 不做 per-page 动态迁移 | Tier 的 optimal allocation 是 workload-stable 的 |

### KV 缓存编辑/控制

| 工作 | 做了什么 | 没做什么 | 隐含假设 |
|------|----------|----------|----------|
| [[PASTA-ICLR24\|PASTA]] | Post-hoc attention score reweighting by user-specified highlights | Query-dependent steering，每次请求需要重新做 | Attention head 的功能可以通过 post-hoc manipulation 改变 |
| [[LLMSteer-NeurIPSW24\|LLMSteer]] | Query-independent contextual re-reading + attention steering | 只在 ≤10K context 上测试 | 两次 prefix-prompt re-reading 能稳定识别关键 token |

### 相关但非直接 KV cache 的工作

| 工作 | 做了什么 | 与 KV cache 的关系 |
|------|----------|-------------------|
| [[DeepSeek-V4-arXiv26\|DeepSeek-V4]] | Hybrid CSA+HCA attention 把 1M context 的 KV 压到 10% | §3.6.1 明确说「violates fundamental assumptions behind PagedAttention」——异构 KV 结构让 PagedAttention 的 uniform block 抽象不适用 |
| [[Jenga-SOSP25\|Jenga]] | 异构 attention 的 LCM slab KV 分配 | 单 GPU 内，揭示 PagedAttention 在非 uniform attention 下的浪费（79.6%） |
| [[FluxMoE-arXiv26\|FluxMoE]] | MoE expert paging：把专家权重当 streaming resource | PagedTensor 抽象——把分页思路推广到 weight，间接释放 HBM 给 KV cache |

### 社区盲区总结

**整个表格最刺眼的一列是「隐含假设」**。所有 KV cache tiering/compression 工作的核心 heuristic——recency（TTKV）、stability（FlexiCache）、attention score（DiffKV）——都建立在 normal decode 的 attention pattern 假设上：
- Attention 集中在最近 token（sliding window）
- Head 的 top-K 选择跨 step 稳定
- 高 attention score 的 token 就是重要的

**但这些假设对 thinking model 的 CoT trace 是否成立？没有人验证过。** CoT 的特点——decode KV >> prefill KV、semantic milestone-driven 跳跃式访问、attention head 在 reasoning 各阶段切换模式——每一项都在挑战这些隐含假设。

---

## Tensions

### T1：新近度与语义里程碑访问
- TTKV 假设 recency 是好 heuristic。但在 CoT 中，模型在 step 30K 时可能需要回看 step 5K 做的假设——recency 完全抓不到。
- 受影响的论文：TTKV、FlexiCache（unstable head 在 CoT 中可能是功能性的）

### T2: Stability Profiling 的泛化边界
- FlexiCache 在 normal decode 上证明 stability 是 model-intrinsic（跨 8 个 task overlap 0.83）。但如果 CoT 的 attention pattern 是 **phase-dependent**（探索 vs 验证 vs 输出），那 offline stability profiling 的有效性存疑。
- 受影响的论文：FlexiCache

### T3：注意力分数≠持续重要性
- DiffKV 用 attention score 分配精度——对当前 step 重要的 token 用高精度。但 CoT 中「未来会被反复回看的 token」是那些构成推理骨架的 milestone——它们当前的 attention score 不一定高。
- 受影响的论文：DiffKV

### T4: PagedAttention 的 uniform block 假设在瓦解
- DeepSeek-V4 的 CSA+HCA 让不同层的 KV 结构不再 uniform——有些层压缩 100×，有些层保留 dense。PagedAttention 的 fixed-size block + uniform block table 假设不再成立。
- 受影响的论文：vLLM、所有基于 PagedAttention 的工作

---

## 行业活动

- **NVIDIA Dynamo + KVBM + CMX**：NVIDIA 的闭源 KV 缓存平台。4 层（HBM→DRAM→SSD→网络存储）+ KV 感知路由。策略未公开。
- **InfiniStore (ByteDance)**：分布式 KV cache store，RDMA 互联。面向 chatbot prefix reuse。
- **Junchen Jiang 博客 (2026-04-28)**："Stop Calling It KV Cache"——KV cache 已是一等数据对象，需要独立的存储栈、生命周期和 API。LMCache 的 production telemetry 显示 KV cache 总量远超 GPU 内存。
- **Thinking model serving 是 2026 最大的 LLM inference trend**，但 system venue 上零 KV cache 相关 coverage。

---

## 候选空白

### CB1：思维模型KV页面访问模式表征
**是什么**：系统性地测量 CoT trace 中 KV page 的访问模式——reuse distance distribution、per-head stability、语义 milestone identification——与 normal decode 做直接对比。
**为什么现有工作没覆盖**：所有 KV cache 测量/优化都在 normal decode 上做。DiffKV 在 thinking model 上评测但只测 compression ratio vs accuracy，不做 access pattern characterization。

### CB2：思考工作量的启发式失败
**是什么**：在 CoT trace 上测试 recency/stability/attention-score 三类 mainstream heuristic 的预测力。如果它们集体翻车，意味着 thinking model 需要全新的 KV cache 管理设计原则。
**为什么现有工作没覆盖**：社区还没意识到 thinking model 的 workload 特征与正常 decode 有本质差异。

### CB3：KV 预取的语义里程碑检测
**是什么**：在 CoT trace 中识别那些「未来会被反复回看」的 milestone token，用于指导 remote tier 的 prefetch。不依赖于 attention score（当前重要性）而依赖于预测未来重要性。
**为什么现有工作没覆盖**：没有人把 CoT 的 access pattern 当作 prediction 问题。

### CB4：超越 PagedAttention 的异构 KV 抽象
**是什么**：当模型架构（如 DeepSeek-V4）让不同层的 KV 结构不再 uniform 时，什么抽象能替代 PagedAttention 的 uniform block 模型？
**为什么现有工作没覆盖**：DeepSeek-V4 太新，PagedAttention 的假设 violation 还没被系统化讨论。

---

## 关键未知数

### KU1: CoT trace 的 page reuse locality 有多强？
- **需要什么 measurement**：在 Qwen2.5/R1-Distill 上跑 AIME/GPQA/BBH 等 reasoning benchmark，instrument vLLM 收集 per-page access trace，画 reuse distance CDF
- **关键问题**：top 20% page 承载多大比例的 access？这个比例 vs normal decode 是更高还是更低？

### KU2: Temporal recency 在 CoT 的哪一段开始失效？
- **需要什么 measurement**：按 decode step 分段计算 recency 的 recall@k，找 recall 崩塌的 inflection point
- **关键问题**：崩塌点在什么 decode length？是否在所有模型上一致？

### KU3: FlexiCache stability 在 CoT 上的泛化性
- **需要什么 measurement**：在 CoT trace 上 compute per-head RCO，与 normal trace 的 RCO 对比
- **关键问题**：stability ranking 是否保持不变？如果不保持——哪些 head 发生了最大的 stability shift？

### KU4: Attention score vs milestone token 的 reuse 相关性
- **需要什么 measurement**：对 CoT trace 中 manual-labeled milestone token 计算 reuse count，与 attention score top-20% token 的 reuse count 做对比
- **关键问题**：两者 overlap 有多大？如果 <30%，DiffKV 的 attention-score-based 精度分配在思考模型中可能误导资源布局

### KU5: CoT 中的错误级联效应
- **需要什么 measurement**：在 CoT 中故意 evict 某些类型的 KV page（milestone vs non-milestone、stable head vs unstable head、early reasoning vs late verification），measure final answer accuracy 的变化
- **关键问题**：是否某些特定的 page eviction 会导致 disproportional accuracy drop？
