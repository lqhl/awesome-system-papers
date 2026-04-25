---
type: paper
name: NEX+DSim
full_title: "Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks"
authors: [Jiacheng Ma, Jonas Kaufmann, Emilien Guandalino, Rishabh Iyer, Thomas Bourgeat, George Candea]
venue: SOSP
year: 2025
tags: [simulation, hardware-accelerator, performance-modeling, co-design, ebpf]
source_pdf: "[[3731569.3764825.pdf]]"
source_md: "[[3731569.3764825]]"
---

# Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks (SOSP 2025)

> **一句话总结**:对加速器软硬件栈的端到端性能模拟——软件原生执行 + 加速器 di-simulation(性能 track 用 Latency Petri Net,功能 track 独立做),通过 [[eBPF]] 调度器维持虚拟时钟同步,在三个加速栈(深度学习、RPC 序列化、JPEG 解码)上比 SOTA 全栈模拟器快 6-879×,平均误差 7%,最坏 14%,让模拟从批处理(几小时)变成交互式(几秒)。

## 问题

随着硬件加速器(ML、视频、压缩、加密、基础设施卸载)普及,软硬件协同设计者需要全栈性能模拟,但 [[gem5]] + RTL simulator 这类工具模拟 1 秒执行要几小时(10,000× slowdown),把开发卡回了 1960 年代「打孔卡 + 批处理」模式。根源是所有组件都在 cycle-level 精度上模拟,但 systems developer 往往不需要 CPU 微架构层面的可见性。

## 核心方法

**Minimality principle**:(1) 只模拟不可用的组件,其他原生跑;(2) 对不得不模拟的组件,只 cycle-accurate 模拟性能关键部分。基于此设计两个模块:

**NEX (Native-Execution Orchestrator)**:让原生执行软件和模拟加速器共存并严格同步。
- NEX scheduler 用 Linux [[eBPF]] + sched-ext 实现 epoch-based 调度(EBS),在 epoch 边界控制线程执行,每个 epoch 让应用线程执行 epoch 时长的虚拟时间
- NEX runtime 用 ptrace + mprotect 拦截应用对 MMIO / shared memory 的访问,仅在真正发生交互时才 lazy-synchronize 加速器模拟
- 支持 eager / lazy / hybrid 三种同步,hybrid 支持中断
- 额外提供 CompressT / SlipStream / JumpT 三种「时间扭曲」原语做 what-if 分析

**DSim (Di-Simulator)**:把加速器模拟分解成两个解耦 track:
- **Performance track**:基于 [[LPN]](Latency Petri Net)抽象,只建模流水、并行、背压等性能关键行为,不做 cycle-by-cycle 信号翻转
- **Functionality track**:标准功能仿真,配合 zero-cost DMA 在不影响虚拟时间的前提下交换数据
- 两 track 偶尔同步以正确打 DMA 时间戳

NEX 和 DSim 可独立使用,能与 gem5 / 专有 RTL simulator 通过标准接口搭配。

## 关键结果

- 三个加速栈(DL、RPC 序列化、JPEG 解码)上 6× - 879× 加速 vs SOTA 全栈模拟
- 模拟时间误差:平均 7%,最坏 14%(CPU 核不 underprovision 时)
- DL 栈对 FPGA 实机:平均误差 6%,最坏 12%
- 模拟时间从小时量级降到秒量级,开发者可交互式迭代设计
- 开源

代价:丢失了 cycle-level 硬件执行 trace,只能给 coarse-grained 跨 CPU / 加速器的 cycle 分布,但对大多数 system-level 开发场景足够。

## 相关

- **相关概念**:[[Latency-Petri-Net]]、[[eBPF]]、[[Full-Stack-Simulation]]
- **同类系统**:[[gem5]]、Simbricks、Verilator、Wisconsin Wind Tunnel
- **同会议**:[[SOSP-2025]]
