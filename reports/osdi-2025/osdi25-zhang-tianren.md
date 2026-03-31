# KRR: Efficient and Scalable Kernel Record Replay

**作者**：Tianren Zhang（SmartX）、Sishuai Gong（Purdue University）、Pedro Fonseca（Purdue University）
**会议**：OSDI 2025（第19届 USENIX 操作系统设计与实现研讨会），2025年7月，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/zhang-tianren
**源文件**：[osdi25-zhang-tianren.pdf](../../papers/osdi-2025/osdi25-zhang-tianren.pdf)

---

## 一、背景

现代内核庞大且复杂，线上部署中出现的故障往往难以复现——尤其是并发 bug 和非确定性 bug。Record-Replay（RR）技术通过在记录阶段捕获所有影响执行的输入事件，在回放阶段精确重现故障执行，是诊断此类难以复现故障的强力手段，可支持反向调试（reverse debugging）和自动化分析等高级技术。

然而，数据中心工作负载呈现两大趋势：一是多核并发性越来越高，二是 kernel-bypass 技术（DPDK、SPDK 等）的广泛采用。这两个趋势恰好是现有 RR 技术的软肋：多核并发要求记录并强制调度序列化，而高 I/O 强度意味着需要记录大量事件，两者叠加导致开销急剧上升。

---

## 二、要解决的问题

**现有方案的核心痛点**：

1. **多核开销过高**：现有 whole-VM RR（如 Samsara）在记录多核 VM 时，开销与核数近似线性增长——记录 2 核 VM 已有 2.3–3.5× 开销，记录 8 核 VM 可达 8.97×–29.94×，对生产工作负载完全不可接受。

2. **I/O 密集型工作负载更差**：kernel-bypass 工作负载（RocksDB + SPDK、Redis + DPDK）下，VM-RR 需要记录全部硬件输入，SPDK 场景下 VM-RR 的吞吐量下降高达 29–64×，根本原因是整机序列化阻塞了 SPDK polling 线程而 worker 线程却无法获得 I/O 结果。

3. **根本矛盾**：whole-VM RR 的记录边界包含整个 VM，大量与内核无关的用户态执行也被序列化，浪费了本可规避的开销。

---

## 三、核心设计

KRR 的核心思路是**将 record-replay 的边界收窄到内核层**，即"Kernel RR"（见 Figure 1）。不同于记录整个 VM，KRR 只记录和回放内核的执行，让用户态代码自由运行。

**Sliced Record-Replay（切片 RR）的两大优势**：

- **Kernel-bypass 场景下输入减少**：当应用通过 DPDK/SPDK 绕过内核直接访问硬件时，这些数据路径不再是内核的输入，KRR 无需记录，开销接近于零。
- **多核序列化成本降低**：只有执行内核代码的 vCPU 需要序列化，而典型工作负载中大多数时间 CPU 都在执行用户态代码，序列化对端到端吞吐量影响有限。

**Split-Recorder 架构（Figure 2）**：

KRR 采用双记录器联合设计：
- **Guest Recorder（客户机记录器）**：运行在 guest kernel 中，负责记录软件输入（系统调用、用户内存访问、page table entry 更新、非确定性指令如 RDTSC）。
- **Hypervisor Recorder（宿主机记录器）**：运行在 KVM/QEMU 中，负责记录硬件输入（中断、磁盘/网络 DMA、I/O 读结果）。

**RC Spinlock（多核确定性的核心机制）**：

为在多核环境下强制确定性执行顺序，KRR 引入了自定义的 RC spinlock（Replace-Count spinlock）。标准 spinlock 本身是非确定性的（spin 次数依赖调度），KRR 的 RC spinlock 记录锁获取前执行的指令数（cycle count）和获取顺序，并在回放时强制相同的指令计数，确保异步事件（中断、DMA）在精确相同的时间点被注入。

---

## 四、实现细节

**Hypervisor Recorder**：
- 修改 KVM（0.8K LoC）和 QEMU（1.2K LoC），共涉及 7 个文件
- 拦截 KVM 的中断注入函数、PIO/MMIO 仿真函数
- 磁盘 I/O：记录 DMA buffer 数据并与触发指令配对
- 网络 I/O：利用类似 VMware FT 的方式，在设备写入 ring buffer 前 trap vCPU，记录数据和当前指令计数；NAPI 并发访问问题通过 trap 解决
- Kernel-bypass 设备通过 QEMU 参数指定哪些设备输入在 recording 时忽略

**Guest Recorder**：
- 系统调用入口处记录调用号和参数
- 用户内存访问：利用 x86 SMAP 安全机制，用户内存读取只能通过内核固定 API 完成，拦截这些 API 即可完整记录
- Page table entry 更新：instrumentation 访问 PTE 的内核代码，记录 accessed/dirty bit 变化
- 非确定性指令（RDTSC、RDPMC 等）：guest recorder 直接拦截并记录输出，避免 VM exit
- 利用 x86 硬件性能计数器（每核预留 1 个）追踪内核指令数，用于异步事件的时间戳；通过拦截 CPUID 输出将该计数器对 guest 内核屏蔽

**RC Spinlock 与死锁预防**：
- vCPU 进入 kernel mode（系统调用、中断、异常）或从 idle 唤醒时获取 RC spinlock，返回用户态或进入 idle 时释放
- 死锁场景（如持锁线程等待另一持锁线程的资源）通过特殊处理避免

**反向调试（Reverse Debugging）**：
- 回放时周期性拍摄 VM 快照（tagged with 指令计数坐标向量）
- 回退时二阶段执行：加载最近快照 → 向前回放至目标点
- 多核场景使用每 vCPU 指令计数向量（coordinate）唯一标识系统状态

**验证**：成功回放 8,156 个 LTP 测试用例的内核执行，每 1K 指令断言一次寄存器状态一致性。

---

## 五、实验结果

**实验平台**：CloudLab c6420，2× Intel Xeon Gold 6142（16 核），384GB RAM，双口 Intel X710 10GbE NIC

**RQ1：多核工作负载记录开销**

| 工作负载 | 核数 | KRR 慢倍 | VM-RR 慢倍 |
|---------|------|----------|------------|
| RocksDB（随机读） | 2 | 1.01×–1.67× | 2.71×–4.93× |
| RocksDB（随机读） | 4 | 1.06×–2.03× | 5.08×–11.76× |
| RocksDB（随机读） | 8 | 1.52×–2.79× | 8.97×–29.94× |
| 内核编译（make） | 8 | ~1.22× | >8× |
| 内核编译（make） | 32 | 降级（锁争用） | 完全不可用 |

RocksDB 延迟：VM-RR 2.73×–29.99×，KRR 仅 1.01×–2.80×。

**RQ2：Kernel-bypass 工作负载**

| 工作负载 | KRR 开销 | VM-RR 开销 |
|---------|----------|------------|
| RocksDB+SPDK（随机 appender） | 1.49× | 64.51× |
| RocksDB+SPDK（顺序 deletion） | 1.48× | 29.37× |
| Redis+DPDK GET（4 核） | -0.26%（几乎无损） | N/A（不支持） |
| Redis+DPDK SET（4 核） | +1.14% | N/A |
| Nginx+DPDK | 类似 Redis，极低开销 | N/A |

**RQ3：内核 Bug 复现**

| 类别 | 数量 | KRR 成功复现 |
|------|------|-------------|
| 确定性 bug | 6 | 6/6 |
| 非确定性 bug | 6 | 5/6 |
| 高危 CVE | 5 | 5/5 |
| **合计** | **17** | **16/17** |

5 个 CVE 包括：CVE-2024-1086（权限提升）、CVE-2022-0847（Dirty Pipe）、CVE-2022-0185（堆溢出）、CVE-2021-4154（控制流劫持）、CVE-2022-2639（权限提升）。

**RQ4：存储开销**

- Kernel-bypass（SPDK）：KRR 4.8 MB/s，VM-RR 9.4 MB/s（KRR 低 48.9%）
- 普通工作负载（RocksDB）：KRR 53.39 MB/s，VM-RR 8.26 MB/s（KRR 高 6.46×）
  - 但 gzip 压缩后 KRR 降至 6.91× 压缩比，总量 144.52 MB vs VM-RR 464.48 MB

---

## 六、批判性分析

**1. 序列化代价被轻描淡写**

论文将 RC spinlock 的序列化作为标准技术一笔带过，但其实这是核心的性能瓶颈：8 核以上 RocksDB 吞吐量开始下降，32 核场景几乎无法扩展。论文给出的"甜点区域"是 1–8 核，并引用 Azure 8 vCPU 指导方针为其背书，但这是一种相关性论证而非因果推导——Azure 的指导方针是为了其他原因制定的，不能用来为 KRR 的扩展瓶颈辩解。

**2. 存储开销比较不公平**

普通工作负载下 KRR 存储开销是 VM-RR 的 6.46×，但论文随即引入 gzip 压缩数据（6.91× 压缩比），将最终存储量转换为比 VM-RR 更低，而论文并未说明 VM-RR 的数据是否同样经过压缩。这是一处明显的对比不公平。此外，KRR 53.39 MB/s 的写入速率本身就接近许多生产系统存储带宽上限，在长时间持续记录场景下的可行性未作讨论。

**3. 唯一失败 bug 被轻描淡写**

16/17 的 bug 复现率听起来很好，但失败的那 1 个（Bug #8，deadlock 相关的真并行 bug）恰恰是最复杂的并发 bug 类别的代表。论文在 Discussion 中承认 KRR 无法复现需要真并行的 bug，但没有量化这类 bug 在实际内核 bug 数据库中占多大比例，读者无法评估这一限制的实际影响范围。

**4. 初始快照开销未评估**

KRR 在开始记录时需要对内核内存拍摄快照，论文声称这相比 whole-VM 快照更小，但没有给出快照的具体大小、拍摄时间，以及在大内存 VM 上（如 384GB RAM 实验机）快照是否可接受。"未来工作可以用 on-demand-fork 优化"是一句没有量化支撑的承诺。

**5. 单一 Linux 内核版本的局限性**

性能评估主要在 guest Linux 6.1.0 上进行。RC spinlock 需要修改内核自旋锁实现，而不同内核版本的锁路径差异显著，跨版本移植性和性能一致性未作系统评估。

---

## 七、总结

KRR 提出将 record-replay 边界收窄到内核层的"切片 RR"思路，通过 split-recorder 架构（guest 记录软件输入、hypervisor 记录硬件输入）和 RC spinlock 多核序列化机制，在 1–8 核 VM 上将记录开销降低到 VM-RR 的 1/5 至 1/10，kernel-bypass 场景下开销几近于零。在 Linux 内核 bug 复现上，KRR 成功复现了 16/17 个测试 bug，含 5 个高危 CVE。主要局限是 8 核以上扩展性受 RC spinlock 争用制约，以及无法复现严格依赖真并行的并发 bug。KRR 是在生产环境持续记录内核故障的有价值工具，尤其适合 kernel-bypass 驱动的现代数据中心场景。
