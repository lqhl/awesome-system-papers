---
type: paper
name: RLinf
full_title: "RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation"
authors: [Chao Yu, Yuanqing Wang, Zhen Guo, Hao Lin, Si Xu, et al.]
venue: OSDI
year: 2026
tags: [reinforcement-learning, distributed-training, scheduling, embodied-ai, llm]
source_pdf: "[[osdi26-yu-chao.pdf]]"
source_md: "[[osdi26-yu-chao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 以宏观到微观流变换实现灵活高效的大规模强化学习（OSDI 2026）

> **原题**：RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation

> **一句话总结**：RLinf把易组合的RL workflow沿time/resource维度自动拆成micro flows，再以context switching、elastic pipeline与profile-guided search重组执行；reasoning/embodied RL端到端throughput比SOTA提高1.07×–2.43×。

## 问题与动机

RL包含generation、reward/critic、training、tools与simulator，memory、parallelism和动态性差异巨大。固定collocation受长response barrier，完全disaggregation又因资源静态切分而imbalance；同一模式无法覆盖reasoning与embodied RL。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

M2Flow从macro DAG生成temporal/spatial decomposition，估算critical stage与pipeline bottleneck；scheduler以实际device profile搜索collocate/disaggregate/microbatch plan。worker可在同进程切换model role/state，并按需求建立[[NCCL|NCCL]]/Gloo/MPI连接；elastic pipeline监控持续15%偏差后重规划。

## 实验与结果

- GRPO/Qwen reasoning相对veRL/Slime提高1.07×–1.70%。
- embodied LIBERO等任务提高1.05×–2.43%，相对其他execution strategy最高1.87×。
- planner在8→1,024 GPUs耗时7×10^-4秒至5.98秒，开源完整系统。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

“flexibility是效率前提”对异构RL成立，统一flow abstraction比为每算法硬编码好。profile prediction面对response-length/nonstationary policy会失准，context switch的state movement可能抵消收益；throughput提升不证明sample efficiency或训练语义完全一致。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 联合system throughput与RL convergence/sample efficiency评测。
- 对failure/restart、dynamic environment与异构GPU/NPUs测试。
- online uncertainty-aware replan，避免15%阈值振荡。

## 相关

- **相关概念**：[[Reinforcement-Learning]]、[[Pipeline-Parallelism]]、[[Resource-Scheduling]]、[[GRPO]]
- **相关系统**：[[veRL]]、[[Slime]]
- **同会议**：[[OSDI-2026]]
