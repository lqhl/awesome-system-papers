---
type: paper
name: Xerxes
full_title: "Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework"
authors: [Yuda An, Shushu Yi, Bo Mao, Qiao Li, Mingzhe Zhang, et al.]
venue: FAST
year: 2026
tags: [cxl, simulator, interconnect, coherence, pcie]
source_pdf: "[[fast2026-an.pdf]]"
source_md: "[[fast2026-an]]"
---

# Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework (FAST 2026)

> **一句话总结**：从零构建的 CXL 3.1 仿真框架，用 graph-based interconnect layer + peer-centric device layer 首次准确模拟 PBR + DMC + PCIe 6.0 全双工，在真实 CXL hardware 上验证误差 0.1-10%，比 NUMA emulation/MESS/CXLMemSim/gem5-garnet 都更高保真。

## 问题

[[CXL]] 3.0/3.1 引入了 Port-Based Routing (PBR)、Device-Managed Coherence (DMC)、PCIe 6.0 等关键特性，把 CXL 从树状 host-centric 拓扑推向 rack-scale peer-to-peer fabric（最多 4096 endpoint）。但目前没有支持这些新特性的硬件，已有仿真工具又都失效：

- **NUMA emulation**：协议级 mismatch，且 CPU socket 数量有限，无法到 4096
- **gem5/GPGPUsim**：host-centric、tree hierarchy、centralized coherence engine，与 PBR/DMC 不兼容
- **BookSim/Garnet**：网络仿真精确但不懂 memory 语义和 coherence 协议
- **MESS/CXLMemSim**：行为级 latency-bandwidth 曲线注入，只能 reproduce 已知硬件，无法 predict 新拓扑/新 coherence policy

## 核心方法

Xerxes 三个设计原则：modular（interconnect 与 device 解耦）、graph-based connectivity（任意 non-tree 拓扑）、peer-centric device model（host 和 device 都是主动 agent）。两层架构：

1. **Interconnect layer**：用 graph 表示拓扑，提供默认最短路由，switch 实现完整 PBR 转发表。Bus 组件建模 PCIe 6.0 全双工 + 带宽分配单元，可配置 half-duplex 与 turnaround。
2. **Device layer**：所有 component 抽象成 Requester（含 request queue、address translation、cache coherence unit），DMC 通过 device-side inclusive snoop filter（DCOH）实现，支持 BISnp/BIRsp 反向失效流程，victim 策略可插拔。

集成 [[gem5]]、DRAMsim3、SimpleSSD：用 Xerxes Wrapper 把 gem5 `MemCtrl` 包装成 UpInterface/DownInterface 收发 Xerxes packet，复用 gem5 event queue 与 SLICC 缓存失效。开源在 ChaseLab-PKU/Xerxes。

利用 Xerxes 探索三方面 design space：(1) 拓扑（chain/tree/ring/spine-leaf/fully-connected）；(2) DMC snoop filter victim policy + InvBlk 长度；(3) PCIe 全双工。

## 关键结果

- 与真实 CXL hardware 对比：idle latency、loaded latency、bandwidth 误差 0.1-10%；loaded-latency 平均误差 4.3%，远好于 MESS (9.3%)、CXLMemSim (16.6%)
- SPEC CPU2017 mcf/gcc CXL overhead 误差最低 0.7%（gem5-MESS 高达 28.3%）
- Simulation overhead 仅比 vanilla gem5 高 2%（gem5-garnet 高 22.5%）
- 拓扑结论：tree/chain 在 root 形成瓶颈，spine-leaf 提升真实负载吞吐至 3.63×
- DMC 结论：snoop filter 因为大多 miss，**LIFO/MRU 比 LRU 减少 16% invalidation**；InvBlk = 2 是最佳点，更长反而因 cache lookup 开销和带宽竞争收益递减

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]、[[Port-Based-Routing]]、[[Device-Managed-Coherence]]、[[Snoop-Filter]]
- **同类系统**：MESS、CXLMemSim、[[gem5]]、Garnet、DRAMsim3、SimpleSSD
- **同会议**：[[FAST-2026]]
