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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# COpter: Efficient Large-Scale Resource-Allocation via Continual Optimization (SOSP 2025)

> **一句话总结**：把 round-based LP/MILP 资源分配视为慢演化序列，用增量约束矩阵 + proximal-point solver + 轻量整数化，solver 时间比 CPLEX 快 **57–83×**，比 POP 分区同时提升质量与 **1.5–30×** 速度。

## 问题与动机

GPU 集群调度、shard 负载均衡、WAN TE 等每 1–5 分钟解一次 LP/MILP。25k GPU Sia policy：编译 CVXPY 模型 median **226s**、求解仅 11s；round 内 85%→15% 能在 1 分钟内完成。POP 分区可并行但质量-时间 tradeoff 差（POP-32 快但差，POP-4 好但超时）。

关键 insight：连续 round 间 **<0.01%** 变量变值、仅几 % add/remove，黑盒重解浪费先前计算。

## 关键观察 / 隐含假设

- **观察 1**：资源分配最优解在相邻 round 间 ℓ2 距离小，适合 warm-start——但 Simplex/IP 的 warm-start 实际收益不可控。
  - **依赖假设**：2–5 分钟 round 内集群状态慢变（少故障、少新 job）。
  - **可能失效场景**：大规模故障、突发流量导致约束矩阵剧变；first-order method 收敛到可行精度慢。
  - **证据强度**：强——24h 25k GPU trace，<0.01% 变量变化。
- **观察 2**：MILP 时间主要在 integerization（branch-and-cut），LP relaxation 解往往已接近最优。
  - **依赖假设**：问题特定 rounding/heuristic 可恢复可行整数解且 MIP gap 可接受。
  - **可能失效场景**：强耦合整数约束（如复杂 affinity）使 heuristic 失效。
  - **证据强度**：中——三 domain 验证，heuristic 失败 fallback 未详述。
- **假设 1**：增量 differential update 接口可避免每轮重建千万级非零 constraint matrix。
  - **证据强度**：强——编译 dominant cost 有实测。

## 核心方法

**Continual optimization** 三件套：
1. Differential problem representation（增量改约束/变量）
2. Proximal-point method（factorization-free，可证明利用 prior iterate）
3. Lightweight MILP integerization heuristics（绕过指数 branch-and-cut）

## 设计取舍

- **取舍 1**：定制 solver 换通用 CPLEX/Gurobi 鲁棒性——新约束类型需手工扩展。
- **取舍 2**：heuristic 整数解可能 suboptimal，依赖 application 容忍度。
- **边界条件**：可表述为 LP/MILP 的 RA 问题；非凸或 stochastic 不适用。

## 实验与结果

- GPU scheduling (Sia)、shard LB、WAN TE 三域
- Sia trace simulation 中，10k/25k GPU 的平均 JCT 为 0.36 h，对 LP* 的 0.35 h；p99 solve time 为 6.5/40.3 s，对 LP* 的 233.4/2277.4 s（§5.1，Table 1）。
- shard LB 中，COpter 相对 LP-Relaxed 的 end-to-end speedup 为约 2.8×（§5.2）。
- ASN bimodal TE 中，COpter 少于 1 分钟完成，相对 POP 为 30× speedup、1.5% 更多 allocated flow（§5.3，Fig. 11）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| COpter 在 Sia trace 中保留接近 LP* 的质量并降低 tail solve time | 10k/25k GPU：JCT 0.36 h 对 LP* 0.35 h，p99 6.5/40.3 s 对 233.4/2277.4 s（§5.1，Table 1） | 60 s round、7 GPU type、trace-driven 24 h；LP* 是 LP relaxation + shim，不是 exact MILP | high |
| 相邻 round 的解在 trace 中稳定 | 25k-GPU Sia trace 中少于 0.01% variables change，只有少量变量增删（§2.2，Fig. 2） | 单个 24 h simulation trace，不覆盖故障或 burst | high |
| COpter 加快 shard load balancing | 相对 LP-Relaxed 的 end-to-end speedup 约 2.8×（§5.2） | 2048 shard/256 server、synthetic Zipf load；Exact 每题耗时数小时而未纳入 | medium |
| COpter 加快 ASN traffic engineering 并提高分配 flow | 少于 1 min，对 POP 为 30× speedup、1.5% 更多 flow（§5.3，Fig. 11） | synthetic bimodal traffic、10% demand perturbation；LP-All 在 ASN 超过 24 h/round 而未比较 | high |
| continual-optimization 的组成部分有可测贡献 | custom solver 5×、differential update 3.5×、warm start 1.5×，总计 24×（§5.4，Fig. 12） | 10k-GPU Sia LP relaxation、1 min round；不含 MILP integerization | high |

## Critical Analysis

### 论证链条

「round 独立建模 vs 慢演化现实」的 mismatch 是清晰 observation；三 bottleneck 与三 innovation 一一对应，闭合好。

### 假设压力测试

- 100k GPU（论文 Introduction 提及）外推时 incremental update 是否仍 O(小变化)？
- Heuristic integerization 最坏 MIP gap 未系统报告。
- 与 Meta RAS hourly optimization 等 production 系统的集成 friction 未讨论。

### 实验可信度

真实 trace + 商业 solver baseline 公平性较好。三 domain 增强泛化 claim。缺 online A/B 对 job completion time 的影响。

### 系统性缺陷

论文未讨论：solver 失败/不可行时 fallback；多 tenant fairness 约束变化下的 correctness；分布式 parallel solve。

## 局限与 Future Work

- **局限 1**：绑定特定 RA  formulation 工程，非通用 MILP solver。
- **局限 2**：强突变 workload 下 continual 优势减弱。
- **Future work 1**：auto-detect「突变 round」并 fallback 全量重解的 hybrid 策略。

## 相关

- **相关概念**：linear programming、MILP、GPU scheduling、traffic engineering
- **同类系统**：POP、Sia scheduler、Google OR-Tools
- **同会议**：[[SOSP-2025]]
