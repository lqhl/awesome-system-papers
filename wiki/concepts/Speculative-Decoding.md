---
type: concept
aliases: [Speculative Decoding, speculative decoding, SpecDec, Spec-Dec]
parent: "[[LLM-Inference]]"
last_updated: 2026-06-20
tags: [llm-inference, decoding, latency-optimization]
---

# Speculative-Decoding

> 用轻量 draft model（或同模型 self-speculation）连续预测 K 个 token，target model 一次性 forward 验证。命中的 token 直接保留，第一个 reject 位置重采样——**用并行验证取代 K 次串行 decode**，在分布等价前提下把 latency 拉低 1.5–5×。

## 核心思想

自回归 decode 瓶颈是 memory-bound 串行：单 batch 每步只生成一个 token，HBM 带宽被多次低利用率 forward 浪费。Speculative decoding：
1. **Draft**：小模型或早期层连续生成 K 个 candidate token
2. **Verify**：K candidate 一次性喂给 target model 并行算分布
3. **Accept/Reject**：从位置 0 逐位按概率比 `p_target / p_draft` 接受，首 reject 处 corrected sampling
4. 命中越多加速越大；rejection sampling 保证最终分布与 target 直接采样等价

## 为什么重要

[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 在量产 [[vLLM]] 上首次系统评测：verification（target forward）主导 end-to-end 耗时，占 42–95%；batch 1→128 时 EAGLE 加速从 1.73× 降到 1.21×——**实验室 bs=1 夸大 SD 收益**。理想全接受模拟显示与当前实现仍有巨大 gap，自适应组合多方法可达 4.9× 上界。

SD 还与 serving 栈其他机制纠缠：rejection 须 rollback [[KV-Cache]] / [[PagedAttention]] ref count；[[fabric-lib-MLSys26|fabric-lib]] 在 KV transfer 时同时传 last token hidden states + logits 以支持 SD；[[Libra-ICLR26|Libra]] 把投机思想搬到 [[MoE]] gating 预测。这些论文共同假设：**许多 token 对 draft 和 target 都是「显然」的，用小模型猜、大模型验证是用冗余算力换 wall-clock 的有效策略**——但 production batch 与 verification 成本会显著压缩收益。

## 关键观察 / 隐含假设

- **观察 1：verification 主导 end-to-end；大 batch 时系统更 compute-bound，拒绝 token 的验证浪费更严重。** [[SpecDecodeBench-MLSys26|SpecDecodeBench]]：Leviathan 公式 speedup∝f(k,α,c) 中 c、α 随 bs 变。
- **观察 2：diffusion drafter 的 position-wise acceptance 随 draft index 快速衰减。** [[SpecDiff-2-MLSys26|SpecDiff-2]]：AR 蒸馏只修首 token 无效；streak-distillation 在后段 α_j 平均 3.2× 高于 AR-distill。
- **观察 3：draft 占步同步开销可吞噬收益。** [[DataflowIsAllYouNeed-MLSys26|DataflowIsAllYouNeed]]：SN40 上 draft 占步 72% 同步开销，优化后 spec decode 端到端 >6×。
- **观察 4：同模型 self-speculation 可单 forward 并行 draft+verify。** [[TiDAR-MLSys26|TiDAR]]：hybrid diffusion-AR 架构 exact KV cache，wall-clock 超越 EAGLE-3。
- **观察 5：非确定性 kernel 使 SD 与标准解码输出未必 bitwise 相同。** [[SpecDecodeBench-MLSys26|SpecDecodeBench]]：评测以吞吐/延迟为主，合规/调试场景需额外控制。

## 设计空间与取舍

- **Independent draft model（Leviathan 2023）**：单独训小模型；简单但训练成本高，draft KV overhead 显著（0.6B draft +8B 目标 per-token KV 1.77×）。
- **Self-speculation（EAGLE 系列）**：target 前几层做 draft；EAGLE 层 KV overhead 3.1%/1.3%（8B/70B），但 acceptance 随位置衰减。
- **Diffusion drafter（[[SpecDiff-2-MLSys26|SpecDiff-2]]）**：MDM 并行 draft + streak-distillation + self-selection；7B drafter 在 14B verifier 上可能 oversized。
- **Tree-based（Medusa, SpecInfer）**：多分支探索提高命中率；attention kernel 改动大。
- **Parameter switching（[[PRISM-MLSys26|PRISM]]）**：按 draft step 切换参数集，解耦 drafter 容量与 per-step 成本。
- **Adaptive orchestration（[[ReSpec-MLSys26|ReSpec]]、[[SpecDecodeBench-MLSys26|SpecDecodeBench]]）**：按 active batch / token 位置动态开关或组合方法；4.9× 为 bound 非可部署承诺。
- **RL rollout 专用（[[DAS-MLSys26|DAS]]）**：distribution-aware SD + suffix tree drafter，rollout −50% 且 lossless。
- **Sparse draft（[[SparseSpec-MLSys26|SparseSpec]]）**：PillarAttn 稀疏 self-speculation，RLM 上 2.13× over vLLM。

## 引用本概念的论文

- [[Transformer-NeurIPS17|Attention Is All You Need]] — 结论「making generation less sequential」的直接回应方向
- [[SpecDecodeBench-MLSys26|SpecDecodeBench]] — 量产 vLLM 系统 benchmark；verification 占 42–95%
- [[SpecDiff-2-MLSys26|SpecDiff-2]] — diffusion drafter + streak-distillation，平均 +55% tokens/s over EAGLE-2
- [[TiDAR-MLSys26|TiDAR]] — 单模型 self-speculation，diffusion draft + AR reject 同 forward
- [[PRISM-MLSys26|PRISM]] — 按 draft step 切换参数集，SGLang 上 >2.6× 吞吐
- [[DataflowIsAllYouNeed-MLSys26|DataflowIsAllYouNeed]] — 消除 draft 同步开销，SN40 spec decode >6×
- [[SparseSpec-MLSys26|SparseSpec]] — 同模型 self-speculation + 稀疏 draft
- [[ReSpec-MLSys26|ReSpec]] — RL 训练生成阶段 adaptive SD + reward-weighted KD
- [[DAS-MLSys26|DAS]] — RL rollout distribution-aware SD，rollout −50%
- [[Libra-ICLR26|Libra]] — speculative gating function execution 做 MoE expert 预测
- [[fabric-lib-MLSys26|fabric-lib]] — KV transfer 同时传 hidden states + logits 支持 SD
- [[SHIP-MLSys26|SHIP]] — SD 作为额外 PP stage 减 KV 占用
- [[LocalityAwareBeamScheduling-MLSys26|LocalityAwareBeamScheduling]] — test-time compute 多路径解码范式相关
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — MTP 并行 token 预测，非传统 spec decode 路线

## 已知局限 / 开放问题

- 命中率取决于 draft 质量；低命中率反而增加 latency
- 与 [[PagedAttention]] / [[Prefix-Caching]] 配合时 rejection 场景 KV rollback 实现复杂
- 大 batch 下收益缩水（[[SpecDecodeBench-MLSys26|SpecDecodeBench]] EAGLE 1.73×→1.21× @ bs128）
- 4.9× adaptive combo 为 theoretical upper bound，非可部署算法（[[SpecDecodeBench-MLSys26|SpecDecodeBench]]）
- EP/PP、[[Disaggregation]] 下 SD 形态未系统覆盖；非确定性对合规影响未解