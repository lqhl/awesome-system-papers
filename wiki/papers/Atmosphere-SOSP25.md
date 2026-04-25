---
type: paper
name: Atmosphere
full_title: "Atmosphere: Practical Verified Kernels with Rust and Verus"
authors: [Xiangdong Chen, Zhaofeng Li, Jerry Zhang, Vikram Narayanan, Anton Burtsev]
venue: SOSP
year: 2025
tags: [formal-verification, microkernel, rust, verus, systems-programming]
source_pdf: "[[3731569.3764821.pdf]]"
source_md: "[[3731569.3764821]]"
---

# Atmosphere: Practical Verified Kernels with Rust and Verus (SOSP 2025)

> **一句话总结**：用 Rust + Verus 在 **1.5 人年**内完成一个功能完整的 mixed-criticality 微内核 Atmosphere 的形式化验证（6K 行代码 / 20.1K 行证明，proof-to-code 3.32:1），验证本身 <20 秒完成——证明 SMT-based verifier 对低层系统代码已经实用。

## 问题

传统 formally verified kernel 代价高昂：seL4 需 11 人年 + 9 人年工具链，CertiKOS、Hyper-V 等同级投入。"push-button"验证工具（Hyperkernel 等）虽自动化但对 kernel 结构做大量简化假设（如要求所有路径有限、`open()` 必须让用户指定 fd 号）。SMT-based verifier 遇到 kernel 里大量 **递归数据结构 + 非线性指针 + 复杂生命周期** 时证明复杂度迅速失控。

目标：证明这类现代 verifier（Verus = Rust + 线性类型 + permission-based separation logic + SMT/Z3）在真实 feature-rich 系统上已经实用。

## 核心方法

Atmosphere 是 multi-CPU（big lock）微内核，支持进程/线程/IPC/虚拟地址空间/IOMMU/container（隔离组），是 mixed-criticality 场景的 **separation kernel**。关键设计：

- **Pointer-centric design**：主动拥抱 raw、非线性指针——像写 unsafe C 一样实现 kernel 数据结构（内部存储代替指针、反向指针支持 O(1) 链表删除等），由 Verus 的 **permission pointer** 来事后证其正确
- **Flat permission storage**：把所有子对象（页表每一个节点、系统中所有线程、树的所有节点）的 permission 集中存在子系统顶层的 flat map——给 verifier 一个"全局视角"，从而能用非递归方式描述无限/递归数据结构的性质，且结构性（无环、反向指针正确）和非结构性（增/删线程）论证能分开做
- **Manual memory management**：彻底放弃 Rust borrow checker 管理内核对象生命周期，显式 alloc/dealloc（像 C），但用 proof 建立 memory safety 和 leak freedom——这对证明 non-interference（一个 domain 不能耗光整机内存）至关重要
- **Refinement proof**：定义顶层 abstract spec（如 `syscall_mmap_spec` 描述 mmap 后抽象 state 变化），证具体实现是其 refinement；不依赖 Rust 标准库的任何 unverified 类型（Vec、Box、Arc 等）

## 关键结果

- 总耗时 **<1.5 物理年 / 2.5 人年**（verified 部分 1.5 人年，其余 1 人年写 boot/driver/benchmark）
- **6K 行可执行代码 + 20.1K 行证明**（14.3K spec + 5.8K proof hints），proof-to-code **3.32:1**（比此前 seL4 等低）
- 验证在现代 laptop 上 **<20 秒** 完成——比编译都快，可做"交互式"开发循环
- 证明 mixed-criticality container 间可建立自定义 non-interference（完全隔离但可通过 verified 进程共享服务）
- 展示了"不依赖 Rust 标准库的 unverified 指针类型"的完整实用路径

## 相关

- **相关概念**：Formal verification、Microkernel、Separation logic、Linear types
- **同类系统**：seL4、CertiKOS、Hyperkernel、IronFleet、SeKVM、BlueRock
- **同会议**：[[SOSP-2025]]
