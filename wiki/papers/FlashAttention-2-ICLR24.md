---
type: paper
name: FlashAttention-2
full_title: "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning"
authors: [Tri Dao]
venue: ICLR
year: 2024
tags: [attention, gpu-kernel, transformer, long-context, llm-training]
source_pdf: "[[iclr24-dao-flashattention2.pdf]]"
source_md: "[[iclr24-dao-flashattention2]]"
---

# FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning (ICLR 2024)

> **一句话总结**：FlashAttention-2 在 [[Flash-Attention]] 的 exact attention kernel 上重做 work partitioning：减少非 matmul FLOPs、沿 sequence length 增加 thread-block 并行、把 warp 内分工从 split-K 改成 split-Q，在 A100 上相对 FA1 约 **2x**，attention forward 最高 **230 TFLOPs/s**，GPT-style 训练最高 **225 TFLOPs/s/GPU**。

## 问题

[[FlashAttention-NeurIPS22|FlashAttention]] 已经通过 tiling + online softmax 避免物化 `N x N` attention matrix，把 memory 从 `O(N^2)` 降到 `O(N)`，并相对标准 attention 实现获得 2-4x speedup。但 FA1 仍远低于 optimized GEMM：A100 上 forward 只有约 30-50% 理论峰值，backward 约 25-35%，而 GEMM 可到 80-90%。

论文的诊断是：瓶颈已经不只是 HBM IO，而是 GPU work partitioning 还不够好。长序列下 batch/head 数往往小，只按 batch 和 head 维度并行会让 SM occupancy 不足；warp 内 split-K 又引入 shared memory 写回、同步和归约。

## 核心方法

FlashAttention-2 保持 exact [[Attention]] 语义和 FA1 的 IO-aware tiling，不走 sparse / approximate 路线，而是把实现分工改得更接近 GEMM：

1. **减少非 matmul FLOPs**：A100 的 FP16/BF16 Tensor Core matmul 理论吞吐约 312 TFLOPs/s，而非 matmul FP32 约 19.5 TFLOPs/s。FA2 在 online softmax 更新里维护 unscaled output，并且 forward 只保存 logsumexp `L`，减少 rescale、max/sum 统计维护等非矩阵乘开销。
2. **沿 sequence length 并行**：FA1 主要按 batch × heads 发 thread blocks。FA2 把 Q row blocks 也作为并行维度，forward 中每个 row block 独立处理，backward 中按 column block 并行并用 atomic add 合并 `dQ`，解决长序列、小 batch 时 SM 利用率不足。
3. **warp 内从 split-K 改为 split-Q**：FA1 在一个 thread block 内把 K/V 分给不同 warp，warp 之间要把中间结果写 shared memory 后同步归约。FA2 改成把 Q 分给 warp，K/V 对所有 warp 可见，每个 warp 直接得到自己那部分 output，减少 shared memory communication。

实现上仍然手工调 block size，通常在 `{64,128} x {64,128}` 间选择；论文也指出这类参数未来适合 autotuning。

## 关键结果

- A100 80GB 上，attention microbenchmark 中 FA2 相对 FA1 **1.7-3.0x**，相对 Triton FA **1.3-2.5x**，相对标准 PyTorch attention **3-10x**。
- A100 上 attention forward 最高 **230 TFLOPs/s**，约 **73%** 理论峰值；backward 最高约 **63%** 理论峰值。
- 8×A100 训练 GPT-style 模型时，FA2 相对无 FlashAttention baseline 最高 **2.8x**，相对 FA1 最高 **1.3x**。
- GPT3-2.7B、8K context 上达到 **225 TFLOPs/s/GPU**，约 **72% model FLOPs utilization**。
- H100 上未使用 TMA / 4th-gen Tensor Core 新指令时，forward+backward 已达 **335 TFLOPs/s**；论文把 H100 TMA、FP8、新 Tensor Core 路径列为后续方向，也自然导向 [[FlashAttention-3-NeurIPS24|FlashAttention-3]] 和 [[FlashAttention-4-MLSys26|FlashAttention-4]] 等后续工作。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Online-Softmax]]
- **前序工作**：[[FlashAttention-NeurIPS22|FlashAttention]]
- **后续工作**：[[FlashAttention-3-NeurIPS24|FlashAttention-3]]、[[FlashAttention-4-MLSys26|FlashAttention-4]]
- **同主题**：[[Foundation]]、[[AI-Infra]]
