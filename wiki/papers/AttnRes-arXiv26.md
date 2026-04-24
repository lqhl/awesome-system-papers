---
type: paper
name: AttnRes
full_title: "Attention Residuals (Technical Report)"
authors: [Kimi Team]
venue: arXiv
year: 2026
tags: [llm-architecture, attention, residual-connections, kimi, prenorm]
source_pdf: "[[2603.15031v1.pdf]]"
source_md: "[[2603.15031v1]]"
---

# Attention Residuals (arXiv 2026)

> **一句话总结**：把残差连接从「所有先前层固定权重相加」（PreNorm 路径）改为「对先前层做 softmax attention 选择性聚合」，缓解深层 hidden-state 量级单调增长导致的 PreNorm dilution；Block AttnRes 通过分块把 O(Ld) 降到 O(Nd)，端到端训练开销 < 4%、推理开销 < 2%；在 Kimi Linear 48B/3B-active 上 1.4T token 预训练后下游全面提升（GPQA-Diamond +7.5、Math +3.6、HumanEval +3.1）。

## 问题

现代 LLM 标配的残差连接（[[Residual-Connections]] + PreNorm）有一个被忽视的问题：展开递推会发现每层输入都是先前所有层输出的 **均匀权重相加**。这导致：

- **PreNorm dilution**：hidden state 量级 O(L) 增长，深层贡献被稀释
- 深层为了维持影响力被迫学出越来越大的输出，训练不稳
- 早期层信息被埋没，相当大比例的层可剪枝而损失甚微

类比：序列维度从 RNN 演化到 Transformer，是因为 attention 让每个位置可以选择性访问所有先前位置；但深度维度仍停在「RNN 等价」（残差是固定权重的深度递推）。

## 核心方法

**关键洞察**：Time-depth duality——深度维度上的「层间信息聚合」与时间维度上的「序列间信息聚合」对偶。把深度残差从 linear attention 升级到 softmax attention 是一种自然推广。

**Full AttnRes**：每层用一个学习的 pseudo-query `w_l ∈ R^d` 对所有先前层做 softmax attention：
$$h_l = \sum_{i=0}^{l-1} \alpha_{i \to l} \cdot v_i, \quad \alpha_{i \to l} = \text{softmax}(w_l \cdot \text{RMSNorm}(k_i))$$
- 每层只引入一个 d 维向量参数，开销极小
- 但需保留全部 L 层输出做 backprop，pipeline 通信也涨到 O(Ld)

**Block AttnRes**：把 L 层分成 N 块，块内用普通残差求和得到块表示 b_n，跨块再做 softmax attention。memory + 通信降到 O(Nd)。N≈8 即可恢复大部分增益。

**Infrastructure 优化**：
- **Cross-stage caching**：interleaved pipeline 下，每个 physical stage 只增量传送新积累的 block，O(C) 通信降到 O(P)（V× 改进）
- **Two-phase computation**（推理）：Phase 1 把 S 个 layer 的 inter-block attention 批量算完（一次 KV 读），Phase 2 sequentially 处理 intra-block attention 用 [[Online-Softmax]] 合并

## 关键结果

- **Scaling law**：5 个模型规模 + 3 个变体（baseline / Full / Block AttnRes）均匀降 loss，Block AttnRes 等价于 baseline ×1.25 算力
- **下游评测**（Kimi Linear 48B / 3B-active，1.4T tokens 预训练）：
  - GPQA-Diamond +7.5（36.9 → 44.4）
  - Minerva Math +3.6（53.5 → 57.1）
  - HumanEval +3.1（59.1 → 62.2）
  - MMLU、TriviaQA 等也持续提升
- **训练动态**：Block AttnRes 让 hidden-state 量级在每个 block 内有界周期增长，gradient 分布更均匀
- **架构偏好**：Block AttnRes 偏好更深更窄网络（d_model/L_b=45 vs baseline=60），暗示其能更好利用深度
- **开销**：训练 < 4%（with PP）/ ~0%（无 PP），推理 < 2%；prefill 128K context 经 sharding + chunked prefill 后 block representation 内存 < 0.3GB/device

## 相关

- **相关概念**：[[Residual-Connections]]、[[PreNorm]]、[[Online-Softmax]]、[[Pipeline-Parallelism]]、[[FSDP]]
- **集成进的架构**：[[Kimi-Linear]]（48B/3B-active，hybrid KDA + MLA + MoE）
- **相关方法**：DenseFormer（每层访问所有 prior outputs 但用固定标量权重）、mHC（multi-stream Hyper-Connections）、Highway Networks（学习 gate 在 transform 与 identity 之间插值）
- **优化器 / 训练 recipe**：Muon optimizer、WSD lr schedule
- **同期 Moonshot/Kimi 工作**：Moonlight（基础架构）、DeepSeek-V3（参考架构）
