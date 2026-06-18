---
type: paper
name: Catur
full_title: "Virtual Machine NUMA Placement at Scale: Learning the Norm, Shielding the Tail"
authors: [Yibo Zhao, Tianyuan Wu, Hui Xue, Qi Chen, Zhenhua Han, "et al."]
venue: MLSys
year: 2026
tags: [numa, vm-placement, reinforcement-learning, cloud, hypervisor]
source_pdf: "[[ea5d2f1c4608232e07d3aa3d998e5135.pdf]]"
source_md: "[[ea5d2f1c4608232e07d3aa3d998e5135]]"
---

# Virtual Machine NUMA Placement at Scale: Learning the Norm, Shielding the Tail (MLSys 2026)

> **一句话总结**：Catur 用强化学习在 1 亿 VM 生产 trace 上学 NUMA 放置，配合 reward shaping、稳健 action space、drift-aware 持续训练与 speculative shielding，把平均 placement defect 降 34.2%–50.0%，训练效率 16.4×、成本降 93.9%。

## 问题

云物理机按 NUMA 拓扑组织 CPU/内存，hypervisor 要把 VM 的 vCPU 与内存映射到节点。放置不当会带来 **core defect**（单 NUMA 超载 vCPU）和 **memory defect**（跨节点 remote memory），应用性能可跌 **>30%**（TeraSort、SPECjbb、SPTAG、DBApp 等差异敏感）。

规模难点：CloudX trace 有 **1 亿 VM**、数百种 VM 规格与 Intel/AMD 异构硬件；负载模式随时间与集群漂移。Xen pack/spread、OpenStack Nova、E-PVM、Tetris 等规则策略无法同时兼顾平均利用率与尾部 SLA。

## 核心方法

**优化目标：placement defect** = α×core defect + β×memory defect（COR 与 RMR 量化）。

**Learning the norm（RL）**：把 NUMA 放置建模为 POMDP，ResNet Q-network 在单机粒度决策；相比监督学习更能捕捉「当前放置影响未来资源碎片」的长期回报。

**生产化四件套**：
1. **Reward shaping**：55% 无 defect、6.9% 不可避免 defect 的样本降权，聚焦 38% 可避免 defect 场景，解决 skewed trace 学不动的问题。
2. **Robust action space**：从 Xen/Nova/E-PVM/Tetris 等政策归纳候选动作，防 model collapse。
3. **Drift-aware continuous training**：应对每月 ~25% 未见状态导致的性能退化。
4. **Speculative shielding**：对 RL 候选动作做 NUMA-state 树前瞻，避开 defect 超阈值的尾部异常（纯 RL 尾部异常比最佳启发式多 44%）。

已部署 CloudX HyperX hypervisor 早期试用。

## 关键结果

- 1 亿 VM 生产 trace：平均 defect 降 **34.2%–50.0%**（约 **1.5–2×** 于 SOTA baseline）。
- 训练：相对 vanilla RL **16.4×** 效率、**93.9%** 成本节省。
- 微基准：remote memory 0→100% 或 core 超载 0→30% 可导致 **>30%** 性能跌幅，且不同应用对两类 defect 敏感度不同。

## 相关

- **相关概念**：NUMA、VM Placement、Reinforcement Learning、Hypervisor
- **同类策略**：Xen NUMA policy、OpenStack Nova pack/spread、E-PVM、Tetris
- **同会议**：[[MLSys-2026]]