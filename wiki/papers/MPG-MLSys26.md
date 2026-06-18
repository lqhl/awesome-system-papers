---
type: paper
name: MPG
full_title: "Machine Learning Fleet Efficiency: Improving TPU Systems at Scale with ML Productivity Goodput"
authors: [Arissa Wongpanich, Tayo Oguntebi, Jose Baiocchi Paredes, Yu Emma Wang, Phitchaya Mangpo Phothilimthana, "et al."]
venue: MLSys
year: 2026
tags: [fleet-efficiency, tpu, goodput, scheduling, profiling]
source_pdf: "[[d1fe173d08e959397adf34b1d77e88d7.pdf]]"
source_md: "[[d1fe173d08e959397adf34b1d77e88d7]]"
---

# Machine Learning Fleet Efficiency: Improving TPU Systems at Scale with ML Productivity Goodput (MLSys 2026)

> **一句话总结**：Google 提出 ML Productivity Goodput (MPG) 把 TPU 万卡 fleet 效率分解为 Scheduling/Runtime/Program 三层 goodput，各 job size 的 scheduling goodput 经调优后均 >95%，并定位 compiler、runtime、调度全栈瓶颈。

## 问题

ML fleet（AI hypercomputer）有硬件异构、workload 异构、软硬件协同设计三重挑战。传统 datacenter 指标（occupancy、TOPS/W）把「busy」当「productive」，无法刻画 bulk-synchronous 分布式训练「所有 chip 同时可用才前进」的特性，也难解释单 job 优化与 fleet 聚合效率的权衡。

## 核心方法

**MPG** = Scheduling Goodput (SG) × Runtime Goodput (RG) × Program Goodput (PG)：

- **SG**：分子为所有 worker 同时可用的 allocated chip-time，分母为 fleet chip-time capacity。衡量调度层碎片、拓扑不匹配、多 chip 协调延迟。
- **RG**：分子为已 checkpoint 保存的有效前进 chip-time，分母为 SG 分子。覆盖初始化、编译、数据喂入、checkpoint 等 runtime 开销。
- **PG**：用未优化 HLO 图算理想 FLOPs 时间作分子、实际执行时间作分母，避免传统 per-op roofline 惩罚 fusion 等正确全局优化。

按 accelerator 类型、模型架构、训练/ serving 阶段分段分析，指导全栈优化。

## 关键结果

- 各 job size 的 **scheduling goodput >95%**（经 preemption 与 defragmentation 调优）。
- Runtime 改进：框架现代化、异步 checkpointing。
- Program 层：通信-计算 overlap 等 compiler 优化。
- 方法论 vendor-agnostic，适用于任意异构 ML fleet。
- 案例：Google 生产 TPU 基础设施数千加速器。

## 相关

- **相关概念**：roofline model、XLA、Pathways runtime、fleet scheduling、goodput
- **同类系统**：[[XPROF-MLSys26|XPROF]]、warehouse-scale computing metrics
- **同会议**：[[MLSys-2026]]