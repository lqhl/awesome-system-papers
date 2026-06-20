---
type: concept
aliases: [attention, Attention Mechanism, self-attention, self attention, Self-Attention, scaled dot-product attention, SDPA, MHA, GQA, MQA, multi-head attention]
parent: "[[Transformer]]"
introduced_by: "[[Transformer-NeurIPS17]]"
last_updated: 2026-06-20
tags: [transformer, deep-learning, llm]
---

# Attention

> Transformer 核心算子：`softmax(QKᵀ/√d) V`。每个位置通过 query 查所有 key，拿 value 加权求和——取代 RNN 顺序处理，用矩阵乘换 O(1) 深度与全局感受野。其 O(N²) 计算/内存复杂度是过去八年「系统 × 模型」工作的共同敌人。

## 核心思想

设输入 `X ∈ R^{N×d}`，投影出 `Q = XW_Q, K = XW_K, V = XW_V`，则：

```
Attn(Q,K,V) = softmax(QKᵀ / √d) · V
```

QKᵀ 产生 N×N logit 矩阵；÷√d 稳定方差；行方向 softmax 归一；乘 V 加权求和。**Multi-head** 把 d 分成 h 个子空间并行算 h 次再拼接。

推理侧关键推论：decode 每步须 attend 全部历史 → 须缓存 K/V（[[KV-Cache]]）或重算 O(N²)。训练侧：N×N 中间矩阵装不下 HBM → [[Flash-Attention]] 用 tiling + online softmax 避免物化。

## 为什么重要

[[Transformer-NeurIPS17|Transformer]] 在句子级 MT（n < d）证明 attention 可行，但现代 LLM 普遍 n ≫ d，O(N²) 从「可接受」变成系统主矛盾。[[FlashAttention-NeurIPS22|FlashAttention]] 确立 IO-awareness 范式：GPU 上 attention 是 memory-bound，避免读写 N×N matrix 比减 FLOPs 更重要。FA 系列（FA2/FA3/FA4）把瓶颈从 HBM IO 推进到 work partitioning、Hopper asynchrony、Blackwell 新指令。

attention 也是 correctness 与近似优化的战场：[[MAC-Attention-MLSys26|MAC-Attention]]、[[IceCache-arXiv26|IceCache]] 利用 decode 时间冗余或 key 近邻做 full-attention 逼近；[[Sparse-Attention]]、[[Linear-Attention]] 放弃 exact dense 换亚二次复杂度。这些路线共享一个系统问题：**如何在带宽/容量约束下保持 attention 输出质量**。

## 关键观察 / 隐含假设

- **观察 1：GPU 上 attention 是 memory-bound，HBM 访问次数决定 wall-clock。** [[FlashAttention-NeurIPS22|FlashAttention]]：A100 seq=1024 标准实现 35.3 GB HBM R/W、35.1 ms；FA 4.4 GB、11.7 ms——FLOPs 更高却更快。
- **观察 2：FA1 解决 IO 后，瓶颈迁移到 thread block / warp work partitioning。** [[FlashAttention-2-ICLR24|FlashAttention-2]]：长序列 + 小 batch 时 batch×head 并行不足 SM 数；非 matmul FLOP 等价 ~16× matmul 时间成本。
- **观察 3：n < d 假设在 modern LLM 中普遍不成立。** [[Transformer-NeurIPS17|Transformer]] Table 1 渐近分析在 4K–128K context 翻转；需 chunked prefill、sparse/linear 补救。
- **观察 4：decode 流内 query 存在短程语义重复。** [[MAC-Attention-MLSys26|MAC-Attention]]：相似 query 诱导高度相关 attention 分布；pre-RoPE L2 匹配显著提高命中率。
- **观察 5：长上下文 attention 对少数 token 高度稀疏。** [[IceCache-arXiv26|IceCache]]：256-token budget 可保留约 99% Full KV accuracy；但顺序 page layout 降低 query-aware offload 命中率。

## 设计空间与取舍

- **IO-aware exact kernel（[[Flash-Attention]] 族）**：保持数学语义，手工 CUDA/CUTLASS；跨架构需重调 block size，收益随硬件演进（FA1→FA2→FA3→FA4）。
- **KV 共享变体（GQA/MQA/MLA）**：减少 KV 字节数；GQA 为 Llama 折中，MLA（DeepSeek-V2/V3）压 latent 再 up-project。
- **Sparse / linear 路径（[[Sparse-Attention]]、[[Linear-Attention]]）**：放弃 exact dense 换复杂度；质量–cost Pareto 任务相关。
- **Decode 复用（[[MAC-Attention-MLSys26|MAC-Attention]]）**：match-amend-complete 复用 attention summary + band 修正；prefill 中 reuse gap 大时 underperform。
- **语义 page + sparse mask（[[IceCache-arXiv26|IceCache]]）**：DCI-tree 聚类 key + M-DCI retrieval；CPU indexing 开销在弱 CPU 多租户下可能成为瓶颈。
- **Quantized attention（[[Kitty-MLSys26|Kitty]]、[[IntAttention-MLSys26|IntAttention]]）**：低 bit KV/attention matrix；需精度验证。
- **Prefix 树复用（[[RadixAttention]]）**：跨请求共享 attention 计算的 KV 前缀；与 [[PagedAttention]] block 抽象配合。

## 引用本概念的论文

- [[Transformer-NeurIPS17|Attention Is All You Need]] — scaled dot-product attention 与 MHA 原始提出
- [[FlashAttention-NeurIPS22|FlashAttention]] — IO-aware exact attention，HBM 访问 Θ(N²d²/M)
- [[FlashAttention-2-ICLR24|FlashAttention-2]] — work partitioning 优化，A100 上 ~2× over FA1
- [[FlashAttention-3-NeurIPS24|FlashAttention-3]] — Hopper asynchrony + FP8，H100 BF16 840 TFLOPs/s
- [[FlashAttention-4-MLSys26|FlashAttention-4]] — Blackwell 代 attention kernel 演进
- [[MAC-Attention-MLSys26|MAC-Attention]] — decode 复用 summary，KV 访问最高减 99%，128K 延迟降 60%+
- [[IceCache-arXiv26|IceCache]] — 语义 page layout + query-aware sparse attention
- [[BLASST-MLSys26|BLASST]]、[[Kitty-MLSys26|Kitty]]、[[IntAttention-MLSys26|IntAttention]] — attention kernel / 量化变体
- [[SpanQueries-MLSys26|SpanQueries]] — span query IR 优化 attention 局部性
- [[FlexiCache-MLSys26|FlexiCache]] — per-head 稀疏 attention 与 KV 分层
- [[SparseSpec-MLSys26|SparseSpec]] — PillarAttn 稀疏 draft attention
- [[SkipKV-MLSys26|SkipKV]] — 句子级 KV eviction 影响 attention 可见范围
- [[ScaleSearch-MLSys26|ScaleSearchAttention]] — NVFP4 attention 矩阵近零损
- [[SolidAttention-FAST26|SolidAttention]] — attention 正确性形式化验证
- [[NSA-ACL25|NSA]] — native sparse attention 架构变体
- [[AttnRes-arXiv26|Attention Residuals]] — block representation 改进 attention 路径

## 已知局限 / 开放问题

- 原始 Transformer 未讨论 [[KV-Cache]]、分页、投机解码——推理内存墙是时代局限
- FA 系列聚焦单卡训练/prefill；decode seqlen=1、[[Continuous-Batching]] variable-length 集成是后续工作
- exact attention 在 n ≫ d 时渐近劣势未消除，需与 sparse/linear/recurrent 路线持续比较
- attention map 可视化仅定性（[[Transformer-NeurIPS17|Transformer]]），production 可观测性维度论文未覆盖