---
type: paper
name: Snary
full_title: "Snary: A High-Performance and Generic SmartNIC-accelerated Retrieval System"
authors: [Qiaoyin Gan, Heng Pan, Luyang Li, Kai Lv, Hongtao Guan, Zhaohua Wang, Zhenyu Li, Gaogang Xie]
venue: ATC
year: 2025
tags: [smartnic, fpga, retrieval, recommendation, lsh, hbm]
source_pdf: "[[atc2025-gan.pdf]]"
source_md: "[[atc2025-gan]]"
---

# Snary: A High-Performance and Generic SmartNIC-accelerated Retrieval System (ATC 2025)

> **一句话总结**：在 Xilinx U50 SmartNIC FPGA + HBM 上同时支持 EBR 系统的 exact 与 fuzzy retrieval：data-parallel similarity 计算 + 改进的 pipeline parallel Top-K + LSH 缩小 corpus，相比 FAERY 延迟降 20.91-83.88%，相比 GPU Faiss 吞吐高 14-23×。

## 问题

工业 recommendation 两阶段 (retrieval + ranking) 中 retrieval 要从百万 corpus 中 top-K 召回，是性能瓶颈。CPU 内存带宽不足；GPU (Faiss) Top-K 阶段占 80% 延迟、recall 上限 1024；现有 FPGA 方案 FAERY 只支持 exact，不能做 fuzzy。

## 核心方法

SNARY 在 SmartNIC（最靠近用户查询的位置）上做完整 pipeline，HBM 存 corpus，分两个引擎：

1. **Exact search**：corpus 横向均分进 16 个 HBM channel（4 GB / 1024M embeddings），单 cycle 并行读 NE = N·BM/E 个 embedding；similarity 计算用 NE 个并行 unit 在一个 cycle 内输出 NE 个分数。Top-K 用改进的 parallel-swap 算法：长度 K 数组中第 0 位永远是当前最小，新 score 比较后做两轮 parallel swap，O(1) 时间复杂度，仅占 O(K) 片上内存（vs FAERY 的 O(9K/2)）。filter 模块（4 个深 2K 的 FIFO）平衡 NE 个分数 vs Top-K 单 cycle 1 分数的吞吐差异。
2. **Fuzzy search**：用 SimHash-based [[LSH]] 单表查询（Lh = 1 避免 intersection/union 破坏 pipeline），调 Kh、Th 控制 bucket 邻域大小。预处理把每 bucket 内 embedding 按 channel 分类、padding 后重排，保证连续 NE 个元素分布在不同 channel 以维持 NE 并行 corpus 访问。

实现支持 K = 512/1024/2048/4096，集成 100 Gbps TCP/IP 栈直接收发查询。Memory 9M embedding 占约 28% HBM。详见 [[atc2025-gan]]。

## 关键结果

- Exact search：相比 Faiss 延迟降 78.75-83.88%、吞吐 (10 ms 限制下) 14.12-18.27×；相比 FAERY 延迟降 20.91-45.19%、吞吐 1.26-1.64×。
- Fuzzy search：相比 Faiss 延迟降 85.13-87.40%、吞吐 20.18-23.81×；FAERY 不支持 fuzzy。
- 高 recall (K = 4096) 下 Faiss 直接失效（上限 1024），FAERY 资源占用陡增；SNARY 仍稳定运行。
- Top-K 算法改进：片上内存从 O(9K/2) 降到 O(K)，pipeline depth 从 O(log K) 降到 1-2 stage。

## 相关

- **相关概念**：[[SmartNIC]]、[[FPGA]]、[[HBM]]、[[LSH]]、[[Embedding-Based-Retrieval]]、[[Top-K-Selection]]
- **同类系统**：Faiss (GPU)、FAERY (FPGA exact only)
- **同会议**：[[ATC-2025]]
