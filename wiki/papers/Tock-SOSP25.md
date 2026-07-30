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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Tock：从研究到保护 1000 万台计算机（SOSP 2025）

> **原题**：Tock: From Research to Securing 10 Million Computers

> **一句话总结**：十年 experience report：[[Tock]] 从面向约 100kB RAM、少于 1MB nonvolatile storage 的 32-bit Cortex-M 目标演进到多类部署。作者称项目已有 “tens of millions” active devices；这是项目状态陈述，非独立审计或性能 benchmark。异步 API 与 Rust 跨调用所有权不匹配，促成 ABI 重设计。

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

**指标、基线与边界**：deployment scale、target resource envelope、interface steps、project timeline；Tock old/new ABI 或项目阶段；十年经验报告、作者项目状态，不是受控吞吐/延迟 benchmark（§2–7）。

- 项目状态为 “tens of millions of active devices”；部署范围包括 RoT servers、laptops、automotive、space 等（§7，Fig.1）。
- 原始目标 envelope：32-bit Cortex-M、约 **100kB RAM**、少于 **1MB** executable nonvolatile storage（§2）。
- Ti50 fork 将同步等待从 subscribe→command→yield→unsubscribe 的 **4** calls 改为 **1** blocking call；这是其 RISC-V/code-space 情形的接口复杂度经验（§3.2）。
- Tock 2.0 的 ABI 由旧 allow/subscribe 改为 swapping；官方 v2 从 early-2020 到 mid-2021，约 **2.5 years**（§3.3，§6）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| 大规模部署数字是项目状态而非性能试验 | tens of millions active devices | 十年项目状态、非独立审计 | §7，Fig.1 | high |
| 资源数字是目标 envelope 而非实际 footprint | 32-bit、100kB RAM、<1MB storage | original target platforms | §2 | high |
| blocking syscall 的收益限于 Ti50 场景 | 4 calls→1 call | Ti50 RISC-V、code-space/time pressure；其他 adopter仍需 async | §3.2 | high |
| Rust userspace soundness 需要破坏性 ABI 重构 | allow/subscribe switching、core loop rewrite | old ABI ownership issue；v1/v2未并存以省 code size | §3.3 | high |
| 长周期重构与项目治理有关但无因果对照 | academics超过3/4；约2.5-year v2 timeline | 作者经验总结，非实验因果 | §6 | high |

## 批判性分析

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

## 局限与后续工作

- **局限**：非新算法论文；缺 rigorous benchmark；部署数字难独立验证。
- **Future work**：更成熟的 async Rust OS 抽象；产业-学术 governance 模式文档化；formal verification 扩大。

## 相关

- **相关概念**：[[Tock]]、Embedded-OS、Root-of-Trust、Rust、MPU
- **同类系统**：Zephyr、seL4 embedded、TF-M、RIOT
- **同会议**：[[SOSP-2025]]
