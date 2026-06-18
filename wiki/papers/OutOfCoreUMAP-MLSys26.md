---
type: paper
name: OutOfCoreUMAP
full_title: "Massive-Scale Out-of-Core UMAP on the GPU"
authors: [Jinsol Park, Corey J. Nolet, Akira Naruse, Edward Raff, Tim Oates]
venue: MLSys
year: 2026
tags: [umap, gpu, out-of-core, knn-graph, cuml, data-mining]
source_pdf: "[[5f93f983524def3dca464469d2cf9f3e.pdf]]"
source_md: "[[5f93f983524def3dca464469d2cf9f3e]]"
---

# Massive-Scale Out-of-Core UMAP on the GPU (MLSys 2026)

> **一句话总结**：用 IVF+spilling 的 out-of-core 多 GPU all-neighbors 构图突破单卡显存限制，单 GPU 小数据集 22.7× 加速，MIRACL 超大数据集端到端投影 74×、预计算 kNN 后 121×，trustworthiness 与 CPU 参考实现相当。

## 问题

UMAP 的 all-neighbors kNN 构图占端到端时间 75–99%，且需全量数据驻留内存/GPU，使数十到数百 GB 向量在 CPU 上需数小时到数天。既有 GPU UMAP（Nolet et al. 2021）仍要求数据集 fit 单卡显存，成为大规模探索式分析瓶颈。

## 核心方法

四步 out-of-core all-neighbors 构图（开源于 NVIDIA cuVS / cuML）：

1. **分层 balanced k-means** 在 GPU 子样本上划分 $c$ 个 cluster
2. **Spilling**：每向量分配到最近 $s$ 个 cluster（非硬划分），保证边界邻居不丢
3. **Per-cluster local kNN**：按 inverted index gather 到 GPU，独立构图
4. **Global merge**：CSR 行级 k-selection + 去重，增量合并到全局图

多 GPU 时 cluster 构图可并行，避免 all-to-all 广播。参数 $(c, s)$ 在显存、精度、耗时间 trade-off。

## 关键结果

- 小数据集（CPU 可跑完）：单 GPU **22.7×** end-to-end 加速
- Wiki-all / MIRACL（CPU 无法完成）：8 GPU 端到端 **74×**（保守外推对比）
- GPU 预计算 kNN + 剩余 UMAP 步骤：**121×** vs CPU，trustworthiness 无明显下降
- 多 GPU strong scaling 有效；可视化与 CPU embedding 高度一致
- all-neighbors 框架可复用于 Isomap、t-SNE 等流形学习算法

## 相关

- **相关概念**：近似最近邻、流形学习、IVF
- **同类系统**：cuML、cuVS、pynndescent、Faiss
- **同会议**：[[MLSys-2026]]