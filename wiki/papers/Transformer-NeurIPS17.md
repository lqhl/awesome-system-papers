---
type: paper
name: Transformer
full_title: Attention Is All You Need
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, et al.]
venue: NeurIPS
year: 2017
tags: [foundation, attention, sequence-modeling, transformer, self-attention]
source_pdf: "[[1706.03762v7.pdf]]"
source_md: "[[1706.03762v7]]"
---

# Attention Is All You Need (NeurIPS 2017)

> **一句话总结**:提出完全基于 self-attention 的 Transformer 架构,抛弃 RNN/CNN,在 WMT 2014 EN-DE 达到 28.4 BLEU(超过 ensemble 基线 2+ BLEU),EN-FR 达到 41.8 BLEU(single-model SOTA),且训练只需 8×P100 GPU 3.5 天,是几乎所有现代 LLM(GPT、Claude、DeepSeek、Gemini)的共同祖先。

## 问题

2017 年的序列建模被 RNN/LSTM/GRU + encoder-decoder + attention 的组合统治。RNN 的核心缺陷是:沿时间步顺序计算 hidden state $h_t = f(h_{t-1}, x_t)$,**天然无法并行化**,长序列训练极慢且 batch 受限。ConvS2S、ByteNet 用 CNN 缓解了这点,但相关两个远距离位置仍需 $O(\log_k n)$ 或 $O(n/k)$ 层卷积堆叠,长距离依赖学习困难。

本文要回答:能否**完全抛弃 recurrence 和 convolution**,仅用 attention 就完成序列到序列的映射,同时兼得高并行度和短路径长度?

## 核心方法

**Scaled Dot-Product Attention**。 query/key/value 全部线性投影后,$\text{Attention}(Q, K, V) = \text{softmax}(QK^T / \sqrt{d_k}) V$。除以 $\sqrt{d_k}$ 是为了防止 dot product 在高维下进入 softmax 梯度消失区。这一机制是后续 [[KV-Cache]]、[[PagedAttention]]、Flash/Paged/Sparse 各种 attention 变体的共同出发点。

**Multi-Head Attention**。把 $d_{\text{model}}=512$ 切成 $h=8$ 个独立 head(每个 $d_k=d_v=64$),并行跑 attention 再拼接。允许模型在不同表示子空间同时建模不同类型的依赖(句法、语义、指代等)。

**全 self-attention 的 encoder-decoder**。
- Encoder: 6 层,每层 = multi-head self-attention + position-wise FFN,配残差连接与 layer normalization
- Decoder: 6 层,额外插入一个 encoder-decoder cross-attention sub-layer,self-attention 做 causal masking 保持自回归性
- FFN: 两层线性 + ReLU,$d_{ff}=2048$,对每个位置独立应用

**Positional Encoding**。无 recurrence 意味着没有位置信息,作者用正余弦位置编码 $PE_{(pos, 2i)} = \sin(pos / 10000^{2i/d_{\text{model}}})$,让模型能按相对位置 attend。也试了 learned positional embedding,效果几乎相同。

**训练细节**。Adam + warmup + inverse square root decay,label smoothing 0.1,dropout 0.1。Base 模型 65M params,Big 模型 213M params。

## 关键结果

- **WMT 2014 EN-DE**: Transformer big 28.4 BLEU,比之前 SOTA ensemble 好 2+ BLEU;训练成本 $2.3 \times 10^{19}$ FLOPs,远低于 GNMT+RL Ensemble 的 $1.8 \times 10^{20}$
- **WMT 2014 EN-FR**: Transformer big 41.8 BLEU,single-model SOTA;训练成本约竞品 1/4
- **复杂度分析**: self-attention 每层 $O(n^2 \cdot d)$,但 sequential ops 只有 $O(1)$,maximum path length $O(1)$——恰是 RNN($O(n)$)和 ConvNet($O(\log_k n)$)最弱的地方
- **English Constituency Parsing**: 仅用 WSJ 40K 句也能超过多数 RNN baseline,证明架构通用性
- **训练效率**: Base 模型 8×P100 训练 12 小时,Big 3.5 天——以 2017 年的 seq2seq 标准极为便宜

## 相关

- **衍生概念**: [[KV-Cache]]、[[PagedAttention]]、[[Speculative-Decoding]]——所有 LLM serving 优化的根基
- **衍生架构**: [[MoE]] 本质是把 Transformer 的 dense FFN 换成稀疏路由 experts
- **相关系统**: [[vLLM]]、[[SGLang]] 都在为 Transformer-based LLM 做高效推理
- **直接后代**: [[DeepSeek-V4-arXiv26]] 在 Abstract 明确说 "DeepSeek-V4 series retain the Transformer (Vaswani et al., 2017) architecture",9 年后仍是主干
- **同主题**: [[Foundation]]
