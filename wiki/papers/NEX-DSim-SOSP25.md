---
type: paper
name: NEX-DSim
full_title: "Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks"
authors: [Jiacheng Ma, Jonas Kaufmann, Emilien Guandalino, Rishabh Iyer, Thomas Bourgeat, George Candea]
venue: SOSP
year: 2025
tags: [simulation, hardware-accelerator, performance-modeling, co-design, gem5]
source_pdf: "[[3731569.3764825.pdf]]"
source_md: "[[3731569.3764825]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# NEX-DSim：加速硬件-软件栈的快速端到端性能仿真（SOSP 2025）

> **原题**：Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks

> **一句话总结**：全栈 cycle 模拟（[[gem5]]+RTL）模拟 1 秒执行需数小时；NEX 原生跑可用 CPU 软件、DSim 对加速器做 performance/function **di-simulation**（LPN + 功能轨），epoch 同步下比 SOTA 快 6–879×，模拟时间平均误差 7%、最坏 14%（CPU 不过载前提下）。

## 问题与动机

加速器普及使软硬件协同设计依赖 **full-stack performance simulation**，但传统方案对所有组件 cycle-accurate 建模，相对实时慢 **~10,000×**，迫使 batch-mode 开发。Systems developer 往往不需要 CPU 微架构级 trace，却继承了 microarchitect 工具的精度包袱。

## 关键观察 / 隐含假设

- **观察 1**：对 many accelerated stacks，host CPU 已可用，原生执行 + 仅在 MMIO/shared-memory/DMA 边界同步即可保持端到端性能精度。
  - **依赖假设**：加速器交互仅通过明确定义 MMIO/共享内存/DMA；不需建模 CPU 内存争用（lazy sync 明确忽略）。
  - **可能失效场景**：CPU underprovisioned 时误差上升；CPU 与 accelerator 争用 memory bandwidth 的工作负载被系统性低估。
- **观察 2**：加速器可拆成 **performance track**（LPN microarch 等价）与 **function track**（真实响应），对外与 RTL 模拟不可区分。
  - **依赖假设**：LPN 能捕获 pipeline/contention 等 performance-critical  aspect。
  - **可能失效场景**：novel accelerator 微架构需手工建 LPN；gate-level 现象被抽象掉。
- **观察 3**：开发者愿用粗粒度 trace（CPU↔accelerator 时间分配）换 orders-of-magnitude speedup。
  - **依赖假设**：use case 是 early co-design 与 bottleneck 定位，非 tape-out 前 sign-off。
  - **证据强度**：强。三个真实 stack 验证 + FPGA 对比（DL 栈平均 6% 误差）。

## 核心方法

**Minimality principle**：(1) 只模拟不可用组件；(2) 模拟时仅 cycle-accurate performance-critical 部分。

- **NEX**：eBPF/sched-ext epoch scheduler；ptrace+mprotect 拦截 accelerator 交互；eager/lazy/hybrid sync；DMA 专用 simulator 与加速器 lock-step。
- **DSim**：Latency Petri Net performance track + functional track；对外行为与 RTL 一致。
- 可独立或组合接入 gem5/RTL simulator（Table 1 模块化）。

三个 stack：deep learning、RPC serialization、JPEG decode。

## 设计取舍

- **速度 vs 可见性**：无详细 hardware trace；只有 coarse CPU/accelerator 时间线。
- **Lazy sync vs memory contention modeling**：原生 CPU 速度的前提。
- **LPN 建模成本 vs RTL**：快但需人工抽象。
- **Hybrid interrupt sync**：周期性 sync 开销 vs interrupt 频率自适应。

## 实验与结果

- vs state-of-the-art full-stack：**6×–879×** speedup。
- Simulated time 平均误差 **7%**，最坏 **14%**（CPU 不过载）。
- DL stack vs FPGA testbed：平均 **6%**、最坏 **12%**。
- 模拟 1 秒执行降至 **秒级** wall-clock，支持 interactive what-if。

## 批判性分析

### 论证链条

「developer 不需全 cycle visibility」→ minimalist sync + di-simulation → 三 stack 精度/速度，链条在 evaluated stacks 闭合。未证明对所有 accelerator class（network、FPGA fabric、multi-accelerator contention）普遍适用。

### 假设压力测试

- CPU underprovisioned 时论文承认误差恶化——这是重要 fragility。
- 忽略 CPU/accelerator memory contention 对 data-heavy pipeline 可能系统性乐观。
- LPN 构建门槛可能抵消 interactive 收益——论文未量化建模 person-hours。

### 实验可信度

- 三 diverse stacks + FPGA validation 较好。
- 879× 峰值需看具体配置；读者应关注典型而非极端倍数。
- 与 gem5-only/RTL-only 的 fair config 文档在论文 §6，独立复现需开源 artifact（已发布）。

### 系统性缺陷

- 不适合 sign-off 级 verification；论文明确 slower simulator 仍必要。
- Multi-accelerator 拓扑扩展、OS 页迁移等长时间现象评估有限。
- NEX ptrace/mprotect 对 driver 的侵入性（mprotect 补丁）生产不可用——仅开发工具。

## 局限与后续工作

- **局限**：无 CPU memory contention；CPU 过载误差大；粗 trace；LPN 建模成本。
- **Future work**：可选 CPU memory tracing 模式；自动化 LPN 提取；更多 accelerator 模板库。

## 相关

- **相关概念**：[[gem5]]、Hardware-Software-Co-Design、Latency-Petri-Net、Full-Stack-Simulation
- **同类系统**：Simbricks、gem5、Wisconsin Wind Tunnel
- **同会议**：[[SOSP-2025]]
