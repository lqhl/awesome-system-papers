---
type: paper
name: Weave
full_title: "Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training"
authors: [Tianyuan Wu, Lunxi Cao, Yining Wei, Wei Gao, Yuheng Zhao, et al.]
venue: OSDI
year: 2026
tags: [reinforcement-learning, gpu-scheduling, disaggregation]
source_pdf: "[[osdi26-wu-tianyuan.pdf]]"
source_md: "[[osdi26-wu-tianyuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向解耦式 RL 后训练的高效协同调度
> **原题**：Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training

## 问题与动机

on-policy RL 后训练把 rollout 与训练放到异构 GPU 池后，一个作业的阶段依赖会令两侧交替空闲。单作业优化不能消除跨作业的互补气泡，通用 GPU multiplexing 又无法处理模型状态与长达 135 s 的切换开销。

## 关键观察 / 隐含假设

- 多个作业的 rollout/training 阶段可以在统计上互补。
- 模型驻留 host memory 后，重配置成本可被控制在可调度范围。
- 假设作业阶段时长可估计且允许协同执行。

## 核心方法

[[Weave]] 构造 co-execution group；组间用随机规划选择互补作业，组内用最优 round-robin 排序，并以 host-memory residency 避免频繁完整装载。它把 job-level pipeline 变成跨作业的资源填缝问题。

## 实验与结果

在 328 张 H20 rollout GPU 与 328 张 H800 training GPU 的测试床上，Weave 相对标准解耦方案成本效率提高 1.84×，相对共置基线提高 1.38×，且达到 100% SLO attainment（§7，图 11）。边界是同步 on-policy、双 GPU 池的后训练负载。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 跨作业调度可填补阶段气泡 | 大规模异构集群成本效率提升 1.84× | §7 | 强 |
| 性能收益未牺牲作业目标 | 评测报告 100% SLO attainment | 图 11 | 强 |

## 批判性分析

### 论证链条
阶段依赖造成空闲，跨作业互补提供机会，分层调度再处理组合爆炸，设计与瓶颈对应清楚。

### 假设压力测试
阶段强抖动、off-policy 或模型无法放入 host memory 时，分组和驻留假设会受压。

### 实验可信度
数百 GPU 的真实规模很有说服力；仍需长期多租户 trace 验证预测误差与公平性。

## 局限与后续工作

- 后续可支持动态到达、抢占代价学习，以及 rollout、reward、training 多于两阶段的资源拓扑。

## 相关

- [[OSDI-2026]]
- [[Reinforcement-Learning]]
- [[GPU-Scheduling]]
