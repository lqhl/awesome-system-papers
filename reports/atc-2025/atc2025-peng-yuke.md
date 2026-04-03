# ASTERINAS: A Linux ABI-Compatible, Rust-Based Framekernel OS with a Small and Sound TCB

**作者**：Yuke Peng (SUSTech), Hongliang Tian (Ant Group), Junyang Zhang, Ruihan Li (Peking University & Zhongguancun Laboratory), Chengjun Chen, Jianfeng Jiang (Ant Group), Jinyi Xian (SUSTech), Xiaolin Wang, Chenren Xu, Diyu Zhou, Yingwei Luo (Peking University & Zhongguancun Laboratory), Shoumeng Yan (Ant Group), Yinqian Zhang (SUSTech)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/peng-yuke
**源文件**：[[atc2025-peng-yuke.pdf]]

---

## 一、背景

操作系统中的内存安全漏洞一直是系统安全的核心挑战。据估计，C 语言编写的系统软件中 60-70% 的安全漏洞源于内存安全问题，2024 年的 CrowdStrike 事件更是因一个越界内存访问导致数百万 Windows PC 崩溃。

Rust 语言凭借所有权、借用和生命周期等机制，在不依赖垃圾回收的前提下提供内存安全保证，成为系统编程的有力候选。Linux 内核已正式采用 Rust 作为第二编程语言（Rust for Linux），Tock、RedLeaf、Theseus 等 OS 也从零开始用 Rust 构建。然而，现有 Rust OS 在内核开发中大量使用 `unsafe` 代码，导致 Trusted Computing Base (TCB) 过大、soundness 难以保证。

---

## 二、要解决的问题

1. **现有 Rust OS 的 unsafe 使用过于泛滥**：Linux (RFL) 55%、Tock 93%、RedLeaf 62%、Theseus 32% 的 crate 使用了 unsafe，远未达到"尽量少用 unsafe"的最佳实践。

2. **在 legacy 内核上构建 safe 抽象必然导致巨大 TCB**：Rust for Linux 需要在 C API 之上包装 safe Rust 抽象，本身就要大量 unsafe 代码，且 Linux 的"实用主义优先于安全"理念与 Rust 的安全范式存在根本冲突（如 mutex guard 遗忘导致 use-after-free、spin lock 中 sleep 导致数据竞争）。

3. **驱动开发缺乏安全抽象**：设备驱动通常占 OS 代码的 70%（以 Linux 为例），但现有 Rust OS 中驱动普遍直接使用 unsafe 操作原始缓冲区、MMIO、I/O 端口和 DMA 区域。

4. **未覆盖环境级和架构级 UB**：现有 Rust OS 仅关注语言级 UB，忽视了栈溢出、恶意设备 DMA 攻击、中断伪造等执行环境和硬件架构层面的 undefined behavior。

---

## 三、洞察与设计

**关键洞察**：OS 资源可以按是否会被误用以破坏内存安全，细粒度地分为 sensitive（如内核态寄存器、内核代码/栈/堆/页表、核心设备 APIC/IOMMU）和 insensitive（如用户态寄存器、用户虚拟地址空间、外围设备）两类。只需将 sensitive 资源封装在特权框架内，insensitive 资源全部用 safe Rust 实现，就能在不引入硬件隔离开销的前提下实现最小化 TCB。

基于此洞察，论文提出 **framekernel** 架构：

- **单地址空间**（如单体内核），所有组件通过函数调用高效通信，无 IPC 开销
- **逻辑分层**：特权 OS 框架（OSTD，类似微内核）+ 去特权 OS 服务（ASTERINAS）
- 仅 OSTD 允许使用 unsafe，OS 服务（包括驱动）必须全部用 safe Rust
- OSTD 将 CPU、内存、设备三类资源中的 sensitive 部分封装为 safe API

核心设计要素：

1. **Untyped Memory 抽象**：为外部可修改内存（用户映射、DMA capable 内存）提供 read-write 风格接口，仅允许拷贝 POD 类型，避免创建指向此类内存的 Rust 引用
2. **Safe Policy Injection**：将任务调度器、页帧分配器、slab 分配器等复杂策略组件从 TCB 中移出，通过 trait 注入机制由 safe Rust 实现
3. **10 条安全不变式**（Inv.1-10）系统性保障 privilege separation 的 soundness

---

## 四、实现细节

**OSTD 框架**（TCB，约 10.5K LoC）：

- **用户-内核交互 API**：`UserMode`（跳转用户态执行直到 trap）、`UserContext`（用户态寄存器，排除 IF/IOPL 等敏感位）、`VmSpace`（用户地址空间管理，仅接受 UFrame/USegment）
- **内核逻辑 API**：`SpinLock`、`Rcu`、`Mutex`、`WaitQueue`、`CpuLocal` 等同步原语；`LinkedList`、`RbTree` 等数据结构
- **外设交互 API**：`IrqLine`（中断注册）、`IoMem`/`IoPort`（MMIO/PIO，仅允许 insensitive 范围）、`DmaCoherent`/`DmaStream`（DMA 映射，仅在 untyped memory 上创建）
- **Frame 元数据系统**：静态数组跟踪每个页帧的引用计数和自定义元数据，`Frame::from_unused` 通过原子操作检查保证 Inv.1
- **IOMMU 配置**：默认不允许任何 DMA 访问，驱动只能在 untyped memory 上创建 DMA 映射；启用中断重映射防止设备伪造中断
- **栈保护**：每个 Task 栈配 guard page + 编译期栈使用分析，确保函数栈帧小于 guard page

**Safe Policy Injection 实现**：

- **调度器注入**：通过 `Scheduler` + `RunQueue` trait，支持 per-CPU run queue、自定义调度属性；通过 `is_running` 私有标志位强制 Inv.8（每个 Task 最多在一个 CPU 上运行）
- **帧分配器注入**：通过 `FrameAlloc` trait，所有分配结果经 `Frame::from_unused` 校验
- **Slab 分配器注入**：`Slab` + `HeapSlot` 抽象，`Slab` 跟踪活跃 slot 数防止 use-after-free，`HeapSlot::into_box` 检查大小和对齐

**ASTERINAS**（non-TCB，约 65K LoC）：

- 支持 210+ Linux 系统调用
- 文件系统：Ext2、exFAT32、OverlayFS、RamFS、ProcFS、SysFS
- 网络：TCP、UDP、Unix、Netlink sockets（TCP 使用 smoltcp 库）
- 设备：VirtIO Block/Network/Vsock、USB controller/HID
- 架构：x86-64（tier-1）、RISC-V（tier-2）
- 实现 Linux 风格的 CFS 调度器、buddy system 帧分配器（per-CPU caching）、slab 分配器
- DMA 内存池化机制（persistent mapping），减少 IOTLB invalidation

**KERNMIRI**（约 1.2K LoC）：扩展 Miri 工具以支持 OS 级 UB 检测，模拟物理内存和基本分页系统，能检测数据竞争和 mutability 违规等 UB。

---

## 五、实验结果

实验平台：Intel i7-10700, 32GB RAM, Intel SSD, QEMU 9.1.0 VM（单核），基线为 Linux 5.15（关闭 CPU mitigations 和 hugepages）。

**微基准测试（LMbench）**：

| 类别 | 代表性测试 | Linux | ASTERINAS | 归一化性能 |
|------|-----------|-------|-----------|-----------|
| Proc | lat_proc fork | 59.20 µs | 57.46 µs | 1.03 |
| Mem | lat_pagefault | 0.109 µs | 0.100 µs | 1.09 |
| IPC | bw_unix | 7875 MB/s | 14183 MB/s | 1.80 |
| FS | lat_syscall stat | 0.299 µs | 0.400 µs | 0.75 |
| Net (VirtIO) | lat_tcp | 16.75 µs | 12.94 µs | 1.29 |
| **几何平均** | | | | **1.08** |

**宏基准测试**：

| 应用 | 归一化性能 | 说明 |
|------|-----------|------|
| Nginx | 1.17 | 小文件优势来自 smoltcp 无拥塞控制 |
| Redis | 1.31 | 小消息场景优势明显，GET 操作高 40.2% |
| SQLite | 0.85 | Vacuum 测试最差（72%），pwrite64 小数据写入待优化 |

**安全机制开销**：最高 6.7%（帧分配器所有权检查），其余均 < 3%。

**TCB 比较**：

| OS | 总代码量 (LoC) | TCB (LoC) | TCB 占比 |
|----|---------------|-----------|---------|
| RedLeaf | 25992 | 17182 | 66.1% |
| Theseus | 70468 | 43978 | 62.4% |
| Tock | 6628 | 2903 | 43.8% |
| **ASTERINAS** | **75285** | **10571** | **14.0%** |

**KERNMIRI 覆盖率**：134 个单元测试覆盖 OSTD mm 模块 93% 代码行、100% unsafe 块；解释执行约比原生慢 25 倍。

---

## 六、批判性分析

1. **单核评估的局限性**：所有性能评估仅在单核 QEMU VM 上进行，而现代 OS 的关键挑战在于 SMP 可扩展性。论文承认 SMP 优化尚在进行中，但单核结果无法说明 framekernel 在多核场景下的表现——safe Rust 的额外检查和 atomic 操作在高并发下可能放大开销。

2. **性能比较存在系统性偏差**：ASTERINAS 使用 smoltcp（无拥塞控制）与 Linux 完整 TCP 栈比较网络性能，Redis 和 Nginx 的"优势"很大程度来自这一不公平因素，而非 framekernel 架构本身的优势。论文虽有提及但未充分强调这一点。

3. **TCB 度量方法（LCS）有利于自身**：Linked Code Size 仅统计编译链接后的可执行代码行，排除了类型定义、import 等，且 Rule 1 直接将 Rust 工具链排除出 TCB。但 Rust 编译器本身的 bug（如 soundness issues）同样可能危及内存安全，将其完全排除在 TCB 外是一个强假设。此外，其他 OS 使用相同度量可能也会缩小 TCB 占比。

4. **功能完整性差距被淡化**：ASTERINAS 支持 210+ 系统调用，但 Linux 有 400+ 系统调用和大量高级特性（hugepages、CPU mitigations、完整网络栈、高级调度等）。在关闭 Linux 的 CPU mitigations 和 hugepages 后比较，实质上是让 Linux 降级来匹配 ASTERINAS 的功能缺失。

5. **KERNMIRI 的检测能力有限**：KERNMIRI 仅覆盖 mm 模块的单元测试路径，无法检测集成场景下的 UB。两个发现的 case study（数据竞争和 mutability UB）都是 OSTD 自身的 bug，反而说明"sound TCB"的实现并非微不足道。

6. **Safe Policy Injection 的实际安全增益不清晰**：虽然调度器和分配器被移出 TCB，但 OSTD 仍需通过 invariant check（如 `is_running` 标志）防范注入策略的 bug。如果这些检查本身有疏漏，注入的"safe"代码仍可导致内存安全问题。论文未讨论这些检查的完备性。

---

## 七、AI Infra / MLSys 视角

1. **GPU/加速器支持缺失是最大短板**：ASTERINAS 目前仅支持 VirtIO 设备，缺少 GPU 驱动和 PCIe 设备直通支持。对于 AI Infra 场景，GPU 驱动本身就是最大的安全风险来源（如 NVIDIA 驱动的内核模块），如果 framekernel 能提供 safe GPU 驱动抽象，将是非常有价值的方向。

2. **DMA 内存池化机制可借鉴**：ASTERINAS 的 DMA persistent mapping 方案和 IOMMU 优化对 RDMA 和 GPU DMA 场景有直接参考价值。AI 训练中 NCCL 等通信库大量使用 DMA，安全且高效的 DMA 管理是实际需求。

3. **Safe Policy Injection 思路可迁移到 AI 运行时**：将调度策略从内核机制中分离的设计，可以启发 AI 推理框架中的调度器设计（如 vLLM 的 scheduler）——将请求调度策略与底层内存管理/执行机制解耦。

4. **值得跟进的方向**：
   - 在 framekernel 上实现 safe GPU 驱动框架，支持 CUDA/ROCm 工作负载
   - 探索 safe Rust 实现的 RDMA 驱动，用于分布式训练通信
   - 将 untyped memory 抽象扩展到 device memory（如 GPU 显存），提供安全的 host-device 内存交互

---

## 八、总结

ASTERINAS 提出了 framekernel 架构，通过将 OS 资源细粒度分类为 sensitive/insensitive，在单地址空间内实现基于 Rust 语言的内核内特权分离，将 TCB 压缩到仅 14.0%。OSTD 框架提供了 untyped memory、safe policy injection 等创新抽象，使 210+ Linux 系统调用的实现完全使用 safe Rust，性能与 Linux 基本持平。主要局限在于仅验证了单核场景、功能完整性与 Linux 有较大差距、且对 GPU 等加速器设备的支持尚待开发。作为一个开源项目（100K+ LoC, 50+ 贡献者，3 年开发），ASTERINAS 展示了在保持性能的前提下大幅提升 OS 内存安全的可行路径。
