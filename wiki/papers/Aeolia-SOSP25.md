---
type: paper
name: Aeolia
full_title: "Aeolia: A Fast and Secure Userspace Interrupt-Based Storage Stack"
authors: [Chuandong Li, Ran Yi, Zonghao Zhang, Jing Liu, Changwoo Min, et al.]
venue: SOSP
year: 2025
tags: [storage, nvme, user-interrupt, ebpf, file-system, userspace]
source_pdf: "[[3731569.3764816.pdf]]"
source_md: "[[3731569.3764816]]"
---

# Aeolia: A Fast and Secure Userspace Interrupt-Based Storage Stack (SOSP 2025)

> **一句话总结**：打破"userspace 必须 polling"的惯性，用 Sapphire Rapids 的 user interrupt 直投中断到用户态、配合 sched_ext 实现协同调度和 intra-process 隔离；Aeolia 总体性能超 Linux 2×，其上的 AeoFS 比 ext4 快 19.1×。

## 问题

高性能存储栈被迫二选一：userspace + polling（如 SPDK、uFS）吞吐高但无法多任务共享 CPU/磁盘；kernel + interrupt 能共享资源但性能低。作者发现这是两条正交设计轴（userspace vs kernel、polling vs interrupt）被错误耦合。核心观察：

- **polling 比 interrupt 的性能优势其实很小**——大部分 overhead 来自 kernel 线程调度策略而非中断本身，用 active checking 让 interrupt 性能贴近 polling
- polling 的 CPU 占用严重损害 file system 的多核可扩展性（uFS 的 IPC 仍 400ns）

这让 "userspace + interrupt" 成为设计空间里未被探索的甜点。

## 核心方法

Aeolia 建立四支柱达成表 1 四属性（高 I/O 性能 + 协同调度 + 保护共享 + 高性能文件系统）：

1. **User interrupt 直投存储中断**：利用 Sapphire Rapids 支持的 user interrupt 硬件特性，把 [[NVMe]] 中断绕过 kernel 直接送到用户态 handler，首次把该特性用于存储设备（此前只用于 userspace IPI）
2. **intra-address-space 隔离**：用标准硬件保护机制在同一进程地址空间内划 trusted entity，未授信代码不能破坏文件系统元数据，实现 protected sharing
3. **sched_ext 协同调度**：通过 [[eBPF]]-based 的 sched_ext framework 和 kernel 线程调度器共享 eBPF map，桥接 kernel/userspace 语义鸿沟
4. **AeoFS 库文件系统**：基于 Aeolia 构建 POSIX-like library FS，延用 Trio 的 state separation 但把 lazy integrity check 改成 eager check（每次 op 多付 85 cycles 切换到 trusted entity），既易推理又避免数据丢失

总实现 17751 行代码。

## 关键结果

- Aeolia 的存储栈性能接近 SPDK，超 Linux **2×**
- AeoFS 在 LevelDB 上比 ext4/f2fs/uFS 快 **2.87–8.19×**
- 微基准 4KB read 上 AeoFS 比 ext4 快至多 **19.1×**
- 首次证明"userspace + interrupt-based"可行且兼顾四属性

## 相关

- **相关概念**：[[eBPF]]、[[NVMe]]
- **同会议**：[[SOSP-2025]]
