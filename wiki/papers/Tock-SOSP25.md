---
type: paper
name: Tock
full_title: "Tock: From Research to Securing 10 Million Computers"
authors: [Leon Schuermann, Brad Campbell, Branden Ghena, Philip Levis, Amit Levy, Pat Pannuto]
venue: SOSP
year: 2025
tags: [embedded-os, rust, root-of-trust, experience-report, security]
source_pdf: "[[3731569.3764828.pdf]]"
source_md: "[[3731569.3764828]]"
---

# Tock: From Research to Securing 10 Million Computers (SOSP 2025)

> **一句话总结**：十年 experience report：[[Tock]] 从 64kB 安全 multiprogramming 研究 OS 演进到数据中心 RoT、千万台笔记本安全启动与汽车/航天部署；核心观察是 Rust 类型 + 硬件 MPU 隔离几乎零开销，但 async syscall/DMA 与 Rust 同步内存模型冲突迫使多次 ABI 重设计。

## 问题与动机

本文非典型「新机制」论文，而是 **系统演化与 adoption** 复盘：Tock 如何在 academia 主导的开源社区下，从 urban sensing 平台走到 securing **10M+** computers，同时仍是 OS 研究平台。问题：哪些技术选择促成 adoption？Rust 作为 OS 语言的真实代价是什么？学术 stewardship 与产业需求如何平衡？

## 关键观察 / 隐含假设

- **观察 1**：嵌入式安全需 kernel/app 硬件隔离，但传统嵌入式 OS 单保护域；Tock 用 MPU + Rust 类型实现 least privilege，**CPU/state 开销近零**。
  - **依赖假设**：目标平台有 primitive memory protection（Cortex-M 等）；应用可接受 Tock syscall ABI。
  - **可能失效场景**：无 MPU 的极简 MCU 或需 Linux 兼容 API 的场景不适合。
- **观察 2**：RoT/TPM 类需求把用户从 sensing 社区换成 security hardware 厂商——推动 syscall ABI、capsule 模型、多架构支持重构。
  - **依赖假设**：学术维护者能响应产业 urgent product timeline 仍保持 upstream 贡献。
  - **可能失效场景**：product fork 不回流导致 ecosystem 碎片化（论文讨论 tension 但未量化）。
- **观察 3**：Rust 内存模型绑定 threaded/sync 语义，与 **event-driven 单栈 kernel + async syscall** 根本冲突，需 redesign 才能 sound。
  - **依赖假设**：unsafe 可限制在 MMIO/process boundary 等少数点且长期稳定（Fig.5）。
  - **证据强度**：强。有十年演化与 deployment 佐证，但是 experience 非 controlled experiment。

## 核心方法

（经验总结而非单点算法）

- **Original design**：multiprogramming on ~100kB RAM；capsule 驱动模型；Rust kernel。
- **Evolution**：新 syscall ABI、kernel loop、capsule abstraction；formal threat model；多 ISA（x86/RISC-V/ARM）与更强 isolation。
- **Type-based guarantees**：calling convention 防常见 driver bug；跨层 memory sharing；hardware virtualization 泛化；无动态分配。
- **Unsafe containment**：核心 unsafe 行数稳定 despite features 增长。

## 设计取舍

- **Academic stewardship vs startup 移交**：保持研究平台属性，但面临 incentive 冲突。
- **Rust soundness vs embedded async reality**：大改 ABI 换长期安全。
- **Security-focused scope vs general-purpose OS**：不追求 Linux 替代。
- **Legacy C userspace 支持**：扩 adoption，但增加 FFI 边界风险。

## 实验与结果

- 部署规模：**10M+** computers（笔记本安全启动、数据中心 RoT 等）。
- 领域：automotive、space、wearable、hardware security token。
- Unsafe LOC 稳定（Fig.5）；多轮 ABI/隔离增强支撑产业用例。
- 无传统 microbenchmark 表格——贡献在 adoption 与 engineering lesson。

## Critical Analysis

### 论证链条

「Rust+MPU 隔离 → RoT 市场需求 → 社区演化 → 大规模部署」是 narrative case study，非可 falsify 的单变量实验。读者应将其作为 **qualitative evidence**，而非性能或安全量化 superiority proof。

### 假设压力测试

- 10M 部署数字依赖产业伙伴统计，独立审计未述。
- Rust 编译器/LLVM 变更对 verified subset 的长期影响未 longitudinal 量化。
- 与 Zephyr/TinyOS/TF-M 等的安全/footprint 对比缺少同期 benchmark。

### 实验可信度

- 作为 experience report，可信度高在「教训真实」、低在「可推广公式」。
- Threat model formalization 是加分项，但覆盖范围论文仅概述。

### 系统性缺陷

- 论文未提供统一 failure incident 统计或 CVE 对比。
- 学术团队维护的产业关键路径的 bus factor 风险未讨论。
- DMA/FFI 边界仍是长期 fragility（§5 承认）。

## 局限与 Future Work

- **局限**：非新算法论文；缺 rigorous benchmark；部署数字难独立验证。
- **Future work**：更成熟的 async Rust OS 抽象；产业-学术 governance 模式文档化；formal verification 扩大。

## 相关

- **相关概念**：[[Tock]]、Embedded-OS、Root-of-Trust、Rust、MPU
- **同类系统**：Zephyr、seL4 embedded、TF-M、RIOT
- **同会议**：[[SOSP-2025]]