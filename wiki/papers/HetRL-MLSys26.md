---
type: paper
name: HetRL
full_title: "HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments"
authors: [Yongjun He, Shuai Zhang, Jiading Gai, Xiyuan Zhang, Boran Han, "et al."]
venue: MLSys
year: 2026
tags: [rlhf, heterogeneous-gpu, scheduling, ppo, distributed-training]
source_pdf: "[[7f39f8317fbdb1988ef4c628eba02591.pdf]]"
source_md: "[[7f39f8317fbdb1988ef4c628eba02591]]"
---

# HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments (MLSys 2026)

> **一句话总结**：把 PPO/GRPO 的 RL 工作流（多模型多任务、复杂依赖）部署到跨地区、跨型号的异构 GPU 集群，用 5-level 搜索框架 + nested Successive Halving + 遗传算法决 partition 和 assignment，20K GPU-hour 评估下比 SOTA（verl、OpenRLHF）平均 **3.17× 吞吐**、最高 **9.17×**。

## 问题

现代 RL post-training 是 LLM 推理能力和对齐的核心手段（DeepSeek-R1、Qwen3、Llama 系列都这么做），但算力需求爆炸式增长。同时各地数据中心里有大量 mid-range / 前代 GPU 闲置，单区域高端同构 GPU 短缺——**把 RL 部署到跨区域异构 GPU 集群是自然选择**。

但现有方案都不适配：

- **SOTA RL 系统**（verl、OpenRLHF、RLHFuse）**只针对同构集群**，搜索空间里没 heterogeneity
- **StreamRL** 把 GPU 分两组（actor generation vs 其他任务），但组内仍需同构
- 把 LLM 训练/serving 的 heterogeneity-aware scheduler 搬来 RL 不现实：这些方法只针对 single model/task，需要 100-1000s 才能找近优 plan；RL 有 4 个 model + 6 个 task，直接拼接需要 $1000 \times$ 搜索时间

RL workflow（PPO）复杂性：actor/reference/reward/critic 四模型，actor generation（memory-bound、KV cache）、三个 inference、actor/critic training（compute-bound、gradient + optimizer state）六任务；任务间计算/内存/通信特征差异巨大。

## 核心方法

**问题形式化**：在 NP-hard 的约束联合优化里找 partitioning strategy $\rho$（怎么切）和 assignment strategy $\sigma$（切片放哪个 GPU），最小化每 iteration 执行时间，约束 GPU 内存。

**5 级搜索框架**（粗→细）：

| Level | 决策 |
|---|---|
| 1 | Task grouping：哪些 task 共用 GPU 组（模型 colocate） |
| 2 | 粗粒度 GPU 分配：每个 task group 分多少 GPU（不指定具体） |
| 3 | 中粒度 GPU 分配：task group → 具体 GPU 集合 |
| 4 | Intra-model 并行：TP/PP/DP 切法，task → tasklets |
| 5 | 细粒度 GPU 分配：tasklet → 具体 GPU |

Levels 1/4 决定 $\rho$，Levels 2/3/5 决定 $\sigma$。

**Cost model**：按 PPO 同步版本建，把 6 个 task 的 cost 按依赖关系聚合（$\Phi$ 函数，系数 $\eta$ 控制并行度）。每 task 按其类型（generation / inference / training）有不同的 subcost：compute、HBM、TP/PP/DP comm、pipeline bubble 等。异构设备的算力、memory、HBM 带宽、link latency/bandwidth 作为 input。

**Nested Successive Halving (SHA) + 遗传算法**：
- Level 1 的 task grouping 和 Level 2 的 GPU grouping 作为 multi-armed bandit 的 arm，cost model 给的估计时间作 loss
- 每轮给各 arm 起始预算 $b_m$，用 GA 生成 $b_{m,n}$ 个候选 plan 评估，保留 best half 然后预算翻倍——典型 SHA 节奏
- 下 level（3-5）用 GA 生成具体候选 plan
- **Nested** 表现为：Level 1 round 结束时每个 task grouping 保留最好的一半 GPU grouping 带入下一轮，而不是只留唯一最优或全部
- SHA 有最优 arm 识别的理论保证

**系统实现**：基于 verl，额外 3K 行代码构建 scheduler / profiler / execution engine，扩展 fine-grained resource assignment 和 load balancing。

## 关键结果

- **20K GPU-hour** 大规模评估，跨多种 workload 和 heterogeneous setup
- 对比 SOTA（verl、OpenRLHF 等 homogeneous 系统）：**最高 9.17×**，**平均 3.17×** 吞吐量
- 搜索时间显著优于 naive combination（后者需 $1000 \times$ 搜索时间）
- 同时 handle sync PPO、async RL 等多种 workflow variant

## 相关

- **相关概念**：[[RLHF]]、[[PPO]]、GRPO、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、Data-Parallelism、Successive-Halving
- **同类系统**：verl、OpenRLHF、StreamRL、RLHFuse
- **同会议**：[[MLSys-2026]]
