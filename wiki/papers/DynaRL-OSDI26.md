---
type: paper
name: DynaRL
full_title: "DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training"
authors: [Yuanqing Wang, Hao Lin, Junhao Hu, Chunyang Zhu, Quanlu Zhang, et al.]
venue: OSDI
year: 2026
tags: [reinforcement-learning, distributed-training, dynamic-scheduling, resource-migration]
source_pdf: "[[osdi26-wang-yuanqing.pdf]]"
source_md: "[[osdi26-wang-yuanqing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 大规模强化学习训练的灵活动态调度（OSDI 2026）

> **原题**：DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training

> **一句话总结**：DynaRL以动态hypergraph统一表示rollout、tool、reward和trainer，将GPU从过配组件迁往当前瓶颈；64/128-GPU reasoning/agentic RL相对RLinf/veRL/RLHFuse最高约1.98×，调度与迁移开销低于0.5%。

## 问题与动机

heavy-tailed rollout、multi-turn tool latency和随训练变化的component demand可浪费60% compute；静态GPU partition无法同时适应generation与training瓶颈转换。

## 关键观察 / 隐含假设

- RL pipeline的瓶颈随iteration变化，可由component utilization和queue持续观测。
- 模型/optimizer/communication context可细粒度迁移且不改变RL语义。
- 迁移收益需大于connection rebuild与state movement；阈值过小会振荡。

## 核心方法

central dynamic hypergraph记录component、data edge与resource；multi-level scheduler先定位bottleneck，再做GPU allocation/request priority。统一migration interface保存/恢复trainer或rollout context，context-aware router在拓扑变化时转发数据；利用率阈值与持续窗口抑制频繁重配。

## 实验与结果

- **设置**：64/128 GPUs、1.5B–32B models、math/agentic RL，对比RLinf、veRL和RLHFuse，以token throughput为指标（§7）。
- math reasoning速度提升1.27×–1.98×；相对RLHFuse为1.21×–1.42×。
- scheduler/trainer migration均低于0.5% E2E latency；参数区间内throughput距峰值约1.5%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| dynamic allocation提高RL throughput | 图 11、§7 | 64/128 GPU | 强 |
| migration overhead可控 | 图 14 | 所测模型/state | 强 |

## 批判性分析

### 论证链条

系统直接响应time-varying bottleneck，优于只优化初始placement；跨workload结果与migration breakdown吻合。

### 假设压力测试

极长tool call、网络故障或大optimizer state会使迁移来不及；利用率反馈滞后可能追逐过时瓶颈。

### 实验可信度

多模型/规模与强baseline较完整，但尚非超大生产cluster，sample efficiency与throughput等价性仍需长期验证。

## 局限与后续工作

- 联合RL convergence与system throughput。
- 加入故障、异构accelerator和uncertainty-aware control。

## 相关

- **相关概念**：[[Reinforcement-Learning]]、[[Dynamic-Scheduling]]、[[Resource-Migration]]
- **相关系统**：[[RLinf]]、[[veRL]]、[[RLHFuse]]
- **同会议**：[[OSDI-2026]]
