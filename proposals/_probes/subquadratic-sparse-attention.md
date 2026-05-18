---
type: probe
topic: Content-Dependent Sparse Attention for Long-Context LLM — 以 SubQ SSA 为切入点，梳理稀疏注意力在全量/线性注意力之间的第三条路
created: 2026-05-06
probed_papers:
  - "[[MSA-arXiv26]]"
  - "[[DeepSeek-V4-arXiv26]]"
  - "[[FlashAttention-4-MLSys26]]"
  - "[[BLASST-MLSys26]]"
  - "[[MAC-Attention-MLSys26]]"
  - "[[SparseSpec-MLSys26]]"
  - "[[Cartridges-ICLR26]]"
  - "[[AttnRes-arXiv26]]"
  - "[[PASTA-ICLR24]]"
  - "[[LLMSteer-NeurIPSW24]]"
  - "[[Libra-ICLR26]]"
  - "[[FluxMoE-arXiv26]]"
---

# Probe: Subquadratic Sparse Attention

> 起点：[SubQ SSA 博客](https://subq.ai/how-ssa-makes-long-context-practical) 声称 content-dependent sparse attention 实现了 linear scaling + 保持任意位置检索能力。这是稀疏注意力路线的最新工业投注（$29M seed, May 2026 launch），但它的主张与过去 3 年学术界在 sparse/linear/hybrid attention 上的经验存在多重张力。本 probe 梳理 landscape，定位 SSA 的主张在学术坐标系中的位置。

## Landscape

### 坐标系：长上下文高效注意力的四条路线

```
                    保留 exact attention
                    │
         FlashAttention (IO优化)
         FA1→FA2→FA3→FA4        NSA (原生可训练稀疏)
         BLASST (block sparse)   SSA/SubQ (content-dependent sparse)
         MAC-Attention (query复用)  Twilight (adaptive budget sparse)
         DSA/CSA/HCA (DeepSeek稀疏家族)
                    │
    O(N²)→O(N log N)────────────┼────────────O(N)→O(1)
                    │
         Log-Linear Attention    Mamba/Mamba-2 (SSM)
         Infini-attention         RWKV / DeltaNet (线性注意力)
         Jamba (混合)             Titans (test-time training)
         Hymba (混合)             Linear Transformer
                    │
                    放弃 exact attention
```

### 每条路线的关键工作

| 工作 | 做了什么 | 没做什么 | 隐含假设 |
|------|----------|----------|----------|
| **FlashAttention 1-4** | IO-aware exact attention kernel，tiling + online softmax 避免物化 N×N 矩阵。FA4 针对 Blackwell B200 的非对称硬件 scaling（Tensor Core 翻倍但 MUFU/SFU 未变）做 softmax 软件模拟 + 条件化 rescale | 不改变 attention 的计算复杂度，仍是 O(N²) FLOPs | 硬件带宽是瓶颈而非计算量；exact attention 的数学精度不可牺牲 |
| **NSA (DeepSeek, ACL 2025 Best Paper)** | 原生可训练的稀疏注意力：token 压缩 + token 选择 + 滑动窗口三条分支，门控融合。块重要性评分复用压缩注意力的中间分数（零额外成本）。64K 解码 11.6× 加速，且在 7/9 benchmark 上**超越**全注意力 | 仅在 27B MoE 模型上验证；未扩展到 100B+ 或 dense 架构 | 稀疏性本身可以充当正则化器，过滤噪声 token 反而提升推理质量；硬件对齐的块选择是实现 wall-clock 加速的关键 |
| **DeepSeek DSA (V3.2)** | Lightning Indexer（FP8, 64 index heads）对历史 token 计算相关性分数，选 top-2048。MLA 低秩压缩 KV cache | Indexer 本身仍是 O(N²)，只是 offset 了细粒度 attention；在超长 context（1M+）下 indexer 成本不可忽略 | 通过可学习 indexer 实现 content-dependent selection，indexer 的精度需求远低于 attention 本身 |
| **DeepSeek CSA+HCA (V4)** | CSA = 先沿序列维压缩 KV（m×）再 DSA top-k；HCA = 更激进压缩但保留 dense attention。1M context 单 token FLOPs 压到 V3.2 的 27%，KV cache 到 10% | 混合策略中 HCA 的 dense 分支意味着仍未完全摆脱 O(N²)；CSA 的压缩策略与 selection 策略之间的最优分配未理论化 | 不同层需要不同的 attention 精度：部分层可以极端压缩（HCA），部分需要细粒度选择（CSA）；完全稀疏可能不够 |
| **SubQ SSA (Subquadratic Inc., May 2026)** | 对每个 query token，模型学习选择一个小 subset of positions 做 exact attention。声称三属性同时成立：linear cost + content-dependent routing + arbitrary-position retrieval。128K 7.2× over FA2，1M 52.2× | **无公开论文、无权重、无独立验证**。仅三个 benchmark 报告（RULER/MRCR/SWE-Bench），无通用推理/数学/多语言评测。训练细节未公开 | Content-dependent routing 可以在不牺牲质量的前提下达到 dense attention 的检索能力；三阶段训练（pretrain→SFT→RL，其中 RL 专门针对长上下文检索失败模式）是实现 functional context window 的必要条件 |
| **Magic.dev LTM-2-mini (Aug 2024)** | 100M token context，"sequence-dimension algorithm" 声称 1000× more efficient than Llama attention。HashHop benchmark 95% @ 100M | 未公开架构、未发布模型、未发论文。$465M+ 融资后无外部可验证证据 | 通过 memory-augmented + 特殊 tokenization（hash strings as single tokens）实现超长上下文；subquadratic 但不一定是 sparse attention |
| **BLASST (MLSys 2026)** | 动态 block attention sparsity：复用 FlashAttention 的 running softmax max 做 block 级 thresholding，skip 掉 local max 远低于 running max 的 block。1.62× prefill, 1.48× decode, 零预处理开销 | 只在推理时应用，不涉及训练时稀疏；block 粒度约 128 tokens，对极细粒度（token-level）的关键信息检索可能 miss | Softmax 的 running max 是良好的 block 重要性信号；大部分 block 对当前 query 的贡献可忽略 |
| **Twilight (NeurIPS 2025 Spotlight)** | Adaptive top-p pruning：动态决定每个输入的稀疏预算，可叠加到任何稀疏注意力算法上。剪枝 98% token 无明显质量损失，15.4× self-attention 加速 | 是 meta-framework，本身不定义稀疏模式——依赖底层稀疏方法的质量 | 固定预算（如 top-k）是次优的——不同输入/层/头需要不同的稀疏度；预算的自适应分配问题与稀疏模式选择问题是正交的 |
| **MAC-Attention (MLSys 2026)** | Match-Amend-Complete：复用 pre-RoPE query 的 attention 摘要，仅重算边界带和尾部。128K 下最多 99% KV 访问减少，14.3× attention 加速 | 依赖 pre-RoPE 和 post-RoPE query 之间的相似性——这个假设在长 context 下未经理论验证 | RoPE 对 query 的旋转在长距离上足够小，使得 pre/post-RoPE attention pattern 保持高度相关 |
| **MSA (arXiv 2026)** | 把 RAG 的 retrieve-then-read 替换为可微 sparse attention：document-wise KV 压缩 + routing key projector + cosine similarity top-k。2×A800 跑通 100M token，1M NIAH 94.84% | 需要 continual pre-training 158B tokens；routing 仅在模型后半层使用（前半层 hidden states 语义不够成熟）；document-wise 的粒度限制了对非文档结构长文本的适用性 | Retrieval 和 generation 之间的优化 gap 可以通过 end-to-end differentiable routing 消除；document-wise positional encoding 可以解耦位置与文档数量 |
| **Cartridges (ICLR 2026)** | 把长文档用梯度下降训练成紧凑 KV 表示（prefix-tuning style），38.6× 内存压缩，26.4× 吞吐，context length 从 128K 外推到 484K | 每份文档需要单独跑 self-study（合成对话 + context distillation），离线成本数十 GPU-minutes per document；未验证对多跳推理的有效性 | KV cache 可以从"计算结果"变成"预先训练的持久对象"；self-study 合成的对话能覆盖足够多的 query 分布 |
| **Linear Attention / SSM 路线** (Mamba-2, DeltaNet, RWKV, Log-Linear) | 用固定大小的循环状态替代 KV cache，O(N) 计算 O(1) 内存。Log-Linear Attention 在 O(N log N) 找到 sweet spot | 在精确检索任意远距离的特定事实上弱于 attention；长序列上的 associative recall 退化（Log-Linear 部分改善） | 固定大小 state 足以编码长序列中的关键信息；gating 机制可以帮助选择性保留/遗忘 |
| **Jamba / 混合架构** (AI21, Hymba, Hunyuan-TurboS) | 1 Transformer layer : 7 Mamba layers + MoE，兼顾 Mamba 的吞吐和 Transformer 的精确检索。256K context on single 80GB GPU | 保留了 dense attention 层，意味着最坏情况下的 scaling 仍受限于这些层的 O(N²) | 不需要所有层都做精确检索——少量 Transformer 层足以提供"sharp" retrieval，其余用高效 SSM 处理 |

### 整体画面

过去 3 年，长上下文高效注意力的研究从两个极端向中间收敛：**纯 exact attention（FlashAttention 路线）承认 N² 在硬件上终将碰壁，纯 linear/SSM 路线承认固定 state 在精确检索上不如 attention**。2025-2026 的核心趋势是**在中间地带寻找答案**——sparse attention 保留 attention 的计算形式但限制 visible token 数量；Log-Linear 在 SSM 中引入对数级 memory；混合架构显式 interleave。

SubQ SSA 的主张在这个坐标系中的位置是：**最接近 NSA / DSA 的 content-dependent sparse attention 路线，但声称做到了更彻底——完全 linear scaling 且不需要任何 dense fallback**。这和 DeepSeek-V4 的 HCA（保留 dense attention on compressed KV）形成鲜明对比。

## Tensions

### Tension 1: 稀疏注意力到底是「加速」还是「降质」？

NSA 的实验结果是这个 tension 的核心证据：27B MoE 模型在 270B token 预训练中，**稀疏注意力的下游性能全面超越全注意力**（7/9 benchmark, LongBench +3.2%）。NSA 作者的解释是稀疏化过滤了噪声 token，起到了正则化作用。

但这一发现在以下条件下是否成立是未知的：
- 更大的模型（100B+ dense，而非 27B MoE）
- 更多的训练 token（2T+，而非 270B）
- 不同的稀疏模式（NSA 的三分支 vs SSA 的 content-dependent selection vs Twilight 的 top-p）

SubQ SSA 的 benchmark 结果（RULER 95%, SWE-Bench 81.8%）部分支持 NSA 的结论，但仅三个 benchmark 远不足以支撑「稀疏注意力不降质」的普遍主张。**涉及的论文**：[[NSA]]（外部）、[[BLASST-MLSys26]]、[[SparseSpec-MLSys26]]、Twilight。

### Tension 2: Content-dependent routing 是否比 fixed-pattern 更好？

SubQ 博客中明确批评 fixed-pattern sparse attention（sliding window、strided、dilated）是"基于位置而非内容做 routing"。学术文献中这个问题是分裂的：

- **支持 content-dependent**：NSA（块选择基于压缩注意力分数）、DSA（lightning indexer）、SSA（content-dependent selection）、Twilight（adaptive top-p）
- **支持 fixed/structural 足够**：Sliding window attention（Mistral、Gemma 的实际选择）、BLASST 的 block-wise softmax thresholding（并非 content-aware，而是 score-aware）

关键未知量：content-dependent routing 的**额外计算开销**是否值得？DSA 的 lightning indexer 本身就是 O(N²)，虽然在 FP8 下跑得很快，但在 1M token 时仍然 significant。NSA 的创新（零额外成本的块重要性评分）可能才是正确的方向。SSA 如何解决这个开销问题目前完全不清楚。

**涉及的论文**：DSA/[[DeepSeek-V4-arXiv26]]、NSA、[[MAC-Attention-MLSys26]]、BLASST。

### Tension 3: 是否需要 dense attention fallback？

- **DeepSeek-V4 说需要**：HCA（Heavily Compressed Attention）保留 dense attention，只是压缩了 KV。暗示即使有 CSA 的稀疏选择，某些层仍需要全局 dense 信息。
- **SubQ SSA 说不需要**：声称完全稀疏化，"sparse from the ground up"，无 dense fallback。
- **NSA 没有明确答案**：NSA 的三分支中，滑动窗口（512）和压缩分支提供了一定程度的全局覆盖，但并非 dense。

这是一个架构级的根本分歧。如果 DeepSeek 在 1.6T 参数模型上仍然保留了 HCA 的 dense attention，说明他们的实验表明完全稀疏在某种场景下会退化。SSA 能否在 12M context 下无退化，是这个 tension 的核心检验。

**涉及的论文**：[[DeepSeek-V4-arXiv26]]、SubQ SSA、Twilight。

### Tension 4: 训练-推理 gap — 稀疏注意力应该从什么时候开始？

| 策略 | 代表工作 | 优点 | 风险 |
|------|----------|------|------|
| 预训练阶段就稀疏 | NSA | 模型学习适应稀疏模式，可能提升质量 | 训练成本更高（虽然单步更快），需要修改训练基础设施 |
| 仅推理时稀疏 | BLASST, Twilight, MAC | 即插即用，兼容现有模型 | 模型未学习稀疏模式，可能在某些 pattern 下崩溃 |
| 从 dense 微调到 sparse | SubQ SSA（推测） | 折中方案 | 微调阶段可能不足以让模型重新学习 attention pattern |

SubQ SSA 的训练流程（pretrain→SFT→RL）暗示他们至少在 pretrain 阶段就使用了 SSA，但技术细节不公开。

**涉及的论文**：NSA、[[SparseSpec-MLSys26]]、BLASST、MAC-Attention。

### Tension 5: 基准测试的局限性 — MRCR v2 揭示的问题

MRCR v2 的结果暴露了一个尴尬的事实：**更大的模型在长上下文检索上可能更差**。Opus 4.6 (78.3%) > Opus 4.7 (32.2%)，GPT-5.5 (74.0%) > GPT-5.4 (36.6%)。这说明长上下文能力不是 model scale 的自然副产品，而是一个需要专门工程化的维度。

SubQ SSA 在 MRCR v2 上 65.9%（production）vs 83%（research）的 17-point gap 暗示他们的 production 部署可能存在显著的性能退化，原因不明。

## Industry Activity

### Closed-source / 未公开系统

| 系统/公司 | 关键动作 | 融资/规模 |
|-----------|----------|-----------|
| **Subquadratic Inc. (SubQ)** | May 2026 推出 SubQ API + SubQ Code + SubQ Search。CTO Alex Whedon ex-Meta，11 PhDs。声称 12M context research model，1M production API。定价 $0.08/M tokens | $29M seed, $500M 估值 |
| **Magic.dev** | Aug 2024 宣布 LTM-2-mini 100M context，HashHop 95%。2026 年仍无公开使用证据。Eric Schmidt 领投 | $465M+ total |
| **NVIDIA** | NVFP4 KV cache（4-bit floating point, <1% accuracy loss）、Dynamo KV-aware routing、FlashAttention-4 for Blackwell。Blackwell Ultra (GB300) 双倍 SFU 缓解 softmax 瓶颈 | N/A（硬件厂商） |
| **DeepSeek** | NSA (ACL 2025 Best Paper) → DSA (V3.2) → CSA+HCA (V4)。MLA 低秩压缩 + 稀疏索引 + 混合注意力。开源模型 | N/A |
| **Google DeepMind** | Infini-attention（ICML 2024）、MRCR 评测。Gemini 3.1 Pro 长上下文表现意外弱（MRCR 26.3%） | N/A |
| **Anthropic** | Opus 4.6 在 MRCR 上 78.3%（当前 SOTA），但 4.7 降至 32.2%。Anthropic 在 4.7 系统卡中承认倒退 | N/A |

### 值得关注的信号

- **SubQ 团队背景**：CTO Alex Whedon 的经历是 Meta → TribeAI（40+ enterprise AI implementations），不是学术出身。这意味着 SSA 可能更多是工程创新而非理论突破
- **Magic.dev 的沉默**：$465M 融资后近两年无公开进展，暗示 sparse/long-context 从 demo 到 product 的鸿沟巨大
- **NVIDIA 的硬件对策**：Blackwell Ultra 的 SFU 加倍说明 NVIDIA 认为 attention softmax 是硬件层需要解决的瓶颈，而非完全绕过 attention
- **Anthropic 的倒退**：Opus 4.7 的长上下文能力腰斩是长上下文工程的复杂性证据——即使顶级 lab 也无法在提升通用能力的同时保持长上下文性能

## Candidate Blanks

### Blank 1: Content-dependent sparse attention 的独立验证缺失

SubQ SSA 和 Magic LTM-2-mini 的 claims 都没有经过独立学术验证。SSA 声称 1M 52.2× over FA2 但仅三个 benchmark、单次运行、无置信区间。需要一个第三方的、系统性的对比：把 NSA、DSA、SSA（如果开放 API）、Twilight、BLASST 放在统一的 RULER/MRCR/LongBench 上对比。

**为什么现有工作没覆盖**：SSA 是闭源商业系统；Magic 从未公开；学术界的对比通常不包括商业 API。

### Blank 2: 稀疏注意力在 thinking/reasoning 模型上的行为

所有现有的 sparse attention 工作都在 standard LLM 上评估。Thinking 模型（DeepSeek-R1、QwQ、Claude Opus thinking mode）的 CoT trace 可以长达 100K+ tokens，且 trace 内部有密集的跨位置依赖（数学推导步骤之间、代码审查的逻辑链之间）。NSA 在 AIME 上的 +163% 提升暗示稀疏注意力可能特别适合 reasoning，但这还远不是系统性的研究。

**为什么现有工作没覆盖**：Thinking 模型是 2025 下半年才大规模部署的，现有 sparse attention 论文的实验早于这个时间窗口。

### Blank 3: Sparse attention + KV cache tiering 的联合设计

当前工作是分叉的：
- **Sparse attention** 减少 attention 计算量（NSA, DSA, SSA）
- **KV cache tiering** 优化 KV 存储和传输（LMCache, Cartridges, MSA）

但两者没有联合设计。例如：如果用 NSA 的块重要性评分来指导 LMCache 的 tier placement（重要的块放 HBM，不重要的放 SSD），是否可以同时减少计算和存储？这个「计算稀疏性 × 存储分层」的交叉空间几乎是空白。

**为什么现有工作没覆盖**：学术分治——kernel/算法的人做 sparse attention，系统的人做 KV tiering。DeepSeek-V4 的 CSA+HCA+异构 KV 结构是最近的例外，但仍然没有显式地联合优化稀疏选择和 tier placement。

### Blank 4: 「功能性上下文窗口」的度量问题

SubQ 博客的核心批评——"nominal context window ≠ functional context window"——是准确的。但业界缺乏统一的 "functional context window" 度量标准。RULER 和 MRCR 是好的开始，但它们都是合成任务。真实场景（代码库理解、合同审查、多论文综合）的 functional context 度量几乎不存在。

**为什么现有工作没覆盖**：真实长上下文任务的 ground truth 标注成本极高；合成 benchmark 容易 scale 但生态效度存疑。

### Blank 5: Sparse attention 的训练基础设施

NSA 是少数从预训练就使用稀疏注意力的工作。绝大多数模型在 dense attention 下预训练。如果稀疏注意力确实不降质（NSA 和 SSA 的 claims），那么未来的 foundation model 是否应该默认使用 sparse attention？回答这个问题需要：
- 在多个模型 scale（1B→100B→1T）上验证稀疏预训练的 scaling law
- 确认稀疏注意力在 multilingual、多模态、code 等 diverse domain 上的表现
- 建立 sparse attention 训练的 best practice（稀疏度 schedule、分支权重初始化等）

NSA 做了一小部分（27B MoE, 270B tokens），但远不足以建立普遍结论。

**为什么现有工作没覆盖**：大规模预训练的 compute cost 极其高昂，很少有团队能做 ablation study。

## Key Unknowns

### Unknown 1: SSA 的具体技术方案是什么？

**为什么重要**：SSA 是唯一声称同时实现 "linear cost + content-dependent + arbitrary retrieval" 的系统。如果能验证这个 claim，对整个领域有重大影响。

**测量方法**：
- 等待 Subquadratic 发布技术报告（"coming soon"）
- 通过 API 做黑盒 probe：设计 targeted 的 long-context retrieval 测试，测量延迟 vs context length 的 scaling 关系，推断计算复杂度
- 检查 API 响应的 attention pattern 是否有可检测的 artifacts（如某些位置的 token 被系统性忽略）

### Unknown 2: 稀疏注意力的质量上限在哪里？

**为什么重要**：NSA 证明了稀疏可以超越 dense。但这是否只是一个特定 scale（27B）和特定训练量（270B tokens）的巧合？在 100B+, 2T+ tokens 下，dense attention 是否能学到更精细的 pattern 从而反超？

**测量方法**：
- 需要至少一个开放的 sparse attention 模型（如 NSA 的开源版本）和同 backbone 的 dense 版本，在 comparable training budget 下对比
- Scaling law 实验：固定模型架构，变化训练 token 数，观察 sparse vs dense 的 performance gap 是否随训练量收敛或发散

### Unknown 3: Content-dependent routing 的开销是否值得？

**为什么重要**：DSA 的 lightning indexer 在 128K 以上成本不可忽略。SSA 如何解决这个问题未知。如果 selection 本身的开销接近被节省的 attention 开销，稀疏化就失去意义。

**测量方法**：
- 对 DSA/NSA 做 profiling：分解 attention 总延迟为「selection 开销」和「reduced attention 开销」，看两者的 ratio
- 在不同 context length（1K→128K→1M）下测量这个 ratio 的 scaling
- 对比不同 selection 策略（DSA indexer vs NSA 复用 vs 随机 selection vs oracle selection）的效率-质量 trade-off

### Unknown 4: 稀疏注意力是否会引入新的 failure mode？

**为什么重要**：如果稀疏注意力在 95% 的 case 下表现正常，但在 5% 的 case 下静默失败（错过关键 token 导致错误答案但模型不自知），这比 dense attention 的「统一退化」更危险。SOSP-2025 的 silent failure 主题在这里高度相关。

**测量方法**：
- 构建 adversarial 的 long-context retrieval 测试：target 信息被刻意嵌入到容易被稀疏模式跳过的位置（如低 attention score 的 block）
- 对比 sparse 和 dense 模型在标准 benchmark 上的 calibration（confidence vs accuracy）
- 分析 sparse 模型的 attention pattern，看是否存在系统性的 retrieval blind spot（如中间位置的 context 被系统性地 under-attend）

### Unknown 5: 硬件演进方向会如何影响稀疏注意力的相对优势？

**为什么重要**：Blackwell B200 的非对称 scaling（Tensor Core 翻倍但 SFU/MUFU 不变）让 softmax 成为瓶颈，FlashAttention-4 的应对是软件模拟 exp。Blackwell Ultra 双倍 SFU。如果未来的硬件重新平衡了计算/memory/softmax 的比例，sparse attention 的 wall-clock 优势会不会被抵消？

**测量方法**：
- 在不同硬件代际（H100→B200→B300/Ultra）上 profile NSA/FA4/dense attention 的延迟 breakdown
- 构建分析模型：输入硬件 spec（TC throughput, SFU throughput, memory bandwidth），预测不同 attention 策略的 roofline 位置
- 关注 NVIDIA 的 roadmAP（Rubin, Vera）和 AMD MI400 的架构选择
