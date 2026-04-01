# KRR: Efficient and Scalable Kernel Record Replay

**作者**：Tianren Zhang (SmartX), Sishuai Gong (Purdue University), Pedro Fonseca (Purdue University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhang-tianren
**源文件**：[osdi25-zhang-tianren.pdf](../../papers/osdi-2025/osdi25-zhang-tianren.pdf)

---

## 一、背景

现代操作系统内核（如 Linux 超过 3000 万行代码）庞大且复杂，充满 bug。Syzkaller 在 3 年内就发现了 3736 个 Linux 内核 bug。许多 bug 通过代码审查和测试无法捕获，最终流入生产环境，造成严重后果。

Record-Replay（RR）技术是诊断非确定性和复杂内核故障的有力工具——它能精确记录一次失败执行并确定性地重放，支持反向调试和自动化分析。然而，现有 RR 工具（如 Mozilla RR、PANDA、Samsara）的开销极高，尤其在多核/多线程环境下，开销因子甚至超过核心数（例如 2 核 VM 就有 2.3-3.5× 的开销），完全抵消了并行计算的收益。随着数据中心工作负载日益并发化和 I/O 密集化，现有 whole-VM RR 方法越来越不实用。

---

## 二、要解决的问题

1. **多核可扩展性差**：现有 whole-VM RR 在多核环境下通过全系统序列化来记录并发非确定性，导致开销随核心数线性甚至超线性增长。2 核 VM 记录 RocksDB 就有 2.71×-4.93× 的开销，8 核更是达到 8.97×-29.94×。
2. **I/O 密集型工作负载的高开销**：数据中心工作负载越来越多地使用 kernel-bypass（如 DPDK、SPDK），但 whole-VM RR 仍然记录所有 VM 输入（包括绕过内核的用户态数据），产生大量不必要的记录开销。
3. **双接口记录的技术挑战**：将 RR 边界缩小到内核层需要同时记录硬件输入和用户态软件输入两个接口，而传统方法只需处理一个接口。这带来了事件原子性、跨层排序、内核自序列化、以及非确定性事件注入等全新的技术难题。

---

## 三、洞察与设计

**关键洞察**：在现代数据中心工作负载中，（1）内核虽然是最复杂的软件，但并不是在给定核心上运行时间最长的——大部分 CPU 时间花在用户态应用上；（2）随着 kernel-bypass 技术的广泛采用，提供给内核的输入远小于提供给整个 VM 的输入。因此，只记录内核执行（而非整个 VM 执行）可以大幅降低记录开销，同时仍能有效诊断内核 bug。

基于这一洞察，KRR 采用 **Split-Recorder** 架构，将记录职责分配给两个组件：

- **Guest Recorder**（运行在 guest 内核中）：记录来自用户态的软件输入，包括系统调用（索引+参数）、用户内存访问（通过 instrument `copy_from_user` 等安全 API）、`io_uring` 共享内存读取、页表项更新等。同时记录非确定性指令（RDTSC 等）以避免昂贵的 VM exit。
- **Hypervisor Recorder**（运行在 KVM/QEMU 中）：记录硬件输入，包括中断、I/O 读操作（PIO/MMIO）、DMA 数据。

**内核调度序列化**：KRR 引入 **Replay-Coherent (RC) Spinlock**——一个特殊的自旋锁，确保同一时刻只有一个 vCPU 执行内核代码，用户态线程则可完全并行运行。RC spinlock 记录自旋次数和获取顺序，保证 record/replay 间指令计数的一致性。为防止死锁，KRR 在获取某些内部内核锁之前释放 RC spinlock。

**异步事件定时**：利用 x86 kernel-mode-only 硬件性能计数器跟踪内核指令执行数，精确记录中断和 DMA 事件的时机。

**反向调试**：replay 阶段周期性拍摄 VM snapshot，结合多核执行坐标（per-vCPU 指令计数向量），支持多核 VM 的反向调试。

---

## 四、实现细节

- 基于 **Linux-KVM 5.17.5** 和 **QEMU 7.0.0** 实现
- Guest Recorder：约 1.2K LoC C 代码，提供 16 个 recording API，instrument 了 37 个内核源文件；支持 Linux 5.10 到 6.1 的 13 个内核版本，移植到新版本通常不超过 30 分钟
- Hypervisor Recorder：KVM 修改 0.8K LoC，QEMU 修改 1.2K LoC，共 5 个 instrumentation 接口，涉及 7 个文件
- QEMU 总修改约 4.5K LoC
- **磁盘 I/O 记录**：将 DMA buffer 数据与触发的磁盘 I/O 指令配对
- **网络 I/O 记录**：针对 Linux NAPI 机制，在设备写入 network ring buffer 前 trap 内核态 vCPU，记录数据和指令计数
- **事件原子性**：仅允许 RC spinlock 持有者的 vCPU 更新 event trace；更新时禁用中断并暂停对应 vCPU
- **验证**：通过 Linux Test Project (LTP) 测试套件验证正确性，每 N 条指令（默认 1K）记录并断言 RIP 和所有 x86_64 寄存器状态，成功 replay 8,156 个 LTP 测试

---

## 五、实验结果

实验平台：CloudLab c6420（2×16 核 Intel Xeon Gold 6142，384GB RAM，双口 10GbE NIC）。

### 多核工作负载（vs. VM-RR baseline）

| 工作负载 | 核心数 | KRR 开销 | VM-RR 开销 |
|---------|--------|----------|-----------|
| RocksDB（多种 benchmark） | 2 核 | 1.01×-1.67× | 2.71×-4.93× |
| RocksDB | 4 核 | 1.06×-2.03× | 5.08×-11.76× |
| RocksDB | 8 核 | 1.52×-2.79× | 8.97×-29.94× |
| Linux 内核编译 | 2 核 | 1.22× | 3.26× |
| Linux 内核编译 | 8 核 | 1.56× | 11.47× |
| Linux 内核编译 | 32 核 | 8.68× | 37.20× |

### Kernel-bypass 工作负载

| 工作负载 | 配置 | KRR 开销 |
|---------|------|----------|
| RocksDB + SPDK | 2 核，写工作负载 | 比非 bypass 低 10%-22.7% |
| Redis + DPDK | 4 核 | GET 吞吐降 0.26%，SET 吞吐降 1.14% |
| Nginx + DPDK | 1-32 核，大文件（16KB/64KB） | 仅 1%-5% 开销 |
| Nginx + DPDK | 1-32 核，小文件（1KB） | 46%+ 开销 |

### Bug 复现

- 测试 17 个 Linux 内核 bug（12 个 Syzbot + 5 个高危 CVE）
- 成功复现 16/17（包括 5/6 非确定性 bug 和全部 5 个 CVE）
- 唯一失败的 bug (#8) 要求多核真正并行执行（spinlock 竞争），KRR 的序列化机制无法触发

### 存储开销

- Kernel-bypass 下：KRR 4.8 MB/s vs. VM-RR 9.4 MB/s（低 48.9%）
- 非 bypass 下：KRR 53.39 MB/s vs. VM-RR 8.26 MB/s（高 546.57%），但 gzip 压缩后 KRR 数据缩减 6.91×

### Replay 性能

- 比原生执行慢 20×-150×（使用 QEMU 单步模式 emulation，非基本限制）

---

## 六、批判性分析

1. **可扩展性的天花板**：KRR 在超过 8 核后性能急剧下降（8.68× on 32 核内核编译），这是因为 RC spinlock 的粗粒度序列化本质上将内核执行变为单核——这正是 whole-VM RR 被批评的问题，只是 KRR 将影响限制在了内核执行部分。论文声称 1-8 核是 "sweet spot"，但对于现代大型 VM（几十上百核）这个限制依然显著。

2. **Kernel-bypass 依赖性过强**：KRR 最亮眼的结果（Redis-DPDK 0.26% 开销）高度依赖 kernel-bypass 配置。但在非 bypass 场景（如标准 RocksDB），KRR 的存储开销反而比 VM-RR 高 5.5 倍。论文在宣传时倾向于突出 kernel-bypass 场景的优势，但实际上许多工作负载并不使用 kernel-bypass。

3. **Bug #8 暴露了根本性盲区**：序列化机制无法复现需要真正并行执行才能触发的并发 bug。论文轻描淡写为 "KRR's mechanism effectively models a single-core system"，但这恰恰意味着一类重要的并发 bug（如弱内存序 bug、需要并行不可中断内核代码的 bug）在 KRR 下是不可观测的。这类 bug 可能正是最难诊断的。

4. **Replay 性能过慢**：20×-150× 的 replay 开销虽然被解释为 "不是基本限制"，但在实践中这意味着一个 10 分钟的 workload 需要数小时才能 replay 完。论文将此归因于 QEMU 单步模式，但未提供具体的优化路径或证据表明可以大幅改善。

5. **Baseline 公平性存疑**：VM-RR baseline 是作者自己实现的 whole-VM RR（非现有系统），理由是已有系统不兼容现代硬件或无法获取。虽然论文声称其性能与文献中已有系统一致，但缺乏直接的 apple-to-apple 比较。如果 Samsara 等系统已有改进，KRR 的相对优势可能缩小。

6. **不支持 pass-through 设备和 SR-IOV**：这在使用 GPU、NVMe 等 pass-through 设备的现代数据中心场景中是重大限制，论文仅在 Discussion 中简要提及。

---

## 七、AI Infra / MLSys 视角

1. **GPU 训练/推理场景的局限**：KRR 不支持 pass-through 设备（如 GPU），这直接排除了 AI 训练和推理系统的主要用例。AI 基础设施大量使用 GPU passthrough 和 SR-IOV，KRR 目前无法覆盖这些场景。

2. **Sliced RR 思想的可迁移性**：KRR 的核心思想——"只记录你关心的那一层"——对 AI 系统调试有启发。例如，在分布式训练中，可以只记录通信层（NCCL/Gloo）的非确定性输入而非整个进程，从而在低开销下诊断集合通信中的 bug。

3. **Kernel-bypass + RR 对 RDMA 场景的启示**：AI 训练大量使用 RDMA 进行 GPU-GPU 通信，这本质上就是 kernel-bypass。如果将 KRR 的方法扩展到 RDMA 场景，理论上可以在几乎不影响训练性能的前提下记录内核侧行为，辅助诊断网络栈相关问题。

4. **可能的 future work**：将 sliced RR 扩展到 device driver 层（特别是 GPU driver 如 NVIDIA 的 kernel module），实现 GPU 驱动层面的 record-replay，这将对诊断 GPU hang、CUDA error 等问题极有价值。

---

## 八、总结

KRR 通过将 record-replay 边界从整个 VM 缩小到内核层，采用 split-recorder 架构（guest recorder + hypervisor recorder），在多核环境和 kernel-bypass 工作负载下显著降低了记录开销。在 1-8 核 VM 上，KRR 比传统 whole-VM RR 快数倍到数十倍，在 kernel-bypass 场景下接近原生性能。但其可扩展性受限于内核执行的序列化（超过 8 核后性能退化明显），无法复现需要真正并行执行的并发 bug，不支持 pass-through 设备，且 replay 性能（20×-150×）仍有较大优化空间。KRR 填补了 application RR 和 whole-VM RR 之间的空白，适用于数据中心环境下 1-8 核 VM 的内核 bug 诊断。
