---
status: deprecated
date: 2026-04-02
keywords:
  - RDMA
  - P2P Communication
  - LLM Serving
  - Sparse Attention
  - Long Context
  - KV Cache
  - Disaggregated Inference
target: OSDI 2027 / SOSP 2027
---
# Sparsity-Aware KV Cache Streaming for Disaggregated Long-Context Inference

> **⚠️ 已放弃（2026-04-02）**
>
> 核心观察成立（传 100% KV cache、用 10-50% 确实浪费），但作为独立顶会论文价值不足：
>
> 1. **Incrementality 致命**。Scorer 来自 LServe/DuoAttention，Transfer 来自 Mooncake scatter-gather，Sparse store 来自 FlashInfer BSR——系统贡献的 delta 太薄，本质上是 "Mooncake + attention-based block filter"，难以说服 OSDI/SOSP 审稿人。
> 2. **Mooncake 团队截胡风险高**。他们已在 FAST'25 论文第七节明确提到 KV cache compression 是正交优化方向，且拥有生产级 Transfer Engine + 数千节点部署 + 真实流量数据，做这件事的成本和速度远优于外部团队。
> 3. **问题已被缩小**。Mooncake 的全局分布式 prefix caching 已将 cache hit rate 提升 1.38-2.36×，大量请求的 KV cache 已在 decoder 附近，SparseTransfer 解决的是 cache miss 场景下的传输效率——边际收益有限。
> 4. **核心假设验证风险不小**。Streaming head 比例在 70B 模型上未知（8B 的 ~50% 不能直接推广）；prefill last-token 到 decode pattern 存在分布偏移；code 任务质量退化（KIVI 97.0→30.0）可能需要 per-task routing，削弱通用性。
> 5. **深化方向（co-design scheduling）虽有潜力，但工程量和风险大幅增加**，对 1-2 人团队 6.5 个月 timeline 过于乐观。
>
> **残余价值**：Phase 0 的 empirical study（70B 模型 KV access pattern 量化）本身对社区有参考意义，可作为 workshop paper 或技术博客，但不值得投入全周期。

---

## 一、核心观察

当前 disaggregated inference（prefill/decode 分离）的 KV cache 传输存在一个结构性矛盾：

- **Prefiller 生成完整 KV cache** → 网络传输 → **Decoder 只用其中一部分**

这个矛盾在长上下文场景（128K-1M+ tokens）下被急剧放大。以 Llama 3.1 70B, 128K context 为例：

| 参数 | 值 |
|------|-----|
| KV heads | 8（GQA） |
| Head dim | 128 |
| Layers | 80 |
| KV cache per token | 2 × 8 × 128 × 80 × 2 bytes = 320 KB |
| 128K context KV cache | 320 KB × 128K = **40 GB** |
| 1M context KV cache | 320 KB × 1M = **320 GB** |
| 400 Gbps RDMA 传输时间（128K） | 40 GB / 50 GB/s = **0.8 秒** |
| 400 Gbps RDMA 传输时间（1M） | 320 GB / 50 GB/s = **6.4 秒** |

而 MLSys 2025 的一系列论文证明了：**decode 阶段的 attention 高度稀疏，大部分 KV cache 条目贡献极小**。

| 论文 | 发现 | Decode 阶段实际使用率 |
|------|------|----------------------|
| [[cc8c6b9d89f7a898a29f58869b238e46|LServe]] | ~50% attention heads 是 streaming head（只需 local window + sink tokens） | ~25-50% |
| [[2d04d97593c8c33d415337f408ed0e1b|SampleAttention]] | CRA-guided 动态稀疏，1M context 5.29× 加速 | ~10-30%（CRA threshold 控制） |
| [[26289c647c6828e862e271ca3c490486|Rethinking KV Cache Compression]] | 压缩在 FlashAttention 生产系统中收益与学术 benchmark 差异巨大 | 取决于任务（code 任务退化严重） |
| [[fbe2b2f74a2ece8070d8fb073717bda6|TurboAttention]] | Block-wise INT8 量化 + 稀疏 softmax 近似 | ~40-60%（量化+稀疏） |
| [[96894468eb44631a32d7ebd56f9892c7|FastTree]] | Tree-structured KV sharing 5.1-10.6× kernel 加速 | 取决于共享结构 |

**核心矛盾**：我们用 100% 的网络带宽传输 100% 的 KV cache，但 decode 只会访问其中 10-50%。

---

## 二、研究问题

> **能否在 prefill 阶段预测 decode 所需的 KV cache 子集，只传输这些关键页面，从而将 disaggregated inference 的 KV cache 传输量降低 50-90%+，同时保持模型输出质量？**

### 2.1 为什么之前没人做这个

1. **Disaggregated inference 本身很新**：DistServe（OSDI'24）和 Splitwise 是 2024 年才出现的。此前 KV cache 只在本地 GPU 上，不存在传输瓶颈。

2. **Sparse attention 和 KV transfer 是两个社区**：做 sparse attention 的人（LServe, SampleAttention）关注的是单机 decode 加速；做 KV transfer 的人（Mooncake, BLITZSCALE）关注的是网络传输效率。**没人把两者联合优化。**

3. **技术前提刚刚成熟**：
   - Mooncake 的 BatchTransfer API 让非连续页面的 RDMA 传输成为可能（之前只能传连续 buffer）
   - LServe/DuoAttention 的 streaming/retrieval head 分类让"哪些 KV 重要"有了 profiling-based 的答案
   - FlashInfer 的 BSR format + `return_lse=True`（2026.01）让 decoder 直接消费 sparse KV cache 并获取 attention 统计成为可能
   - Expected Attention（2025.10）提供了预测 future attention 的理论方法

### 2.2 与现有工作的精确区分

| 工作 | 做了什么 | 没做什么 |
|------|---------|---------|
| [Mooncake](https://github.com/kvcache-ai/Mooncake)（FAST'25） | 256-token block 粒度 KV cache 管理 + 拓扑感知 RDMA 传输，支持 scatter-gather | 传输**完整 block**，不做 attention-aware 选择 |
| [[osdi25-zhang-dingyan|BLITZSCALE]] | 网络带宽调度（避免 KV transfer 与 parameter loading 冲突） | 不减少 KV 传输量本身 |
| [[c6ee784cbe46d854843e4c883a3321ef|ThunderServe]] | 4-bit KV cache 压缩后传输 | 均匀量化，不区分重要/不重要 |
| [[cc8c6b9d89f7a898a29f58869b238e46|LServe]] | Decode 端 sparse attention | 假设 KV cache 已在本地，不涉及传输 |
| [Expected Attention](https://arxiv.org/abs/2510.00636)（2025.10） | Gaussian-based KV importance scoring，单机 KV compression | 不涉及跨节点传输；聚焦 compression 而非 transfer |
| [[cbc4ab80cd77aa0eb87da062fbcddb46|Seesaw]] | Prefill/decode 动态 re-sharding | CPU 中转 KV cache，无稀疏化 |
| [[3731569.3764823|Jenga]] | 异构 KV cache 内存管理（per-layer page_size/active_pages 抽象） | 单节点，无跨节点传输 |
| [[osdi25-zhu-kan|NanoFlow]] | GPU→CPU→SSD KV offload | 单机优化，无 disaggregated |
| A³（2025） | Query-aware selective KV recomputation，2× TTFT 降低 | 单节点 cache reuse，非跨节点传输 |

**本工作的独特位置**：将 sparse attention 的知识（哪些 KV 重要）前移到传输决策阶段（传什么），在网络层面实现 "attention-aware data movement"。

> **与 Jenga 的潜在协同**：Jenga 的 layer property 抽象（每层声明 `page_size()`, `active_pages()`, `possible_prefix()`）为 per-layer 差异化传输提供了元数据基础。SparseTransfer 可以利用类似的 layer property 来决定每层的传输策略（streaming head layer 只传 window，retrieval head layer 传 top-K pages）。

---

## 三、系统设计：SparseTransfer

### 3.1 架构总览

```
Prefiller GPU                          Network                    Decoder GPU
┌──────────────────────┐                                  ┌──────────────────────┐
│ Standard Prefill     │                                  │                      │
│ (FlashAttention)     │                                  │                      │
│         │            │                                  │                      │
│         ▼            │                                  │                      │
│ ┌──────────────────┐ │                                  │                      │
│ │ KV Importance    │ │                                  │                      │
│ │ Scorer           │ │                                  │                      │
│ │ (per-layer,      │ │                                  │                      │
│ │  per-head)       │ │                                  │                      │
│ └────────┬─────────┘ │                                  │                      │
│          │           │                                  │                      │
│          ▼           │                                  │                      │
│ ┌──────────────────┐ │    P2P RDMA paged writes         │ ┌──────────────────┐ │
│ │ Page Selector    │─│─────────────────────────────────▶│ │ Sparse KV Store  │ │
│ │ (top-K pages     │ │    (only selected pages)         │ │ (BSR format,     │ │
│ │  per head)       │ │                                  │ │  FlashInfer)     │ │
│ └──────────────────┘ │                                  │ └────────┬─────────┘ │
│                      │                                  │          │           │
│                      │    Metadata (page indices,       │          ▼           │
│                      │     importance scores)           │ ┌──────────────────┐ │
│                      │─────────────────────────────────▶│ │ Sparse Decode    │ │
│                      │                                  │ │ Attention        │ │
│                      │                                  │ │ (FlashInfer/     │ │
│                      │    On-demand fetch (rare)        │ │  LServe kernel)  │ │
│                      │◀─────────────────────────────────│ │                  │ │
│                      │                                  │ └──────────────────┘ │
└──────────────────────┘                                  └──────────────────────┘
```

### 3.2 核心机制一：KV Importance Scoring（Prefiller 端）

**目标**：在 prefill 结束后，快速判断每个 KV page 对后续 decode 的重要性。

**关键设计选择**：利用 FlashAttention/FlashInfer 已有的 `softmax_lse`（Log-Sum-Exp）输出，**近零额外计算**。

LServe 的核心发现给出了一个极其高效的方案：

#### 层级 1：静态 Head 分类（离线，一次性）

基于 LServe/DuoAttention 的方法论（对目标模型做一次 offline profiling）：
- **Streaming heads**（~50% of heads，已在 Llama-3-8B/Llama-2-7B/Minitron-4B 上验证）：只需最近的 local window（如 256 tokens）+ sink tokens（前 4 tokens）
- **Retrieval heads**（~50% of heads）：需要全局 KV cache，但有稀疏 access pattern

对于 streaming heads，只传 local window + sink tokens 即可。这是**无损**的——LServe 证明 streaming head 的 full attention 和 windowed attention 结果完全一致。

这一步就已经能减少 ~50% 的传输量（streaming heads 的远距离 KV 不需要传输）。

> **⚠️ 注意**：50% 这个比例来自小模型（8B）的实验，对于 Llama 3.1 70B 等大模型尚未验证。SampleAttention 的数据显示同一层内不同 head 的稀疏率从 27.4% 到 99.8% 不等，说明该比例高度依赖模型架构。**Phase 0 必须在目标模型上重新 profiling**。

#### 层级 2：动态 Page Selection（在线，per-request）

对于 retrieval heads，需要决定传输哪些 KV pages。三种候选方案：

**方案 A：Softmax LSE Proxy（零改动，粗粒度）**：FlashAttention/FlashInfer 已有 `softmax_lse` 返回值（`return_lse=True`），可作为 token-level attention energy proxy。但 LSE 是 per-query-token 的聚合值，不直接给出 per-KV-page importance 分解，精度不足。

**方案 B：Per-Page Attention Score 提取（推荐，极低开销，无需 kernel 改动）**

在 prefill 最后 1-2 层，对最后一个 query token 单独执行一次 non-FlashAttention 的 attention forward：

```python
# 只对最后一个 query token 计算 attention scores（不需要完整 attention matrix）
# 空间复杂度：O(seq_len) per head，128K context = 128K × 2 bytes = 256 KB per head
# 计算量：一次 QK^T + softmax，远小于完整 prefill
last_q = q[:, -1:, :]  # [batch, 1, head_dim]
attn_scores = (last_q @ k.transpose(-1, -2)) / sqrt(head_dim)  # [batch, 1, seq_len]
attn_scores = attn_scores.softmax(dim=-1).squeeze(1)  # [batch, seq_len]

# Page-level importance
page_scores = attn_scores.reshape(num_heads, num_pages, page_size).sum(dim=-1)
selected_pages = page_scores.topk(k=budget_per_head, dim=-1).indices
```

计算开销：128K context, 8 KV heads, head_dim=128 → ~128K × 128 × 8 = 128M FLOPs，相比完整 prefill（万亿级 FLOPs）可忽略不计。

**方案 C：Expected Attention（理论最优，有额外开销）**

[Expected Attention](https://arxiv.org/abs/2510.00636)（arXiv 2510.00636, 2025.10）提出了基于 Gaussian 分布假设的 closed-form attention 预测方法：
- 假设 hidden states 近似 Gaussian 分布，利用矩生成函数解析计算 expected attention score
- 维护 128 个 hidden state 的 buffer 估计 future query 分布统计量
- 在 Llama3.1-8B 上 50% 压缩率下几乎无损（Ruler benchmark 优于 SnapKV、TOVA）
- **优势**：有理论基础，能预测 future queries 的 attention（不仅仅基于 last token）
- **劣势**：需要额外的 Gaussian moment 计算；当前只有 PyTorch 实现，未优化；每 512 步重新压缩

> **与 SparseTransfer 的关系**：Expected Attention 的 scoring 方法可以替代方案 A/B 作为更准确的 importance estimator。但它增加了计算复杂度，且原论文聚焦单机 KV compression，未涉及跨节点传输。**SparseTransfer 的核心贡献在于将 importance scoring（无论用哪种方法）前移到传输决策层**，这与 Expected Attention 互补而非竞争。

**推荐方案 B**：方案 A（LSE proxy）信息量不足以做 per-page 选择；方案 B 的额外开销极小（单 query token 的 naive attention）且直接给出 per-page importance；方案 C 在 scoring 精度和系统复杂度之间可能过度优化。Phase 0 应同时评估 B 和 C 的 recall@K 表现，再做最终决策。

**为什么 prefill 最后一步的 score 能预测后续 decode？**

- SampleAttention 的实验表明：attention pattern 在连续 decode step 间有很高的 temporal stability（CRA 每 4 步重算一次就够）
- 最后一层的 attention 是模型对"当前上下文哪些部分重要"的最终判断
- 这本质上是一个 **speculative** 决策——我们赌后续 decode 的 attention pattern 与 prefill 最后一步相似

> **⚠️ 关键风险：分布偏移**：Prefill 最后一个 token 的 query 来自 prompt 尾部，而 decode 的 query 来自生成的 token，两者语义可能差异很大（例如 prompt 结尾 "请用 Python 实现..." vs 生成的代码 token）。此外，最后一层的 pattern 不一定能代表中间层。Phase 0 实验 B 必须量化这个跨层、跨步的预测误差。

#### 层级 3：Quantization-Aware Transfer（与 Page Selection 正交）

被选中的 KV pages 可以进一步量化后传输（QServe 的 KV4 或 TurboAttention 的 INT8）。这与 ThunderServe 的做法类似，但**只量化被选中的 pages**，因此可以容忍更激进的量化（重要 pages 用 INT8，次重要 pages 用 INT4 或不传）。

### 3.3 核心机制二：Selective Paged Transfer（网络层）

**利用现有 RDMA transfer engine 的 scatter-gather 能力实现选择性传输。**

基于 [Mooncake](https://github.com/kvcache-ai/Mooncake)（FAST'25, Moonshot AI）的 BatchTransfer API 实现选择性传输。Mooncake 原生支持非连续内存区域的批量传输（通过 TransferRequest 指定 source/target offset/length），拓扑感知的多 NIC 聚合可达 190 GB/s。

```
全量传输 (Mooncake 当前做法):
  Layer 0: [page0][page1][page2]...[pageN-1]  → BatchTransfer ALL
  Layer 1: [page0][page1][page2]...[pageN-1]  → BatchTransfer ALL
  ...

选择性传输 (SparseTransfer):
  Layer 0: [page2][page7][page15][page42]...  → BatchTransfer(selected_requests)
  Layer 1: [page0][page3][page7][page42]...   → BatchTransfer(selected_requests)
  ...
```

**关键设计**：

1. **逐层流水线 + 选择性传输**：Mooncake 支持逐层 KV cache 传输。SparseTransfer 在触发传输前过滤 page indices，构造仅包含 selected pages 的 transfer request batch。

2. **Metadata 先行**：传输 KV pages 前，先将 selected page indices 和 importance scores 发送给 decoder。Decoder 据此预分配 sparse KV store（只分配 selected pages 的 GPU memory），并知道每个 head 的 sparsity pattern。

3. **Memory saving on decoder**：传统方案 decoder 需要为 128K context 分配 40 GB KV cache。选择性传输后，decoder 只需分配 ~6 GB（取决于 sparsity ratio）。**节省的 KV cache 内存可以用来增加 batch size，提升 throughput**。

4. **与 Mooncake 当前做法的差异**：Mooncake 使用 256-token block 粒度做 KV cache 管理（含 hash-based 去重和 SIEVE 替换算法），但传输**完整 block**，不做 attention-aware 选择。SparseTransfer 在 block 传输之上增加 importance-based 的 block selection 层。

5. **Decoder 端 sparse KV 存储**：Sparse KV store 直接映射到 FlashInfer 的 BSR（Block-Sparse Row）format——selected pages 对应 non-zero blocks，page indices 对应 column indices。FlashInfer 的 JIT-compiled sparse attention kernel 和 dynamic load-balancing scheduler 可直接复用，无需自己写 kernel。

### 3.4 核心机制三：On-Demand Fetch（容错层）

Importance scoring 是 speculative 的——我们可能猜错。需要一个 fallback 机制。

**方案：Lazy Page Fetch with Prefetching**

1. **Decoder 端检测**：在 sparse decode attention 中，如果某个 decode step 的 attention score 分布表明缺失的 pages 可能重要（CRA 指标异常），触发 on-demand fetch。

2. **Fetch 协议**：Decoder 向 prefiller 请求特定 page indices → Prefiller 从 GPU/CPU memory 回传 pages → RDMA 完成通知触发 decoder 端更新。

3. **Prefetching**：基于 SampleAttention 的 CRA 观察——attention pattern 变化是渐进的。当 page importance 排名在连续 step 间显著变化时，提前 fetch 即将变重要的 pages。

4. **频率预期**：如果 importance scoring 足够准确（LServe 的 streaming head 分类是确定性正确的，retrieval head 的 top-K 选择有高 recall），on-demand fetch 应该非常罕见（<1% 的 decode steps）。如果 fetch 频率过高（>5%），说明 scoring 策略需要调整（增大 K 或改用 Expected Attention 方案 C）。

---

## 四、定量分析：预期收益

### 4.1 传输量减少

以 Llama 3.1 70B, 128K context, GQA 8 KV heads, 80 layers 为例：

> **基础数据**：KV cache per token = 2 × 8 × 128 × 80 × 2 bytes = 320 KB，128K tokens → 40 GB

假设 streaming head 比例为 S（LServe 在 8B 模型上 S≈50%，70B 待验证），window size = 256 tokens：

| 方案 | 传输量计算 | 传输量 | 减少比例 | 传输时间 (400Gbps) |
|------|-----------|--------|---------|-------------------|
| Full transfer | 40 GB | 40 GB | 0% | 800 ms |
| Streaming head: window only | S × 40GB × (256/128K) + (1-S) × 40GB = 0.04 + 20 ≈ 20 GB | ~20 GB | ~50% | ~400 ms |
| + Retrieval head top-30% | 0.04 + (1-S) × 40GB × 30% = 0.04 + 6 ≈ 6 GB | ~6 GB | ~85% | ~120 ms |
| + KV4 quantization (4-bit) | 6 GB × 0.25 ≈ 1.5 GB | ~1.5 GB | ~96% | ~30 ms |

**从 800ms 降到 30-120ms**，传输不再是 TTFT 的瓶颈。注意 streaming heads 的 window KV 非常小（256 tokens × 320KB/token × 50% heads ≈ 40 MB），传输量主要取决于 retrieval heads 的 budget。

> **⚠️ 上述数字高度依赖 S（streaming head 比例）和 retrieval head 的 top-K 阈值。如果 70B 模型的 streaming head 比例低于 50%（如 30%），减少比例会从 85% 降至 ~79%。Phase 0 需在目标模型上验证实际比例。**

### 4.2 Decoder 端内存节省

假设模型参数占用约 35 GB（70B FP16 with TP=2），H100 80GB 剩余 ~45 GB 可用于 KV cache：

| 方案 | KV cache memory per request (128K) | Max batch size (H100 80GB, TP=2) |
|------|-----------------------------------|---------------------------|
| Full KV cache | 40 GB | 1 |
| Sparse KV (S=50%, top-30% retrieval) | ~6 GB | 7-8 |
| Sparse KV + KV4 (4-bit) | ~1.5 GB | 20+ |

Batch size 的提升直接转化为 throughput 提升。对 decode 来说，这可能比传输时间的改善更有价值。

### 4.3 质量影响预期

| 组件 | 质量影响 | 依据 |
|------|---------|------|
| Streaming head classification | 无损 | LServe 证明 Λ-shaped mask 对 streaming head 无损 |
| Retrieval head top-30% | Near-lossless | SampleAttention CRA 99%+ accuracy |
| KV4 quantization | <1% perplexity degradation | QServe 实验数据 |
| On-demand fetch fallback | 补偿 scoring 错误 | CRA 检测异常 pattern |

**⚠️ 最大质量风险**：Rethinking KV Cache Compression 论文的核心发现——**code 任务在 KV 压缩下质量灾难性退化**（KIVI 从 97.0 降到 30.0）。SparseTransfer 的选择性传输本质上也是一种"压缩"（丢弃不重要的 pages）。**必须在 Phase 0 验证 code generation 场景下的质量表现**。如果 code 任务退化严重，需要 per-task routing（类似 Rethinking 论文的 request routing 方案）。

---

## 五、可行性深度分析

### 5.1 技术可行性

#### ✅ 已验证的组件

| 组件 | 来源 | 成熟度 |
|------|------|--------|
| KV cache RDMA 传输 + 非连续内存 scatter-gather | Mooncake BatchTransfer API | 生产级（Moonshot/Kimi 线上使用，5K stars, >1B tokens/day） |
| Softmax LSE 输出 | FlashAttention `return_attn_probs` / FlashInfer `return_lse` | 已实现（FlashInfer 2026.01 起支持） |
| Streaming/retrieval head 分类 | LServe / DuoAttention | 开源实现（仅在 ≤8B 模型验证） |
| Sparse attention kernel | FlashInfer BSR | 已集成到 SGLang |
| KV cache quantization | QServe KV4 | 已实现 |
| Expected Attention scoring | Expected Attention (arXiv 2510.00636) | 开源 PyTorch 实现（未优化） |

#### ⚠️ 需要新实现的组件

| 组件 | 难度 | 预计工作量 | 备注 |
|------|------|-----------|------|
| Last-token naive attention (方案 B) | 低 | 0.5 周 | 单 query token，O(seq_len) 空间 |
| Page importance scoring + selection | 低 | 1 周 | Top-K selection on CPU |
| 选择性传输层（基于 Mooncake） | 中 | 2-3 周 | 在 Mooncake block selection 上封装 attention-aware filter |
| Metadata 传输协议 | 低 | 0.5 周 | |
| Sparse KV store 分配器 | 中 | 2 周 | 基于 FlashInfer page table |
| On-demand fetch 协议 | 中 | 2 周 | |
| 与 vLLM/SGLang 的 scheduler 集成 | 高 | 4-6 周 | 含 batch scheduling 对 sparse memory 的适配 |
| 70B 模型 head 分类 profiling | 低 | 1 周 | LServe 方法论在大模型上的复现 |

#### 🚨 关键技术挑战

**挑战 1：Per-Page Attention Score 提取**

FlashAttention 的 online softmax 不保留完整 attention matrix。推荐方案 B（见 3.2 节）：对最后一个 query token 执行一次 naive attention，O(seq_len) 空间，~128M FLOPs，无需修改 FlashAttention kernel。

**挑战 2：Scoring 延迟 vs 传输延迟的 overlap**

Scoring 和 page selection 发生在 prefill 结束后、传输开始前。如果 scoring 延迟较大，会增加 TTFT。

分析：
- 方案 B 的 naive attention（last query token）仅需 ~128M FLOPs，在 H100 上 <1ms
- Top-K selection 在 CPU 上做（GPU 继续做下一个 request 的 prefill）
- 预期延迟：128K context, page_size=16, num_pages=8192 → top-K selection ~10µs
- 可以与前几层的 KV 传输 overlap（streaming head 的 KV 在任何 scoring 之前就已经可以开始传输）

**挑战 3：多轮对话中 importance 变化**

第一轮对话的 scoring 基于第一轮的 context。第二轮的 query 可能关注不同的 KV pages。

应对：
- On-demand fetch 机制处理这种情况
- 如果多轮命中率下降显著，可以在每轮 decode 结束后 re-score（利用该轮的 attention 统计）
- Marconi 的 FLOP-aware eviction 可以参考——对 re-score 后不重要的 pages 做 eviction

### 5.2 实验可行性

| 需求 | 是否满足 | 备注 |
|------|---------|------|
| GPU 集群 | 最少 4 GPU（2 prefill + 2 decode），理想 16-32 GPU | |
| 模型 | Llama 3.1 8B/70B（开源），Qwen2.5-72B（开源） | 70B 需 TP，增加集成复杂度 |
| Baseline 系统 | vLLM disaggregated inference（已开源）, SGLang | vLLM disagg RFC 已关闭，实现可能不稳定 |
| 通信库 | Mooncake（[开源](https://github.com/kvcache-ai/Mooncake), 5K stars） | BatchTransfer API 原生支持 scatter-gather |
| Sparse attention kernel | FlashInfer（已集成到 SGLang，支持 `return_lse=True`） | |
| Importance scoring | Expected Attention（开源 PyTorch）或 naive attention on last token | |
| Benchmark | LongBench, RULER, ∞Bench, Needle-in-a-Haystack | |
| 真实 trace | ShareGPT, LMSYS-Chat-1M | |

**最小可行实验**：4×H100/A100 + 100Gbps+ RDMA。可在大多数学术实验室获得。

### 5.3 风险矩阵

| 风险 | 严重度 | 概率 | 缓解方案 |
|------|--------|------|---------|
| **Attention score 对 decode pattern 预测不准（分布偏移）** | 高 | 中-高 | Phase 0 验证 recall@K；对比 Expected Attention scoring；on-demand fetch 兜底 |
| **70B 模型 streaming head 比例显著低于 50%** | 中 | 中 | Phase 0 重新 profiling；调整传输 budget |
| **Code 任务质量灾难性退化** | 高 | 中 | Per-task routing（Rethinking 论文方案）；code 任务 fallback full transfer |
| **Scoring 延迟增加 TTFT** | 中 | 低 | 方案 B（naive attention on last token）仅需 ~128M FLOPs；可与 streaming head KV transfer overlap |
| **On-demand fetch 频率过高（>5%）** | 高 | 低 | 增大传输 budget K；或放弃对 retrieval head 的稀疏化 |
| **On-demand fetch 引入 tail latency jitter** | 中 | 中 | 每次 fetch 需 ms 级往返；streaming 输出场景下用户可感知。需设计 speculative prefetch |
| **Mooncake/vLLM 团队已在做** | 高 | 中 | 快速验证 Phase 0，抢先发表 |
| **OSDI reviewer 认为是 "LServe + Mooncake integration"** | 高 | 中-高 | 需要深化方向 B co-design（见 9.4 节） |
| **Expected Attention 论文扩展到 transfer 场景** | 中 | 低 | EA 作者聚焦单机 compression；但需关注后续工作 |

### 5.4 与被截胡风险的分析

**最可能的竞争者**：

1. **Moonshot AI (Mooncake 团队)**：拥有最成熟的 disaggregated KV cache 系统（FAST'25, 5K stars, >1B tokens/day 生产部署）。Transfer Engine 已支持 scatter-gather，距离 attention-aware selection 只差 scoring 层。**风险最高**。

2. **LServe 作者（PKU + SJTU + MIT）**：最了解 sparse attention 的人。但他们的下一步更可能是 training-time sparsity 或更长 context 支持，而非 disaggregated inference。

3. **Expected Attention 作者**：已有 scoring 方法，如果意识到 disaggregated transfer 场景，可能快速扩展。但当前 PyTorch 实现未优化，距离系统级集成较远。

4. **vLLM/SGLang 团队**：vLLM 的 disaggregated inference RFC #13020（async KV transfer）已被关闭（not_planned），说明短期不会深入。

**结论**：6 个月内被截胡的概率中等（~30%），**Mooncake 团队是最大威胁**。Phase 0 validation 应在 4 周内完成以降低风险。

---

## 六、论文定位

### 6.1 OSDI 故事线

**Title**: *SparseTransfer: Attention-Aware KV Cache Migration for Disaggregated Long-Context LLM Inference*

**One-sentence claim**: 
> Disaggregated inference 中的 KV cache 传输应该是 attention-aware 的——只传输 decode 阶段实际需要的 KV pages，而非完整的 KV cache。

**为什么这是一个 systems insight 而非简单的 engineering optimization**：

1. 它改变了 disaggregated inference 的**接口语义**：从 "transfer complete KV cache" 到 "transfer sparse KV cache + metadata + on-demand fetch"。这是一个 **API-level** 的设计变更，不是实现层面的优化。

2. 它揭示了一个跨层的 co-design opportunity：attention 层的稀疏性信息（之前只用于加速 compute）可以指导网络传输决策。这种 **cross-layer information flow** 是 systems 论文的经典贡献模式。

3. 它有 **second-order effect**：sparse transfer 不仅减少传输时间，还释放 decoder 端的 GPU memory，从而增加 batch size，产生 throughput 的 multiplicative improvement。这种效应只有在 system-level 评估中才能体现。

### 6.2 贡献列表

1. **Problem identification + empirical study**：首次系统性量化 disaggregated long-context inference 中 KV cache 传输的浪费程度（传输 100%，使用 10-50%），并分析 prefill attention 对 decode access pattern 的预测能力（per-layer, per-head, per-task 的 recall@K 曲线）
2. **Attention-aware transfer protocol**：利用静态 head 分类 + 动态 page importance scoring，在 prefiller 端决策传输内容。接口语义从 "transfer complete KV" 变为 "transfer sparse KV + metadata + on-demand fetch"
3. **Sparse KV store + on-demand fetch**：decoder 端直接消费 sparse KV cache（FlashInfer BSR format），with speculative prefetch + on-demand fallback for scoring errors
4. **Second-order throughput analysis**：量化 sparse transfer → decoder memory saving → batch size increase → throughput amplification 的级联效应
5. **End-to-end system**：基于 Mooncake + FlashInfer + vLLM/SGLang 的完整实现，支持 128K-1M context

### 6.3 对标论文

| 论文 | 会议 | 核心 insight | SparseTransfer 的类比 |
|------|------|-------------|----------------------|
| DistServe | OSDI'24 | Prefill 和 decode 特性不同，应分离 | KV cache 内容重要性不同，应选择性传输 |
| Mooncake | FAST'25 | KV cache 应分布式管理，拓扑感知传输 | 在 Mooncake 的 block 传输上叠加 attention-aware selection |
| BLITZSCALE | OSDI'25 | 网络带宽是 autoscaling 的瓶颈，应调度 | KV 传输量是 disaggregated inference 的瓶颈，应裁剪 |
| Jenga | SOSP'25 | 不同 attention 类型的 KV cache 异构管理 | 不同 head 的 KV cache 差异化传输；可复用 layer property 抽象 |
| LServe | MLSys'25 | 50% heads 是 streaming（只需 local window） | 前移 sparsity 判断到传输决策 |
| Expected Attention | arXiv'25 | Gaussian-based 预测 future attention | 可作为 scoring 方法的候选/对比 |

### 6.4 论文结构

1. **Introduction**: Disaggregated inference + long context → KV transfer 瓶颈 → observation: decode 只用部分 KV
2. **Background & Motivation**: 量化传输浪费（Section 一的数据）+ 分析 sparse attention 的 predictability
3. **Design**: Head classification → page scoring → selective paged transfer → sparse KV store → on-demand fetch
4. **Implementation**: Mooncake + FlashInfer BSR + vLLM/SGLang scheduler integration
5. **Evaluation**: End-to-end TTFT/throughput + quality + ablation + scaling + per-task analysis
6. **Discussion**: Limitations (code tasks, multi-turn) + future work (training-time co-design)

---

## 七、实验规划

### Phase 0：可行性验证（4 周）— Go/No-Go 决策点

> **目标**：验证四个核心假设，任何一个假设失败都应重新评估方向。同时，Phase 0 的数据将决定系统设计的深化方向和目标会议（见 Section 9.4 的决策矩阵）。

#### 实验 A：Decode Attention 的 KV Page Access Pattern 分析

**做什么**：在真实 long-context inference 中，统计 decode 阶段每个 head 实际 attend to 的 KV pages 分布。

**怎么做**：
1. 使用 Llama 3.1 8B（快速迭代）**+ Llama 3.1 70B**（目标模型验证）+ RULER/LongBench 128K inputs
2. 在 decode 阶段提取 attention score（用 naive attention，不用 FlashAttention，只对少量样本做）
3. 对每个 decode step，计算每个 head 的 page-level attention concentration：
   - 定义 "effective pages" = 最少多少 pages 覆盖 X% 的 attention mass
   - 统计 effective pages 的比例（X=90%, 95%, 99%）
4. 分析 temporal stability：连续 decode steps 之间 effective pages 的 overlap ratio
5. 分析 per-layer 差异——不同层的 sparsity 是否一致？是否存在某些层 sparsity 显著低于平均？

**Go/No-Go 标准**：
- ✅ 如果 90% attention mass 集中在 <30% 的 pages：方向可行
- ⚠️ 如果 90% attention mass 需要 30-60% 的 pages：收益有限，需要更精细的设计
- ❌ 如果 90% attention mass 需要 >60% 的 pages：放弃方向

#### 实验 A2：70B 模型 Head 分类 Profiling

**做什么**：在 Llama 3.1 70B 上复现 LServe/DuoAttention 的 streaming/retrieval head 分类。

**怎么做**：
1. 使用 DuoAttention 的 gating value 方法对 70B 模型的 80 层 × 8 KV heads = 640 个 head 做分类
2. 统计 streaming head 比例（与 8B 的 ~50% 做对比）
3. 验证 streaming head 的 windowed attention 是否真的无损（在 128K context 下）

**Go/No-Go 标准**：
- ✅ Streaming head 比例 ≥40%：方向可行
- ⚠️ Streaming head 比例 20-40%：减少比例缩小但仍有价值
- ❌ Streaming head 比例 <20%：70B 模型不适合 streaming head 优化路径

#### 实验 B：Prefill Score 对 Decode Pattern 的预测能力

**做什么**：验证 prefill 最后一步的 attention score 能否预测 decode 的 page access pattern。

**怎么做**：
1. 使用实验 A 的数据
2. 计算 prefill last-layer 的 page importance ranking（方案 B：最后一个 query token 的 naive attention）
3. 同时计算 Expected Attention 方法的 importance ranking 作为对比
4. 计算 "如果只传输 prefill-predicted top-K% pages，decode 的 attention recall 是多少？"
5. 画 K vs. recall 曲线（类似 precision-recall curve）
6. 分析 per-layer recall——最后一层的 score 对中间层 decode pattern 的预测能力如何？如果差距大，需要 per-layer scoring

**Go/No-Go 标准**：
- ✅ 传输 30% pages → recall >95%：very promising
- ⚠️ 传输 30% pages → recall 80-95%：需要 on-demand fetch，但仍可行
- ❌ 传输 30% pages → recall <80%：prefill score 预测力不足，需要 Expected Attention 或其他方法

#### 实验 C：Per-Task 质量影响

**做什么**：验证 sparse KV transfer 对不同任务类型的质量影响。

**怎么做**：
1. 使用 LongBench 的各类任务（QA, summarization, code, few-shot, multi-doc）
2. 在 decode 端使用 sparse attention（只用 top-K% pages），测量任务准确率
3. 特别关注 code 任务（Rethinking 论文发现的高风险类别：KIVI 从 97.0 降到 30.0）
4. 测试不同 sparsity budget（10%, 20%, 30%, 50%）下各任务的退化曲线

**Go/No-Go 标准**：
- ✅ 所有任务在 top-30% pages 下质量下降 <5%：直接可用
- ⚠️ Code 任务下降 >10%，其他任务 <5%：需要 per-task routing
- ❌ 多数任务下降 >10%：放弃方向

### Phase 1：SparseTransfer 原型（8 周）

#### 1a：Prefiller 端 Importance Scorer（2 周）
- 实现 last-token naive attention 的 per-page importance scoring（方案 B，无需修改 FlashAttention kernel）
- 实现 streaming head detection（离线 profiling，复用 LServe/DuoAttention 方法）
- 实现 page selection：streaming heads → window + sink；retrieval heads → top-K pages

#### 1b：Selective Paged Transfer（3 周）
- 基于 Mooncake BatchTransfer API 实现选择性页面传输层
- Metadata 传输协议：selected page indices + per-head sparsity pattern
- 逐层完成通知

#### 1c：Decoder 端 Sparse KV Store（3 周）
- 基于 FlashInfer BSR format 的 sparse KV memory allocator
- 将收到的 sparse pages 填入 BSR 结构
- 适配 FlashInfer 的 sparse decode attention kernel

### Phase 2：On-Demand Fetch + 系统集成（6 周）

#### 2a：On-Demand Fetch 协议（2 周）
- Decoder 端 CRA 检测 + fetch request
- Prefiller 端 page server（从 GPU/CPU memory 回传 requested pages）
- Fetch 频率统计与自动 K 调整

#### 2b：vLLM/SGLang Scheduler 集成（4 周）
- 将 SparseTransfer 集成为 vLLM/SGLang 的 disaggregated inference backend
- Scheduler 根据 sparsity ratio 估算 decoder 内存使用，优化 batch scheduling
- Support for continuous batching with mixed sparse/dense KV cache

### Phase 3：端到端评估（4 周）

#### 评估维度

| 维度 | 指标 | Baseline |
|------|------|---------|
| TTFT | P50, P95, P99 | Full KV transfer (Mooncake) |
| Throughput | Requests/sec | Full KV transfer + vLLM dense attention |
| Quality | Perplexity, LongBench scores, RULER accuracy | Full KV cache decode |
| Memory | Decoder KV cache memory per request | Full KV cache |
| Network | Total bytes transferred, bandwidth utilization | Full transfer |
| On-demand fetch | Fetch rate, fetch latency overhead | N/A |

#### 实验配置

| 配置 | 硬件 | 模型 | Context Length |
|------|------|------|---------------|
| Small | 4×H100 (2P+2D) | Llama 3.1 8B | 128K |
| Medium | 8×H100 (4P+4D) | Llama 3.1 70B | 128K |
| Large | 16-32×H100 | Llama 3.1 70B | 512K-1M |

#### 关键对比实验

1. **SparseTransfer vs Full Transfer**：端到端 TTFT + throughput
2. **SparseTransfer vs ThunderServe（KV4 quantization only）**：验证 sparsity 的增量价值
3. **Ablation: Static only vs Static+Dynamic**：量化 streaming head 分类 vs page selection 的各自贡献
4. **Varying sparsity budget（K = 10%, 20%, 30%, 50%）**：画 quality-transfer tradeoff 曲线
5. **Scaling context length（32K → 128K → 512K → 1M）**：验证长 context 下收益是否增大
6. **Per-task breakdown**：特别关注 code, QA, summarization, multi-doc

### Phase 4：论文撰写（4 周）

- 定位：OSDI 2027 spring submission（如果 timeline ~2026-10-01 ddl）
- 或 SOSP 2027（如果 timeline 不赶 OSDI）

---

## 八、时间线与里程碑

| Phase | 时间 | 里程碑 | 决策点 |
|-------|------|--------|--------|
| Phase 0 | Week 1-4 | KV access pattern 分析 + scoring 预测能力 + 70B head profiling | Go/No-Go |
| Phase 1 | Week 5-12 | Working prototype: scorer + selective transfer + sparse store | Demo |
| Phase 2 | Week 13-18 | On-demand fetch + vLLM/SGLang integration | System complete |
| Phase 3 | Week 19-22 | 端到端评估完成 | Paper-ready data |
| Phase 4 | Week 23-26 | 论文撰写 + submission | Submit |

**总计 ~6.5 个月**（1-2 人全职）。主要耗时在 Phase 1-2 的系统实现——选择性传输层需要在 Mooncake 之上自行封装，vLLM/SGLang scheduler 集成涉及 batch scheduling 对 sparse memory 的适配。

---

## 九、OSDI 可发表性评估

### 优势

1. **问题极其 timely**：Disaggregated inference 是 2024-2025 最热的 serving 架构方向；long-context 是模型能力前沿；两者的交叉点（long-context disaggregated inference）正在成为生产瓶颈。

2. **Insight 清晰且 non-trivial**：KV cache 传输应该是 attention-aware 的。这是一个跨越 attention 算法层和网络传输层的 co-design insight。

3. **Second-order throughput effect**：减少传输 → 释放 decoder 内存 → 增加 batch size → throughput 乘法级提升。这种 system-level amplification effect 是 OSDI 审稿人喜欢看到的。

4. **组件成熟、集成新颖**：核心底层技术（Mooncake, FlashInfer, LServe/DuoAttention, Expected Attention）都已各自验证，但没人把 sparse attention 的知识与 KV cache 传输决策组合在一起。这是经典的 "right combination at the right time" 系统论文。

5. **评估故事完整**：端到端 TTFT + throughput + quality + per-task + scaling，涵盖了 serving 论文的所有维度。

### 劣势与反驳

| 审稿人可能的质疑 | 反驳 |
|-----------------|------|
| "This is just LServe + Mooncake" | LServe 做 decode 加速（单机），Mooncake 做传输（全量）。将 sparsity 前移到传输决策是新的 API-level 设计（接口从 "transfer complete KV" 变为 "transfer sparse KV + metadata + on-demand fetch"）。类比：DistServe 也是 "Orca + prefill/decode 分离"，但 insight 的价值在于跨层 co-design。 |
| "Scoring 不准怎么办？" | On-demand fetch 兜底。Streaming head 分类是确定性正确的（已占 ~50% 减少）。Retrieval head 的 scoring 可用 Expected Attention 方法增强。 |
| "Expected Attention 已经做了 KV importance scoring" | Expected Attention 做的是单机 KV compression（evict 不重要的 KV 节省内存）。SparseTransfer 做的是跨节点 transfer-time selection（减少网络传输量 + decoder 内存）。两者的系统语义不同：EA 是 "compress then use"，ST 是 "select then transfer then use with on-demand fallback"。 |
| "Code 任务质量退化" | Per-task routing（Rethinking 论文验证的方案）。Code 任务自动 fallback 到 full transfer。评估中明确报告 per-task 质量。 |
| "只在长 context 有效" | 短 context (<32K) 的 KV cache 传输不是瓶颈（<100ms）。Long-context 是 2025-2026 的趋势（Llama 3.1 128K, Gemini 1M+），OSDI 应关注前沿问题。且 sparsity 随 context 增长而增大，SparseTransfer 的收益与 context length 正相关。 |
| "增量贡献不够" | 量化 second-order effect：传输量减少 85% → decoder 内存节省 → batch size 增加 5-10× → throughput 乘法级提升。这种跨层 amplification effect 只有在端到端系统评估中才能体现。 |

### 总体判断

| 维度 | 评分 | 说明 |
|------|------|------|
| 问题重要性 | ★★★★★ | Long-context + disaggregated inference 是最前沿的交叉点 |
| 新颖性 | ★★★½ | Cross-layer co-design insight 真实存在；但 "obvious next step" 风险较高，需要深化 scoring 方法或 second-order analysis 来加厚 novelty |
| 技术深度 | ★★★★ | Scoring + selective transfer + sparse store + on-demand fetch |
| 评估说服力 | ★★★★★ | 端到端 + per-task + scaling + ablation + second-order throughput |
| 可行性 | ★★★★ | 核心组件已有开源实现，但选择性传输层和 scheduler 集成需要中等工程量 |
| 被截胡风险 | ★★★ | 中等（Mooncake 团队风险最高） |

**结论：这是一个高可行性、高影响力的方向，但存在 incrementality 风险——需要在 Phase 0 之后根据数据决定最终的系统设计深度和目标会议。详见 9.4 节。**

### 9.4 Incrementality 风险与深化方向

#### 核心问题

当前方案建立在 Mooncake 之上。如果最终实现只是 "Mooncake + attention-based block filter"，审稿人大概率会认为 incremental：

- Importance scorer（last-token naive attention + top-K）：几十行代码
- Block selection 过滤：在 Mooncake 的 block selection policy 上加一层 attention-based filter
- Decoder 端 sparse KV：复用 FlashInfer BSR

**最尖锐的质疑**："换个 eviction policy 就是一篇顶会论文？"

诚实评估各层面增量：

| 维度 | 增量大小 | 说明 |
|------|---------|------|
| 算法层 | 小 | Scoring 方法都是已有的（LServe head classification + naive attention top-K） |
| 系统层 | 中 | 接口语义变了（full → sparse + metadata + on-demand fetch），但改动量有限 |
| Insight 层 | 中 | "传输应该是 attention-aware 的" 是真实 insight，但说出来显而易见 |
| Second-order effect | 大 | Memory saving → batch size → throughput，但这是 sparse attention 的自然延伸 |

**判断：如果只做 "Mooncake + filter"，不够 OSDI/SOSP。** 需要在以下至少一个方向做出实质性深化。

#### 深化方向 A：发现非平凡的 empirical insight

如果 Phase 0 数据揭示**意料之外**的现象，empirical study 本身就是贡献。可能的发现：

- Decode 前几步和后几步的 attention sparsity 有结构性差异（"warm-up" phase 需要显著更多 KV pages）
- 不同层的 attention pattern 预测难度差异很大（某些层几乎不可预测，某些层完全可预测）
- Sparsity 与内容类型的关系不只是程度差异而是模式差异（code 和 natural language 的 attention 拓扑完全不同）

但如果结论只是 "sparsity 确实存在，top-K 能 work"，那只是验证已知事实，贡献不够。**这条路径有运气成分。**

#### 深化方向 B：Co-design 调度（最推荐）

不只 "传少点"，而是利用 sparse transfer 的特性做**传统 full transfer 做不了的事**：

**B1. Speculation-based transfer pipeline**

Sparse transfer 天然有两个阶段：确定性部分（streaming head 的 window KV）和投机部分（retrieval head 的 selected pages）。这启发了一种新的流水线设计：

```
  Full Transfer (当前):
    prefill done → [===== transfer all KV =====] → decode start
                   ↑                             ↑
                   scoring 不存在                 TTFT

  Speculation Pipeline (SparseTransfer):
    prefill done → [stream window] → decode start (with partial KV)
                        ↑ scoring    [selected pages] → merge
                        并行              ↑
                                     on-demand fetch (rare)
```

Streaming head 的 window KV 是确定性正确的，可以在 scoring 完成前就开始传输。Scoring 完成后再传 retrieval head 的 selected pages。Decoder 可以在只有 streaming head KV 的情况下开始前几步 decode（质量略降但 TTFT 更快），selected pages 到达后逐步提升质量。

这是一个**新的 pipeline 设计**——full transfer 没有这个 "确定性/投机" 分层结构。

**B2. SLO-aware adaptive budget**

Sparse transfer 引入了一个 full transfer 不存在的 latency-quality tradeoff knob：

- SLO 紧（高并发、TTFT 预算即将超标）→ 降低 K，传更少，更快但质量略降
- SLO 松（低负载、余量充足）→ 增大 K，传更多，更高质量
- 极端情况 → fallback 到 full transfer（code 任务、SLO 无压力时）

这可以与 SOLA（MLSys'25）的 SLO-aware scheduling 协同——SOLA 做的是 prefill/decode 优先级调度，SparseTransfer 加入后，scheduler 多了一个维度：不只调度 "谁先做"，还调度 "传多少"。

**B3. Importance-weighted cross-request KV sharing**

共享 prefix 的不同 request 可能选中不同的 important pages。Sparse transfer 让 decoder 可以维护 "union of important pages across requests"：

- Request A 选中 pages {2, 7, 15, 42}
- Request B（共享 prefix）选中 pages {2, 7, 31, 55}
- Decoder 存储 union {2, 7, 15, 31, 42, 55}，两个 request 共享

这比 Mooncake 的 block-level prefix caching 更细粒度——Mooncake 要么缓存整个 block，要么不缓存。SparseTransfer 可以做 importance-weighted 的部分缓存，在相同内存下服务更多 request。

**B1+B2+B3 加在一起，系统贡献就从 "换 filter" 变成了 "新的 transfer-scheduling co-design"，技术深度足够 OSDI。**

#### 深化方向 C：不基于 Mooncake 的 Sparse-First 设计

最激进的方案：不在 Mooncake 上加 filter，而是**从 sparse 出发重新设计 disaggregated KV cache 系统**：

- KV cache 的存储格式从一开始就是 BSR（不是 dense → filter → sparse）
- Scheduler 按 sparse KV budget 做 admission control 和 placement（不是按 context length）
- Prefill 和 decode 的 GPU 资源分配基于 actual KV transfer volume

这是一个更大的 story，但工程量也大得多。适合有充足人力（3+ 人）的团队。

#### Phase 0 后的决策矩阵

| Phase 0 结果 | 推荐深化方向 | 目标会议 |
|-------------|------------|---------|
| 数据有意外发现（非平凡 insight） | A + B（empirical insight + co-design） | OSDI/SOSP |
| 数据验证已知结论，top-K work well | B（co-design 是核心贡献） | OSDI/SOSP |
| 数据验证已知结论，但 co-design 实现困难 | 聚焦 B1（speculation pipeline）+ 端到端评估 | EuroSys/ATC |
| Sparsity 不够或预测不准 | 降级到 Section 十的备选路径 | MLSys/Workshop |

---

## 十、备选降级路径

如果 Phase 0 部分失败：

| 失败情况 | 降级方案 | 目标会议 |
|---------|---------|---------|
| Page access 不够稀疏（需 >60% pages） | 转向 quantization-only transfer（ThunderServe 路线，但做更好的 adaptive quantization） | MLSys |
| Prefill score 预测不准 | 用 Expected Attention 的 Gaussian-based scoring（方案 C）或训练 lightweight MLP predictor + on-demand fetch 为主 | EuroSys |
| Code 任务严重退化，per-task routing 复杂 | 聚焦 QA/summarization 场景，承认 limitation | ATC |
| 整体收益不显著 | 发布 empirical study "KV Cache Access Patterns in Long-Context LLM Inference" | Workshop |

---

## 十一、与已有 ideas 的关系

### vs. [[elastic-moe-p2p|Elastic MoE]]

两个方向共享 P2P RDMA 通信层，但完全正交：
- ElasticMoE 优化的是 **MoE expert 的负载均衡**（compute-side）
- SparseTransfer 优化的是 **KV cache 的传输效率**（data-movement-side）
- 可以同时做：在 MoE 模型的 disaggregated inference 中，expert 用 ElasticMoE 调度，KV cache 用 SparseTransfer 传输

### vs. [[p2p-rdma-dynamic-context-parallelism|P2P RDMA Dynamic Context Parallelism]]

DCP 方向关注的是 **training** 的 context parallelism 通信优化。SparseTransfer 关注的是 **inference** 的 KV cache 传输。两者面向不同 workload，但共享 "P2P 比 collective 更适合动态/稀疏通信" 的核心 insight。

### 优先级建议

三个方向中，**SparseTransfer 的 risk-adjusted expected value 最高**（实验规模最小、降级路径最丰富）。详见 Section 九。
