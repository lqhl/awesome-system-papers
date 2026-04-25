---
type: paper
name: Voltrix-SpMM
full_title: "Voltrix: Sparse Matrix-Matrix Multiplication on Tensor Cores with Asynchronous and Balanced Kernel Optimization"
authors: [Yaqi Xia, Weihu Wang, Donglin Yang, Xiaobo Zhou, Dazhao Cheng]
venue: ATC
year: 2025
tags: [sparse-matrix, tensor-core, gpu-kernel, gnn, hopper]
source_pdf: "[[atc2025-xia.pdf]]"
source_md: "[[atc2025-xia]]"
---

# Voltrix: Sparse Matrix-Matrix Multiplication on Tensor Cores with Asynchronous and Balanced Kernel Optimization (ATC 2025)

> **一句话总结**：用 bit-wise BMat 压缩 + warp-specialized producer-consumer 多级流水 + I/O co-balanced 持久化 kernel 让 SpMM 真正吃满 H100 Tensor Core，平均比 TC-GNN 快 36.5×、比 DTC-SpMM 快 1.8×、比 CUDA Core 的 RoDe 快 1.7×。

## 问题

SpMM 在 [[GNN]] 训练里占 80%+ 计算量。现有 Tensor Core SpMM（TC-GNN/DTC-SpMM）有两大问题：(1) 数据加载占 kernel 80% 时间——SparseA 用 CSR/ME-TCF 解压贵、DenseB 用 LDGSTS 一次只能 16B、单层 pipeline overlap 太少；(2) workload imbalance——TC-GNN 输出均衡导致输入差异巨大、DTC-SpMM 输入均衡导致输出跨 RowWindow 需 atomic add 开销大。结果 Tensor Core 即便有 7.3× 算力优势也跑不过 CUDA Core。

## 核心方法

- **BMat bit-wise 压缩**：把 16×8 的稀疏 SparseA 用 4 个 Uint32（128 bit）表示，用一条 LDGSTS.128 vectorized 加载；用 hybrid row+column tiling 切成 4 个 8×4 子块避免 shared memory bank conflict；非零浮点值另存 value vector，用 popc 直接定位 offset。
- **Warp-specialized producer-consumer**：1 个 warp 作 producer 用 [[TMA]] + LDGSTS 异步加载 SparseA/DenseB 到 shared memory，其他 warp 作 consumer 跑 m16n8k8 [[WGMMA]]；用 MBarrier 做 ping-pong 调度。
- **多级流水**：每个 consumer 同时挂多个 MMA + 多个 buffer，把 instruction issue 摊销，overlap rate 在 256/512 维下达到 85%/97%。
- **Persistent SM-aligned kernel + I/O co-balanced 分区**：CTA 数 = SM 数避免调度开销；输入按 RowWindow 粗粒度切（保证连续不跨界、不需 atomic）+ 输出按 dense 维度细粒度切；用 cost model + 贪心+启发式搜索找最优分区点。

深度细节回 [[atc2025-xia]]。

## 关键结果

- 12 个真实图数据集 + SuiteSparse：H100 上比 cuSPARSE 平均 2.7×（dim=256），比 RoDe 1.9×、比 DTC-SpMM 1.8×、比 TC-GNN 36.5×。
- GCN 端到端训练：比 DGL 快 2.0×、比 TC-GNN 快 4.01×。
- Pipeline overlap rate：dim=512 时达 97%；TCU pipe utilization 在三方对比里最高。
- 在 ddi 不均衡数据集上 SM 平衡使 kernel time 再降 8.6%。

## 相关

- **相关概念**：[[GNN]]、[[Tensor-Core]]、[[TMA]]、[[Sparse-Computation]]
- **同会议**：[[ATC-2025]]
