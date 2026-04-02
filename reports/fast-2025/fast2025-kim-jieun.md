# OPIMQ: Order Preserving IO Stack for Multi-Queue Block Device

**作者**：Jieun Kim (KAIST), Joontaek Oh (University of Wisconsin–Madison), Juwon Kim (KAIST), Seung Won Yoo (KAIST), Youjip Won (KAIST)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/kim-jieun
**源文件**：[[fast2025-kim-jieun.pdf]]

---

## 一、背景

现代存储设备（如 NVMe SSD）通过多命令队列（multi-queue）和多通道/多路（multi-channel/way）并行架构实现了巨大的性能提升，从 HDD 时代的 300 IOPS 提升到 NVMe 设备的 550K IOPS。然而，许多关键应用（文件系统日志、日志结构文件系统、数据库事务等）需要保证 **存储顺序（storage order）**——即一组数据块按特定顺序变为持久化。

当前保证存储顺序的标准做法是 **Transfer-and-Flush**：在发出下一个写请求前，等待前一个写请求的数据传输完成并刷入持久化存储。这种做法极大地抵消了现代存储设备的并发和并行优势。实验显示，使用 Transfer-and-Flush 时随机写吞吐量仅为理想值的 3.4%。

Linux 内核自 4.16 起采用多队列块设备层（blk-mq），每个 CPU 核心绑定一个请求队列。存储设备侧的 NVMe 接口可暴露多达 64K 个提交队列/完成队列对。这种多队列架构使得跨队列的存储顺序保证成为一个复杂的系统性问题。

---

## 二、要解决的问题

1. **Transfer-and-Flush 开销过大**：传统 EXT4 使用 flush + FUA 写保证存储顺序，fsync() 延迟中 63% 的时间花在 FUA 写上，严重限制吞吐量。

2. **单队列方案无法扩展**：BarrierFS 等先前工作仅支持单命令队列，无法利用多队列并行性。Wait-on-Dispatch 配合单队列只能达到理想吞吐量的 47%。

3. **流内存储顺序被破坏（Intra-stream）**：Linux 的 work-stealing 机制会将线程从一个核心迁移到另一个核心（实测 JBD 线程约每 120ms 迁移一次），导致同一 stream 的写请求被分散到不同队列（stream bounce），epoch 被分裂（epoch split），存储顺序无法保证。

4. **流间存储顺序难以维护（Inter-stream）**：不同线程的写请求之间存在顺序依赖（如应用线程写 dirty pages 必须在 JBD 线程写 journal commit block 之前持久化），而它们运行在不同核心、使用不同队列。实测 EXT4 compound transaction 的流间依赖度平均为 17。

5. **已有多队列方案的局限**：HORAE 将所有流合并为单一全局流，对无关请求施加不必要的顺序约束；ccNVMe（MQFS）让每个线程独立提交事务，无法使用 compound transaction，导致 flush 命令泛滥、无法扩展。

---

## 三、洞察与设计

**关键洞察**：存储顺序的保证可以从"数据块实际持久化的物理顺序"解耦为"FTL 映射表更新的逻辑顺序"——只要 FTL 按正确的 epoch 顺序更新映射表，即使写回缓存中的数据块以任意顺序刷入闪存，从主机视角看存储顺序仍然是正确的。

基于这一洞察，OPIMQ 设计了四个关键组件：

1. **Epoch Pinning**：解决流内存储顺序问题。将请求队列从绑定 CPU 改为绑定线程，同一 epoch 的有序写请求始终进入同一请求队列，即使线程被 work-stealing 迁移到其他核心。仅在 epoch 结束后才更新当前请求队列（CRQ）。

2. **Dual-Stream Write**：解决流间存储顺序问题。引入一种特殊写请求，同时携带两个 `<stream id, epoch id>` 对，从而同时属于两个 stream。前驱 stream 的写请求被标记为 dual-stream write，其 secondary stream id 指向后继 stream。Many-to-one 依赖被分解为多个 one-to-one 依赖。

3. **Order-Preserving Mapping Table Update**：OPFTL 中，epoch 经历 active → closed → durable → mapped 四个状态。映射表更新仅在前驱 epoch 达到 mapped 状态后才执行，确保映射表反映正确的存储顺序。不可立即更新的映射信息暂存于 delayed mapping list。

4. **Sibling-Aware Delayed Mapping**：针对 dual-stream write，在两个 stream 的 delayed mapping list 中各插入一条互相引用（sibling）的条目。只有当两个 stream 的前驱 epoch 都达到 mapped 状态后，才更新映射表——确保流间顺序。

**文件系统接口**：OP-EXT4 提供 `fbarrier()` 和 `fdatabarrier()` 作为 `fsync()` 和 `fdatasync()` 的顺序保持版本，发出所有命令后立即返回，不等待持久化完成。

---

## 四、实现细节

- **内核版本**：在 Linux 5.18.18 上实现。
- **Stream/Epoch 标识**：在 `struct bio` 中定义 stream id 和 epoch id。有序写的 stream id = 进程 id；无序写的 stream id = 0。每个 stream 在 `task_struct` 中维护 epoch counter。
- **NVMe 命令扩展**：利用 NVMe 命令对象中 8 字节未使用空间存储两对 `<stream id, epoch id>`。使用 barrier write 命令（在写命令中设置 barrier flag），替代单独发送 cache barrier 命令，节省队列空间和延迟。
- **Dual-stream write 实现**：在 `struct bio` 中增加一个指向 secondary stream 的 `task_struct` 指针（单流写时为 NULL）。
- **OPFTL 实现**：每个 stream 对象维护 epoch 集合、最近持久化 epoch（RPE）和 delayed mapping list。每条 delayed mapping 为 32 字节 `<LPN, PPN, epoch id, sibling>`。
- **Crash consistency**：使用 CrashMonkey 工具验证，生成 1,000 个 crash state 进行测试，OP-EXT4 全部通过。
- **开源**：https://github.com/ESOS-Lab/OPIMQ.git

---

## 五、实验结果

**实验平台**：DELL PowerEdge R740XD（2×Intel Xeon Gold 6230，共 40 核），Samsung 980 Pro NVMe SSD（2TB），Linux 5.18.18。由于 980 Pro 不支持 order-preserving FTL，加入 1.05% 性能惩罚模拟 OPFTL。

### 吞吐量（Docker 容器场景）

| 工作负载 | 容器数 | OPIMQ vs EXT4 | OPIMQ vs BarrierFS-SQ | OPIMQ vs MQFS |
|---------|--------|---------------|----------------------|---------------|
| varmail | 40 | 1.1× | 3.0× | 5.2× |
| varmail | 450 | 1.8× | 1.3× | 6.4× |
| dbench | 40 | 2.8× | ~1× | 6.1× |
| dbench | 600 | 1.5× | 1.1× | 20× |
| sysbench | 40 | 2.9× | 1.4× | — |
| sysbench | 400 | 2.6× | 1.4× | 1.8× |

### fsync() 延迟

| 指标 | OPIMQ | EXT4 |
|------|-------|------|
| 4KB 随机写 fsync() 延迟 | 2.2 ms | 6.7 ms（3× 于 OPIMQ）|
| T_FUA 开销 | 0 ms | 4.2 ms（占 EXT4 fsync 总延迟 63%）|

### 尾延迟（msec，40 容器）

| 工作负载 | 平均 EXT4/OPIMQ | P99.99 EXT4/OPIMQ |
|---------|----------------|-------------------|
| varmail | 12.7 / 4.1 | 346.6 / 162.2（2.1×）|
| dbench | 11.8 / 3.6 | 55.2 / 17.1（3.2×）|
| sysbench | 6.9 / 2.7 | 22.6 / 14.8（1.5×）|

### OPFTL 开销

在 Cosmos OpenSSD 上实测，OPFTL 相比 page mapping FTL 仅有 1.05% 的吞吐量下降，地址转换延迟相同（2.65 μs）。

### Epoch Pinning 影响

99.99% 的 epoch 仅包含一个请求，epoch split 极其罕见（varmail 中仅 6 次，dbench/sysbench 中 0 次）。启用 Epoch Pinning 后无显著性能开销，队列负载分布均匀。

---

## 六、批判性分析

1. **OPFTL 验证规模受限**：OPFTL 仅在 Cosmos OpenSSD（单核、8 通道、230GB）上以 5 个 stream 验证，作者声称"扩展到 200 个 stream 开销也不会显著变化"，但未提供实测数据。单核 FTL 不存在锁竞争这一结论不能推广到多核 SSD 控制器。

2. **980 Pro 模拟而非真实 OPFTL**：主实验使用加 1.05% 惩罚的普通 SSD 模拟 order-preserving FTL，这无法反映真实 OPFTL 在高并发、多 stream 下的延迟分布和尾延迟行为。1.05% 是从低并发 Cosmos 板测得的，外推到 40 核高并发场景的有效性存疑。

3. **仅验证 EXT4 一种文件系统**：论文声称 OPIMQ 是 filesystem agnostic，但仅移植并评测了 EXT4。F2FS、XFS 等文件系统的 journaling 模型差异较大，移植难度和收益均未量化。

4. **MQFS 对比的公平性**：论文指出 MQFS 不日志文件系统元数据，crash consistency 存疑，又将其作为性能对比基线，这种"既质疑其正确性又拿来比性能"的做法在方法论上不太严谨。

5. **Epoch Pinning 的锁竞争分析不充分**：论文提到 Epoch Pinning 使请求队列可被多核访问，依赖自旋锁保护。但 99.99% 的 epoch 仅含一个请求意味着 Epoch Pinning 几乎不生效，无法说明其在 epoch 较大（含多个请求）时的锁竞争表现。

6. **应用场景局限于 journaling**：Inter-stream order 的实现假设系统中只有一个 "following stream"（如 JBD 线程），这是一个较强的假设。对于更复杂的多流依赖模式（如分布式存储引擎），该设计可能不适用。

7. **缺少与 io_uring 等现代 IO 路径的讨论**：Linux IO 栈正在向 io_uring 等异步提交机制演进，论文未讨论 OPIMQ 与这些新路径的兼容性。

---

## 七、总结

OPIMQ 通过 Epoch Pinning、Dual-Stream Write、Order-Preserving Mapping Table Update 和 Sibling-Aware Delayed Mapping 四个机制，在多队列 IO 栈中实现了存储顺序保证，同时充分利用多队列并行性。核心思路是将存储顺序的保证从物理数据刷写顺序转移到 FTL 映射表更新顺序。在 EXT4 上的实现（OP-EXT4）相比原版 EXT4 在 varmail、dbench、sysbench 上分别取得 2.9×、2.8×、2.9× 的吞吐量提升，fsync() 延迟降低至原来的 1/3。主要局限在于 OPFTL 的真实硬件验证规模较小，以及 inter-stream order 的实现假设仅适用于单一 following stream 的场景。
