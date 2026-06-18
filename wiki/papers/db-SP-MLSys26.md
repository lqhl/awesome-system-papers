---
type: paper
name: db-SP
full_title: "Accelerating Sparse Attention for Visual Generative Models with Dual-Balanced Sequence Parallelism"
authors: [Siqi Chen, Ke Hong, Tianchen Zhao, Ruiqi Xie, Zhenhua Zhu, "et al."]
venue: MLSys
year: 2026
tags: [diffusion-transformer, sparse-attention, sequence-parallelism, load-balancing, video-generation]
source_pdf: "[[d3d9446802a44259755d38e6d163e820.pdf]]"
source_md: "[[d3d9446802a44259755d38e6d163e820]]"
---

# Accelerating Sparse Attention for Visual Generative Models with Dual-Balanced Sequence Parallelism (MLSys 2026)

> **一句话总结**：db-SP 在 block-wise 稀疏注意力下同时平衡 head 维与 block 维的 sequence parallelism 工作量，把 Wan2.1-T2V-14B 视频生成的端到端延迟再降 1.25×，attention 层 1.40×。

## 问题

Diffusion Transformer (DiT) 视频生成中 [[Attention]] 占总延迟 50%+。Block-wise [[Sparse-Attention]]（PAROAttention、SpargeAttn）在单卡上有效，但 Ulysses（按 head 分）和 Ring Attention（按 sequence 分）均出现严重工作量不均：head 间稀疏度差异大、dense block 分布不规则。sparse imbalance ratio ρ_s 在 Wan2.1 上达 1.513，8 GPU 仅获 6.09× / 5.81× 加速而非理想 8×。

## 核心方法

**db-SP** 提出 dual-level 分区 + 动态策略选择：

1. **Decouple 两级优化**：先 greedy 做 head-level 近完美均衡，再在均衡假设下做 block-level 分区。
2. **Block-level biased greedy**：reward factor 惩罚跨 GPU 数据交换。
3. **跨去噪步复用分区**：利用相邻 step sparse mask 相似性。
4. **Sparsity-aware 策略选择**：动态在 Ulysses / Ring / USP (UxRy) 间选最优并行度。

## 关键结果

- 端到端视频生成 **1.25×** 提速，attention 层 **1.40×**（8× A800 平均）。
- ρ_s 从 1.513 降至接近 1.0。
- 优于 USP、Ulysses、Ring Attention。
- Code: https://github.com/thu-nics/db-SP

## 相关

- **相关概念**：[[Attention]]、[[Sparse-Attention]]、Sequence Parallelism、Ulysses、Ring Attention
- **同类系统**：xDiT、ParaAttention、DSV、BurstAttention
- **同会议**：[[MLSys-2026]]