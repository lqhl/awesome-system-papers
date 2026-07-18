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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Asterinas: A Linux ABI-Compatible, Rust-Based Framekernel OS with a Small and Sound TCB (ATC 2025)

> **一句话总结**：基于「现有 Rust OS 的 unsafe 渗透 driver 导致 TCB 膨胀」这一观察，提出 framekernel——单地址空间内用语言级权限分离把 unsafe 锁进 OSTD 框架（TCB 14.0%），其余 210+ syscall / driver 全 safe Rust；QEMU 单核下 LMbench 几何均值 1.08×、Nginx 1.17×、Redis 1.31×，与 Linux 5.15 性能可比。

## 问题与动机

作者 claim：可以构建**功能完整、通用用途、几乎全 safe Rust** 的内核，同时保持**最小且 sound 的 memory-safety TCB**。动机来自两类失败路径：

1. **在 legacy C 内核上 Rust 化（[[Rust-for-Linux]]）**：为桥接海量 C API 必然产生大量 unsafe wrapper；RFL 已有 19K LoC upstream + 112K LoC pending，且 Linux 的 pragmatism（mutex guard forget 触发 UAF、atomic context 里 sleep）与 Rust soundness 根本冲突。TCB 还包含整个 C 内核。
2. **Clean-slate Rust OS（[[Tock]]、[[RedLeaf]]、[[Theseus]]）**：driver 占成熟 OS 代码 ~70%，但这些系统在 MMIO、DMA、I/O port、raw buffer 上仍广泛用 unsafe（Table 1：unsafe crate 占比 93%/62%/32%）。Theseus 的 MappedPages 对 externally-modifiable memory 建 `&T` 引用在语义上 unsound。

CrowdStrike  outage 等事件说明：即便转向 Rust，若 unsafe 散布在 driver 层，memory safety 仍不可信。论文要回答的是：**能否在不牺牲 monolithic 性能的前提下，把 unsafe 压缩到真正必要的框架层？**

## 关键观察 / 隐含假设

- **观察 1**：OS 三类资源（CPU、memory、device）可在细粒度上分为 sensitive / insensitive 子集——kernel-mode CPU 状态、内核页表/栈/堆、APIC/IOMMU 等 core device 敏感；user VA、peripheral device、user-mode trap 相对不敏感。driver 所需低层资源大多可归入 insensitive 并经 safe API 封装。
  - **依赖假设**：mis-programming insensitive 资源不会通过框架漏洞级联破坏 kernel memory safety；IOMMU + interrupt remapping 能挡住 architecture-level UB（恶意 DMA、伪造中断）。
  - **可能失效场景**：无 IOMMU 的 bare-metal 部署、固件/ACPI 标注错误导致 sensitive MMIO 被暴露、或新型 side-channel 绕过语言隔离。

- **观察 2**：externally-modifiable memory（user mapping、DMA buffer、MMIO）不能承载 Rust 引用语义；必须用 **untyped memory**（`UFrame`/`USegment`，仅 POD copy 读写）才能 sound 地写 driver。
  - **依赖假设**：kernel 逻辑中「需要强类型引用」与「需要容忍外部改写」的内存区域可清晰划分；POD 接口足以覆盖 driver 热路径。
  - **可能失效场景**：复杂 zero-copy 网络栈或需要 in-place 解析非 POD 结构的 driver，可能被迫把逻辑塞回 TCB 或引入额外拷贝。

- **观察 3**：调度器、frame/slab allocator 等**策略组件**会随功能增长而膨胀（Linux scheduler 17×、slab 6×、frame alloc 6×），但策略 bug 仍可能破坏内存安全（双核跑同一 task）；因此 TCB 应只保留 mechanism，策略用 safe Rust **注入**到 non-TCB。
  - **依赖假设**：OSTD 的 metadata system、`is_running` flag、`Frame::from_unused` 等 guard 足以把注入策略的逻辑错误限制为 panic/拒绝服务，而非 silent memory corruption。
  - **证据强度**：**中**——论文用 KERNMIRI 抓到 frame allocator 竞态等 UB 并修复，但未形式化证明所有注入策略的错误类都被拦住。

- **假设 1**：crate 级 unsafe 边界 + Linked Code Size (LCS) 是衡量 runtime TCB 的合理代理。
  - **证据强度**：**中**——比数 crate 个数更精细，但 crate 内仍可能有 dead code；且 Rule 3「TCB 依赖链」会把无 unsafe 的 helper crate 也算进 TCB。

## 核心方法

**Framekernel** 架构：整个内核单地址空间、Rust 实现，逻辑切为 privileged **OSTD**（唯一可用 unsafe，类似 [[Microkernel]] TCB）与 de-privileged **OS services**（含全部 driver，强制 safe Rust）。组件间用函数调用/共享内存通信，避免硬件隔离的 IPC 开销，作者称此结合 [[Monolithic-Kernel]] 性能与 microkernel 安全边界（Figure 1）。

**OSTD 三类 safe API**（回应观察 1–2）：
- **User-kernel**：`UserMode`/`UserContext`（x86 仅暴露非敏感 RFLAGS 位）、`VmSpace`（只能映射 untyped memory）。
- **Kernel logic**：`SpinLock`/`Rcu`/`Mutex`/`WaitQueue`/`CpuLocal`、`LinkedList`/`RbTree`。
- **Kernel-peripheral**：`IrqLine`、`IoMem`/`IoPort`（仅 insensitive 区域）、`DmaCoherent`/`DmaStream`（仅覆盖 untyped memory）；配合 [[IOMMU]] 默认禁止 DMA，驱动显式建 mapping。

**10 条 safety invariants**（Inv.1–10）覆盖：frame 从未使用页分配、kernel CPU 状态不被 client/设备篡改、敏感内存不被 user/DMA 写、IoMem 不暴露 APIC 等敏感寄存器、task 同时最多一核运行、HeapSlot 不 outlive Slab、size/alignment 检查等。细节见 [[atc2025-peng-yuke]]。

**Safe policy injection**：`Scheduler`/`RunQueue`、`FrameAlloc`、`Slab`/`HeapSlot` trait 让 [[Asterinas]]（non-TCB）注入 Linux 风格 CFS、buddy frame allocator、slab heap，而 OSTD 只保留类型安全的「机制 + 注册 API」。

**KERNMIRI**：扩展 [[Miri]] 模拟物理页、页表与 OS 状态同步，对 OSTD `mm` 模块做解释执行 UB 检测；发现如 `from_unused` 与 `drop` 并发写 ref_count 的 data race 等真实 bug。

**Asterinas 实现**：基于 OSTD 的 Linux ABI 兼容内核，210+ syscall，Ext2/exFAT/OverlayFS/RamFS/ProcFS/SysFS，TCP/UDP/Unix/Netlink（smoltcp），Virtio block/net/vsock、USB；x86-64 tier-1、RISC-V tier-2；100K+ LoC、50+ contributor、3 年开发。中断下半部、softirq、时钟等 intentionally 放在 non-TCB。

## 设计取舍

- **语言隔离 vs 硬件隔离**：选择 compile-time privilege separation 而非 MPK/VMFUNC（对比 PerspicuOS、CubicleOS、RustyHermit-MPK），换取零 IPC 开销，但 single address space 内 speculative 侧信道或 TCB 漏洞影响面仍等于全内核。
- **Untyped memory 的 expressiveness**：放弃对 DMA/MMIO 区域的 `&T` 直接别名，换 soundness；Nginx 大文件 sendfile 需经中间 buffer，64 KiB 时吞吐落后 Linux。
- **IOMMU 默认开启**：安全优先；SQLite VACUUM 等小 pwrite 场景 IOMMU 开销显著（最差 72% Linux 性能），block driver pooling 不如 net driver 完善。
- **Policy 外置**：scheduler/allocator 复杂度移出 TCB，但 OSTD 仍需 `is_running` 等运行时检查（`Task::yield_now` 额外 0.6% cycles）来兜底策略 bug。
- **边界条件**：单核 QEMU virtio VM、Linux 5.15 baseline、关闭 mitigations/hugepages 的对比环境对「production parity」结论外推有限；SMP 可扩展性仍在进行中。

## 实验与结果

- **LMbench**（syscall 密集）：归一化几何均值 **1.08**（相对 Linux 5.15）；部分 FS open/stat 慢于 Linux（缺 RCU-walk），loopback TCP 更快（smoltcp 无 congestion control）。
- **Macro**：Nginx ApacheBench 几何均值 **1.17×**（4 KiB 文件 +19% rps）；Redis benchmark **1.31×**（GET +40.2%）；SQLite speedtest1 几何均值 **0.85×**（VACUUM 最差 ~72%）。
- **Safety 机制开销**（API 微基准）：除 `FrameAlloc::alloc` **6.7%** 外，其余边界检查/guard page/running flag 均 **<3%**。
- **TCB 规模**（LCS）：Asterinas **14.0%** vs RedLeaf 66.1%、Theseus 62.4%、Tock 43.8%；三年演化曲线显示 non-TCB 超线性增长、OSTD 次线性（Figure 7）。
- **KERNMIRI**：134 个单元测试，unsafe 覆盖 **100%**，行覆盖 **93%**；解释执行约 25× 慢于 native，用于一次性 soundness 审计。

## Critical Analysis

### 论证链条

Observation（Rust OS unsafe 渗透 driver → TCB 过大）→ Design（resource-centric 分类 + framekernel 双域 + untyped memory + policy injection）→ Result（14% TCB + 可比性能）链条整体闭合，但 **性能 parity** 与 **安全最小化** 两条线的证据强度不对称：TCB 数字有明确方法论，性能「与 Linux 持平」部分依赖对手未启用同等优化、己方网络栈行为差异（无 CC）等，作者自己在 macro 章节承认了这些 asymmetry。

「Sound TCB」主要靠 invariant 设计 + KERNMIRI 单元测试支撑，**未**对完整 Asterinas 内核或真实 workload 做端到端 UB 证明；与配套工作 [[Converos-ATC25]] 的 model checking 互补，但本论文实验节未整合该验证结果。

### 假设压力测试

- **已证明**：在 QEMU 单核、IOMMU on、virtio 设备下，常见 syscall 与三类 I/O 应用的吞吐/延迟与 Linux 同量级；OSTD `mm` 模块经 KERNMIRI 未发现残留 UB（在测试覆盖范围内）。
- **可能失效**：多核 SMP（论文明确未评）、真实 NIC/NVMe 裸机（非 virtio）、需要完整 TCP 语义的生产流量（smoltcp 缺失 CC 扭曲 net 结论）、无 IOMMU 嵌入式板卡、恶意 PCI 设备对抗性测试（仅 architectural 设计，无 red-team eval）。
- **论文未覆盖**：TCB 之外的可信基（Rust 编译器、`core`/`alloc`、bootloader、firmware）攻击面；info-leak、DoS、liveness 等非 memory-safety 性质。

### 实验可信度

- **Baseline 公平性**：禁用 Linux CPU mitigations 和 hugepages 有利于 Asterinas 对齐功能缺口，但也让 Linux 并非「全特性生产配置」；网络优势部分来自实现差异而非 framekernel 本身。
- **Benchmark 代表性**：LMbench + Nginx/Redis/SQLite 覆盖 syscall 与 I/O，但缺少多租户隔离、driver 热插拔、长时间 soak、故障注入；Redis/SQLite 偏小包/随机 I/O，对 block pooling 缺陷敏感。
- **Ablation**：Table 8 量化 OSTD safety check 开销；IOMMU on/off 与 pooling vs dynamic（Figure 6）说明性能瓶颈来源，但缺少「若无 framekernel 分离、unsafe 散布全内核」的安全回归 ablation（只能通过与其他 Rust OS 的 TCB 横比间接论证）。

### 系统性缺陷

- **尾延迟 / 多核**：论文未讨论 P99 latency；SMP 锁粒度与 RCU 优化仍在进行，当前结论不宜外推到高核数服务器。
- **故障恢复 / 可观测性**：论文未讨论 panic 策略、driver 崩溃隔离、kdump/live patch、生产 tracing 开销。
- **运维与兼容**：210+ syscall 是子集；与 Linux 在 security module、eBPF、cgroups v2、perf 等生态的差距未量化。
- **部署成本**：需 IOMMU、对 ACPI 标注敏感 I/O 的依赖，在低端硬件上可能直接不成立。

## 局限与 Future Work

- **局限 1**：评估限于 **单核 QEMU**；SMP 可扩展性是 ongoing work，结论不能外推到多 socket 生产机。
- **局限 2**：KERNMIRI 覆盖率绑定 OSTD 单元测试；完整内核启动路径、并发 driver 交互、错误注入路径未系统解释执行。
- **局限 3**：网络性能部分受益于 smoltcp **无 congestion control** 与 Linux 功能不对等，削弱「整体 OS 优化水平相当」的 claim。
- **Future work 1**：补齐 block device DMA pooling、sendfile zero-copy、RCU-walk 等路径后重做 macro benchmark，分离「framekernel 架构开销」与「实现成熟度」。
- **Future work 2**：多核 LMbench + 生产 trace（容器启动、数据库 checkpoint）下的 TCB 违规率与 tail latency 联合测量。
- **Future work 3**：将 KERNMIRI/Converos 类验证与 TCB 边界自动审计打通，量化 policy-injected scheduler/allocator 的错误类覆盖。

## 相关

- **相关概念**：[[Memory-Safety]]、[[Rust]]、[[TCB]]、[[Microkernel]]、[[Monolithic-Kernel]]、[[IOMMU]]、[[MMIO]]、[[DMA]]、[[Untyped-Memory]]、[[Driver-Safety]]
- **同类系统**：[[Theseus]]、[[Tock]]、[[RedLeaf]]、[[Rust-for-Linux]]、Redox、rCore
- **同会议**：[[ATC-2025]]、[[Converos-ATC25]]（对 Asterinas 的 PlusCal model checking）
- **对比**：framekernel 语言隔离 vs PerspicuOS 页表写保护 vs CubicleOS/RustyHermit-MPK 硬件域隔离；safe policy injection vs ghOSt/Enoki 的 scheduler 外置/半外置方案
