---
type: paper
name: Rex
full_title: "Rex: Closing the language-verifier gap with safe and usable kernel extensions"
authors: [Jinghao Jia, Ruowen Qin, Milo Craun, Egor Lukiyanov, Ayush Bansal, et al.]
venue: ATC
year: 2025
tags: [ebpf, kernel-extensions, rust, language-based-safety, verifier]
source_pdf: "[[atc2025-jia.pdf]]"
source_md: "[[atc2025-jia]]"
---

# Rex: Closing the language-verifier gap with safe and usable kernel extensions (ATC 2025)

> **一句话总结**：用 safe Rust + 轻量 runtime 替代 eBPF 的 in-kernel verifier，闭合 language-verifier gap，在 BMC 等大型 extension 上达到与 eBPF 同等性能但代码更干净，无需为 verifier 做 workaround。

## 问题

eBPF 已从简单 packet filter 演化成大型程序（存储、网络、调度），靠 in-kernel verifier 静态符号执行验证安全。作者分析 Cilium、Aya、Katran 等项目的 72 个 commit，发现 verifier 错误 reject 安全程序的几大原因：(1) 符号执行 scalability 限制（程序拆成多个 tail call）；(2) 编译器（LLVM）和 verifier 期望不一致，得用 inline assembly 阻止某些优化；(3) verifier 自身 bug，不同 kernel 版本得 workaround。

作者把这种「开发者按 high-level 语言契约写、verifier 却基于 bytecode 不同的契约」的 mismatch 称为 **language-verifier gap**。这导致 eBPF 用大型程序难写难维护——开发者要懂 verifier 内部实现细节。

## 核心方法

**核心思想**：直接基于 safe language 提供的 language-based safety + 轻量 extralingual runtime 来替代静态 verifier，从而闭合 gap。Linux 已经支持 Rust，且 Rust 的 ownership/borrow 提供天然的内存/资源安全。

设计要点：

- **强制 safe Rust**：Rex extension 只允许 safe Rust 子集（编译器 flag 禁 unsafe、unstable feature、SIMD、float、`mem::forget`），no_std 环境
- **kernel crate**：用 safe Rust wrapper 包住已有 eBPF helper function 接口（约 200 个），提供 type-safe binding，extension 只能通过这个接口与 kernel 交互
- **extralingual runtime**：用于静态分析难保证的属性——Rust panic 时安全 stack unwinding + 资源清理；watchdog timer 强制 termination；运行时检查 kernel stack 用量
- **复用 eBPF hook point**，假设无嵌套 extension（嵌套在 vanilla eBPF 也不安全）
- **TCB**：Rust toolchain + Rex kernel crate + Rex runtime（比 eBPF verifier 更大但生态成熟）

不追求 unprivileged 用例（与现代 eBPF 实践对齐，因为 Spectre 等 transient execution 攻击难靠静态分析防）。深度细节回 [[atc2025-jia]]。

## 关键结果

- 实测 BMC（BPF Memcached Cache）：在 eBPF 下需拆成 7 个 program 通过 tail call 串接以满足 verifier 限制；Rex 实现更干净更简单
- 性能与 eBPF 持平——可用性提升不带来性能损失
- Rex 项目开源：https://github.com/rex-rs

## 相关

- **相关概念**：[[eBPF]]、[[Kernel-Extensions]]、[[Rust-for-Linux]]、[[Language-Based-Safety]]
- **同类系统**：KFlex（用 SFI 扩展 eBPF 表达力，但仍依赖 verifier）
- **同会议**：[[ATC-2025]]
