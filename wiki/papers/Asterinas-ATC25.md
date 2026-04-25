---
type: paper
name: Asterinas
full_title: "Asterinas: A Linux ABI-Compatible, Rust-Based Framekernel OS with a Small and Sound TCB"
authors: [Yuke Peng, Hongliang Tian, Junyang Zhang, Ruihan Li, Chengjun Chen, et al.]
venue: ATC
year: 2025
tags: [os, rust, framekernel, memory-safety, tcb]
source_pdf: "[[atc2025-peng-yuke.pdf]]"
source_md: "[[atc2025-peng-yuke]]"
---

# Asterinas: A Linux ABI-Compatible, Rust-Based Framekernel OS with a Small and Sound TCB (ATC 2025)

> **一句话总结**：提出 framekernel 架构（单地址空间但内核内做语言级权限分离），让所有 OS service / driver 都用 safe Rust 写、unsafe 仅集中在 OSTD 框架内；Linux ABI 兼容、支持 210+ syscalls，性能与 Linux 持平，TCB 仅 14% 代码量（Tock 43.8% / Theseus 62.4% / RedLeaf 66.1%）。

## 问题

Rust 内核要靠 unsafe 处理低层硬件，但现有 Rust OS 都用得太多：Linux RFL 55% crate 含 unsafe、Tock 93%、RedLeaf 62%、Theseus 32%。RFL 还要桥接 Linux 旧 C API（19K LoC + 112K LoC pending），导致 TCB 巨大且无法解决 sleep-in-atomic、mutex guard forget 这类老问题。Tock/RedLeaf/Theseus 等 clean-slate Rust OS 在 driver 里仍频繁裸写 unsafe（MMIO、DMA、I/O port、raw buffer）。

## 核心方法

**Framekernel** 把内核分成两部分：privileged OS framework（仅其内可用 unsafe，类似 microkernel TCB）+ de-privileged OS services（包括 driver，全部 safe Rust）。所有组件单地址空间共享、通过函数调用通信（无 IPC 开销）。

- **OSTD（OS framework）**：暴露 small expressive API：
  - 用户交互：`UserMode`/`UserContext`（仅暴露非敏感 RFLAGS bits）/`VmSpace`
  - 内核逻辑：`SpinLock/Rcu/Mutex/WaitQueue/CpuLocal`、`LinkedList/RbTree`
  - 外设交互：`IrqLine/IoMem/IoPort/DmaCoherent/DmaStream`
  - 物理内存：`Frame<M>`/`Segment<M>`，并提出 **Untyped Memory** (`UFrame/USegment`) 仅允许 POD copy 来安全处理 MMIO/DMA 这类外部可改的内存
- **10 条 Safety Invariants**：从 kernel/user CPU 状态、敏感物理页、IOMMU 限制设备 DMA 范围，到 task 同时只在一核运行、HeapSlot 不能 outlive Slab、size/alignment check
- **Safe Policy Injection**：通过 trait 把 task scheduler / frame allocator / slab allocator 这些"会越长越大"的策略组件移出 TCB，让用户用 safe Rust 注入复杂调度（如 Linux CFS）和 SLAB；OSTD 用 metadata system + is_running flag 等机制保证策略 bug 不破坏内存安全。
- **KernMiri**：retrofitted Miri 用于 Rust OS 的 UB 检测。

详细 invariant 与 OSTD API 见 [[atc2025-peng-yuke]]。

## 关键结果

- LMbench 几何均值 normalized = 1.08（Asterinas 略快于 Linux 5.15）
- Nginx 1.17×、Redis 1.31×、SQLite 0.85×（norm vs Linux）
- TCB 只占 14.0% 代码量，对比 Tock 43.8% / Theseus 62.4% / RedLeaf 66.1%
- 100K+ LoC Rust，50+ contributor，开发 3 年
- 支持 210+ Linux syscall、Ext2/exFAT/OverlayFS/RamFS、TCP/UDP/Unix/Netlink、Virtio Block/Net/Vsock、x86-64 (tier-1) + RISC-V (tier-2)

## 相关

- **相关概念**：[[Memory-Safety]]、[[Rust]]、[[TCB]]、[[Microkernel]]、[[Untyped-Memory]]、[[Driver-Safety]]
- **同类系统**：[[Tock]]、[[RedLeaf]]、[[Theseus]]、Rust-for-Linux
- **同会议**：[[ATC-2025]]
