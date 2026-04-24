---
type: paper
name: NEST
full_title: "NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning"
authors: [Irene Wang, Vishnu Varma Venkata, Arvind Krishnamurthy, Divya Mahajan]
venue: MLSys
year: 2026
tags: [device-placement, parallelism, distributed-training, dynamic-programming, ai-infra]
source_pdf: "[[37693cfc748049e45d87b8c7d8b9aacd.pdf]]"
source_md: "[[37693cfc748049e45d87b8c7d8b9aacd]]"
---

# NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning (MLSys 2026)

> **一句话总结**：用 level-wise 网络抽象 + 集成 memory modeling 的新型结构化动态规划把 tensor/pipeline/data/expert/sequence/context/ZeRO 七种并行组合起来同时优化，比 Alpa/TopoOpt/Mist 最多 2.43× 高吞吐，可扩展到 1000+ GPU。

## 问题

分布式训练同时涉及 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、data parallelism、[[Expert-Parallelism]]、sequence/context parallelism、ZeRO 等并行维度，每种都带独特 collective 通信和 memory trade-off。

真实数据中心网络是**分层且常被超卖**的（DGX SuperPOD NVLink+IB、MAIA 分层 RDMA、TPUv4 torus），不同层级 latency/bandwidth 差距巨大。

已有 placement 框架的盲点：
- **TopoOpt**：MCMC 随机搜索，无最优性保证，扩展性差。
- **Alpa**：DP+ILP，但假设扁平 2D mesh，post-hoc check memory，被迫 over-sharding，>64 GPU 崩。
- **Mist**：MILP + brute-force，memory 处理更好但 network 被降为次要约束，大规模慢。

## 核心方法

**1. 并行策略分层**

- **SUB-GRAPH** 策略（TP/EP/SP/CP）：改层内计算，离线 profile 成本，不扩 DP 状态空间。
- **GRAPH-GLOBAL** 策略（PP/DP/ZeRO）：重塑层间边界，由 DP 显式搜索。

两层正交化避免组合爆炸。

**2. Level-Wise Network Abstraction**

网络异构导致 DP 反向推进时「上游 forward cost 未知」，破坏 optimal substructure。解法：

- 把网络离散成 3–5 个 level（intra-node / intra-rack / inter-rack），每个 level 一套 profile 延迟。
- DP state 加上 level 维度 $dp^{te}[l][D][k][s]$，作为「deferred forward cost」。
- 对 Spine-Leaf/Fat-Tree/NVSwitch/Torus 都能通用，由物理链路映射成 level 成本矩阵。

**3. 集成 memory modeling**

- 用 Torch.fx symbolic trace 每层的 weights/grad/opt-states/activations/stashed data。
- 按 pipeline schedule（1F1B 或 GPipe）建模 stashed 数据随 stage index 线性变化。
- 两种 recomputation 策略共同评估，ZeRO 各 stage 也在 DP 里 adaptive 选择。
- memory 作为 DP 约束（硬剪枝），而非 post-hoc fix，模型与 compile 结果 7% 以内。

**4. 统一的 DP 公式**

递推同时最小化 compute 延迟、collective latency，受 memory 上界约束，给出可证最优的 placement + 并行策略组合。

## 关键结果

- **吞吐**：相比 manual / MCMC / SOTA DP baseline（Alpa、Mist）在 GPT3-175B、Llama3-70B、Mixtral-8×7B 上最多 **2.43× 更高**。
- **可扩展性**：顺利跑到 1000+ GPU（Alpa 在 ≈64 GPU 就崩）。
- **memory 可行性**：在 memory 受限场景仍能找出最优 placement，自适应启用 ZeRO stage 解锁原本不可行的配置。
- **topology 覆盖**：oversubscribed tree、fat-tree、spine-leaf、torus 都验证。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[RDMA]]
- **同类系统**：Alpa、TopoOpt、Mist、Aceso、Megatron-LM、DeepSpeed、NeMo、PipeDream
- **同会议**：[[MLSys-2026]]
