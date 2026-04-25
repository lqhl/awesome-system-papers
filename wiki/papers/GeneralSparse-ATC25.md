---
type: paper
name: GeneralSparse
full_title: "GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs"
authors: [Yaoyu Wang, Xiao Guo, Junmin Xiao, De Chen, Guangming Tan]
venue: ATC
year: 2025
tags: [llm-inference, sparsity, spmm, gpu, pruning, kernel]
source_pdf: "[[atc2025-wang-yaoyu.pdf]]"
source_md: "[[atc2025-wang-yaoyu]]"
---

# GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs (ATC 2025)

> **一句话总结**：通过抽象 memory access space + reduction space 的两个空间和自动代码生成器，对剪枝后 LLM 权重矩阵的 SpMM 比 cuSPARSE 快 20.82×、端到端推理快 2.33×。

## 问题

LLM 权重剪枝后 matmul 变成 SpMM (Sparse Matrix-Matrix Multiplication)，但剪枝方法多样导致稀疏模式各异，单一 SpMM kernel 难以普适：

- **稀疏模式 (sparsity pattern)** 多样：random、magnitude、structured 等；ASpT/Sputnik/SparTA 各自只擅长某一类
- **稀疏率 (sparsity level)** 跨层不同：LLM 顶/底层 70%，中间层 90%，需要匹配的 reduction 算法
- 缺乏 GPU 上 SpMM 自动代码生成器（[[TVM]] 不支持 SpMM；TACO 偏 CPU；AlphaSparse 是 SpMV）

## 核心方法

GeneralSparse 把 SpMM 分解为 4 个组件：

1. **Memory Access Space**：把 sparse/dense 矩阵切分抽象成「分箱」过程，正交两个维度——row-based（single/multiple-row）和 split-based（row-nonsplit/split），用 thread/warp/block offset 分层表达，配合 sort/pad/interleave/向量化指令做 format adjustment
2. **Reduction Space**：设计两类多层 reduction 算法——TOTAL（thread/warp/block 三级，对应 single-row）和 BITMAP（多行场景，用 bitmap 标记跨行边界 + 并行 SEGMENT 算法），可按稀疏率从高到低选择 thread→warp→block，并支持组合（如 thread_total + warp_bitmap）
3. **Cost Model**：评估候选组合
4. **Code Generator**：根据具体稀疏矩阵自动生成 CUDA kernel

深度细节回 [[atc2025-wang-yaoyu]]。

## 关键结果

- 在剪枝 LLM 权重矩阵 + SuiteSparse collection 上比 cuSPARSE 加速最高 **20.82×**
- 端到端 LLM 推理比 SOTA SpMM 实现加速最高 **2.33×**
- 适配 random / magnitude 等多种 unstructured pruning

## 相关

- **相关概念**：[[Quantization]]、[[Attention]]
- **同会议**：[[ATC-2025]]
