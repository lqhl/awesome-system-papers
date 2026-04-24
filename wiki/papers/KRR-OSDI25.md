---
type: paper
name: KRR
full_title: "KRR: Efficient and Scalable Kernel Record Replay"
authors: [Tianren Zhang, Sishuai Gong, Pedro Fonseca]
venue: OSDI
year: 2025
tags: [record-replay, kernel-debugging, virtualization, concurrency]
source_pdf: "[[osdi25-zhang-tianren.pdf]]"
source_md: "[[osdi25-zhang-tianren]]"
---

# KRR: Efficient and Scalable Kernel Record Replay (OSDI 2025)

> **一句话总结**：KRR 把 record-replay 的边界从「整机 VM」收窄到「guest kernel 切片」，通过 split recorder（guest + hypervisor）协作记录，在 8-core RocksDB/kernel build 上仅带来 1.52×–2.79× 减速，相比传统 VM-RR 的 8.97×–29.94× 有数量级改进。

## 问题

现代内核庞大复杂、bug 频发，record-replay 对诊断非确定性 bug 极具价值，但现有工具（Mozilla RR、VM-RR）在多核、高 I/O 的数据中心负载下开销爆炸——开销因子常常超过 core 数（2-core VM 已达 2.3-3.5×），完全吃掉了多核并行的收益。

原因有二：(1) whole-VM RR 必须记录所有硬件输入，kernel-bypass 负载（DPDK、SPDK、io\_uring）下数据量极大；(2) 为了处理并行必须串行化所有 vCPU 或记录内存访问序，代价与 core 数同阶。恰恰并发 + I/O 密集这两个最需要 RR 的场景，被现有技术支持得最差。

## 核心方法

**Sliced RR**：把 record-replay 的边界收窄到 guest kernel 的切片——只记录进入 kernel 的输入（syscall、user-memory 访问、页表 accessed/dirty bits、硬件中断/IO/DMA），不记录 user-space 的输入和执行。关键观察是：在 kernel-bypass 负载下，进入 kernel 的数据远小于进入 VM 的数据；且多数 CPU 时间花在 user 态，串行化只 kernel 态对端到端影响很小。

**Split-recorder 架构**：同时需要记录 user/kernel 和 kernel/hardware 两个接口——任何单一特权层都看不全。KRR 让 guest 内 recorder 负责 syscall、copy\_from\_user、io\_uring 共享队列、非确定指令（RDTSC/RDRAND）等，hypervisor recorder 负责中断、MMIO、DMA。两者通过一把 **Replay-Coherent (RC) spinlock** 协作——guest kernel 中的这把锁串行化内核执行，同时记录 spin cycle 数与获取顺序，使 replay 能精确对齐 instruction count（用于注入异步事件）。`copy_from_user` 这类 API 的集中化让 KRR 能只插桩少数入口点就捕获所有 user→kernel 数据流。

其他技术：用 kernel-mode-only 硬件性能计数器给异步事件打时间戳，避免与 guest 冲突；非确定性指令由 guest recorder 直接记录，省掉 VM exit；内核态的内部锁（spinlock、CSD lock）冲突通过额外记录 acquisition ordering 来防死锁。

## 关键结果

- 8-core RocksDB / kernel compilation：KRR 减速 1.52×–2.79×，VM-RR 为 8.97×–29.94×。
- Redis + DPDK（4-core VM）：KRR 吞吐损失仅 GET 0.26% / SET 1.14%，VM-RR 因无法记录 physical NIC 而不适用。
- RocksDB + SPDK：KRR 减速 1.17×–1.27×，VM-RR 达到 29×–64×（串行化把 SPDK polling 线程饿死）。
- Bug 复现：17 个真实 Linux bug（6 个非确定、5 个 CVE）复现 16 个。
- 实现：KVM ~0.8K + QEMU ~1.2K + guest Linux ~1.2K LoC，支持 Linux 5.10–6.1，新版本移植约 30 分钟。

## 相关

- **相关概念**：record-replay、sliced RR、kernel-bypass、split-recorder、[[RC-Spinlock]]
- **同类系统**：Mozilla RR、[[QEMU-Reverse-Debugging]]
- **同会议**：[[OSDI-2025]]
