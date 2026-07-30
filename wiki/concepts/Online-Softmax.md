---
type: concept
aliases: [Streaming-Softmax, Blockwise-Softmax]
last_updated: 2026-07-18
tags: [attention, gpu, numerical-stability, kernels]
---

# Online Softmax

> 在线 softmax 通过运行最大值和归一化统计数据，跨块增量计算归一化指数减少，从而允许注意力内核避免具体化满分矩阵。

## 核心思想

对于每个块，该算法更新数值稳定的运行最大值和指数总和，重新调整先前的部分结果，并结合新的贡献。这使得内存使用与块状态成正比，而不是与所有成对注意力分数成正比，但正确性和速度取决于精度、缩减顺序、图块形状和硬件执行。

## 为什么重要

在线 softmax 是 IO 感知注意力内核背后的关键原语。内核改进应区分算法内存节省和 GPU 特定实现增益，并在规定的序列长度和精度下验证数值行为。

## 关键观察 / 隐含假设

- **观察**：阻塞可以在没有分数矩阵具体化的情况下实现注意力。 [[FlashAttention-2-ICLR24]] 和 [[FlashAttention-3-NeurIPS24]] 在不同的内核代中使用此原语。
- **观察**：硬件和精度改变最佳实现。 [[FlashAttention-4-MLSys26]] 和 [[AttnRes-arXiv26]] 暴露了性能/数值边界。
- **假设**：关联式约简在数值上是可以互换的；有限精度和并行顺序需要显式验证。

## 设计空间与取舍

- **图块大小与占用/寄存器压力**：较大的图块会减少调度开销，但可能会降低并行度。
- **精度与稳定性**：低精度可提高吞吐量，同时使缩放和累积选择变得重要。
- **精确注意力与近似**：在线softmax将softmax计算保留到有限精度行为；它与稀疏或近似注意力不同。

## 引用本概念的论文

- [[FlashAttention-2-ICLR24]] — attention kernel implementation.
- [[FlashAttention-3-NeurIPS24]] — GPU-specific kernel generation.
- [[FlashAttention-4-MLSys26]] — later attention-kernel design.
- [[AttnRes-arXiv26]] — attention execution/numerical context.
