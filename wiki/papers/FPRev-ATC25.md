---
type: paper
name: FPRev
full_title: "Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations"
authors: [Peichen Xie, Yanjie Gao, Yang Wang, Jilong Xue]
venue: ATC
year: 2025
tags: [floating-point, reproducibility, testing, tensor-core, numerical-analysis]
source_pdf: "[[atc2025-xie.pdf]]"
source_md: "[[atc2025-xie]]"
---

# Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations (ATC 2025)

> **一句话总结**：用「masked all-one array」(M, -M, 1, 1, ..., 1) 黑盒探测把 summation/dot/matmul 的累加顺序还原成 summation tree，时间复杂度从 brute-force 的 O(4ⁿ/n^1.5) 降到 O(n²)；首个支持 [[Tensor-Core]] 多项 fused summation（multiway tree）的工具。

## 问题

浮点加法非结合，但 NumPy/PyTorch/cuBLAS/MKL 这些库的 accumulation 顺序在不同 CPU/GPU、不同版本里可能不同，又都不公开顺序——给数值复现性（航空航天、银行、AI 训练）带来巨大风险。比如 fp16 下 (0.5+512)+512.5=1025 而 0.5+(512+512.5)=1024。Tensor Core 的 multi-term fused summation 还用 align+truncate 这种非 IEEE-754 算术。

## 核心方法

- **Masked all-one array**：构造 A^{i,j} = (1, ..., M_at_i, ..., -M_at_j, ..., 1)，M 大到能 swamp 任何 (n-2)+M=M。SUMIMPL(A^{i,j}) 的输出 = 没被 M 或 -M mask 掉的 1 的个数 = n - l^{i,j}，其中 l^{i,j} 是 summation tree 中 i、j 的 LCA 子树叶子数。
- **BasicFPRev**：枚举所有 (i,j) 算 l^{i,j}，按升序自底向上构造完全二叉 summation tree，O(n² t(n))。
- **FPRev refinement**：on-demand 计算 l^{i,j}，best case O(n t(n))（顺序求和的 cache-friendly 实现）；递归分子树。
- **Multiway tree for matrix accelerators**：对 [[Tensor-Core]] 的 multi-term fused summation（一组 summands 对齐截断后定点加），用 w 路节点表示；通过比较返回子树叶子数与 |J_l| 区分「兄弟」与「父」节点。

深度细节回 [[atc2025-xie]]。

## 关键结果

- NumPy 的 sum 在三种 CPU 上一致（8-way SIMD-friendly + pairwise），跨平台可复现；但 dot/matvec/matmul 受 CPU 核数等影响顺序不一致。
- PyTorch 在 V100/A100/H100 上 sum 一致，但其他 BLAS 后端 op 不一致。
- 时间复杂度 O(n²t(n)) 远优于 brute force O(4ⁿ/n^1.5)；实际多数库属于 best case O(n t(n))。
- 开源在 github.com/peichenxie/FPRev。

## 相关

- **相关概念**：[[Tensor-Core]]、[[Floating-Point]]、[[Reproducibility]]
- **同会议**：[[ATC-2025]]
