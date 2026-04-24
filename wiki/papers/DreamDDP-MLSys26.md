---
type: paper
name: DreamDDP
full_title: "DreamDDP: Accelerating Data Parallel Distributed LLM Training with Layer-wise Scheduled Partial Synchronization"
authors: [Zhenheng Tang, Zichen Tang, Junlin Huang, Xinglin Pan, Rudan Yan, et al.]
venue: MLSys
year: 2026
tags: [distributed-training, local-sgd, data-parallel, communication-overlap, llm-training]
source_pdf: "[[9f61408e3afb633e50cdf1b20de6f466.pdf]]"
source_md: "[[9f61408e3afb633e50cdf1b20de6f466]]"
---

# DreamDDP: Accelerating Data Parallel Distributed LLM Training with Layer-wise Scheduled Partial Synchronization (MLSys 2026)

> **一句话总结**：把 Local SGD 的「整模型 H 步同步」解耦为 layer-wise 的 partial synchronization，使参数同步能和 BP 重叠，在 32 GPU 低带宽环境上把 ResNet-18/50、GPT-2、Llama-2 训练加速 1.49–3.91× vs. LSGD/ASC-WFBP。

## 问题

跨地理分布式数据中心训练 LLM 受限于 10 Mbps–1 Gbps 的带宽，S-SGD 每步 gradient all-reduce 成为瓶颈。Local SGD（LSGD）通过每 H 步才同步一次模型参数把通信开销降 H 倍，INTELLECT-1 也验证了它在 10B 规模 decentralized 训练可行。但 LSGD 的"整模型全同步"是 hard synchronization point：update 必须等 BP 结束、communication 必须等 update，导致通信与计算无法像 WFBP/ASC-WFBP 那样重叠。三大挑战：(1) 如何移除硬同步点；(2) 如何在不增加 GPU 显存前提下 in-place 同步参数且不破坏 FP/BP 正确性；(3) 如何在 $H^L$ 搜索空间中调度 L 层 × H 步的分配。

## 核心方法

**1. Partial Synchronization (PLSGD)**：把模型 $\mathcal{L} = \{1, ..., L\}$ 划分成 H 个不相交的子集 $\mathcal{L}_1, ..., \mathcal{L}_H$，第 r 步只同步 $\mathcal{L}_{r \mod H}$。H 步内全部参数恰好各同步一次，通信总量与 LSGD 相同。
- 理论上证明 PLSGD 的收敛率与 S-SGD 同阶 $O(1/R)$（Theorem 1）。
- 实验上 partial sync 的 model divergence $\Gamma_r$ 反而更小——full sync 存在「layer-wise divergence amplification」（前层散度被后层放大），partial sync 持续消除部分层的散度。

**2. In-place Overlapping without Extra Memory**：将层通信紧跟在该层 BP 之后 launch，与后续层的 BP 重叠。关键约束：参数同步必须在对应层 BP 完成后才能 launch，否则 in-place 修改会破坏前向/反向。

**3. DFS-based Scheduling with Pruning**：构建 FP/BP/通信时间成本模型（Eq. 7），把层-迭代分配建模成优化问题。识别三个可剪枝性质：
- **Optimal hiding**：通信能被计算完全 hide 时无需进一步优化。
- **Delayed CO assignment**：倾向把通信分配到较晚的迭代。
- **At-least-one assignment**：每个迭代至少分配一层通信。

基于这三点做 DFS 显著剪枝搜索空间。

**4. Bubble Filling**：DFS 解后若仍有通信带宽 bubble，插入额外的参数同步（提升这些层的同步频率，加快收敛），只要新通信能完全被计算 hide。

集成 PyTorch Distributed 实现，profiler 动态测每层 FP/BP/COMM 时间，按 GPU 和带宽配置自适应。

## 关键结果

- 32 GPU 跨两 cluster 实验：相比 LSGD / ASC-WFBP 迭代时间加速 **1.49× – 3.91×**。
- ResNet-18 / ResNet-50 / GPT-2 / Llama-2 四个模型收敛速度与 S-SGD 接近。
- Model divergence 比 full sync 更低（layer-wise 持续清理）。
- 无额外 GPU 显存占用（in-place 层级同步）。

## 相关

- **相关概念**：[[Local-SGD]]、[[Data-Parallel]]、[[Communication-Computation-Overlap]]、[[WFBP]]
- **同会议**：[[MLSys-2026]]
