# ScaleLFS: A Log-Structured File System with Scalable Garbage Collection for Commodity SSDs

**作者**：Jin Yong Ha (Seoul National University), Sangjin Lee (Chung-Ang University), Hyeonsang Eom (Seoul National University), Yongseok Son (Chung-Ang University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/ha
**源文件**：[[fast2025-ha.pdf]]

---

## 一、背景

Log-structured file system (LFS) 通过将小的随机写聚合为大的顺序写，在 SSD 上获得了显著的性能优势，被广泛应用于现代存储系统（如 Linux 内核中的 F2FS）。然而，LFS 依赖连续的空闲 segment 来执行追加写，随着文件系统老化，可用 segment 逐渐耗尽，必须通过 garbage collection (GC) 回收无效页来释放空间。

现代硬件平台已演进到多核 CPU + 高带宽 commodity SSD 的配置，单块 SSD 可提供数 GB/s 的带宽，多核 CPU 提供了大量并行能力。然而，现有 LFS 的 GC 过程仍然是串行化的、由单线程执行的，无法利用这些硬件资源，导致 GC 期间应用性能骤降，sustained performance 严重不足。

---

## 二、要解决的问题

1. **串行化 GC 过程（one-to-all model）**：现有 LFS（如 F2FS、MAX）使用单个 GC 守护线程处理所有脏 segment，GC 期间应用写带宽下降高达 68×，设备带宽下降 24.8×，大量 SSD 带宽和 CPU 核心处于闲置状态。

2. **并行 GC 的锁竞争瓶颈**：即使简单地增加 GC 线程数（如 P-GC），也会因以下锁竞争导致性能不升反降：
   - `seglist_lock`：victim segment 选择时扫描全局 dirty segment bitmap 需要互斥锁
   - `sentry_lock`：segment metadata（valid page count/bitmap）的更新使用粗粒度信号量
   - `curseg_mutex`：GC I/O 共享单一写入流的分配锁
   - `i_gc_rwsem`：文件级 GC 保护锁，阻止了 page 级别的并行

3. **文件级 GC 粒度过粗**：现有 LFS 在 GC 时对整个文件加锁（file-level protection），同一文件的不同 page 无法被多个 GC 线程同时清理，严重限制并发度。

---

## 三、洞察与设计

**关键洞察**：GC 期间应用线程被阻塞等待 GC 完成，此时多核 CPU 上有大量空闲核心，同时 SSD 设备带宽严重未被利用（实测 GC 时设备带宽仅为峰值的 1/25）。如果能利用这些空闲的 CPU 核心和设备带宽来加速 GC 过程，就能显著缩短应用阻塞时间，提升 sustained performance。

基于此洞察，ScaleLFS 提出了三个核心组件：

### Dedicated Garbage Collector (DGC)
采用 per-core 的专用 GC 线程，每个 DGC 拥有独立的资源：dedicated victim segment、dedicated page buffer (DPB)、dedicated write stream (DWS)。这实现了 one-to-one model（每个 collector 对应自己的资源），消除了 GC 线程间的资源共享竞争。DPB 避免了 page cache 的锁竞争和缓存污染；DWS 使每个 DGC 能独立分配 LBA 无需争抢 `curseg_mutex`。

### Scalable Victim Manager (SVM)
解决 victim segment 选择和 metadata 更新的并发问题：
- **Concurrent Victim Selection (CVS)**：使用 atomic test-and-set 操作在 victim segment bitmap 上实现无锁的并发 victim 选择，多个 DGC 可同时扫描 dirty segment bitmap 并通过原子操作竞争 victim，保证不会选到同一 segment。
- **Loose-Synchronization Update (LSU)**：将 segment metadata 拆分为 valid page bitmap (VPB) 和 valid page count (VPC)，各自独立进行原子更新，消除 `sentry_lock`。代价是可能出现 less-optimal victim selection 和 false-positive GC read，但实验表明这两个副作用影响极小（WAF 增加 ≤3.6%，false-positive read 频率仅 0.006/IO 请求）。

### Scalable Victim Protector (SVP)
用基于 concurrent hash table 的 page 级保护替代 file 级锁 `i_gc_rwsem`。线程通过 CAS 操作将目标 page 插入 hash bucket 的链表来"预订"该 page，不同 page 可被不同 DGC/I/O 线程同时访问，仅在同一 page 上产生冲突时才需等待。这将 GC 粒度从文件级细化到 page 级。

---

## 四、实现细节

- 基于 **F2FS** 在 **Linux kernel 6.0.0** 上实现
- 源代码开源：https://github.com/syslab-CAU/ScaleLFS
- 默认使用 **32 个 DGC**，每个 DGC 选择 M 个 victim（M 为总容量的 0.1%，30GB 分区下为 16 个 segment，7.68TB 分区下为 4096 个 segment）
- DPB 大小为每线程 2MB（与 segment 大小一致），32 DGC 共需 64MB
- SVP 每个 hash bucket 8 bytes，每个 hash element 36 bytes，使用 32 buckets/文件，单文件最多 1444 bytes
- DWS 每个流仅需额外 7 bytes 元数据用于 checkpoint，48 核时 checkpoint 从 192 bytes 增至 528 bytes
- 数据一致性通过 node lock 保证：DGC 和 flush thread 竞争 node lock，通过检查 LBA 是否被更新来判断是否需要跳过写入
- Crash consistency 通过 LFS 已有的 checkpoint 机制（reader-writer lock `cp_rwsem`）保证，VPC 和 VPB 在 checkpoint 时原子持久化

---

## 五、实验结果

**实验平台**：Intel Xeon E5-2650 (2.2GHz, 24 物理核/48 逻辑核)，160GB DRAM，7.68TB Samsung 9A3 SSD。微基准测试使用 30GB 分区 + 8GB DRAM。

### 微基准（FIO random write）

| 指标 | vs F2FS | vs F2FS-L | vs MAX | vs P-GC |
|------|---------|-----------|--------|---------|
| 平均带宽提升 | 3.5× | 2.4× | 4.6× | 7.0× |
| 执行时间缩短 | 71.1% | 58.1% | 78.1% | 85.8% |
| 设备带宽利用提升 | 15.2× | 2.7× | 19.6× | 8.1× |
| P99 延迟降低 | 99.95% | 99.64% | 99.95% | 99.96% |

ScaleLFS 在 GC 期间设备带宽达到 2.9GB/s，接近峰值 3.4GB/s。

### 核心可扩展性
在 2/4/8/16/32/48 核下分别实现 3.4×/3.7×/3.9×/4.4×/5.2×/5.8× 的性能提升，48 核时略有饱和。

### 宏基准（Filebench）

| 工作负载 | 最大吞吐量提升 |
|----------|----------------|
| Fileserver | 30.3% |
| Varmail | 40.6% |
| OLTP | 83.1% |

### 真实应用（MySQL + YCSB）

| YCSB 负载 | 吞吐量提升 | 执行时间缩短 |
|-----------|-----------|-------------|
| Workload A (50% update) | 3.38× | 70.4% |
| Workload B (5% update) | 1.37× | 27.3% |
| Update-only (100% update) | 3.22× | 68.9% |

### 各组件贡献分解（Table 3, 32 核 FIO）

| 配置 | 带宽 | 执行时间 | 解决的锁瓶颈 |
|------|------|---------|-------------|
| Baseline (F2FS-L) | 213.5 MB/s | 577.8s | — |
| SPGC (简单并行) | 98.4 MB/s | 1221.5s | 引入 i_gc_rwsem 21% |
| +SVP | 277.8 MB/s | 444.9s | 消除 i_gc_rwsem，暴露 curseg_mutex 45.7% |
| +DWS | 297.1 MB/s | 412.7s | 消除 curseg_mutex，暴露 sentry_lock 32.8% |
| +LSU | 371.6 MB/s | 331.9s | 消除 sentry_lock，暴露 seglist_lock 31.8% |
| +CVS | 476.9 MB/s | 246.4s | 消除 seglist_lock |
| +DPB | 509.3 MB/s | 236.1s | GC 时间再降 7.8% |

---

## 六、批判性分析

1. **核心前提的局限性被轻描淡写**：ScaleLFS 的关键假设是 GC 期间应用线程被阻塞、CPU 核心空闲。但论文承认（Section 6），在 compute-intensive 或 memory-intensive 应用与 I/O 密集型应用混合部署时，空闲核心可能不存在。作者将适用场景限定为"disaggregated storage servers"和"file servers"，但这大幅缩小了方案的通用性。论文对此讨论仅一页，未给出动态资源分配的解决方案。

2. **微基准与宏基准差距悬殊**：FIO 下提升 3.5×–7.0×，但 Filebench fileserver 仅 30.3%，且论文解释是"fileserver 和 varmail 经常删除文件导致 GC 不频繁"。这实际上说明在 GC 不频繁的正常工作负载下，ScaleLFS 的收益有限。论文对此未做深入分析，没有给出 GC 频率与收益的关系曲线。

3. **CPU 利用率代价**：ScaleLFS GC 期间 CPU 利用率从 ~3% 飙升到 29.1%，是其他方案的 ~10 倍。在共享环境中，这一代价可能影响其他 workload。论文虽在 Section 5.6 用 Redis 做了简单评估（Redis 执行时间增加 9.8%），但仅测了一种非 I/O 密集型负载的搭配。

4. **实验分区大小过小**：微基准使用 30GB 分区（7.68TB SSD 的 0.4%）和 8GB DRAM，人为触发高频 GC。这种极端配置放大了 GC 瓶颈，使得改进显得更加显著。虽然论文在 Figure 9f 做了全盘容量实验，但全盘实验中的改进幅度（快 37 分钟 / 15340 秒 ≈ 2.4% 时间差）远不如微基准惊人。

5. **Loose-synchronization 的副作用评估不充分**：论文声称 WAF 增加"negligible"（YCSB 下 3.6%），但 3.6% 的 WAF 增加在长期运行中会累积为可观的额外写入量，对 SSD 寿命的影响未被讨论。

6. **缺少与更多现代基线的比较**：论文未与 ZNS SSD 上的优化方案做直接比较（声称 out of scope），也未与 IPLFS、ParaFS 做比较（声称需要定制 SSD）。这使得读者无法判断在整体存储系统设计空间中 ScaleLFS 的相对位置。

---

## 七、总结

ScaleLFS 针对 LFS 在 GC 期间 sustained performance 严重下降的问题，提出了一套系统化的并行 GC 方案：per-core dedicated GC、concurrent victim selection、loose-synchronization metadata update、page-level victim protection。通过逐层消除串行化瓶颈中的锁竞争，在多核 + commodity SSD 平台上实现了最高 7× 的 GC 性能提升。该方案最适合 I/O 密集型、GC 频繁触发的场景（如存储服务器），在 GC 不频繁或 CPU 资源紧张的混合部署环境中收益有限。方案的核心贡献在于展示了 LFS GC 可以通过细致的并发设计在纯软件层面大幅扩展，无需定制硬件。
