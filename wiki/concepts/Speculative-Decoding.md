---
type: concept
aliases: [Speculative Decoding, speculative decoding, SpecDec, Spec-Dec]
parent: "[[LLM-Inference]]"
last_updated: 2026-04-24
tags: [llm-inference, decoding, latency-optimization]
---

# Speculative Decoding

> 用一个轻量 draft model（或同模型的 self-speculation）连续预测 K 个 token，再用 target model 一次性 forward 验证。命中的 token 直接保留，第一个不命中的位置重采样。本质：**用并行验证取代 K 次串行解码**，在不损失分布的前提下把单次 latency 拉低 1.5–4×。

## 核心思想

LLM 自回归 decode 的瓶颈是「memory-bound 串行」——单 batch 一次只生成一个 token，HBM 带宽被多次低利用率的 forward 浪费。

Speculative decoding：
1. **Draft 阶段**：用一个比 target model 小 10-100× 的 draft model（或同模型的早期层）连续生成 K 个 candidate token
2. **Verify 阶段**：把 K candidate 一次性喂给 target model，并行算出 K 个分布
3. **Accept/Reject**：从位置 0 开始逐位接受（按概率比 `p_target / p_draft`），第一个 reject 位置用 corrected sampling 重采样
4. 命中越多，加速越大；分布等价 target model（无 quality loss）

## 为什么这样做

观察：很多 token 的预测对 draft 和 target model 都是「显然」的（如代码里的 closing brace、对话里的 the/of/is）。让小模型猜，大模型只做验证，是用计算冗余换时间。

数学保证：rejection sampling 框架下，最终采样分布与 target model 直接采样等价（Leviathan et al., ICML 2023; Chen et al., DeepMind）。

## 实现路线

- **Independent draft**：单独训一个小模型（Leviathan 2023）。简单，但训练成本高
- **Self-speculation**：用 target model 的前 K 层做 draft（EAGLE 系列）
- **Tree-based**：draft 同时探索多分支，提高命中率（Medusa, SpecInfer）
- **Lookahead**：用 n-gram cache 做 draft（Lookahead Decoding）
- **Diffusion-based draft**：[[SpecDiff]]（MLSys 2026）等

## 相关概念

- 上游：[[LLM-Inference]]、[[Decoding-Strategies]]
- 相关：[[KV-Cache]]（speculation 失败时要 rollback KV）、[[Continuous-Batching]]
- 思想类似但场景不同：[[Libra-arXiv26|Libra]] 的「投机执行下一层 gating function」是把 spec 思想搬到 [[MoE]] 路由预测——用当前层 hidden state 提前算下层 router

## 引用本概念的论文

- *Leviathan et al., ICML 2023*（待生成 paper wiki 页）— speculative sampling 框架
- *EAGLE / EAGLE-2 / EAGLE-3*（待生成）— self-speculation 路线
- [[Transformer-NeurIPS17|Attention Is All You Need]] — 原论文末尾 "making generation less sequential is another research goal" 的直接回应方向
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 相关上游,但 V4 主要通过 MTP 而非传统 spec decode 实现并行 token 预测
- [[Libra-arXiv26|Libra]] — speculative gating function execution 用同样思想做 expert 预测
- [[TransferEngine-arXiv25|TransferEngine]] — KV transfer 同时传 last token hidden states + logits 以支持 speculative decoding

## 已知局限

- 命中率取决于 draft model 质量；小模型 draft 命中率低时反而增加 latency
- 与 [[PagedAttention]] / [[Prefix-Caching]] 配合时，rejection 场景下的 KV rollback 实现复杂
- 大 batch 下收益缩水（计算被批量摊薄）
- Tree-based 方法对 attention kernel 改动较大
