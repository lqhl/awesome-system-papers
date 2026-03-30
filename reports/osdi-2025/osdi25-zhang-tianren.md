# KRR: Efficient and Scalable Kernel Record Replay

## 论文基本信息

- **标题**: KRR: Efficient and Scalable Kernel Record Replay
- **作者**: Tianren Zhang (SmartX), Sishuai Gong, Pedro Fonseca (Purdue University)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zhang-tianren

## 研究背景与动机

现代内核（如 Linux，超过 3000 万行代码）极其庞大复杂，存在大量 bug。内核故障在生产环境中难以诊断：部署环境遇到的问题在开发/测试环境中难以复现。

**Record-Replay (RR)** 技术通过记录导致故障的所有非确定性输入，然后在 replay 阶段精确复现原始执行，使得开发者可以进行确定性的离线分析和调试（如 reverse debugging）。但现有最好的 RR 系统（如 Mozilla RR）在多核/多线程环境下开销因子高达 8-29 倍，严重影响其实用性。

现有全系统 RR 方法的根本问题：
- **全系统序列化**：所有 vCPU 共享执行（一次只能有一个核心运行）→ 完全抵消了多核的并行性优势
- **高记录频率**：记录所有 VM 输入（硬件中断、I/O 等），数据量巨大

## 要解决的核心问题

如何设计一个高效的**内核级记录-重放**系统，在支持现代数据中心多核 VM 工作负载的同时，实现**远低于现有系统**的记录开销？

## 主要贡献

1. **Slice Record-Replay 边界**：将 RR 边界从"整个 VM"缩小到"仅内核"，避免记录 guest 应用的开销
2. **Split-Recorder 架构**：Guest 内核记录器和 Hypervisor 记录器协同工作，分别记录软件输入/硬件输入
3. **RC Spinlock**：Replay-Coherent 自旋锁，在 guest 内核中实现核间同步，无需 VM exit
4. **极低开销**：8 核 VM 记录 RocksDB 和内核编译工作负载仅 1.52×-2.79× 减速（vs 全系统 RR 的 8.97×-29.94×）
5. **广泛适用性**：成功复现了 17 个跨 Linux 5.10-6.1 各版本的真实 bug，包括 6 个非确定性 bug 和 5 个高危 CVE

## 研究方法与设计

### 核心观察

**观察一**：在大多数工作负载下，CPU 时间主要花在用户态而非内核态（尤其在 kernel bypass 场景下）

**观察二**：当应用使用 kernel bypass 技术（RDMA、SPDK、DPDK 等）时，传递给内核的输入远小于传递给机器的总输入

→ 因此仅记录**内核执行**（而非整个 VM）可大幅减少需要记录的数据。

### Split-Recorder 架构

```
Guest Kernel ──→ Guest Recorder（记录软件输入）
    ↑
    │
Hypervisor（记录硬件输入）
```

**Guest Recorder 记录的内容**：
1. **系统调用**：入口点记录系统调用号和参数
2. **用户内存访问**：监控 `copy_from_user`/`get_user` 等 API，记录复制内容
3. **io_uring 等共享内存机制**：监控内核对用户空间共享内存的读取
4. **页表更新**：记录 PTE 的修改（accessed/dirty bits 等隐式输入）
5. **非确定性指令**：如 RDTSC、RDSEED 等

**Hypervisor Recorder 记录的内容**：
1. **硬件中断和异常**：向量号、时机（指令计数）、寄存器状态
2. **I/O 操作**：Port I/O、MMIO、DMA 数据

### RC Spinlock（Replay-Coherent 自旋锁）

**动机**：记录时序信息需要指令计数，而普通自旋锁的等待次数本身是非确定性的（取决于调度）。

**解决方案**：RC Spinlock 不仅记录锁的获取顺序，还记录每个获取点的**指令计数**（Cycle Count）。在 replay 时强制恢复相同的指令计数顺序，保证多次运行的指令计数严格一致。

**死锁预防**：RC Spinlock 在获取某些内部锁之前会释放，在释放内部锁后重新获取。这避免了两个线程互相等待的死锁情况。

### 内核初始状态快照

KRR 仅需要**内核内存快照**（而非整个 VM 内存快照），显著减小了存储开销和快照时间。

### Reverse Debugging

KRR 在 replay 时结合 VM 快照和指令计数坐标，实现反向调试能力。通过在目标指令计数处加载最近的 VM 快照并向前 replay 至目标点。

## 关键实现细节

- **Guest Recorder**：约 1.2K 行 C 代码，修改 37 个 Linux 内核源文件
- **Hypervisor (KVM)**：约 0.8K 行 C 代码
- **QEMU**：约 1.2K 行 C 代码
- **支持 13 个 Linux 内核版本**（5.10 到 6.1），支持新版本通常只需 30 分钟

### 多核协调机制

使用**多核执行坐标**（Multi-Core Execution Coordinate）：记录 replay 时的向量形式的每 vCPU 指令计数，确保在多核回放时状态一致。

## 实验结果与分析

### RocksDB 吞吐量（多核）

| 核数 | Native | KRR | VM-RR |
|------|-------|-----|-------|
| 1 核 | 基准 | 1.0× | 1.1× |
| 2 核 | 基准 | 1.0× | 2.7-4.9× |
| 4 核 | 基准 | 1.1× | 5.1-11.8× |
| 8 核 | 基准 | 2.8× | >20× |

KRR 在 8 核时仍保持有效扩展，而 VM-RR 性能在 2 核后就开始严重衰退。

### 内核编译（多核）

| 核数 | Native | KRR | VM-RR |
|------|-------|-----|-------|
| 1 核 | 基准 | 1.15× | 1.11× |
| 2 核 | 基准 | 1.22× | 3.26× |
| 4 核 | 基准 | 1.26× | 6.27× |
| 8 核 | 基准 | 1.56× | 11.47× |
| 16 核 | 基准 | 3.56× | 20.62× |

### Kernel-Bypass 工作负载（Redis-DPDK）

KRR 在 Redis-DPDK 场景下吞吐量降低不足 0.26%（GET）和 1.14%（SET），因为内核在 kernel bypass 下接收的输入大幅减少。

### Bug 复现

成功复现了 17 个真实 Linux bug：
- 6 个非确定性 bug：成功复现 5 个
- 5 个高危 CVE：全部成功复现

## 潜在问题与局限性

1. **需要修改 guest 内核**：需要在内核源代码中加入记录代码，限制了即插即用性
2. **多核扩展性有上限**：超过 8 核后锁竞争成为瓶颈，性能不再随核数线性提升
3. **不支持用户态 bug 分析**：KRR 的设计目标是帮助内核开发者，用户态 bug 分析不在范围内
4. **Reverse debugging 对多核 VM 的支持不完整**：论文坦承多核 reverse debugging 需要更多的协调机制
5. **需要硬件辅助虚拟化**：假设使用 KVM，在裸机上或非虚拟化环境下不适用
6. **Kernel bypass 下 DMA 记录**：需要修改 QEMU 的 NVMe 模拟来记录 DMA 数据

## 未来工作方向

- 减少锁竞争以支持更多核心
- 异步快照以降低性能影响
- 更高效的 fork 支持

## 个人评注

1. **核心思想简洁有力**：仅记录内核层而非整个 VM 的思想符合直觉，且在大数据和 kernel bypass 趋势下越发重要。

2. **Split-Recorder 设计精巧**：将记录职责分配给 guest 和 hypervisor 各尽所长，避免了单一视角的效率问题。尤其是将软件输入交给 guest recorder，避免了大量 VM exit。

3. **RC Spinlock 的死锁预防机制**：这个设计值得注意——看似简单的"获取内部锁前释放 RC spinlock"实际上需要仔细分析所有锁获取路径，容易出错。

4. **轻微夸大**：摘要称"KRR ... achieves 1.52×-2.79× slowdown"指的是特定工作负载（8 核 RocksDB/内核编译），在某些配置下（如 Redis-DPDK）开销更低但并非所有场景都如此。

5. **实验完整性好**：涵盖了传统多核工作负载（RocksDB、内核编译）和 kernel bypass 场景，以及大量真实 bug 的复现，展示了系统的广泛适用性。

6. **支持 13 个内核版本但仅限 x86**：ARM 支持缺失，考虑到 ARM 在服务器市场的增长，这是一个重要的未来方向。
