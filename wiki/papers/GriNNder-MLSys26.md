---
type: paper
name: GriNNder
full_title: "GriNNder: Breaking the Memory Capacity Wall in Full-Graph GNN Training with Storage Offloading"
authors: [Jaeyong Song, Seongyeon Park, Hongsun Jang, Jaewon Jung, Hunseong Lim, Junguk Hong, Jinho Lee]
venue: MLSys
year: 2026
tags: [gnn, full-graph-training, storage-offloading, nvme, pytorch-geometric]
source_pdf: "[[1679091c5a880faf6fb5e6087eb1b2dc.pdf]]"
source_md: "[[1679091c5a880faf6fb5e6087eb1b2dc]]"
---

# GriNNder: Breaking the Memory Capacity Wall in Full-Graph GNN Training with Storage Offloading (MLSys 2026)

> **一句话总结**：首个把 NVMe SSD 纳入 GPU-host-storage 三层层次做 full-graph GNN 训练的框架，用 cache-(re)gather-bypass 协调分区缓存、梯度 regather 和轻量图划分，在单卡上相对 HongTu 最高 9.78× 加速、吞吐接近 16-GPU 分布式基线。

## 问题

Full-graph GNN training 保留完整邻域信息，算法验证最直接，但每层都要存全部顶点 activation/gradient，大图轻松超出 GPU 与 host memory。单服务器方案（Betty、HongTu）仍受内存上限约束；分布式方案（CAGNET、Sancus）硬件成本高，且跨节点通信可占 80–98% 时间。

直接把 LLM offload 或 mini-batch GNN storage 思路搬过来不行：GNN 权重共享、activation 才是大头；mini-batch 仍有 neighbor explosion。朴素 storage offload 还会遇到随机读放大、activation snapshot 的 α 倍冗余、METIS 划分本身 OOM 三大问题。

## 核心方法

GriNNder 提出 **structured storage offloading (SSO)**，用 cache-(re)gather-bypass 管理三层内存：

- **Cache**：按 partition × layer 粒度把 activation 缓存在 host，利用跨 partition 依赖的 power-law 分布做 intra-layer reuse，避免细粒度 storage 随机读。
- **(Re)gather**：forward 只 gather 输入 activation；backward 从原始 A0 **just-in-time regather**，不存 α 倍放大的 snapshot，中间值也按需重算。相对 PyTorch autograd + HongTu，storage I/O 可从约 8.5× 降到 2D 量级（典型 α≈8）。
- **Bypass**：拓扑和输出 activation 经 GPUDirect Storage 直写 SSD，减轻 host cache 压力。

**Switching-aware partitioning**：不用内存饥渴的 METIS，在 CSR 上做 label-propagation 式轻量划分，内存仅 O(2|V|+2|E|)，比 MT-METIS 省 7.10–24.37×；收敛 30–50 轮，训练时间开销 <0.4%。

实现为 **PyGriNNder**：继承 PyTorch Geometric 的 `GriNNderGNN` 基类，通常只需改几行即可接入；不改训练算法，精度与基线一致。

## 关键结果

- 单 RTX A5000（24 GB）+ 128 GB DRAM + PCIe 5.0 NVMe 上，3/5-layer GCN（hidden 256）：
  - vs Betty：最高 **30.98×**（Products）
  - vs Ginex：最高 **77.92×**
  - vs HongTu（IGBM）：**6.97× / 9.78×**
  - vs 16-GPU CAGNET（IGBM）：**1.52× / 1.38×**；Papers 100M 节点单卡仍快 **1.10×**
- 峰值 host memory 比 HongTu 低 **5.75×**（layer-wise cache）
- SSD 写量：IGBM 每 epoch HongTu 192.4 GB vs GriNNder 2.1 GB
- 支持 GAT、GraphSAGE、多 GPU partition parallelism

## 相关

- **相关概念**：Full-Graph Training、Activation-Checkpointing、Graph-Partitioning
- **同类系统**：HongTu、Betty、Ginex、CAGNET、Sancus
- **同会议**：[[MLSys-2026]]