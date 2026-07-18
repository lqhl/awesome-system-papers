---
type: paper
name: TickTock
full_title: "TickTock: Verified Isolation in a Production Embedded OS"
authors: [Vivien Rindisbacher, Evan Johnson, Nico Lehmann, Tyler Potyondy, Pat Pannuto, Stefan Savage]
venue: SOSP
year: 2025
tags: [formal-verification, embedded-os, rust, mpu, isolation]
source_pdf: "[[3731569.3764856.pdf]]"
source_md: "[[3731569.3764856]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# TickTock: Verified Isolation in a Production Embedded OS (SOSP 2025)

> **一句话总结**：Flux 验证 Tock process-memory isolation，并以 granular abstraction 降低验证时间。它发现 5 个 MPU 与 2 个 interrupt bugs，其中 **6** 个破坏 isolation；kernel verification 从 **5m19s** 降至 **36s**，全项目含 interrupts 约 **3 min**。

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

**指标、基线与边界**：verification time、context-switch CPU cycles、functional differential tests；TickTock vs upstream Tock；checked kernel/interrupt scope 或 ARM ROT13 two-app benchmark（§6）。

- monolithic kernel：660 functions、**5m19s**；granular kernel：791 functions、**36s**；全项目含 interrupts 约 **3 min**（§6.3，Fig.15）。
- ARM ROT13 two-app test：Tock **32,640** cycles、TickTock **32,740**，**0.3%** overhead；RISC-V 未做性能 benchmark（§6.2）。
- 五个 MPU + 两个 interrupt bugs，**6** 个 break isolation；剩余为 underflow crash DoS（§1、§2.2）。
- 21 applications 在双方运行；5 个 output differences 为 memory-layout tests/sensor data 的预期差异（§6.1）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| granular redesign 降低 checked kernel 验证时间 | 5m19s→36s；whole project~3min | Flux checked code、660/791 functions；非“under30s full project” | §6.3，Fig.15 | high |
| context-switch 结果是 ARM microbenchmark | 32640 vs32740 cycles、.3% | upstream ROT13 two-app ARM test；非 RISC-V | §6.2 | high |
| bugs 有明确类型与安全影响 | 5 MPU+2 interrupt，6 isolation break、1 DoS | original Tock verification | §1、§2.2 | high |
| 某些 granular operation 改善但 setup_mpu 回退 | allocate_grant 641 vs1290.32，setup_mpu97.86 vs90.55 | 21 ARM tests、3 runs；非全局 speedup | §6.2，Fig.14 | high |
| functional compatibility 测试有限 | 21 apps；5 expected differences | ARM NRF52840dk + RISC-V QEMU subsets | §6.1 | high |

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
