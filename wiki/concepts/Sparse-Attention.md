---
type: concept
aliases: [sparse attention, Sparse Attention, sparse-attention, Attention Sparsity, attention sparsity, Block-Sparse-Attention, block sparse attention]
parent: "[[Attention]]"
last_updated: 2026-07-30
tags: [attention, long-context, efficiency, llm-inference, llm-training]
---

# Sparse-Attention

> 稀疏注意力（sparse attention）只计算或读取每个 query 的一部分 key/value，以放弃 dense O(N²) pairs 换取长上下文的计算与 KV bandwidth 降低。

## 核心思想

稀疏集合可由固定 local/global pattern、content/index score、learned router 或 token/block hierarchy 决定。native sparse model 从训练起使用稀疏语义；runtime pruning 则在 dense model 上近似跳过低贡献 pairs，两者的质量与 correctness 边界不同。

系统不只需找出“重要 KV”，还要让选择、index、prefetch 和 irregular kernel 的成本低于被跳过的 dense work，并在 selection miss 时提供保守回退。

## 为什么重要

长 context 使 KV capacity 和 attention bandwidth 成为 inference/训练瓶颈。稀疏 attention 能同时降低 compute 与 memory traffic，但选择依赖、host offload、batch irregularity 和 quality drift 会抵消理论 sparsity；必须报告实际 selected ratio、端到端 latency 和任务质量。

## 关键观察 / 隐含假设

- **selection signal 可用于无损预取**：[[ECHO-OSDI26]] 利用相邻 query 的 index score/boundary 预测下一步必选 KV，在 native sparse model 中 overlap host prefetch；假设 selection 具有时序可预测性。
- **memory-controller observability 可支持细粒度 policy**：[[NEMO-OSDI26]] 在 controller 侧以 address/request rules 聚合 telemetry，适合发现 sparse/offload memory behavior，但需要可信 translation 与 tenant isolation。
- **activation sparsity 可扩展到 FFN/GPU–CPU hybrid**：[[KAIROX-OSDI26]] 在线平衡 sparse neurons，显示小 batch 有利、较大 speculative batch 可能被 index overhead 反超。
- **exact dense kernel 仍是必要基线**：[[Flash-Attention]] 保持完整 attention semantics；[[BLASST-MLSys26]]、[[NSA-ACL25]]、[[MSA-arXiv26]] 必须与最新 exact IO-aware kernel 比较。
- **cache/offload 与 sparse selection 耦合**：[[CacheSlide-FAST26]]、[[IceCache-arXiv26]]、[[FlexiCache-MLSys26]] 将稀疏访问模式用于 KV placement，但 miss 会直接伤害 TPOT tail。

## 设计空间与取舍

- **固定 pattern**：kernel 规则、性能稳定，无法适应内容相关依赖。
- **content/index-based**：质量更好，增加 selector compute、metadata 与 prediction miss。
- **token vs block sparsity**：token 精细但 irregular；block 更适合 GPU/coalescing但多算无用 pairs。
- **native sparse model**：训练/serving 一致，生态与模型兼容受限。
- **runtime approximate pruning**：可用于现有模型，需质量 guard 和 dense fallback。

## 引用本概念的论文

- [[ECHO-OSDI26]] — 对 native sparse attention 做 lossless KV offload/prefetch。
- [[KAIROX-OSDI26]] — 利用 neuron sparsity 平衡 GPU–CPU inference。
- [[NEMO-OSDI26]] — 提供 memory-controller 侧细粒度 memory observability substrate。
- [[BLASST-MLSys26]] — 设计 block-sparse attention kernel/selection。
- [[NSA-ACL25]] — 代表 native sparse attention architecture。
- [[SparseSpec-MLSys26]] — 将 sparsity 与 speculative decoding 结合。

## 已知局限 / 开放问题

- 在更多模型、domain 和 context distribution 上验证 selection quality 与 drift。
- 联合 selector、prefetch、offload 与 sparse kernel，而非分别报告局部 speedup。
- 建立 quality no-regression guard、uncertainty 与 dense fallback。
- 处理 multi-tenant host memory/NUMA/network contention 和 p99 TPOT。
