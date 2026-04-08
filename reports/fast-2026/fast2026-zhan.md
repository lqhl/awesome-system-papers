# Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs

**作者**：Yekang Zhan, Tianze Wang, Zheng Peng, Haichuan Hu, Jiahao Wu, Xiangrui Yang, Qiang Cao（华中科技大学）; Hong Jiang（University of Texas at Arlington）; Jie Yao（华中科技大学）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/zhan
**源文件**：[[fast2026-zhan.pdf]]

---

## 一、背景

Buffered I/O 通过内核 page cache 为应用提供透明、友好的文件访问接口，几十年来一直是主流的 I/O 模式。Page cache 吸收用户读写请求，内部完成数据合并、I/O 对齐、预取和脏页刷写等工作。

随着 NVMe SSD 的快速发展，存储带宽从 PCIe 3.0 时代的不到 3 GB/s 提升到 PCIe 5.0 时代的 10+ GB/s，内存与存储之间的带宽差距已从两到三个数量级缩窄到一个数量级以内。多盘 RAID 配置可进一步将聚合带宽提升到 50+ GB/s。在这样的高带宽存储环境下，page cache 的管理开销已经不再可忽略——它反而成为了 buffered I/O 写性能的瓶颈。

Direct I/O 虽能绕过 page cache 直接利用 SSD 带宽，但对请求的偏移、大小和用户缓冲区地址有严格的对齐约束，增加了编程复杂度，不适用于大量遗留应用。

---

## 二、要解决的问题

论文实验揭示了 buffered I/O 写路径在高带宽 SSD 上的三大性能瓶颈：

1. **C1：page cache 被过度用于缓冲所有写入**。即使在理想条件下（内存充足、关闭后台刷写），buffered I/O 的写带宽仍显著低于 direct I/O（1.10×–4.46×差距）。page cache 的分配、查找、状态维护和 LRU 管理开销已无法被内存的带宽优势抵消。

2. **C2：page 管理的并发性有限，导致内存效率低下**。在高强度写入 + 有限内存的场景下，频繁的页替换导致 XArray 的非可扩展自旋锁（xa_lock）成为瓶颈。脏页刷写过程中每个页需多次获取 xa_lock（dirty → writeback → clean），进一步加剧锁竞争。写吞吐量对内存供给高度依赖（70% 内存时吞吐下降高达 54%）。

3. **C3：partial-page write 的 read-before-write 代价极高**。对于 page cache 中不命中的部分页写入，需先从 SSD 读取整页再更新，延迟是全页写入的 1.51×–84.37×。SSD 的小粒度随机读延迟仍然很高，无法利用 SSD 内部并行性。

现有方案要么优化 page cache（如 ScaleCache、StreamCache），但受限于"全缓冲"架构无法根本突破；要么绕过 page cache（如 direct I/O、SPDK、OrchFS），但牺牲了 buffered I/O 的透明性和兼容性。

---

## 三、洞察与设计

**关键洞察**：在高带宽 SSD 时代，内存相对于 SSD 的带宽优势已不足以抵消 page cache 管理的开销，因此应该将大部分写数据直接发送给 SSD 而非全部缓冲在内存中——只需用内存缓冲 SSD 不擅长处理的小写入和非对齐写入，就能同时获得 buffered I/O 的编程便利性和 direct I/O 的高带宽。

基于此洞察，论文提出 WSBuffer（Write-Scrap Buffering）架构，重构 buffered I/O 的写数据路径：

### 3.1 Scrap Buffer（§3.2）

引入新的内存页结构 scrap-page，取代 page cache 的写缓冲角色：
- 每个 scrap-page 由 128B header + 256KB data-zone 组成（远大于传统 4KB page）
- Header 记录有效数据字节数、数据段数量、对应 SSD ID、刷写状态和索引条目（最多约 19 个不连续数据段）
- 写入时直接放置数据，无需 read-before-write；利用 header 中的索引进行地址重叠数据段的合并
- 批量分配 32 个 scrap-page，header 区和 data-zone 区分离存放，减少内存碎片

### 3.2 Buffer-Minimized Data Access（§3.3）

将用户写请求按大小和对齐拆分：
- 小于阈值（默认 1MB）的写入：全部由 scrap buffer 缓冲
- 大于等于阈值的写入：拆分为 partial-scrap-page 部分（由 scrap buffer 缓冲）和 scrap-page-data-zone 对齐的大块部分（直接发送到 SSD）
- 对齐粒度为 256KB（scrap-page data-zone 大小），确保 SSD 写入始终是大块对齐的，避免文件碎片化
- 读取时：先查 scrap buffer（数据最新），再查 page cache + SSD
- Page cache 变为只读缓存，不再管理脏页

### 3.3 Opportunistic Two-stage Flush（OTflush）（§3.4）

两阶段异步脏数据刷写：
- **Stage-1**：异步从 SSD 读取数据填充 unfilled scrap-page（完成 read-before-write）
- **Stage-2**：将 full scrap-page 写回 SSD
- SSD 忙碌感知：通过 per-SSD Bcount（跟踪在飞 I/O 字节数，阈值 4MB）判断 SSD 是否繁忙，避免向繁忙 SSD 发送刷写请求
- 利用环形队列管理，忙碌时重新入队稍后重试

### 3.4 Concurrent Page Management（§3.5）

分离管理读页和写页，最小化锁竞争：
- **XArray**：仅管理只读 memory-page，不再维护脏页状态，page fault 引起的树更新只阻塞自身线程
- **SXArray**：管理 scrap-page 的索引和删除；删除操作仅修改索引条目为 NULL（用轻量的条目级锁），延迟执行树结构更新
- **Per-scrap-page lock**：细粒度锁管理 scrap-page 状态，使多个 scrap-page 可并发执行写入和 OTflush

---

## 四、实现细节

- 基于 XFS 在 Linux kernel 6.8 上实现，约 4500 行内核代码
- 编译为内核文件系统模块，scrap buffer 与文件系统的交互逻辑类似 page cache 与文件系统的交互
- **fsync()** 实现：查找相关 scrap-page，唤醒专用 fsync 线程执行类 OTflush 刷写；由于高带宽 SSD + OTflush 的预处理，多数 scrap-page 已完成刷写
- 数据持久性和崩溃一致性委托给底层文件系统（如 XFS 的 journaling 机制）
- 延迟存储空间分配：新 scrap-page 不立即分配 SSD 空间，OTflush Stage-2 时选择最空闲的 SSD 分配
- 默认配置：request-size 阈值 1MB，scrap-page data-zone 256KB（8 channels × 16KB SSD-page × 2），OTflush 线程 2 个（Stage-1 和 Stage-2 各 1 个），SSD 忙碌阈值 Bcount = 4MB

---

## 五、实验结果

**实验环境**：2× Intel Xeon Gold 6348（28 cores, 2.60GHz），256GB DDR4，8× Samsung 990 PRO PCIe 4.0 SSD（RAID0，总带宽约 55 GB/s），Ubuntu 22.04，Linux kernel 6.8。

**基线**：EXT4、F2FS、BTRFS、XFS、ScaleCache-XFS（kernel 5.4）。

| 实验 | WSBuffer 提升 | 说明 |
|------|-------------|------|
| Full-page write 延迟 | 1.03×–3.29× | 小写入靠 scrap buffer 批量分配优势，大写入直接发 SSD |
| Partial-page write 延迟 | 1.70×–82.80× | 消除 read-before-write，小写入优势极为显著 |
| 对比 Direct I/O / AutoIO | 1.59×–231.28× | Direct I/O 受 RMW 拖累，AutoIO 两端都不占优 |
| 多线程随机写吞吐 | 1.21×–3.91× | 线程增多时 WSBuffer 增长更快 |
| Filebench Fileserver | 1.23×–2.51× | 写密集混合负载 |
| Filebench Webproxy（读密集）| 1.07×–4.37× | 省出的内存加速了读缓存 |
| Filebench Varmail | 1.06×–2.84× | 元数据密集，大粒度 scrap-page 加速 fsync |
| YCSB + LevelDB | 1.32×–2.02× | KV store 场景 |
| GridGraph PageRank | 1.09×–4.37× | 图处理，混合读写 |
| Nek5000 科学计算 | 1.74×–3.09× | 585GB 写入，内存密集 HPC 场景 |
| CPU 利用率 | 降低 3.2%–28.4% | 80%+ 写数据走 DMA，节省 CPU |
| 内存消耗 | 实际应用中仅 0.34%–1.67% | 大写直发 SSD，小写被后续覆写回收 |

---

## 六、批判性分析

1. **单一文件系统实现的代表性**。WSBuffer 仅在 XFS 上实现和评估。虽然论文声称架构独立于特定文件系统，但承认"data-access mechanism 和 OTflush 需要针对不同文件系统进行工程适配"。在 EXT4、F2FS 等文件系统上的实际效果和移植复杂度未经验证。

2. **ScaleCache 的对比公平性存疑**。ScaleCache 运行在 Linux kernel 5.4，而 WSBuffer 和其他基线运行在 kernel 6.8。论文自己承认 kernel 5.4 的 XFS 缺少 folio module、delayed logging 等后续优化，导致 ScaleCache-XFS 在某些实验中甚至不如 kernel 6.8 的原生 XFS。这使得与 ScaleCache 的对比缺乏可信度。

3. **崩溃一致性和 fsync 语义被轻描淡写**。论文将数据持久性和崩溃一致性完全委托给底层文件系统，但 scrap buffer 引入了新的中间数据状态（unfilled scrap-page、延迟分配的存储空间）。论文未讨论在 scrap buffer 和 SSD 之间的数据一致性窗口、crash 后的恢复路径，也未进行任何崩溃恢复测试。

4. **OTflush 的 SSD 忙碌感知过于粗糙**。Bcount 阈值固定为 4MB，论文承认"SSD 性能行为复杂且动态"，但仅提供了这个 coarse-grained 的感知方式。在混合读写负载下，Bcount 能否准确反映 SSD 实际忙碌程度未经充分分析。

5. **实验配置倾向于展示最优结果**。微基准测试中禁用了 page flushing 并提供了充足内存，这对基线文件系统不利（它们依赖 flushing 释放内存），而 WSBuffer 天然减少了内存使用。虽然后续实验补充了有限内存的测试，但主要结果仍基于理想配置。

6. **256KB 对齐粒度的适用性**。scrap-page data-zone 大小为 256KB，依赖于具体 SSD 的通道数和页大小（8 channels × 16KB）。不同 SSD 配置下该参数需要调整，论文未讨论参数选择错误时的性能退化。

7. **读性能在高 scrap-page 占用时存在回退**。Webproxy 实验中，禁用 OTflush 时 WSBuffer 略逊于 XFS，因为需要"两次页索引查找"（SXArray + XArray）。这意味着在 OTflush 来不及清理 scrap-page 的场景下，读性能可能显著下降。

---

## 七、AI Infra / MLSys 视角

1. **对 AI 训练/推理 checkpoint 的启发**。大模型训练中 checkpoint 写入是典型的大块、突发写操作。WSBuffer 的"大写直发 SSD + 小写缓冲"策略天然适合这个场景：checkpoint 的主体数据可直接绕过 page cache 写入 SSD 阵列，而元数据等小写入通过 scrap buffer 处理。这比完全切换到 direct I/O（如 3FS）更透明，不需要修改应用代码。

2. **GPU Direct Storage 的互补性**。WSBuffer 聚焦于 CPU 侧的 buffered I/O 优化，而 GPU Direct Storage 关注 GPU 到 SSD 的直接路径。在 CPU-GPU 混合 I/O 场景（如数据预处理走 CPU、模型权重走 GPU）中，两者可能互补。WSBuffer 的 SSD 忙碌感知机制（Bcount）在多路径 I/O 下需要扩展以考虑 GPU 发起的 I/O。

3. **分布式训练的数据加载管道**。数据加载器通常使用 buffered I/O 读取训练数据。WSBuffer 将 page cache 变为只读缓存后，省出的内存可用于扩大预取窗口或增加 data loader worker 的并发度。不过需注意 WSBuffer 当前仅优化写路径，读路径保持不变。

4. **可行的延伸方向**：
   - 将 scrap buffer 的思想扩展到 NVM/CXL 场景——用持久内存作为 scrap buffer 的载体，同时获得持久性和低延迟
   - 在 KV store（如 RocksDB compaction）场景中，WSBuffer 的大块对齐写入策略可能减少写放大
   - 探索 WSBuffer 与 io_uring 的集成，进一步降低系统调用开销

---

## 八、总结

WSBuffer 重构了 buffered I/O 的写数据路径，核心思想是将大部分写数据直接发送给高带宽 SSD，仅用新设计的 scrap buffer 缓冲小写入和非对齐写入，配合两阶段异步刷写和并发页管理机制。在 8 块 PCIe 4.0 SSD 的 RAID0 配置上，WSBuffer 相比 EXT4/F2FS/BTRFS/XFS 等主流文件系统实现了最高 3.91× 吞吐提升和 82.80× 延迟降低，同时减少了 CPU 利用率和内存消耗。其主要局限在于仅在 XFS 上验证、崩溃一致性分析不充分、以及与 ScaleCache 的对比不够公平。该工作适用于写密集型应用在高带宽 SSD 环境下的性能优化，对 AI 训练 checkpoint、HPC 科学计算等场景有直接参考价值。
