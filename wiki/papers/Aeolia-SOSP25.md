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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Aeolia：快速、安全的基于用户空间中断的存储栈（SOSP 2025）

> **原题**：Aeolia: A Fast and Secure Userspace Interrupt-Based Storage Stack

> **一句话总结**：测量表明 polling 相对 interrupt 的 I/O 优势主要来自 kernel 调度策略而非中断本身；据此用 Sapphire Rapids [[user interrupt]] 把 [[NVMe]] 完成事件直投用户态，配合 intra-process 隔离与 [[sched_ext]] 协同调度，Aeolia 总体性能超 Linux 2×，AeoFS 在 LevelDB 上比 ext4 快至多 19.1×。

## 问题与动机

高性能存储栈长期被耦合在两条正交轴上：userspace vs kernel、polling vs interrupt。[[SPDK]]/[[uFS]] 等 userspace polling 方案 I/O 快，但难以让多任务安全共享磁盘与 CPU；kernel interrupt 栈能共享资源，却受 syscall、VFS、调度策略拖累。作者 claim 这不是「polling 天生更快」，而是设计空间未被充分探索的甜点：**userspace + interrupt**。

现代 [[NVMe]] 延迟降至微秒级后，kernel 在 I/O 完成时过早 sleep 并切到 idle task 的调度策略成为主要开销（4KB read 上约 1.8μs），真正 interrupt 机制仅约 0.6μs。与此同时 polling 的高 CPU 占用让 [[uFS]] 不得不独立进程 + IPC（仍约 400ns），并限制文件系统多核扩展。Aeolia 要同时满足表 1 四属性：高 I/O 性能、协同调度、protected sharing、高性能文件系统。

## 关键观察 / 隐含假设

- **观察 1**：在 active checking 调度策略下，optimized interrupt 与 polling 的 4KB read 延迟接近（6.3μs vs 5.4μs），SPDK 相对 kernel 的主要收益来自 bypass kernel 而非 polling 本身。
  - **依赖假设**：工作负载以 ≥4KB 访问为主（Alibaba trace 中 >95% 请求 ≥4KB）；单任务或 moderate 并发。
  - **可能失效场景**：512B 小 I/O 下 interrupt 开销占比上升，AeoDriver 比 SPDK 慢至多 18.2%；未来 interrupt 硬件优化可能缩小差距。
- **观察 2**：polling 在多任务共享单核时无法让调度器感知 I/O 完成，导致高 tail latency 与 compute 任务被饿死。
  - **依赖假设**：LC/TP 与 I/O 任务会 collocate 在同一物理核；需要 kernel 与用户态栈协同调度。
  - **可能失效场景**：专用 polling 核、完全隔离的 I/O 线程池可缓解，但牺牲资源利用率。
- **观察 3**：library FS 若基于 polling 子系统，IPC 与 event-driven 单线程元数据设计会成为 FS 扩展瓶颈。
  - **依赖假设**：应用愿以 library call 而非 syscall 访问 FS；可信实体 + 硬件 intra-process 隔离可用。
  - **可能失效场景**：多 untrusted 应用并发写同一文件时 AeoFS 需 rebuild auxiliary state + fsync，性能低于 uFS。
- **假设 1**：Sapphire Rapids [[user interrupt]] 可安全用于存储设备完成通知（此前多用于 userspace IPI）。
  - **证据强度**：中。论文有硬件行为分析与小 I/O 边界讨论，但依赖特定 Intel 代际。
- **假设 2**：[[sched_ext]] + eBPF map 足以桥接 kernel/userspace 调度语义鸿沟。
  - **证据强度**：中。多任务共享核实验有效，但 sched_ext 仍属较新 upstream 路径。

## 核心方法

Aeolia 四支柱：

1. **AeoDriver**：利用 [[user interrupt]] 把设备中断绕过 kernel 送到用户态 handler，实现 direct userspace disk access + interrupt completion。
2. **Intra-address-space 隔离**：在同一进程内用标准硬件保护划 trusted entity，未授信代码不能破坏 FS 元数据，实现 protected sharing。
3. **sched_ext 协同调度**：通过 eBPF-based [[sched_ext]] 与 kernel scheduler 共享 map，避免 interrupt 路径上的病态 sleep/idle 切换。
4. **AeoFS**：POSIX-like library FS，延用 [[Trio]] 的 state separation，但把 lazy integrity check 改为 eager check（每次 op 多付约 85 cycles 切到 trusted entity），易推理且避免 check 失败时数据丢失。

总实现约 17751 行代码。AeoFS 支持 direct data/metadata access 与细粒度并行。

## 设计取舍

- **Interrupt 换协同调度与 FS 可扩展性**：相对 SPDK 在小 I/O 上略慢，但多任务共享核时 tail latency 与吞吐显著更好（LC 场景至多 291×）。
- **Userspace 栈 + trusted entity**：避免独立 FS 进程的 IPC，但多应用共享写同一文件时有 synchronization/fsync 开销。
- **依赖 user interrupt 与 sched_ext**：可移植性受硬件与 kernel 特性约束；RISC-V 有类似方向但尚未同等成熟。
- **Eager metadata integrity**：每次操作付固定 trusted-entity 切换成本，换取更简单正确性故事。

## 实验与结果

- Aeolia 存储栈接近 SPDK，超 Linux **2×**；AeoDriver 4KB 多读场景超 POSIX 至多 **2×** 吞吐。
- AeoFS 4KB read 微基准比 ext4 快至多 **19.1×**；64 线程 2MB write 比 ext4/f2fs/uFS 分别快 **19.1×/28.9×/8.4×**。
- LevelDB db_bench：AeoFS 比 ext4/f2fs/uFS 快 **2.87–8.19×**。
- Filebench：AeoFS 比 ext4/f2fs 快至多 **3.1×/6.6×**。
- 多任务共享单核：interrupt 栈相对 polling 显著降低 LC tail latency；AeoDriver 相对 io_uring/POSIX 吞吐提升 **1.3–3.7×**。
- Active checking ablation：kernel 劣质调度策略带来约 **10.6%** 性能损失。

## 批判性分析

### 论证链条

测量（§2 interrupt vs polling 分解）→ 设计 userspace interrupt 栈（§3–4）→ 微基准与 macrobenchmark（§9）链条闭合较好。AeoFS 的多核扩展实验直接回应「polling 限制 FS」这一独立 observation，而非仅依附于 driver 数字。

较弱环节是把 **Optane P5800X + 128 核 Intel 单机** 结论外推到更普遍云/容器存储栈：protected sharing 与 sched_ext 的运维复杂度在生产环境未验证。

### 假设压力测试

- 小 I/O 密集 trace 会削弱「interrupt ≈ polling」主张。
- 无 Sapphire Rapids / sched_ext 的平台需回退到 kernel 或 polling，设计空间甜点消失。
- 多租户共享写同一 directory/file 时 AeoFS 可能不如中心化 uFS——论文 §9.4 已承认。

### 实验可信度

- Baseline 覆盖 Linux io_uring（poll/default/opt）、SPDK、ext4/f2fs/uFS，较完整。
- 多核 FS 与 LevelDB/Filebench 有代表性；缺少真实多租户安全隔离压力测试。
- 设备与 CPU 代际较新，结论对旧 SSD/ARM 服务器的外推需谨慎。

### 系统性缺陷

- 论文未讨论生产可观测性、故障恢复、在线升级。
- user interrupt 与 trusted entity 的安全边界依赖硬件正确实现；侧信道未讨论。
- AeoFS 元数据 hash rehashing 成为高线程数瓶颈（论文提及）。

## 局限与后续工作

- **局限**：小 I/O（<4KB）仍有 interrupt 劣势；依赖特定硬件特性；共享文件并发更新开销高。
- **Future work**：在 RISC-V/ARM 上验证 user interrupt 存储路径；降低共享目录元数据 contention；与 io_uring 混合栈对比的长期维护成本。

## 相关

- **相关概念**：[[NVMe]]、[[eBPF]]、[[SPDK]]、[[io_uring]]、[[sched_ext]]
- **同类系统**：[[uFS]]、[[Trio]]、[[SPDK]]、Linux kernel stack
- **同会议**：[[SOSP-2025]]
- **对比**：userspace polling（SPDK）vs kernel interrupt vs Aeolia（userspace interrupt）
