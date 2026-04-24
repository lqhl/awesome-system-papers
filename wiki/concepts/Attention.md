---
type: concept
aliases: [attention, Attention Mechanism, self-attention, self attention, Self-Attention, scaled dot-product attention, SDPA, MHA, GQA, MQA, multi-head attention]
parent: "[[Transformer]]"
introduced_by: "[[Transformer-NeurIPS17]]"
last_updated: 2026-04-24
tags: [transformer, deep-learning, llm]
---

# Attention

> Transformer 的核心算子：`softmax(QKᵀ/√d) V`。每个位置通过 query 去查所有位置的 key，拿对应的 value 加权求和——取代 RNN 的顺序处理，用矩阵乘换来 O(1) 深度和全局感受野，是 2017 年之后整个深度学习范式的起点。其 O(N²) 计算/内存复杂度也是过去 8 年几乎所有「系统 × 模型」工作的共同敌人。

## 核心思想

设输入 `X ∈ R^{N×d}`，投影出：

```
Q = X W_Q,  K = X W_K,  V = X W_V    # 都是 N × d
Attn(Q,K,V) = softmax(QKᵀ / √d) · V
```

- **QKᵀ**：每对 token 之间打一个 logit → N×N matrix
- **÷√d**：避免大 d 下 dot product 方差爆炸
- **softmax(行方向)**：每行归一成概率
- **·V**：加权求和

**Multi-head**：把 d 分成 h 个 d/h 的子空间并行算 h 次 attention 再拼接，让不同 head 学不同的关系。

## 变体

| 变体 | 关键特征 | 典型代表 |
|---|---|---|
| Multi-Head Attention (MHA) | 每 head 独立 K/V | 原始 Transformer |
| Multi-Query Attention (MQA) | 所有 head 共享 K/V | 推理时 KV cache 小 h 倍 |
| Grouped-Query Attention (GQA) | head 分组共享 K/V | Llama-2/3，折中方案 |
| Multi-head Latent Attention (MLA) | KV 压成小 latent 再 up-project | DeepSeek-V2/V3 |
| [[Sparse-Attention]] | 限制可见范围 | Longformer, BigBird |
| [[Linear-Attention]] | 去掉 softmax | Performer, RWKV, [[DeltaNet]] |
| [[Flash-Attention]] | kernel 层 IO-aware 实现 | FA1/2/3/4 |
| [[RadixAttention]] | prefix 树复用 | [[SGLang]] |

## 系统视角的两大难题

attention 本质是 O(N²) 的 dense 矩阵运算，且推理时要缓存所有历史 K/V：

### 1. 训练：N² 中间 matrix 装不下 HBM

N=8K 时 N×N × BF16 = 128 MB/层 × 80 层 = 10 GB 仅中间态。FlashAttention 用 tiling + online softmax 把它从 HBM 赶到 SRAM，再不写回——attention 再也不"物化"。

### 2. 推理：KV cache 撑爆显存

decode 每步只算一个 token，但要看所有历史 K/V。不缓存→重算是 O(N²)；缓存→O(N) 但内存压力巨大。围绕这个问题衍生了 [[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]、[[KV-Cache-Compression]] 等一连串系统工作。

## 引用本概念的论文

- [[FlashAttention-4-MLSys26|FlashAttention-4]]、[[MAC-Attention-MLSys26|MAC-Attention]]、[[Flashlight-MLSys26|Flashlight]]、[[HipKittens-MLSys26|HipKittens]]、[[Kitty-MLSys26|Kitty]]、[[BLASST-MLSys26|BLASST]]、[[IntAttention-MLSys26|IntAttention]]、[[SparseSpec-MLSys26|SparseSpec]]、[[SpanQueries-MLSys26|SpanQueries]]、[[FlexiCache-MLSys26|FlexiCache]] — attention kernel / 变体
- [[EventTensor-MLSys26|EventTensor]]、[[SkipKV-MLSys26|SkipKV]]、[[DistCA-MLSys26|DistCA]]、[[PIKE-MLSys26|PIKE]] — 事件驱动 / KV 管理 / 分布式
- [[Transformer-NeurIPS17|Attention Is All You Need]] — 原始提出

## 相关概念

- 上游：[[Transformer]]
- 互斥路径：[[Linear-Attention]]、[[Sparse-Attention]]（放弃 exact dense）
- kernel：[[Flash-Attention]]、[[Online-Softmax]]、[[Tree-Attention]]、[[RadixAttention]]
- 存储：[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]
- 位置编码：[[RoPE]]
