# Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery

**作者**：Yaotian Cui, Zhiqi Wang（The Chinese University of Hong Kong）；Renhai Chen（Tianjin University）；Zili Shao（The Chinese University of Hong Kong）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，Boston, MA，July 7–9, 2025）
**链接**：https://www.usenix.org/conference/osdi25/presentation/cui
**源文件**：[osdi25-cui.pdf](../../papers/osdi-2025/osdi25-cui.pdf)

---

## 一、背景

F2FS（Flash-Friendly File System）是专为闪存存储设计的日志结构文件系统，在 Android 设备中广泛应用。它采用顺序写区域（out-of-place update）存储文件元数据和数据，利用多通道 IO 并行性，并通过热/温/冷数据分离实现优化。

在崩溃恢复领域，EXT4 等原地更新文件系统已有成熟的 JBD2 等日志机制，但 F2FS 作为异地更新文件系统，其 inode 位置不固定，不能直接套用这些方案。目前 F2FS 依赖粗粒度 checkpoint 机制做崩溃恢复，而 checkpoint 在 Android 设备上的长尾延迟和数据丢失问题在生产环境中日益突出。

---

## 二、要解决的问题

F2FS checkpoint 机制存在三个核心问题：

**问题1：时间开销大**
Checkpoint 触发时会阻塞所有文件读写，直到所有脏数据/元数据写回磁盘。实测最坏情况延迟高达 293ms（unlink-4KB 场景），checkpoint 时间在总执行时间中占比 17%~47%，对用户交互和系统响应不可接受。

**问题2：数据与元数据丢失**
Checkpoint 由脏元数据阈值或超时（默认 60 秒）触发，两次 checkpoint 之间的修改在崩溃时会丢失。fsync() 不触发 checkpoint，导致已 flush 的文件数据也可能丢失。实测 F2FS 数据丢失率高达 9.1%。

**问题3：Roll-forward 恢复不一致**
F2FS 的 roll-forward 恢复机制依赖对 inode/dnode 的 tag 标记，但在 no-barrier 和 POSIX fsync 模式下，IO 栈的乱序导致 inode/dnode tag 与文件数据的持久化顺序无法保证，可能出现新 inode 指向旧数据的不一致状态。

**直接套用 JBD2 的困难**
- 若只 journal in-memory inode，因 F2FS 中 on-disk 文件系统元数据（SIT/NAT/SSA）位置会随 out-of-place 更新而变化，无法正确恢复 inode
- 若同时 journal 文件系统元数据和 inode，开销过大（数据需写两次）
- JBD2 的集中式设计导致严重的锁竞争（占 journal 时间 24%~30%）和 journal 周期切换等待（占 7%~16%）

---

## 三、核心设计

本文提出 **F2FSJ**，一套专为 F2FS 设计的有序日志（ordered journal mode）机制，包含四个核心创新：

**1. 基于元数据变更的日志（Metadata-change-based Journaling）**
只记录元数据的变更内容（changed fields），而非整个 4KB 元数据页。这显著降低了 IO 和存储开销，并减少了文件操作因 journal commit 被阻塞的时间。此设计是总体性能提升中贡献最大的部分（约 49%）。

**2. 去中心化 Per-inode 日志列表（Decentralized Per-inode Log Lists）**
将 journal log 嵌入每个 inode，每个 inode 维护独立的 per-inode log list，记录与该 inode 相关的所有元数据变更（包括 SIT/NAT/SSA 条目）。与 JBD2 集中式全局 log list + 全局锁方案相比，锁竞争降低 18.8%~78.2%，各 inode 间互不干扰，扩展性更好（贡献约 21%）。

**3. 基于 Epoch 的数据/控制面解耦（Epoch-based Data/Control-plane Decoupling）**
将每个 journal 周期绑定到一个 epoch。数据面（per-inode log lists 记录元数据变更）与控制面（epoch 中只注册 inode ID）解耦：
- 控制面只在 epoch 中登记 inode 编号，journal commit 时再汇总所有变更
- 当 data flush 触发当前 epoch commit 时，可立即开启新 epoch 接收新操作，几乎无等待
- 相比 JBD2 数据/控制耦合导致的 journal 周期切换等待降低 86.8%~92.0%（贡献约 14%）

**4. Fast-forward-to-latest Journal Apply**
在 journal apply 阶段，对同一元数据的多次跨 epoch 变更合并为一次写入。利用 F2FS out-of-place 更新不修改旧数据的特性，引入新页状态 `F2FSJ_Dirty`（区别于 `Dirty` 和 `Uptodate`），实现跨 epoch 的元数据去重应用，消除大量小写操作（贡献约 16%）。

---

## 四、实现细节

- 基于 Linux Kernel 5.15 的 F2FS 实现，约 **3,000 行 C 代码**，已开源
- 新增多种 log type 和 log record 结构，覆盖不同文件操作类型（含文件大小、NAT/SIT/SSA 条目等变更）
- 修改 `struct f2fs_inode_info`，添加 per-inode log list 和 `e2l_mapping` 映射表（epoch-to-log，数组实现），epoch 用链表管理
- 独立内核线程处理 journal commit（维护 COMMIT epoch 链表）；另一内核线程处理 journal apply，基于 journal 文件空余空间的高低水位线触发/停止
- Journal 文件以连续磁盘区域存储，round-robin 使用，默认大小 256MB（仅占 256GB SSD 的 0.1%，而 JBD2 需要 1GB）
- GC（垃圾回收）前需先完成所有待 apply 的 journal records，避免 inode 迁移导致地址失效
- 页状态扩展：`F2FSJ_Dirty` 标志某 in-memory 元数据页正参与另一 ongoing journal commit，不可用于 apply，需直接用 journal record 更新磁盘

**崩溃恢复流程**：系统启动时检测到未 apply 的 journal records，按 epoch 顺序逐条 apply；利用 journal record 中的 SIT/NAT/SSA 元数据定位旧 inode，应用变更并更新到磁盘。out-of-place 更新保证旧数据完整，崩溃时重放不会导致不一致。

---

## 五、实验结果

**实验环境**
- Desktop：Intel i9-10850K（19核 3.6GHz），64GB DRAM，256GB Samsung 980 Pro PCIe 4.0 NVMe SSD，ClearLinux + Kernel 5.15
- ARM 嵌入式板：Rockchip RK3588S（Cortex-A76×4 + Cortex-A55×4，8nm），16GB LPDDR4，128GB eMMC，Linux 5.10 + Android 12

**对比系统**：F2FS-F2FSJ、F2FS-CKPT、EXT4（+JBD2，有序模式）、XFS（元数据日志）

| 指标 | 结果 |
|------|------|
| Checkpoint 时间减少 | F2FSJ journal 时间为 F2FS checkpoint 的 1/2.4x ~ 1/4.9x |
| 尾延迟 | F2FS-CKPT 尾延迟比 F2FSJ 高三个数量级 |
| 平均延迟降低 | mkdir -23%、rmdir -35%、create-4KB -13%、unlink-4KB -33% |
| 吞吐量提升（元数据密集） | vs F2FS-CKPT：1.11x~1.29x；vs EXT4（部分）：1.37x~2.0x |
| 吞吐量提升（小文件密集） | vs F2FS-CKPT：1.14x~1.69x |
| 数据恢复率 | F2FSJ ≈ 100%，F2FS-CKPT（60s）丢失率达 9.1% |
| 锁竞争时间减少 vs JBD2 | 18.8%~78.2% |
| Journal 周期切换等待减少 vs JBD2 | 86.8%~92.0% |
| Journal Apply 时间减少 vs JBD2 | 68.4%~95.3% |
| 存储占用 | F2FSJ 256MB（JBD2 的 25%） |
| 内存开销 | +1.4%（3.50~3.55GB vs 3.45~3.50GB） |
| CPU 开销 | +1.8%（4.8% vs 3%） |
| Android 实测（Twitter/Facebook） | vs F2FS-CKPT 减少 28.5%/47.3%，vs EXT4 减少 41.9%/62.0% |
| CrashMonkey 一致性测试 | 全部通过 |

---

## 六、批判性分析

**1. 异地更新假设的核心依赖**
F2FSJ 的 fast-forward-to-latest 的无冲突性依赖于 F2FS out-of-place 更新"旧数据不被修改"的特性。然而 F2FS 的 GC（垃圾回收）会迁移 inode 和数据，论文虽提到"GC 前先 apply 所有 journal records"，但未深入分析 GC 期间崩溃的边界情况，也未给出 GC 与 journal apply 并发的正确性证明。

**2. 恢复时间的双面性**
论文展示 F2FSJ 崩溃恢复时间在文件数 ≤4K 时优于 F2FS-CKPT，但文件数达 8K 时恢复时间是 F2FS-CKPT 的 1.4 倍。这意味着在文件密集型 Android 应用场景下，F2FSJ 的恢复时间可能劣于现有方案，而这一结果在摘要和结论中被轻描淡写。

**3. EXT4 胜出场景被低调处理**
在 create-empty、unlink-empty 和 RanWR_W 等场景中，EXT4 性能优于 F2FS-F2FSJ，原因是 F2FS NAT 的查询开销和锁竞争（论文承认 NAT 竞争导致 Webproxy 场景落后于 EXT4 和 XFS），但作者对此语焉不详，未提供系统性优化方向。

**4. Journal 文件大小配置缺乏理论依据**
论文固定使用 256MB journal 文件，并用高低水位线控制 apply。但在极端写入负载下 journal 文件是否会溢出（即 apply 速度跟不上写入速度）？论文未给出最坏情况分析或动态扩容机制。

**5. 实验规模与工业场景的差距**
最大测试规模为 8K 文件、6 小时长期测试，而实际 Android 设备上的文件数量通常达数百万。Aged filesystem 测试虽然使用了 Geriatrix，但仅针对元数据密集和小文件场景，未覆盖混合真实负载下的老化行为。

**6. 与 F2FS 自身 roll-forward 机制的对比不完整**
论文将 F2FSJ 与 F2FS roll-forward 对比了恢复时间，但对于 Problem3（roll-forward 不一致性）只做了定性描述，未给出量化对比，也没有说明 F2FSJ 是否完全解决了 no-barrier 模式下的不一致问题。

---

## 七、总结

F2FSJ 是首个针对 F2FS 的有序日志机制，通过元数据变更级日志、去中心化 per-inode log list、epoch 数据/控制面解耦和 fast-forward-to-latest apply 四项设计，将 checkpoint 时间压缩 4.9 倍、平均延迟降低 35%，同时将数据丢失率降至接近 0。系统已在 Linux 内核实现约 3,000 行代码，适用于 Android 等闪存存储场景。主要局限在于大量文件时恢复时间反而增加、部分场景（高并发删除创建）性能落后于 EXT4，以及 GC 并发场景的边界情况处理有待深入验证。
