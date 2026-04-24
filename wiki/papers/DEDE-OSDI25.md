---
type: paper
name: DEDE
full_title: "Decouple and Decompose: Scaling Resource Allocation with DEDE"
authors: [Zhiying Xu, Minlan Yu, Francis Y. Yan]
venue: OSDI
year: 2025
tags: [resource-allocation, optimization, admm, cluster-scheduling, traffic-engineering]
source_pdf: "[[osdi25-xu.pdf]]"
source_md: "[[osdi25-xu]]"
---

# Decouple and Decompose: Scaling Resource Allocation with DEDE (OSDI 2025)

> **一句话总结**：DEDE 发现真实云资源分配问题普遍具有「separable structure」，用 ADMM 把 resource/demand 约束解耦成 per-resource 与 per-demand 子问题并行求解，在集群调度、流量工程、负载均衡三类任务上同时得到 **3.1×–7.6×** 加速和 **5.3%–12.6%** 质量提升，且不依赖任何领域假设。

## 问题

现代云系统的资源分配规模越来越大（百万变量级），商业 LP/MILP 求解器（Gurobi、CPLEX）要跑几十分钟到几小时，远不能满足秒级 SLO。已有加速方案都有局限：POP 假设问题是 "granular"（每个 demand 只要一小部分可互换资源），实际工作负载下 (33% GPU 任务只能跑特定类型) 解质量明显下降；Teal 是针对流量工程定制的神经网络；NCFlow、Soroush 等也都依赖领域特定设计或特定目标。

作者想找一个 **domain- and workload-agnostic** 的通用加速框架。

## 核心方法

对数十篇论文中的真实分配问题做总结，发现普遍的 separable 结构：目标是 $\sum_i f_i(x_{i*}) + \sum_j g_j(x_{*j})$，约束为 per-resource $R_i x_{i*} = r_i$ 和 per-demand $D_j x_{*j} = d_j$，耦合只来自共享变量 $x_{ij}$ 同时出现在两侧约束。

**Decouple**: 引入辅助变量 $z = x$，把 demand 约束和目标里的 demand 项改写成关于 $z$，加入新约束 $x = z$。这把问题改写成 $\min f(x) + g(z), \text{s.t. } Ax + Bz = c$ 的标准 ADMM 形式。

**Decompose**: 在 ADMM 的 augmented Lagrangian 上分别对 $x$ 和 $z$ 做交替极小化。由于可分离结构，x-min 自然分解成 $n$ 个独立的 per-resource 子问题（各 $m$ 变量），z-min 同样分解成 $m$ 个 per-demand 子问题。每个子问题用现成 LP/MILP solver 求解，可真正并行，理论复杂度从 $O((nm)^{2.373})$ 降到 $n \cdot O(m^{2.373})$。

Python 包 `pip install dede`，基于 cvxpy 提供类似 API，Ray 实现真并行（非 POP 的"模拟并行"）。对连续、整数、布尔变量都适用，后者通过投影处理。

## 关键结果

- 集群调度（16,520 GPU 实例, 456 种类型）：相比 POP 最佳变体，分配质量高 **7.3%**、速度快 **3.1×**；比 Exact sol. 快 15× 同时保持质量
- 流量工程（1,739-node WAN）：**+5.3% / 7.6×**；90% 满足率只用 30 s（Exact 需 minutes）
- 负载均衡（2,048 shard / 256 server MILP）：**+12.6% / 2.2×**
- 对粒度变化（POP 假设失败的场景）鲁棒：POP 下降最多 12.3%，DEDE 只降 0.8–2.1%
- 在 64 CPU core 下近线性加速（DEDE* 61.7×，DEDE 18.2×，Exact 仅 3.4×）

## 相关

- **相关概念**：[[ADMM]]、[[Lagrangian-Method]]
- **同类系统**：POP、Teal、NCFlow、Soroush、Gurobi、Gandiva
- **同会议**：[[OSDI-2025]]
