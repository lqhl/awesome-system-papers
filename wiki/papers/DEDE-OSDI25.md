---
type: paper
name: DEDE
full_title: "Decouple and Decompose: Scaling Resource Allocation with DeDe"
authors: [Zhiying Xu, Minlan Yu, Francis Y. Yan]
venue: OSDI
year: 2025
tags: [resource-allocation, optimization, admm, cluster-scheduling, traffic-engineering]
source_pdf: "[[osdi25-xu.pdf]]"
source_md: "[[osdi25-xu]]"
---

# Decouple and Decompose: Scaling Resource Allocation with DEDE (OSDI 2025)

> **一句话总结**：大规模 LP/MILP 资源分配（调度/TE/负载均衡）在 Gurobi 上需数十分钟；DEDE 发现多数目标可分离为 per-resource + per-demand 效用之和，用辅助变量 z 解耦约束后 ADMM 交替求解 n+m 个小问题，Ray 并行，质量优于 POP **5.3–12.6%**、速度 **2.2–7.6×**。

## 问题与动机

云调度、广域 TE、负载均衡等反复解百万变量 LP/MILP，商业求解器分钟到小时级，无法满足秒级 SLO。启发式/ML 牺牲质量或领域窄；POP 依赖「每 demand 只占少量资源」granular 假设，真实负载下质量下降。

## 关键观察 / 隐含假设

- **观察 1**：文献中绝大多数资源分配可写成 separable 结构：目标 Σ f_i(x_i*) + Σ g_j(x_*j)，每资源/每 demand 线性约束（表 1 调研）。
  - **依赖假设**：非 separable 问题需改写或不适配（§4 讨论局限）。
  - **可能失效场景**：强全局耦合约束（如单一总 cap 跨所有 pair）需额外技巧。
- **观察 2**：x_ij 同时出现在资源与 demand 约束导致无法直接分解；引入 z 副本 + x=z 后适合 ADMM 两块交替更新。
  - **依赖假设**：凸问题 ADMM 收敛；MILP 依赖经验收敛（论文引多篇非凸 ADMM 实践）。
  - **证据强度**：强——与 penalty/增广 Lagrangian 联合优化对比在 §7.3 ablation。
- **假设 1**：per-resource / per-demand 子问题可用现成求解器高效解（变量数 m 或 n 而非 nm）。
  - **可能失效场景**：单资源关联极多 demand 时子问题仍大。

## 核心方法

**Decouple**：x 与 z 分裂，资源约束在 x、需求约束在 z，x−z=0 进增广 Lagrangian。

**Decompose**：Lagrange 项可拆到每个 resource row / demand column，独立并行子问题。

**实现**：Python `pip install dede`，cvxpy 风格 API，Ray 真并行（非模拟）。

## 设计取舍

- **取舍 1**：迭代求解换单次 monolithic 最优性，需调 ρ 与停止准则。
- **取舍 2**：通用框架不嵌入领域启发式，依赖问题可 separabilize。
- **边界条件**：三任务：cluster scheduling、TE、load balancing。

## 实验与结果

- vs POP 最佳变体：scheduling 质量 **+7.3%**、**3.1×** 快；TE **+5.3%**、**7.6×**；LB **+12.6%**、**2.2×**。
- §7.3：joint x,z 优化劣于 ADMM 交替（验证 decouple 必要）。

## Critical Analysis

### 论证链条

大规模生产痛点 → 结构调研 → ADMM 分解 → 三领域双指标胜出，论证扎实。MILP 最优性为近似，需对照最终目标值与 Gurobi 时间上限实验（论文有质量对比叙述）。

### 假设压力测试

非 separable 扩展（耦合 budget）论文 §4 承认需改写。ADMM 迭代次数随规模增长是否稳定？整数解舍入后可行性论文应查 §7 细节。

### 实验可信度

POP 为强 relevant baseline；Gurobi 时间限制设置影响对比公平性需读者核对实验配置。

### 系统性缺陷

运维需维护 Ray 集群与 ρ 调参；论文未讨论 warm-start 与在线 demand 突变时的延迟 tail。

## 局限与 Future Work

- **局限 1**：非所有 MILP 可 separable 或 ADMM 收敛保证弱。
- **Future work 1**：与生产 scheduler 的 incremental update 联调。
- **Future work 2**：LLM inference GPU 异构调度实例的 separability 审计工具。

## 相关

- **同会议**：[[OSDI-2025]]