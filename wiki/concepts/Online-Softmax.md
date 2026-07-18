---
type: concept
aliases: [Streaming-Softmax, Blockwise-Softmax]
last_updated: 2026-07-18
tags: [attention, gpu, numerical-stability, kernels]
---

# Online Softmax

> Online softmax computes a normalized exponential reduction incrementally across blocks by carrying running maximum and normalization statistics, allowing attention kernels to avoid materializing the full score matrix.

## 核心思想

For each block, the algorithm updates a numerically stable running maximum and sum of exponentials, rescales prior partial results, and combines the new contribution. This makes memory use proportional to block state rather than all pairwise attention scores, but correctness and speed depend on precision, reduction order, tile shape, and hardware execution.

## 为什么重要

Online softmax is a key primitive behind IO-aware attention kernels. A kernel improvement should distinguish algorithmic memory savings from GPU-specific implementation gains and validate numerical behavior under the stated sequence length and precision.

## 关键观察 / 隐含假设

- **观察**：blocking enables attention without score-matrix materialization. [[FlashAttention-2-ICLR24]] and [[FlashAttention-3-NeurIPS24]] use this primitive in different kernel generations.
- **观察**：hardware and precision alter the best implementation. [[FlashAttention-4-MLSys26]] and [[AttnRes-arXiv26]] expose performance/numerical boundaries.
- **假设**：associative-looking reductions are numerically interchangeable; finite precision and parallel order require explicit validation.

## 设计空间与取舍

- **Tile size vs occupancy/register pressure**：larger tiles reduce scheduling overhead but may reduce parallelism.
- **Precision vs stability**：low precision improves throughput while making scaling and accumulation choices material.
- **Exact attention vs approximations**：online softmax preserves the softmax computation up to finite-precision behavior; it is distinct from sparse or approximate attention.

## 引用本概念的论文

- [[FlashAttention-2-ICLR24]] — attention kernel implementation.
- [[FlashAttention-3-NeurIPS24]] — GPU-specific kernel generation.
- [[FlashAttention-4-MLSys26]] — later attention-kernel design.
- [[AttnRes-arXiv26]] — attention execution/numerical context.
