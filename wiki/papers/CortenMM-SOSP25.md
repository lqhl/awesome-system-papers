---
type: paper
name: CortenMM
full_title: "CortenMM: Efficient Memory Management with Strong Correctness Guarantees"
authors: [Junyang Zhang, Xiangcan Xu, Yonghao Zou, Zhe Tang, Xinyi Wan, et al.]
venue: SOSP
year: 2025
tags: [memory-management, virtual-memory, formal-verification, concurrency, operating-system]
source_pdf: "[[3731569.3764836.pdf]]"
source_md: "[[3731569.3764836]]"
---

# CortenMM: Efficient Memory Management with Strong Correctness Guarantees (SOSP 2025)

> **一句话总结**:在 [[Asterinas]] OS 中 clean-slate 重构内存管理,去掉 VMA 这一层软件抽象只留硬件页表,用事务接口 + 两种可扩展锁协议 (rw / adv-RCU) 并对核心并发代码做形式化验证,在 384 核机器上比 Linux MM 快 1.2×-26×。

## 问题

现代内存管理系统在性能和正确性上同时陷入困境。Linux 沿袭自 1986 年 SunOS 的两层抽象设计——软件层的 VMA 树(现为 maple tree)加硬件层的页表——为了可移植性和高级语义(on-demand paging、CoW)而生,但两层数据结构差异巨大,同步极其复杂。Linux 为此引入四种锁(mmap_lock、VMA lock、粗粒度页表锁、细粒度 PTE 锁),官方锁规则文档长达 5000 字。

即便如此,VMA 仍是多线程应用的可扩展性瓶颈(Android app startup、Google Fibers 线程创建、TCP 零拷贝),并且 2023 年 4 月 Linux 引入细粒度 VMA 锁后,两年内出现 10 个 CVE,其中 9 个可致系统崩溃。学术界如 RadixVM、NrOS 尝试改进但功能不全或扩展性仍不理想。

## 核心方法

**关键 insight**:现代主流 ISA (x86/ARM/RISC-V) 已统一采用多级 radix 页表,软件层抽象不再必要。CortenMM 彻底去掉软件层,只保留硬件 MMU 抽象,用 C 宏/语言特性处理 ISA 微差,为每个页表项关联一个 auxiliary memory region 存储高级语义所需的最小元数据(如 CoW 标志)。

架构有三个关键设计:

1. **事务接口**:唯一的 MMU 编程入口。一个事务接受一个虚拟地址区间 + 一个基本操作序列(map/unmap 等),原子地应用到页表上。这极大简化了并发推理。
2. **两种锁协议**:CortenMM_rw 基于读写锁,简单;CortenMM_adv 基于 [[RCU]] 的 lock-free 页表遍历,性能更高。没有软件层抽象后,不存在 VMA 这一额外争用点。
3. **形式化验证**:得益于设计简洁,作者用定理证明形式化验证了事务接口中基本操作的功能正确性,以及两种锁协议的正确性。其它组件用 safe Rust,保证 memory-safe、data-race-free,且只能通过已验证的事务接口访问 MMU。

CortenMM 是与工业界合作从零构建生产 OS [[Asterinas]] 的一部分,支持 x86/ARM/RISC-V,定位为 Linux 在 [[TEE]]、数据中心、移动端的 drop-in 替代。

## 关键结果

- 在 384 核机器上,形式化验证过的 CortenMM 比 Linux 快 **1.2×-26×**(真实应用)
- 支持与 Linux 几乎等同的高级语义:on-demand paging、CoW、page swapping、reverse mapping、mmaped file、huge page(仅 NUMA policy 未实现)
- 形式化验证覆盖并发代码核心路径,提供 Linux MM 和 RadixVM/NrOS 都缺失的强并发正确性保证
- 代码已开源:github.com/TELOS-syslab/CortenMM-Artifact

## 相关

- **相关概念**:[[RCU]]、[[Page-Table]]、[[TLB]]、[[Formal-Verification]]、[[Copy-on-Write]]、[[Readers-Writer-Lock]]
- **相关系统**:[[Asterinas]]、Linux、RadixVM、NrOS、Barrelfish、Bonsai
- **同会议**:[[SOSP-2025]]
