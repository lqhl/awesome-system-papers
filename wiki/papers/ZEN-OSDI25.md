---
type: paper
name: ZEN
full_title: "ZEN: Empowering Distributed Training with Sparsity-driven Data Synchronization"
authors: [Zhuang Wang, Zhaozhuo Xu, Jingyi Xi, Yuke Wang, Anshumali Shrivastava, T. S. Eugene Ng]
venue: OSDI
year: 2025
tags: [distributed-training, gradient-compression, sparse-tensor, collective-communication, allreduce]
source_pdf: "[[osdi25-wang-zhuang.pdf]]"
source_md: "[[osdi25-wang-zhuang]]"
---

# ZEN: Empowering Distributed Training with Sparsity-driven Data Synchronization (OSDI 2025)

> **一句话总结**：ZEN 通过系统地刻画稀疏梯度张量的特征并沿「通信 / 聚合 / 切分 / 负载均衡」四个维度搜索最优通信方案，配合一个 GPU 友好的分层哈希算法实现数据无关的负载均衡，使稀疏 AllReduce 通信时间最多缩短 5.09×，端到端训练吞吐提升 2.48×。

## 问题

分布式训练的核心瓶颈是梯度同步通信。虽然 Ring-AllReduce、[[BytePS]] 等方案在稠密张量下是带宽最优的，但现代模型的梯度张量普遍高度稀疏：DLRM 的 embedding 稀疏度高达 93%，GNN 邻接矩阵 ≥ 99%，NLP 词向量 > 97%；加上 DGC 等 top-k 梯度压缩算法可进一步压缩 99% 的通信流量。

然而已有针对稀疏张量的方案（AGsparse、SparCML、OmniReduce）并未系统刻画稀疏张量的统计特征，导致通信策略次优：要么不能充分利用跨 GPU 的重叠梯度、要么产生严重的负载不均。论文要回答：**稀疏梯度同步的真正最优通信方案是什么，如何在 GPU 上高效实现**。

## 核心方法

ZEN 先在六个代表模型上实测稀疏张量三个关键特征：(C1) 不同 GPU 的非零索引重叠率呈现宽分布；(C2) 聚合后张量会变稠但稠密化比 $\gamma_G^n < n$；(C3) 非零梯度分布严重倾斜（128 个分区时一个分区可占 70%+）。基于这三个特征，作者把稀疏同步方案抽象为四个正交维度：通信模式（Ring / Hierarchy / Point-to-point）、聚合方式（增量 vs 一次性）、切分（整体 vs 并行分区）、负载（均衡 vs 不均衡），并证明理论最优方案只能是 "Balanced Parallelism"（Point-to-point + Incremental + Parallelism + Balanced）或 "Hierarchical Centralization" 两种；在实际 overlap ratio 下前者通常更优。

为把 Balanced Parallelism 落地，ZEN 设计了一个**数据无关的 GPU 并行分层哈希算法**，用多组哈希函数把非零梯度索引映射到不同 GPU 的接收桶，实现无信息损失的均衡切分，避免之前方案依赖数据分布而引入的串行写入或通信轮次。为了降低索引表示开销，ZEN 又用 **hash bitmap** 取代 COO，使得即便张量稠密度达到 95% 仍能比稠密张量减少传输量。ZEN 与 [[RDMA]] 网络协同，能在 25/100 Gbps 网络下稳定工作，并与 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、ZeRO 等并行策略组合使用。

## 关键结果

- 与最好基线对比，训练吞吐在 LSTM 上 **2.48×**、DeepFM **1.44×**、NMT **1.51×**、Llama3.2-3B **1.68×**（25 Gbps 网络）
- 通信时间最多缩短 **5.09×**（vs AllReduce）、**2.82×** (vs SparCML)、**5.16×** (vs OmniReduce)
- 哈希计算开销仅 ~6 ms（214M 参数张量），相比 270 ms 通信节省可忽略；100 Gbps RDMA 下也仅占节省的 9%
- Hash bitmap 在 95% 稠密度时仍优于稠密张量，而 COO、bitmap 在 50% 稠密度以上就失效
- 对模型精度无影响：DGC top-5% 下训练 loss 曲线与 AGsparse 完全一致

## 相关

- **相关概念**：[[RDMA]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Quantization]]（作为压缩类比）
- **同类系统**：OmniReduce、SparCML、AGsparse、BytePS（均属稀疏/稠密同步方案）
- **同会议**：[[OSDI-2025]]
