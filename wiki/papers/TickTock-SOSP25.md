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

> **一句话总结**:用 [[Rust]] refinement-type verifier Flux 形式化验证生产微控制器 OS Tock 的进程隔离(ARMv7-M + 3 个 RISC-V 平台),重构出更简单的 granular MPU 抽象,发现 7 个隔离漏洞,验证时间从 5+ 分钟降到 30 秒。

## 问题

Tock 是被 Google Security Chip(GSC)、Microsoft Pluton 2 等安全关键系统部署的嵌入式 OS,用 Rust 写内核、MPU(Memory Protection Unit)硬件隔离用户进程。但 MCU 没 MMU,MPU 配置有 size/alignment 限制且要 per-process 切换,还要处理中断与 context switch 中的各种 race。之前已记录过多起隔离破坏 bug(CVE 级别)。

## 核心方法

三块贡献:

- **Granular MPU abstraction**:原 Tock 把进程内存布局和 MPU 硬件约束揉在一个 monolithic 抽象里,导致内核视图与硬件实际配置可能不一致,且产生大量易错 check。TickTock 解耦成"kernel 逻辑布局" + "MPU 硬件配置" + bridge logic,让二者始终一致。
- **Flux verification**:用 Flux(基于 SMT 的 Rust refinement type 检查器)对 MPU 配置代码、context switch 的 inline 汇编、中断 handler 做形式化证明,验证"进程只能访问自己的 code/stack/data/heap,别的都不能碰"。
- **FluxArm**:把 ARM 的 Architecture Specification Language (ASL) 提升到 Rust,用 Flux contract 定义 ARMv7-M 汇编的可执行 operational semantics,用来验证汇编中断 handler。
- 22K LOC Rust 源码,加了 3.5K LOC Flux annotation。

发现的 bug 包括:MPU subregion 可能与 kernel grant 区域重叠;context switch 的 inline 汇编漏了切 CPU mode(进程仍在 privileged 下运行,完全绕开 MPU);整数下溢导致 MPU 错误配置。

## 关键结果

- 发现 5 个 MPU 配置 bug + 2 个中断处理 bug(共 6 个能破坏隔离),已报给上游。
- Context switch 性能与原 Tock 相差 0.3% 以内。
- 验证时间:原 Tock 5+ 分钟 → TickTock <30 秒。
- 覆盖所有 ARMv7-M 平台 + 3 个 RISC-V 32-bit 平台。

## 相关

- **相关概念**:[[Formal-Verification]]、[[Rust]]、MPU、Refinement Types、[[seL4]]
- **同类系统**:Tock、seL4、CertiKOS
- **同会议**:[[SOSP-2025]]
