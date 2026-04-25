---
type: paper
name: μFork
full_title: "μFork: Supporting POSIX fork Within a Single-Address-Space OS"
authors: [John Alistair Kressel, Hugo Lefeuvre, Pierre Olivier]
venue: SOSP
year: 2025
tags: [operating-systems, unikernel, cheri, fork, single-address-space]
source_pdf: "[[3731569.3764809.pdf]]"
source_md: "[[3731569.3764809]]"
---

# μFork: Supporting POSIX fork Within a Single-Address-Space OS (SOSP 2025)

> **一句话总结**：μFork 在真正的单地址空间 OS 里用 [[CHERI]] capability 实现 POSIX fork，forkµprocess 仅 54 μs（比 FreeBSD 传统 fork 快 3.7×、比 Nephele VM 方案快 198×），内存开销降至 2.2× / 12.3×。

## 问题

单地址空间 OS（SASOS，如 [[Unikernel|unikernel]]）把内核与所有应用放在同一地址空间，省下页表切换、TLB flush 等开销，是 [[FaaS]]、边缘、机密计算的理想底座；但 POSIX fork 语义依赖多地址空间（父/子各自拥有独立虚拟地址空间），与 SASOS 天然冲突。50% 的 Debian popcon top-50 与 46% GitHub C top-50 用到 fork（Nginx 多 worker、Redis 快照、OpenSSH 特权分离、Zygote FaaS 冷启动等）。

现有方案都在 SASOS 的轻量性、隔离性、透明性与性能之间放弃了一项：1990 年代 Mungi/Angel 用段相对寻址但现代编译器/工具链支持不足；OSv、Junction 放弃进程隔离；Nephele、KylinX、Graphene 用 VM 或 libOS-as-process 再引入多地址空间，失去 SASOS 轻量性；Iso-Unik 干脆把页表塞回 SASOS。

## 核心方法

μFork 用 CHERI 的硬件能力（capability）和内存标签在真·单地址空间内完成 fork。核心思想是给父 µprocess 在同一地址空间不同位置做一份内存拷贝给子 µprocess，然后解决两个挑战：(C1) 子内存里的绝对指针指向父地址，需识别并重定位——利用 CHERI 标签位（每 128-bit 指针独立的 1-bit valid tag）在运行时精准区分指针 vs 整数，重定位时加偏移到子区域；(C2) 跨 µprocess 和与内核的隔离——用 CHERI 的 bounded capability 实现 intra-address-space 隔离。

创新点：Copy-on-Pointer-Access（CoPA），在传统 [[Copy-on-Write|CoW]] 基础上，子 µprocess 读取含指针的页时也触发拷贝（以便重定位），写时仍走 CoW，写入非指针页时共享。基于 Position-Independent Code 让大多数引用都是 PC/SP/BP 相对，免修改。隔离级别可参数化：qmail 式互不信任用完整隔离，Nginx 式同一应用多 worker 用轻量 fault 隔离，Redis 式纯信任可关闭。原型基于 [[Unikraft]] + ARM Morello 开发板实现。

## 关键结果

- fork µprocess 54 μs，FreeBSD CHERI 传统 fork 3.7×，Nephele VM-based 198×
- 内存开销相比 FreeBSD 降 2.2×、相比 Nephele 降 12.3×
- 三个真实应用：Redis 快照、Nginx 多 worker、MicroPython Zygote FaaS 冷启动；FaaS fork-bound 吞吐比单体 OS 高 24%
- 首个同时满足 SAS + 隔离 + self-contained + fast IPC + non-segment 的 fork 方案（论文 Table 1）

## 相关

- **相关概念**：[[CHERI]]、[[Copy-on-Write]]、[[Unikernel]]、[[Position-Independent-Code]]、[[FaaS]]
- **同类系统**：[[Unikraft]]、Nephele、KylinX、[[Graphene]]、OSv、Junction
- **同会议**：[[SOSP-2025]]
