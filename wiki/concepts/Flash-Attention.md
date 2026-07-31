---
type: concept
aliases: [FlashAttention, flash-attention, Flash Attention, FlashAttention-2, FlashAttention-3, FA, FA2, FA3]
parent: "[[Attention]]"
introduced_by: "[[FlashAttention-NeurIPS22]]"
last_updated: 2026-07-30
tags: [attention, gpu-kernel, llm-training, llm-inference]
---

# Flash-Attention

> FlashAttention 是 IO-aware 的 exact attention kernel family：以 tiling、online softmax 和 fusion 避免把完整 N×N score matrix 写回 HBM，在不引入 attention sparsity 的前提下降低 memory traffic。

## 核心思想

standard attention 分别 materialize QKᵀ、softmax 和 PV。FlashAttention 将 Q/K/V 分块装入 SRAM，增量维护 row max、normalizer 和 output accumulator，只从 HBM 读必要 inputs、写最终 output；backward 通过 recomputation 减少保存中间矩阵。

FA2 调整 work partition 和 loop order，FA3 利用 Hopper warp specialization/TMA/FP8，FA4 面向 Blackwell 重新平衡 MMA、exponential 与 shared-memory pipeline。同一算法思想需要随 GPU ISA 重写。

## 为什么重要

attention 的理论 FLOPs 未变，但 HBM I/O 从 O(N²) 中间状态显著下降，使 exact long-context attention 可训练/推理。它也成为 compiler、kernel DSL、mega-kernel 与 sparse attention 的基线：新方案必须区分胜过 naive attention 还是胜过最新 FlashAttention。

## 关键观察 / 隐含假设

- **IO complexity 比单纯 FLOPs 更能解释收益**：[[FlashAttention-NeurIPS22]]、[[FlashAttention-2-ICLR24]] 证明 tiling/online softmax 避免 N² HBM materialization。
- **新 GPU 需要联合 software pipeline 与 warp specialization**：[[Twill-OSDI26]] 用 ILP/SMT 联合优化 software pipelining 和 warp roles，挑战手写 heuristic。
- **大 kernel 需要跨 operator 调度**：[[MPK-OSDI26]] 将 attention、collective 和其他 tensor tasks 放入 persistent mega-kernel，以 SM-level dependency 提前执行。
- **训练鲁棒性不能只看 kernel throughput**：[[RobustRL-OSDI26]] 表明长 RL step、failure/recovery 与 role utilization 会吞没单 kernel gain。
- **exact 与 sparse 是不同路线**：[[Sparse-Attention]] 减少 token pairs，FlashAttention 保持 dense semantics；二者可组合但需重新设计 irregular kernel。

## 设计空间与取舍

- **tile/loop order**：影响 SRAM reuse、parallelism 与 occupancy。
- **recomputation**：省 HBM/state，增加 backward FLOPs。
- **warp specialization/pipeline**：提高 overlap，增加 register/SMEM pressure 和架构绑定。
- **FP8/低精度**：提高 Tensor Core throughput，需 scale 与数值误差控制。
- **sparse/ragged extension**：减少实际 pairs，irregular indexing 破坏 dense coalescing。

## 引用本概念的论文

- [[FlashAttention-NeurIPS22]] — 提出 IO-aware exact attention 与 online softmax kernel。
- [[FlashAttention-2-ICLR24]] — 改进 work partition 与并行效率。
- [[FlashAttention-3-NeurIPS24]] — 针对 Hopper/TMA/FP8 重构 pipeline。
- [[FlashAttention-4-MLSys26]] — 面向 Blackwell 继续推进 kernel family。
- [[Twill-OSDI26]] — 自动联合搜索 software pipeline 与 warp specialization。
- [[MPK-OSDI26]] — 将 attention 纳入 SM-level mega-kernel scheduling。

## 已知局限 / 开放问题

- 自动跨 GPU generation 迁移 tile、pipeline、register 与 warp plan。
- 对 ragged、paged KV、sparse attention 和 continuous batching 保持高利用率。
- 形式化低精度 online softmax 的误差，并报告端到端质量。
- 将 compilation/search time、binary cache 和动态 shape 纳入部署成本。
