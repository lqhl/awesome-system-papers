---
type: paper
name: FlashAttention
full_title: "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness"
authors: [Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Ré]
venue: NeurIPS
year: 2022
tags: [attention, gpu-kernel, io-aware, transformer, long-context]
source_pdf: "[[neurips22-dao-flashattention.pdf]]"
source_md: "[[neurips22-dao-flashattention]]"
---

# FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness (NeurIPS 2022)

> **一句话总结**：FlashAttention 把标准 [[Attention]] 改写成 IO-aware 的 exact GPU kernel，用 tiling + online softmax + backward recomputation 避免物化 `N x N` attention matrix，在 A100 上 attention 计算最高 7.6x 加速、内存线性随序列长度增长，并让 GPT-2 / BERT / LRA 训练获得 15%-3.5x 端到端收益。

## 问题

标准 self-attention 的数学形式是 `softmax(QK^T)V`，但常规实现会把 `QK^T` 和 softmax 后的 `P` 两个 `N x N` 中间矩阵写到 HBM，再读回来继续算。长序列下这不仅带来 `O(N^2)` 显存占用，也把运行时间压在 HBM 读写上。

当时很多 long-context 工作选择 sparse / low-rank / linear attention，试图减少 FLOPs，但论文指出这些方法经常没有带来真实 wall-clock speedup：GPU 上 FLOPs 不是唯一瓶颈，HBM 与 SRAM 之间的 IO 才是 attention kernel 的关键约束。FlashAttention 的定位就是：不改变 dense attention 语义，先把 exact attention 的内存访问做对。

## 核心方法

FlashAttention 的核心是把 [[Attention]] 当作 IO-aware 算子重新实现，而不是把 matmul、mask、softmax、dropout、matmul 作为多个 PyTorch kernel 串起来执行。

具体做法有三点：

1. **Tiling**：把 Q/K/V 切成 block，K/V block 与 Q block 分批搬进 GPU on-chip SRAM，在 SRAM 内完成局部 `QK^T`、softmax、乘 V。
2. **Online softmax**：每行维护 running max 和 normalization sum，让 softmax 可以跨 block 增量合并，不需要一次看到完整 `N x N` 行。
3. **Backward recomputation**：forward 只保存输出和 softmax 统计量，backward 再从 Q/K/V block 重新算局部 attention，避免保存 `O(N^2)` 中间态。虽然 FLOPs 增加，但 HBM 访问大幅减少，实际更快。

论文还把同一思路扩展到 block-sparse FlashAttention：只计算非零 block，在保持 block sparsity 语义的同时继续避免无效 IO。这个版本不是 exact dense attention，但展示了 FlashAttention 可以作为 sparse attention 的底层 primitive。

## 关键结果

- A100 上 GPT-2 attention 计算相对 PyTorch 实现最高 **7.6x** 加速。
- BERT-large 序列长 512 的训练比 MLPerf 1.1 Nvidia 记录快 **15%**：17.4 分钟 vs 20.0 分钟。
- GPT-2 small / medium 训练相对 HuggingFace 分别 **3.5x / 3.0x**，相对 Megatron-LM 分别约 **1.7x / 1.8x**，perplexity 不变。
- GPT-2 small 用 4K context 仍比 Megatron-LM 的 1K context 快 **30%**，perplexity 从 18.2 降到 17.2。
- Long Range Arena 上 vanilla Transformer 使用 FlashAttention 获得 **2.4x** 训练加速；block-sparse FlashAttention 为 **2.8x**。
- Path-X 16K 上首次让 Transformer 超过随机表现，准确率 **61.4%**；block-sparse 版本扩到 Path-256 64K，准确率 **63.1%**。
- Attention memory footprint 线性随序列长度增长，论文报告相对 exact attention baseline 最高 **20x** 更省显存。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Sparse-Attention]]
- **后续工作**：[[FlashAttention-2-ICLR24|FlashAttention-2]]、[[FlashAttention-4-MLSys26]]
- **同主题**：[[Foundation]]、[[AI-Infra]]
