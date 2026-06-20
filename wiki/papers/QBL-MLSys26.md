---
type: paper
name: QBL
full_title: "Practical Adversarial Multi-Armed Bandits with Sublinear Runtime"
authors: [Kasper Overgaard Mortensen, Ama Bembua Bainson, Mathias Ravn Tversted, Kristoffer Strube Græm, Andrea Paudice, et al.]
venue: MLSys
year: 2026
tags: [multi-armed-bandit, database-tuning, index-selection, adversarial, combinatorial]
source_pdf: "[[9b8619251a19057cff70779273e95aa6.pdf]]"
source_md: "[[9b8619251a19057cff70779273e95aa6]]"
---

# Practical Adversarial Multi-Armed Bandits with Sublinear Runtime (MLSys 2026)

> **一句话总结**：在 k 可达数千、环境非平稳的 combinatorial adversarial MAB（动机来自 DB 自动 index tuning）中，观察到 O(k) 每轮采样是生产瓶颈；QBL 用 leader–follower priority queue + 有限权重更新实现 **O(m log k)** 每轮复杂度，并配套 Exp3.M Heap 等数值稳定子线性 Exp3 变体，在 benchmark 与 TPC-H index tuning 上同时优于时间与质量，但**无理论 regret 保证**。

## 问题与动机

Combinatorial adversarial MAB：每轮从 k 个 arm 中选大小为 m 的子集，reward 可任意变化（非平稳）。经典 Exp3/Exp3.M 等最优 regret 算法每轮 **O(k)**，在 automatic physical design tuning（index/materialized view 选择，k 上千）中，MAB 决策时间可能超过 index 构建本身。

作者 claim：工业场景更需要**可扩展 runtime** 与 empirical dynamic regret，而非仅理论 regret 界；现有非平稳方法还叠加 O(log T) 开销。

## 关键观察 / 隐含假设

- **观察 1：stationary index-tuning MAB 在非平稳 workload 下明显失效。** TPC-H 10GB 非平稳 workload 上，DBAbandit/HMAB 等 stationary 方法 dynamic regret 恶化（Fig. 1）。
  - **依赖假设**：index reward 定义（query 加速 vs creation cost）足以代表 DBA 真实目标；workload shift 频率与生产一致。
  - **可能失效场景**：reward 噪声极大、或 m 接近 k 时 combinatorial 探索空间退化。

- **观察 2：Exp3 的瓶颈是每轮全量权重→概率分布，而非仅权重更新。** sumheap + streaming LogSumExp 可把 Exp3.M Heap 降到 **O(m log k)**，且 long-horizon 数值稳定。
  - **依赖假设**：权重单调增（Exp3 特性）在 DT 长部署中成立；m ≪ k。
  - **可能失效场景**：m 很大时 Exp3.M Heap 相对 thresholded Exp3.M 无优势（论文承认）。

- **假设 1：QBL 的 leader 比较（局部 Lt vs 全局 Gt）+ 随机 demotion 足以在非平稳 adversarial 下保持竞争力，无需完整概率模型。**
  - **证据强度**：**中**——多 synthetic + DT benchmark 领先，但无 regret 证明；Tent Map 等环境 combinatorial 策略仍接近 random。

## 核心方法

**Exp3 工程化**：Algorithm 1 UpdateSumExp（log 域增量 LSE）、sumheap 采样（HeapUpdate/HeapSample）、Exp3.M Heap **O(m log k)**。

**QBL（Queuing Behind the Leader）**：维护 priority queue；每轮选 top-m arms。Leader arm 用局部均值 Lt 与全局加权 Gt 比较，适时 demotion（含随机 γ 防 adversarial 拖延）。Reward 归一化 + counter reset 引入隐式 discount。QBL.M 复杂度 **O(m log k)**。

应用：online index tuning——每 query 一轮，reward 为执行时间改进减 index 创建成本。

## 设计取舍

- **无理论 regret vs 实用 O(m log k)**：赢得大规模 k 上的可部署性，失去最优性证明与最坏情况保证。
- **Leader 启发式 vs Exp3 概率探索**：更新次数少、采样快，但 combinatorial + 单优 arm 环境（Tent Map）表现差。
- **单参数 γ**：易用，但环境异质性下未系统扫描敏感性。
- **边界条件**：k 大、m 小、长 horizon DT；单 arm 或需精确 combinatorial 探索时 QBL 非最优。

## 实验与结果

- Exp3 Fast / Exp3Light Fast 与原版 indistinguishable，且 k=10000 时明显优于线性 Exp3。
- QBL 在 Stochastic Constrained、Mod2 等环境 combinatorial/single-choice 上 empirical regret 与 runtime 双优。
- DB index tuning（TPC-H 等）上 QBL 在时间与 solution quality 上优于 Exp3 族与 FPL 等。
- 论文未给出与 RL-based DBA 的全面对比。

## Critical Analysis

### 论证链条

问题（O(k) 阻碍 DT）→ sumheap/QBL 设计 → benchmark 改进，工程链条闭合。但「无 regret 仍可工业采用」依赖 DT 评测，外推到其他 combinatorial bandit（图摘要等）证据有限。

### 假设压力测试

k 小或 m≈k 时 sublinear 优势消失；reward 延迟反馈（index 构建很慢）时 per-round 复杂度不再是主瓶颈；强非平稳下 leader 机制可能被操纵（论文用随机 demotion 缓解但未量化）。

### 实验可信度

Synthetic + DB benchmark 覆盖主要 claim；baseline 含 Exp3 工程强化版，较公平。缺生产 DBMS 端到端 A/B 与长期 drift 跟踪。

### 系统性缺陷

论文未讨论分布式 DBA、多表耦合 index 选择；在线 serving 路径未涉及。

## 局限与 Future Work

- **局限**：无 theoretical regret；QBL 在部分 combinatorial 环境接近 random；参数 γ 与 demotion 阈值敏感性未充分 ablation。
- **Future work**：在保持 O(m log k) 前提下证明 adaptive regret 界；与 learned cost model 结合；multi-tenant workload 下鲁棒性测量。

## 相关

- **相关概念**：[[Multi-Armed-Bandit]]
- **同类系统**：OpenTuner、DBAbandit
- **同会议**：[[MLSys-2026]]