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

Diffusion Transformer (DiT) 视频生成中 attention 占总延迟 50%+。Block-wise 稀疏注意力（PAROAttention、SpargeAttn、SparseVideoGen2）在单卡上有效，但应用 sequence parallelism 到多卡时，Ulysses（按 head 分）和 Ring Attention（按 sequence 分）均出现严重工作量不均：

- **Head-level 不均**：不同 attention head 稀疏度差异显著，Ulysses 分到不同 GPU 上后工作量悬殊。
- **Block-level 不均**：稀疏 mask 中 dense block 分布不规则，Ring Attention 下各 GPU 的 K/V chunk 对应的有效 block 数不等。

作者量化定义 sparse imbalance ratio ρ_s = max-loaded / avg-loaded，在 Wan2.1 / CogVideoX1.5 实测 1.159 - 1.513，意味着工作均衡后可获 15%-50% 加速空间。

## 核心方法

**db-SP** 提出 dual-level 分区 + 动态策略选择：

1. **decouple 两级优化**：先按 greedy 做 head-level 分区达近完美均衡，再在「每 GPU head-level 工作已均衡」假设下做 block-level 分区。
2. **Block-level biased greedy**：引入 reward factor 惩罚跨 GPU 数据交换，降低 reorganize 开销。
3. **跨去噪步复用分区结果**：利用相邻 denoising step 的 sparse mask 相似性跳过重复分区。
4. **Sparsity-aware 策略选择**：动态在 Ulysses / Ring / USP (UxRy) 之间选最优的并行度组合，依据 latency 预测模型；每层 transformer 可用不同策略。

## 关键结果

- 端到端视频生成 1.25× 提速，attention 层 1.40× 提速（平均，8× A800）。
- 在 Wan2.1-T2V-14B + PAROAttention 下，ρ_s 从 1.513 降至接近 1.0。
- 相比 USP、Ulysses、Ring Attention 三种 SOTA 均有显著优势。
- Code: https://github.com/thu-nics/db-SP

## 相关

- **相关概念**：[[Attention]]、Sparse Attention、Sequence Parallelism、Ulysses、Ring Attention、USP
- **同类系统**：xDiT、ParaAttention、DistriFusion、PipeFusion、DSV、BurstAttention
- **相关论文**：PAROAttention、SpargeAttn、Sparse VideoGen2、[[Flash-Attention]]
- **同会议**：[[MLSys-2026]]
