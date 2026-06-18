---
type: paper
name: QBL
full_title: "Practical Adversarial Multi-Armed Bandits with Sublinear Runtime"
authors: [Kasper Overgaard Mortensen, Ama Bembua Bainson, Mathias Ravn Tversted, Kristoffer Strube Græm, Andrea Paudice, Renata Borovica-Gajic, Davide Mottin, Panagiotis Karras]
venue: MLSys
year: 2026
tags: [multi-armed-bandit, database-tuning, index-selection, adversarial]
source_pdf: "[[9b8619251a19057cff70779273e95aa6.pdf]]"
source_md: "[[9b8619251a19057cff70779273e95aa6]]"
---

# Practical Adversarial Multi-Armed Bandits with Sublinear Runtime (MLSys 2026)

> **一句话总结**：提出 Queuing Behind the Leader (QBL)，组合对抗 MAB 每轮 **O(m log k)**（m 为选中 arm 数），用 priority queue + selective weight update 替代 Exp3 的 O(k) 采样；DB index tuning 等非平稳 workload 上 empirical regret 与效率均优于 Exp3/DBAbandit。

## 问题

组合对抗 MAB（每轮选 m-of-k arms）现有最优 regret 算法每轮 **O(k)**，k 上千时（自动 index tuning 等）不可实用。非平稳环境还需 O(log T) 额外开销。

## 核心方法

**Exp3 工程化**：streaming LogSumExp + sumheap 采样，Exp3.M 从 O(k log m) 降到 **O(m log k)**。

**QBL / QBL.M**：leader-follower priority queue，仅 demote leader 时更新权重；normalized reward + counter reset 防 overcommitment；单参数 γ 控制 exploration。

## 关键结果

- 每轮复杂度 **O(m log k)**，k 很大时比 Exp3 线性采样实用
- TPC-H 10GB 非平稳 workload：QBL.M index utilization 比 DBAbandit/HMAB 稳定高约 **10%**
- combinatorial dummy reward benchmark：QBL.M 采样+更新远快于 Exp3.M（k=2000, m=k/10）

## 相关

- **相关概念**：MoE（正交：DB physical design，非 ML MoE）
- **同类系统**：DBAbandit、HMAB、Exp3、Exp3.M
- **同会议**：[[MLSys-2026]]