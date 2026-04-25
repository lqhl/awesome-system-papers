---
type: paper
name: Tock
full_title: "Tock: From Research to Securing 10 Million Computers"
authors: [Leon Schuermann, Brad Campbell, Branden Ghena, Philip Levis, Amit Levy, Pat Pannuto]
venue: SOSP
year: 2025
tags: [embedded-os, rust, retrospective, root-of-trust, isolation]
source_pdf: "[[3731569.3764828.pdf]]"
source_md: "[[3731569.3764828]]"
---

# Tock: From Research to Securing 10 Million Computers (SOSP 2025)

> **一句话总结**:10 年回顾论文——Rust 写的嵌入式 OS Tock 从「64KB 安全多程序」研究原型演化成部署在千万级笔记本和服务器 root-of-trust、FIDO 安全密钥、航天/车载产品中的开源 OS,论文反思 Rust 异步安全、interior mutability、capsule 隔离、heapless grants 等设计决策,以及由学术界主导的 open-source OS 工程路径。

## 问题

多数研究系统止步于 paper,即便开源也常被分化成 startup 或私有分支。Tock 如何在学术主导下持续演化 10 年,并走进 FIDO 密钥、Chromebook Ti50、数据中心 BMC、车载/航天等高安全场景?什么是对的设计,什么是代价?

## 核心方法

**原始设计(Signpost 城市感知)**:
- 32-bit Cortex-M、~100KB RAM、无虚拟内存,但有硬件内存保护
- **Capsules**:Rust type-safety 提供的编译期隔离,用作 kernel 扩展,拒绝 unsafe;进程用硬件 MPU 隔离,支持多语言(C / Lua / Rust)应用
- **Heapless kernel + Grants**:内核不用全局 heap,动态分配都从进程 memory region 切出去,应用间无 fate-sharing
- **异步一切**:事件驱动单栈内核 + 异步系统调用(allow-buffer、subscribe-callback、command、yield 四步序列),为了 ultra-low-power 场景最大化 sleep

**演化过程中的痛点**:
- Rust 所有权与循环引用(FS ↔ storage driver 互相持有引用)冲突 → Tock 选择 **interior mutability** 而非 message passing
- 异步 syscall 在 root-of-trust 场景是累赘(无省电压力 + 顺序状态机业务),早期采纳者 Oxide 因此弃 Tock 自写同步 OS Hubris;Ti50 fork 了 Tock 加 blocking command。教训:后续加了新 yield 变体来让同步库容易写
- RISC-V LLVM codegen 不成熟,4 次 syscall 开销被 Ti50 优化成 1 次
- DMA 硬件不尊重 Rust 类型 → 专门设计安全抽象
- 整个 10 年 kernel 中 `unsafe` 使用量保持稳定,只出现在必须的 MMIO、进程边界、capability 处(见论文 Figure 5)

**适配 root-of-trust**:加入正式威胁模型(应用数据对 kernel 保密)、更强隔离保证、更多 CPU 架构、更好 Rust userspace 支持。

## 关键结果

- 部署在千万级设备:Google OpenSK FIDO 密钥、Ti50(Chromebook 信任根)、数据中心服务器 root-of-trust、车载/航天/可穿戴
- 开源项目由学术界主导仍能支撑生产用户
- `unsafe` 代码量多年未显著增长,尽管功能大幅扩展
- 提供对 Rust OS 设计的第一手经验:异步对 root-of-trust 是坑、interior mutability 是必须的、异步 ABI 重设计不可避免
- 学术/工业张力管理:向上游贡献 vs 产品压力 vs novelty pressure

## 相关

- **相关概念**:[[Rust]]、[[Embedded-OS]]、[[Root-of-Trust]]、[[Capsules]]、[[Interior-Mutability]]
- **同类系统**:Hubris(Oxide)、FreeRTOS、Zephyr、TinyOS
- **相关理念**:Spin(Modula-3)、Singularity(Sing#)
- **同会议**:[[SOSP-2025]]
