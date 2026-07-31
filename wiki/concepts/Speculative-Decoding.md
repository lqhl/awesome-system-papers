---
type: concept
aliases: [Speculative Decoding, speculative decoding, SpecDec, Spec-Dec]
parent: "[[LLM-Inference]]"
last_updated: 2026-07-30
tags: [llm-inference, decoding, latency-optimization]
---

# Speculative-Decoding

> 推测解码（speculative decoding）先用便宜的 draft 路径产生多个候选 token，再由 target model 并行验证，以额外计算换取更少串行 decode steps。

## 核心思想

经典方案由 draft model 连续生成 K tokens，target 一次 forward 计算这些位置的分布，按 acceptance rule 保留前缀并在首个 reject 处校正采样。若协议正确，输出分布与 target 自回归采样等价；self-speculation、multi-head、retrieval 与 sparse draft 则改变候选来源。

加速取决于 acceptance length、draft cost、verify batch efficiency、memory bandwidth 和调度。K 太小浪费并行度，太大则 reject 后做无用工作；production scheduler 还要把不同 acceptance 的请求持续重组。

## 为什么重要

decode 串行且 memory-bound，推测解码可把多个 token 合并验证，是不改 target quality 的主要系统路线之一。但它不是固定倍数优化：domain shift、temperature、batch、长尾请求与 foreground contention 都会使 draft overhead 反超。

## 关键观察 / 隐含假设

- **组内 context 可提高 acceptance**：[[Seer-OSDI26]] 在 RL prompt group 中共享 online acceptance statistics，并自适应高/低优先级 draft length；group correlation 失效时收益会下降。
- **系统应优化 throughput model 而非固定 K**：[[SpecDecodeBench-MLSys26]]、[[FlashInfer-Bench-MLSys26]] 与 [[PRISM-MLSys26]] 表明 kernel、batch 和 acceptance 共同决定 break-even。
- **speculation 可与 sparse execution 组合**：[[SparseSpec-MLSys26]]、[[KAIROX-OSDI26]] 尝试降低 draft/verify compute，但后者发现某些 speculative batch 使 sparse kernel 不如 dense baseline。
- **移动端需服从 foreground memory-bandwidth SLO**：[[Sereno-OSDI26]] 说明后台 LLM speculation 的额外 bandwidth 不能侵占交互 workload；reactive yielding 仍需更强 deadline-aware 控制。

## 设计空间与取舍

- **独立 draft model**：acceptance 可调且实现清晰，但多一份 weight/memory 与调度资源。
- **self-speculation/early exit**：复用 target parameters，减少 footprint，但 layer scheduling 更复杂。
- **multi-token head**：draft latency 低，需额外训练并受 domain generalization 影响。
- **group/context adaptive**：[[Seer-OSDI26]] 利用共享 prompt statistics，收益高但有 sample-correlation 假设。
- **sparse/quantized draft**：降低 cost，可能改变 acceptance 或被 indexing/dequant overhead 抵消。

## 引用本概念的论文

- [[Seer-OSDI26]] — 为同步 RL rollout 做 adaptive grouped speculative decoding。
- [[Sereno-OSDI26]] — 在移动端 memory contention 下控制后台 LLM inference/speculation。
- [[KAIROX-OSDI26]] — 讨论 speculative batch 对 GPU–CPU sparse inference break-even 的影响。
- [[ReSpec-MLSys26]] — 重构 speculation/verification 执行。
- [[SparseSpec-MLSys26]] — 将 activation/attention sparsity 引入 speculative decoding。
- [[SpecDecodeBench-MLSys26]] — 系统刻画不同 speculative methods 的 workload 边界。

## 已知局限 / 开放问题

- 在 production domain drift 下在线估计 acceptance，并避免 controller oscillation。
- 同时核算 draft GPU、KV memory、verify batching、energy 与 p99 latency。
- 证明优化后的 acceptance/rejection 实现保持 target distribution。
- 处理 continuous batching 中不同 draft progress、取消和优先级公平性。
