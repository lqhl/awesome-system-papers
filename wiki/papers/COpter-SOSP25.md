---
type: paper
name: COpter
full_title: "COpter: Efficient Large-Scale Resource-Allocation via Continual Optimization"
authors: [Suhas Jayaram Subramanya, Don Kurian Dennis, Virginia Smith, Gregory R. Ganger]
venue: SOSP
year: 2025
tags: [resource-allocation, optimization, scheduling, linear-programming, milp]
source_pdf: "[[3731569.3764846.pdf]]"
source_md: "[[3731569.3764846]]"
---

# COpter: Efficient Large-Scale Resource-Allocation via Continual Optimization (SOSP 2025)

> **一句话总结**:把 round-based 资源分配(GPU 调度、shard 负载均衡、WAN TE)建模为"慢演化 LP/MILP 序列",通过增量问题表示 + proximal-point solver + 轻量整数化启发式,solver 时间比商业 solver 快 57–83×,比 POP 分区法同时提高 1.5–30× 的速度和分配质量。

## 问题

大规模资源分配(25k GPU 集群、万级 jobs)用优化器(LP/MILP)每隔几分钟重新求解一次,可惜现代 commercial solver 黑盒调用下,Sia policy 从 10k GPU 扩到 25k GPU 时 solver 时间 ≈ 100×,1 分钟 round deadline 内能解完的问题比例从 85% 降到 15%。

现有绕路要么牺牲质量(POP-32 分区,分配差)要么错过 deadline(POP-4),要么 warm-start 对 Simplex/Interior-Point 不 robust(ℓ2 接近不一定意味着 central path 接近、Simplex 的 vertex 路径可能指数级)。根本问题:每轮当独立问题处理,丢掉了"连续 round 间 < 0.01% 变量值变化、仅几 % 的 add/remove" 这一强时间结构。

## 核心方法

**Slowly Evolving LP 范式**:定义两个 path-length —— P_η(T)(问题维度变化)和 P_x(T)(最优解 ℓ2 变化)——要求 τ(T) = O(P_x, P_η)。对 resource allocation 这两条通常 α, β ≪ 1。

**三件套实现连续优化**:(1) **Differential problem interface**:避免全量重编译,用支持就地修改的稀疏矩阵表示,add/remove-request、add/remove-resources 只更新受影响的列/行;在 25k GPU 实验中编译时间从 226s 的中位数骤降。(2) **Factorization-free solver**:放弃 Barrier/Simplex 的矩阵分解,用 proximal-point 类一阶方法——内部状态极小,能从前一轮最优解 warm-start,理论保证 dynamic regret 随 path-length 增长。(3) **轻量 MILP 启发式**:绕开 branch-and-cut 的组合爆炸,用 problem-specific heuristic 从 LP relaxation 恢复整数解,质量损失 negligible。

## 关键结果

- Solver 时间比商业 solver([[Gurobi]]、[[CPLEX]])快 57–83×
- 对比 POP 分区:同时提升分配质量并减少端到端 runtime 1.5–30×
- 跨三个领域验证:GPU 集群调度(Sia policy)、shard 负载均衡、WAN traffic engineering
- 可用几个 CPU 线程解有上百万变量的问题

## 相关

- **相关概念**:[[Resource-Allocation]]、[[Scheduling]]、[[Linear-Programming]]、[[Proximal-Point-Method]]、[[Warm-Start]]
- **同类系统**:[[POP]]、Sia、MAST、Meta RAS
- **同会议**:[[SOSP-2025]]
