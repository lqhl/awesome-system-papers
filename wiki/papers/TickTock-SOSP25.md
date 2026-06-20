---
type: paper
name: TickTock
full_title: "TickTock: Verified Isolation in a Production Embedded OS"
authors: [Vivien Rindisbacher, Evan Johnson, Nico Lehmann, Tyler Potyondy, Pat Pannuto, et al.]
venue: SOSP
year: 2025
tags: [formal-verification, embedded-os, rust, mpu, isolation]
source_pdf: "[[3731569.3764856.pdf]]"
source_md: "[[3731569.3764856]]"
---

# TickTock: Verified Isolation in a Production Embedded OS (SOSP 2025)

> **一句话总结**：Flux 验证 Tock MPU 隔离，重构 granular abstraction，发现 **7** 个隔离漏洞，验证从 5+ 分钟降至 **30 秒**，context switch 性能与 Tock 持平（0.3% 内）。

## 问题与动机

[[Tock]] 部署于 Google GSC、Microsoft Pluton 2 等安全芯片：Rust 内核 + MPU 隔离用户进程。无 MMU，MPU 配置/对齐约束复杂，中断与 context switch 易出错——历史已有 isolation CVE，验证原始内核又慢（5+ 分钟）且 specification 臃肿。

## 关键观察 / 隐含假设

- **观察 1**：Tock 原 monolithic process 抽象把 memory layout 与 hardware MPU 约束缠在一起，导致 spec 大、实现易漏检查（grant region 重叠等）。
  - **依赖假设**：解耦后 kernel 与 hardware enforcement 始终一致。
  - **可能失效场景**：新 SoC MPU 语义扩展需重证。
  - **证据强度**：强——Flux 证不出 postcondition 直接发现 bug。
- **观察 2**：ARMv7-M interrupt/上下文切换可用 lifted ASL 操作语义 + Flux spec 验证 assembly 路径。
  - **依赖假设**：ASL .lift 完整覆盖相关指令语义。
  - **可能失效场景**：vendor-specific MPU 变体未覆盖的 platform。
  - **证据强度**：中——ARMv7-M + 3×RISC-V 声明，非全架构。
- **假设 1**：3.5K LOC Flux annotation / 22K LOC Rust 是可接受的验证税。
  - **证据强度**：强——half-minute verify time。

## 核心方法

**TickTock**（Tock fork）：

1. **Granular MPU abstraction**：分离 process layout 与 hardware config
2. **Flux verification**：MPU 配置、memory alloc、interrupt/asm、context switch
3. 发现 **7** 新 bug（**6** 破 isolation）

## 设计取舍

- **取舍 1**：verification-guided 重设计换更安全更简单内核，upstream 合并成本。
- **取舍 2**：仅证明 isolation，不验证 liveness/availability。
- **边界条件**：MPU-based MCU，非 MMU Linux。

## 实验与结果

- 验证时间：5+ min → **<30s**
- Context switch：within **0.3%** of Tock
- **7** bugs found，**6** break isolation
- ARMv7-M + 3 RISC-V platforms

## Critical Analysis

### 论证链条

「生产 embedded OS 需要可验证隔离 → 原抽象太难证 → 重构」路径典范，与 seL4 故事呼应但工具链现代（Flux/refinement types）。

### 假设压力测试

- Capsule（内核内 driver）隔离仍靠 Rust type safety，未 form verify。
- 新 syscall 添加是否需重证全流程？维护负担随内核演进增长。
- RISC-V 覆盖是否同等深度于 ARM？

### 实验可信度

Bug 发现是硬证据。性能 microbenchmark 可信。缺独立第三方复现 verification 报告。

### 系统性缺陷

论文未讨论：verified kernel 与 unverified capsule 组合的攻击面；功耗/代码 size 回归；认证流程（Common Criteria）路径。

## 局限与 Future Work

- **局限 1**：isolation only，无 full functional correctness。
- **局限 2**：架构覆盖有限。
- **Future work 1**：verify capsule API boundary 或自动生成 syscall wrapper spec。

## 相关

- **相关概念**：MPU、process isolation、formal verification、[[Rust]]
- **同类系统**：Tock、seL4、[[CHERIoT-RTOS]]
- **同会议**：[[SOSP-2025]]