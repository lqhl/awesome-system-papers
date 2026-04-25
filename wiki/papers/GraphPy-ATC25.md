---
type: paper
name: GraphPy
full_title: Identifying and Analyzing Pitfalls in GNN Systems
authors: [Yidong Gong, Arnab Kanti Tarafder, Saima Afrin, Pradeep Kumar]
venue: ATC
year: 2025
tags: [gnn, benchmarking, framework-overhead, methodology, pitfalls]
source_pdf: "[[atc2025-gong.pdf]]"
source_md: "[[atc2025-gong]]"
---

# Identifying and Analyzing Pitfalls in GNN Systems (ATC 2025)

> **一句话总结**：系统性揭露 20+ 个 GNN 训练系统中由「不报训练精度 + 只用小数据集」导致的多类设计 / 实现 / 评估陷阱，并给出参考系统 GRAPHPY，对比 DGL 平均 6.92× 显存节省、1.69× 训练加速。

## 问题

近 5 年发表在 OSDI/ASPLOS/ATC/MLSys 等顶会的单 GPU GNN 训练系统普遍**不报训练 accuracy**，且**严重依赖小数据集**得出 runtime 加速结论。作者怀疑这些做法掩盖了底层正确性 bug 与评估盲点，导致 community 对 GNN system 优化的认知失真。

## 核心方法

把陷阱分两大类：

**EVAL-P1: 缺少 accuracy 测量**——在 DGL 之外，只有 PyG 和 FuseGNN 在 GCN 上能跑出正常精度，其他系统 accuracy 异常或干脆没实现 backward。引出四个 system design 子陷阱：
- **SYS-P1 Omitted state tensor**：激进 fuse forward kernel 但不 materialize backward 需要的 state tensor（attention score、ReLU mask）。
- **SYS-P2 Sparse matrix transpose**：要么不做 transpose（TC-GNN 用 forward SpMM 当 backward），要么用 eShuffle / `cusparseCsr2cscEx2` 等比 cuSPARSE 原生 SpMMᵀ 慢 64–130% 的方案。
- **SYS-P3 Wrong backward order**：fused forward 的 SpMM+degree-norm 在 backward 中没倒序调用（GNNAdvisor、Seastar），导致少一次 |E| 数据加载，「跑得快」但训练错。
- **SYS-Others**：GNNAdvisor / TC-GNN 等漏 bias、漏 dropout、漏 degree-norm。

**EVAL-P2/P3: Framework overhead**——
- **Runtime overhead**：在 < 4M edge 的图上 DGL 的训练时间 100% 是 framework overhead，GPU 大多 idle。Cora/Pubmed/Citeseer 上「速度提升」其实只是 Python/C++ glue 代码差异。Sample-based GNN（GraphSage / MariusGNN）的 sampled batch 也只有 13k–2M edge，同样 100% overhead。
- **Memory overhead**：DGL 的 SpMM 因为 PyTorch 非标集成调用 `torch::empty()` 在 backend，引入 12,046 MB 额外显存（Reddit 上实测），让所有「以 DGL 为唯一 baseline 的省显存工作」结果膨胀。

参考系统 **GRAPHPY** 用正确的 cuSPARSE SpMMᵀ + 数据局部性 + 数据集对称性挖掘，证明陷阱的量化影响。

## 关键结果

- GRAPHPY 相比 DGL 平均显存降 6.92× / 3.4× / 1.96×，训练 1.69× / 1.22× / 2.20× 加速（GCN/GIN/GAT-1）。
- GRAPHPY 在单 A100 上能训练 1B-edge 图，DGL 连 500M-edge 都 OOM。
- 用 GRAPHPY 做 baseline 重测 dgNN：dgNN 的 kernel fusion 在 GAT 上比 GRAPHPY 慢 1.48×，显存仅省 6.4%（之前对比 DGL 看起来很好）。

## 相关

- **相关概念**：GNN、SpMM、SDDMM、framework-overhead
- **同类系统**：DGL、PyG、GNNAdvisor、TC-GNN、Seastar、dgNN、FuseGNN
- **同会议**：[[ATC-2025]]
