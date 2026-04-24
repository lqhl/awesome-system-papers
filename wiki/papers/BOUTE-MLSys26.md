---
type: paper
name: BOUTE
full_title: "BOUTE: Cost-Efficient LLM Serving with Heterogeneous LLMs and GPUs via Multi-Objective Bayesian Optimization"
authors: [Youhe Jiang, Fangcheng Fu, Eiko Yoneki]
venue: MLSys
year: 2026
tags: [llm-serving, heterogeneous-gpu, model-routing, bayesian-optimization, cost-efficiency]
source_pdf: "[[d9d4f495e875a2e075a1a4a6e1b9770f.pdf]]"
source_md: "[[d9d4f495e875a2e075a1a4a6e1b9770f]]"
---

# BOUTE: Cost-Efficient LLM Serving with Heterogeneous LLMs and GPUs via Multi-Objective Bayesian Optimization (MLSys 2026)

> **一句话总结**：BOUTE 用多目标 Bayesian 优化 (MOBO) 联合优化「heterogeneous model routing（小模型/大模型）」和「heterogeneous GPU deployment（RTX 5090/H100）」，在同等成本下把 LLM serving 吞吐提升最多 157%（平均 59%），或在同等性能下降低 15%-61% 成本。

## 问题

LLM 推理成本高，两条正交省钱路线：
(A) **算法层**：model routing——简单 query 走小模型，难 query 走大模型（RouteLLM、HybridLLM）；
(B) **系统层**：混用 H100 + RTX 5090 等异构 GPU（ThunderServe、Helix）。

二者本质互补：不同模型偏好不同 GPU（小模型在 5090 上 1.5× 快于 H100，大模型在 H100 上 2× 快于 5090），但协同优化困难——路由策略决定各模型负载分布，进而影响最优部署；部署又反过来决定各模型的 latency 特性进而影响路由。孤立优化必得次优解。

## 核心方法

将联合调度建模为多目标约束优化：
$$
\min_{\tau, \mathbf{A}, \mathbf{P}} (L(\tau,\mathbf{A},\mathbf{P}), -Q(\tau))
$$
其中 τ 是路由阈值（threshold-based 路由），A 是 GPU 分配矩阵（model × GPU 类型），P 是并行策略（TP/PP/DP）。

**两阶段 MOBO 框架**：

- **Offline**：用 inference simulator 枚举 ⟨单 replica 配置, load⟩ 的 TP/PP 组合（剪枝内存不足和跨机 TP），按 Pareto (latency, cost) 骨架保留 10-20 个候选；再通过多选择背包问题 (multiple-choice knapsack) 聚合异构 GPU 候选。
- **Online**：GP 代理模型 + additive kernel `k_τ + k_c + φ k_×` 分别建模路由效应、部署效应、交互效应；constrained qNEHVI 获取函数做探索-利用平衡，迭代输出 Pareto-optimal 集。

## 关键结果

- 对比 SOTA：同成本 + 同质量要求下 latency 降 2.6×（平均 1.6×），吞吐升 1.9×（平均 1.6×）。
- 成本降 15%-61%（平均 38%）同时维持性能。
- 对比 Approach 1/2/3：单一 Llama3.1-70B 部署 25.6s → routing + uniform 28.2s → routing + optimal homo 20.5s → + heterogeneous GPU 17.1s（总降 33%）。
- 12 H100（$32.28/h）vs 6 RTX 5090 + 10 H100（$32.24/h）同预算下异构配置显著优。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、Data Parallelism、Model Routing、Bayesian Optimization
- **同类系统**：RouteLLM、HybridLLM、ThunderServe、Helix、Mélange
- **同会议**：[[MLSys-2026]]
