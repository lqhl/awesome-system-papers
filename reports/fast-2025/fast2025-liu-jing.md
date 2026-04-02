# Fast, Transparent Filesystem Microkernel Recovery with Ananke

**作者**：Jing Liu (Microsoft Research), Yifan Dai, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau (University of Wisconsin–Madison)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/liu-jing
**源文件**：[fast2025-liu-jing.pdf](../../papers/fast-2025/fast2025-liu-jing.pdf)

---

## 一、背景

微内核架构将文件系统等子系统运行在独立的用户态进程中，与传统宏内核相比能够提供更好的故障隔离和可扩展性。近年来，uFS 等高性能微内核文件系统在数据中心环境中展现出优异性能。然而，当文件系统服务进程崩溃（称为 p-crash，即 process crash）时，如何让上层应用透明地继续运行是一个尚未充分解决的问题。

在宏内核中，文件系统崩溃意味着整个系统崩溃（s-crash），所有应用同时丢失进度，因此传统的 s-crash recovery（如 journaling）只需保证磁盘一致性即可。但在微内核中，文件系统崩溃后操作系统和应用仍在运行，应用期望文件系统状态完整恢复——包括尚未持久化的缓冲更新和打开的文件描述符等临时状态。这种应用期望的状态与磁盘实际持久化状态之间的差异被称为 **state gap**。

---

## 二、要解决的问题

1. **State gap 恢复**：p-crash 后，文件系统内存中缓冲的写入、打开的文件描述符、未持久化的元数据更新全部丢失。仅靠 s-crash recovery 无法弥补 state gap，导致应用看到不一致的数据或错误。

2. **性能与正确性的矛盾**：一种简单方案（uFS-Sync）是强制每次操作后刷盘消除 state gap，但这导致写密集型工作负载性能下降 3-6 倍，完全不可接受。

3. **内存损坏的鲁棒性**：现有系统（Membrane、Rio、Otherworld、TxIPC）在恢复时复用失败进程的地址空间或内核状态，面对内存损坏（硬件/软件 bug 导致）时无法保证恢复正确性。

4. **重启的可靠性**：复用失败进程的资源进行恢复可能因资源本身已损坏而导致恢复失败。需要一种干净重启机制。

5. **错误的及时检测**：需要在损坏数据返回给应用或持久化到磁盘之前尽早发现错误。

---

## 三、洞察与设计

**关键洞察**：在微内核架构中，文件系统进程崩溃时整个机器仍然存活——操作系统内核可以充当理想的恢复协调者，而服务进程内存中残留的关键信息（如正在执行的系统调用及其参数）可以被捕获并用于精确重建 state gap，无需将所有更新强制刷盘。

基于这一洞察，Ananke 设计了以下核心机制：

**P-Crash Log（p-log）**：一个内存中的循环缓冲区，每个 CPU 核心独立维护一份。在正常执行路径上，每完成一个文件系统操作就将系统调用信息记录到 p-log。p-log entry 包含操作类型、参数、返回值，以及一个 `targets_status` 位图来追踪该操作对 fd、inode、path↔inode 三类抽象的修改是否仍属于 state gap。当 fsync 或后台同步使数据持久化，或文件描述符关闭时，对应 bit 被清除。p-log 通过 replication 和 checksum 保护，是崩溃后唯一被信任的内存区域。

**AIM（Act-Ignore-Modify）算法**：基于 p-log 中每个 entry 的 `targets_status`，决定恢复时如何处理每个记录的操作：
- **Ignore**：所有关联的 fd 已关闭且 inode 更新已持久化（全部 bit 清零）
- **Act**：直接按原始形式重放
- **Modify**：部分效果已持久化，需要将操作降级为只恢复剩余 state gap 的形式（如 write → lseek）

**Kernel-coordinated Speculative Restart**：预先投机性地创建一个被动的备用进程，提前完成耗时的设备连接初始化（约 2.9 秒）。当主进程崩溃时，OS 内核协调将 p-log 和 IPC 连接从旧进程转移到新进程，新进程使用干净的地址空间执行恢复。

**Lightweight Checksum**：对所有内存中的语义状态（fd、metadata、data bitmap 等）添加轻量级 CRC 校验，在每次读写时验证/更新，用于尽早检测内存损坏并触发 fail-fast。

---

## 四、实现细节

Ananke 基于开源的 uFS 文件系统实现，新增约 **4K 行代码**。

**P-log 实现**：每个 worker 线程维护私有 p-log，避免并发竞争。p-log entry 在操作完成后写入，采用精心设计的 4 步写入协议保证 exactly-once 语义：(1) 写系统调用信息；(2) 写 descriptor（含 ipc_idx）；(3) 设置消息环的完成标志位；(4) 清除 ipc_idx。步骤间插入 compiler barrier 防止重排序。

**P-log Replication**：维护两份 p-log 副本，主副本更新后再更新副本。恢复时先验证主副本 CRC，失败则使用副本。

**CRC 保护**：inode 使用嵌入在已有 padding 空间中的 1-byte CRC；datablock bitmap、inode bitmap、dentry block 每 32 字节一个 1-byte CRC，利用 CPU 硬件加速指令（Intel ISA-L）。

**Speculative Restart**：通过 `PTHREAD_MUTEX_ROBUST` 属性的共享 mutex 实现主进程崩溃时对备用进程的通知。主进程崩溃后由信号处理程序（sigaltstack）执行数据页救援，将 p-log 引用的数据页保存到 tmpfs。

**P-log 垃圾回收**：基于 AIM 判断——当 entry 满足 Ignore 条件时可回收。阈值设为 4MB，触发时可选择 GC-NoSync（仅回收可回收项）或 GC-Sync（无可回收项时触发后台 sync）。

---

## 五、实验结果

**实验平台**：128GB RAM，AMD 2.80GHz CPU，Samsung PM173X NVMe SSD（原始延迟约 70μs），CloudLab 机器。

### 透明恢复正确性

| 工作负载 | 操作数 | uFS (S_OK) | Ananke (S_OK) |
|---------|--------|-----------|---------------|
| Sort | 5327 | 部分 F_OK/F_BAD | 5327 (100%) |
| CpDir | 82 | 部分 F_OK/F_BAD | 82 (100%) |
| Unzip | 77 | 部分 F_OK/F_BAD | 77 (100%) |
| SQLite | 154 | 部分 F_OK/F_BAD | 154 (100%) |
| LevelDB | 1997 | 部分 F_OK/F_BAD | 1997 (100%) |

- 总计 **30,000+** 故障注入实验（包括每个系统调用之后和期间的注入），Ananke 全部实现透明恢复（S_OK）

### 内存损坏恢复

| 内存区域 | 测试数 | 成功重启 | 元数据正确 | 数据正确 |
|---------|--------|---------|----------|---------|
| Stack | 15 | 100% | 100% | 73% |
| Heap | 2547 | 100% | 100% | 99.8% |
| DMA-mem:Metadata | 375 | 100% | 100% | 100% |
| P-log | 436 | 100% | 100% | 100% |

### 性能开销

- **写密集型**（copy、LevelDB-Load）：无 CRC/Replication 时 < 4%，完整保护时 ~7%
- **其他工作负载**：完整保护时 < 2%
- uFS-Sync 对比：写密集型慢 3-6 倍
- Membrane 风格重放：copy 工作负载慢 3.4 倍

### 内存开销

- P-log：4MB/核心（含副本共 8MB/核心）
- CRC：< 0.02%（相对工作负载内存）

### 恢复时间

- 所有情况下 **≤ 400ms**
- LevelDB 恢复时间：Load 114ms，YCSB-A 171ms，YCSB-C 102ms
- 得益于 speculative restart 隐藏了 2.9 秒的设备重连延迟

---

## 六、批判性分析

1. **故障模型假设**：Ananke 假设 p-log 的 logging 代码本身正确、信号处理程序执行时栈完好。实验也证实了这一弱点——stack 区域损坏时数据恢复正确率仅 73%（15 个案例中 4 个失败）。虽然作者提出可用 eBPF 将 rescue 过程移到内核空间，但这尚未实现。

2. **共享消息环不受保护**：Ananke 明确不保护应用与文件系统之间的共享消息环（App-Worker MsgRing），理由是"应用本身也可能损坏它"。但这意味着内存损坏如果恰好发生在消息环上，恢复无法保证正确性，这是一个非平凡的攻击面/故障面。

3. **确定性错误不处理**：Ananke 假设故障是瞬时的，同一错误不会在重放时再次发生。对于确定性 bug（如特定输入触发的 bug），Ananke 无法处理，需要额外技术（如作者自己的 Shadow Filesystem 工作）。

4. **工作负载覆盖面有限**：实验主要使用单线程或少量并发的简单应用（sort、cp、unzip、SQLite、LevelDB）。缺乏真实数据中心多租户、高并发场景下的压力测试。多进程实验仅在 300 个随机点注入故障，覆盖面较浅。

5. **POSIX 语义覆盖**：论文排除了 mmap、chown、chmod 等操作的讨论（Figure 4 注释），但这些在实际应用中非常常见。特别是 mmap 会引入应用直接修改内存映射文件的场景，state gap 的追踪将更加复杂。

6. **单设备限制**：基于 uFS 的架构限制，Ananke 针对单 NVMe 设备。现代存储系统通常涉及多设备、RAID 或分布式存储，扩展性尚不清楚。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint/Recovery 启发**：Ananke 的 p-log + AIM 机制可以启发 AI 训练中的轻量级 checkpoint 方案。当前大模型训练的 checkpoint 开销巨大，如果能借鉴"只记录 state gap 的源头（操作日志）而非完整状态快照"的思路，可能减少 checkpoint 数据量。

2. **微内核式 AI 推理服务**：大规模 AI 推理服务（如 vLLM）中，推理引擎进程崩溃时如何快速恢复而不丢失正在处理的请求，与 Ananke 解决的问题高度相似。speculative restart（预先创建备用进程并初始化设备连接）的思路可直接迁移到 GPU 推理服务——预先初始化 CUDA context 和模型权重加载，在主进程崩溃时快速切换。

3. **分布式训练的进程级容错**：当前分布式训练中单个 worker 崩溃通常导致整个训练作业重启。Ananke 的"p-crash vs s-crash 分离"思想可以应用于训练框架——单个 worker 崩溃时，只恢复该 worker 的状态（从最近的 gradient 状态和通信 buffer 中重建），而非重启整个集群。

4. **KV Cache 恢复**：推理系统中 KV cache 是重要的临时状态，类似于文件系统的 page cache。如果 KV cache 服务进程崩溃，Ananke 风格的操作日志可以帮助快速重建正在服务的请求的 KV cache 状态。

---

## 八、总结

Ananke 是首个为微内核文件系统实现完整、高性能 p-crash 透明恢复的系统。通过 p-log 记录操作日志追踪 state gap、AIM 算法智能决策重放策略、kernel-coordinated speculative restart 实现快速干净重启、以及轻量级 CRC 保护关键数据结构，Ananke 在 30,000+ 故障注入实验中实现了无损恢复，恢复时间 ≤ 400ms，常规路径性能开销 < 2%（大多数工作负载）。其主要局限在于 POSIX 语义覆盖不完整（如 mmap）、确定性 bug 无法处理、以及信号处理程序对栈完整性的依赖。
