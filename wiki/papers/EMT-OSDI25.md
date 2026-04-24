---
type: paper
name: EMT
full_title: "EMT: An OS Framework for New Memory Translation Architectures"
authors: [Siyuan Chai, Jiyuan Zhang, Jongyul Kim, Alan Wang, Fan Chung, et al.]
venue: OSDI
year: 2025
tags: [operating-systems, memory-management, page-tables, linux, mmu]
source_pdf: "[[osdi25-chai-siyuan.pdf]]"
source_md: "[[osdi25-chai-siyuan]]"
---

# EMT: An OS Framework for New Memory Translation Architectures (OSDI 2025)

> **一句话总结**：EMT 给 Linux 补一个架构中立的 memory translation 框架，让 ECPT、FPT 等新 MMU 架构无需重写架构无关代码就能在 Linux 上跑起来，overhead < 0.5%。

## 问题

TB 级内存、CXL memory expander、ML/graph 等 weak-locality 工作负载让 TLB miss 越来越贵，地址翻译已经成为主要瓶颈（nested translation 可占执行时间 50%+）。学术界提出了很多新 MMU 架构：ECPT（Elastic Cuckoo Page Table，哈希并行查 PTE）、FPT（Flattened Page Table，合并 L3/L4 与 L1/L2）、各种 flattened/range/hybrid 方案。

但这些方案几乎没有在 commodity OS 上落地过。原因：Linux 的内存管理代码**硬编码**了 radix-tree 假设（L4→L3→L2→L1→page 的指针迭代、按 9-bit 切位、pmd_none_or_clear_bad 等 overloaded 语义等），散布在架构无关模块里。加一个 L5 就要改 23 个文件 715 行；换成 hash table 架构基本等于重写。现有评估只能用性能模型估计或 trace-driven 仿真，假设 OS 开销跨架构不变——本文证明这个假设错得很大。

Linux 没有像 VFS 那样的可扩展 translation 接口；Mach/BSD 的 pmap 接口又太高层，不支持 Linux 所需的「直接操作 PTE」式优化（比如 range batching + 细粒度锁）。

## 核心方法

EMT 给 Linux 加一个「translation 子系统的 VFS」——架构无关模块通过抽象接口访问 translation 信息，所有硬件细节封装在 MMU driver 里。API 组织在三个 object-oriented 原语上：

- **Translation object**（tobj）：一组 VA→PA mapping 和元数据的抽象；MMU driver 决定具体编码方式。
- **Translation database**（tdb）：一个地址空间的所有 tobj；支持 find/update/remove。
- **Translation service**（tsvc）：管 MMU 状态如当前 tdb 切换。

API 分两层：**basic functions**（必须实现，最小集合）和 **customizable functions**（有默认通用实现，MMU driver 可覆写做 hw-specific 优化，例如 range walk 时批量拿锁、就地更新 PTE attr、按 offset 直接 fetch entry）。EMT 保留了 Linux 性能敏感的三类关键优化模式，弥补 pmap 的不足。

基于 EMT，作者实现了：

1. **EMT-Linux**：把 Linux v5.15 的架构无关内存管理代码迁到 EMT API。
2. **ECPT MMU driver** + **FPT MMU driver**：新架构作为纯 driver 落地。
3. **模拟工具链**：在 QEMU 上跑 EMT-Linux，emulated MMU 里实现新翻译逻辑；也对接 cycle-accurate simulator。

支持过程中发现并解决了 ECPT 在真实 OS 语境下的设计问题：**self-reference paradox**（kECPT 自己管理自己的翻译，移动 entry 时可能把访问 kECPT 所需的 entry 临时抽走，导致 kernel crash；用「先复制再删除」加允许重复 entry 解决）；**atomic kECPT switch**（KPTI 切换需要原子更新多个控制寄存器，类似 VMLAUNCH 的机制）；sparse address space 管理、多核锁等。

## 关键结果

- EMT-Linux 的接口开销：LEBench 微基准平均 **99.9%** vanilla Linux（标准差 1.1%）；GraphBIG/GUPS/Sysbench 宏基准 < **0.1%**；Redis/Memcached/PostgreSQL 吞吐、平均延迟、尾延迟偏差都 < **0.2%**。
- 通过 1,208 项 LTP 测试（覆盖 376 个 syscall），功能无回归。
- ECPT/FPT MMU driver 无需修改架构无关代码；相比之下传统移植需要 23 个文件、700+ 行改动。
- 用 ECPT driver 在 emulator 上跑 GraphBIG + Redis/Memcached/PostgreSQL 等，给出了过去 trace-driven 方案看不到的 OS 侧开销洞察（如 ECPT 在 OS 稀疏地址扫描、huge page 管理、多核 locking 上的挑战）。

## 相关

- **相关概念**：Page-Tables、TLB、MMU、Virtual-Memory、Hashed-Page-Table
- **同会议**：[[OSDI-2025]]
