# Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery

**作者**：Yaotian Cui, Zhiqi Wang (The Chinese University of Hong Kong); Renhai Chen (Tianjin University); Zili Shao (The Chinese University of Hong Kong)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/cui
**源文件**：[osdi25-cui.pdf](../../papers/osdi-2025/osdi25-cui.pdf)

---

## 一、背景

F2FS（Flash-Friendly File System）是一种日志结构文件系统，广泛应用于 Android 系统，因其 append-only 写入和冷热数据分离等特性而特别适配闪存存储。尽管 Android 设备有电池供电，但低温环境导致的异常关机、系统更新引发的崩溃等场景使得崩溃恢复仍然至关重要。

传统文件系统（如 EXT4）使用 JBD2 等成熟的 journaling 机制实现细粒度崩溃恢复，但 F2FS 作为 out-of-place-update 文件系统，其崩溃恢复一直依赖粗粒度的 checkpointing 机制。Checkpointing 将所有 dirty 的数据和元数据一次性刷盘，形成 checkpoint pack 作为快照，恢复时回滚到最近的 checkpoint。

---

## 二、要解决的问题

F2FS checkpointing 存在三个关键问题：

1. **时间开销大**：Checkpoint 触发时会阻塞所有文件写入，直到所有 dirty 数据和元数据全部刷盘。实验显示 checkpoint 时间占总执行时间的 17.2%–47.3%，worst-case 延迟高达 293ms，严重影响用户交互体验。

2. **恢复不完整**：F2FS checkpointing 只能恢复到最近一次 checkpoint 的状态，两次 checkpoint 之间的数据和元数据修改可能丢失。实验表明 F2FS 的恢复率仅为 90.9%，远低于 journaling 方案的 98.3%–98.8%。

3. **无法直接套用 in-place-update 文件系统的 journaling 方法**：在 EXT4 等 in-place-update 文件系统中，inode 位置固定，可以先 journal 再 apply 或恢复。但 F2FS 的 inode 位置因 out-of-place-update 而不固定——仅 journal in-memory inode 无法正确恢复（因为 on-disk 的文件系统元数据已过时）；而同时 journal 文件系统元数据和 inode 又会导致数据被写两遍的巨大开销。

---

## 三、洞察与设计

**关键洞察**：F2FS 的 out-of-place-update 特性意味着旧数据在更新后不会被原地覆盖，而是保留在原位。这一特性使得只需 journal 元数据的"变化量"（changes）而非完整的元数据页即可实现正确的崩溃恢复——即使崩溃发生，旧数据仍然完好，可以通过按 epoch 顺序逐条 apply 变化记录来恢复到一致状态。

基于此洞察，F2FSJ 提出了四个核心设计：

### 1. Metadata-change-based Journaling
不 journal 整个元数据页，只 journal 元数据的变化内容（delta），采用 ordered journal mode：先 flush 数据，再 commit 对应的元数据变化。这显著降低了 I/O 和存储开销。

### 2. Decentralized Per-inode Log Lists
将 journal log 分散嵌入到每个 inode 中，每个 inode 维护自己的 log list，记录该 inode 相关的所有元数据变化（包括 SIT、NAT、SSA 的变更）。相比 JBD2 的全局集中式日志，大幅降低了锁竞争。

### 3. Epoch-based Data/Control-Plane Decoupling
每个 journal period 关联一个 epoch。数据平面（per-inode log lists 中的元数据变化记录）和控制平面（epoch 中注册的 inode 信息）解耦。当数据 flush 触发当前 epoch 的 commit 时，可以立即创建新 epoch 来接收新的元数据变化，几乎零等待时间完成 journal period 转换。而 JBD2 由于数据/控制平面耦合，必须等待当前 running transaction 的所有文件操作完成后才能开启新的 transaction。

### 4. Fast-forward-to-latest Journal Apply
在 apply journal 时，对同一元数据的多次跨 epoch 更新合并为一次写入。通过引入 F2FSJ_Dirty 页面状态，在 apply 时检查 in-memory 元数据页状态：若为 Dirty 则直接 flush；若为 Uptodate 则跳过（已被 flush）；若为 F2FSJ_Dirty 则直接 apply journal 记录。这避免了大量小写入。

---

## 四、实现细节

- 基于 Linux Kernel 5.15 的 F2FS 实现，总代码修改约 **3,000 行 C 代码**
- 定义了各种文件操作的 log 类型和结构体，包含操作类型和元数据变化内容
- 修改 `struct f2fs_inode_info` 实现 per-inode log lists 和 e2l_mapping 映射表
- 每个 log list 使用 journal ticket counter 记录正在进行的文件操作
- e2l_mapping 表用数组实现，epochs 用链表实现
- 使用一个内核线程执行 journal commit（维护 COMMIT epochs 链表），另一个内核线程执行 journal apply（基于 journal 文件空闲空间的高低水位线触发和停止）
- Journal 文件使用连续的磁盘区域，可配置大小（实验中为 256MB），以 round-robin 方式使用
- GC（垃圾回收）可能迁移 inode 和数据，因此 GC 前需 apply 所有 journal 记录
- 崩溃恢复时按 epoch 顺序逐条读取和 apply journal 记录，由于 out-of-place-update 保留旧数据，即使恢复过程中再次崩溃也能保证一致性
- 源码已开源：https://github.com/10033908/F2FS-J

---

## 五、实验结果

**实验平台**：
- 桌面：Intel i9-10850K (19 cores, 3.6 GHz), 64GB DRAM, Samsung 980 Pro 256GB NVMe SSD
- 嵌入式：Rockchip RK3588S (4×A76 + 4×A55), 16GB LPDDR4, 128GB eMMC, Android 12

**对比系统**：F2FS-CKPT（默认 checkpointing）、EXT4（JBD2）、XFS

| 指标 | 结果 |
|------|------|
| Checkpoint 时间缩减 | F2FSJ 比 F2FS-CKPT 快 1.7×–4.9× |
| 尾延迟改善 | F2FS-CKPT 的尾延迟比 F2FSJ 高三个数量级 |
| 平均延迟降低 | mkdir 23%, rmdir 35%, create-4KB 13%, unlink-4KB 33% |
| 元数据密集型吞吐量 | F2FSJ 比 F2FS-CKPT 高 1.11×–1.29× |
| 小文件密集型吞吐量 | F2FSJ 比 F2FS-CKPT 高 1.14×–1.69× |
| 崩溃恢复率 | F2FSJ 98.3%–98.8% vs F2FS 90.9% |
| 恢复时间 | F2FSJ 比 F2FS roll-forward 快 5.4×–6.8× |
| 内存开销 | 仅增加约 1.4%（3.50–3.55GB vs 3.45–3.50GB） |
| CPU 开销 | 仅增加约 1.8%（4.8% vs 3.0%） |
| 存储开销 | Journal 文件 256MB（SSD 总容量的 0.1%），为 JBD2 的 25% |
| 可扩展性 | 多线程下 F2FSJ 吞吐量最优（16 线程 mkdir 比 F2FS-CKPT 高 1.72×） |
| ARM 嵌入式板 | 元数据密集型比 F2FS-CKPT 快 1.36×–1.83×，Twitter/Facebook 延迟分别降低 28.5%/47.3% |

各组件贡献分析（metadata-intensive workloads 的性能提升来源）：
- Metadata-change-based journaling: ~49%
- Per-inode log lists: ~21%
- Data/control-plane decoupling: ~14%
- Fast-forward-to-latest: ~16%

---

## 六、批判性分析

1. **数据密集型负载改善有限**：在 Seq_write、Rand_write、Seq_read 等大文件顺序/随机 I/O 场景下，F2FSJ 与 F2FS-CKPT 带宽几乎相同。论文在摘要中强调"reduce latency by up to 35%"，但这主要在 metadata-intensive 场景成立。对于实际 Android 使用中占比很大的媒体文件读写、应用数据读写等场景，改善可能不显著。

2. **恢复时间在大规模场景下的退化**：当文件数量增加到 8K 时，F2FSJ 的恢复时间比 F2FS-CKPT 增加了 1.4×。论文没有讨论更大规模（如数十万文件）下恢复时间的趋势。在真实 Android 设备上，应用可能创建大量小文件，F2FSJ 的恢复时间可能成为瓶颈。

3. **GC 的约束被轻描淡写**：所有 journal 记录必须在 GC 之前 apply 完毕，这意味着 GC 可能被延迟。在存储空间紧张的场景下（Android 设备常见），GC 频繁触发，这一约束可能严重影响性能。论文未对此场景进行实验评估。

4. **Journal 文件空间固定为 256MB**：论文使用 round-robin 方式使用 journal 文件，当 journal 空间不足时需要触发 journal apply 来回收空间。在高负载下，journal apply 的速度是否跟得上 journal 产生的速度？论文虽然提供了高低水位线机制，但缺乏对 journal 空间压力场景的深入分析。

5. **Webproxy 场景下 F2FS-F2FSJ 不如 EXT4 和 XFS**：论文将此归因于 F2FS 的 NAT/SIT 锁开销，但这恰恰说明 F2FSJ 没有从根本上解决 F2FS 元数据管理的扩展性问题——只是把 journaling 层面的锁竞争消除了，底层元数据结构的锁竞争仍在。

6. **CrashMonkey 验证的覆盖范围有限**：只测试了 rename 和 create/delete 两种工作负载的崩溃一致性，没有覆盖更复杂的场景如 concurrent writes + truncate + crash、journal apply 过程中崩溃后的 GC 等。

---

## 七、总结

F2FSJ 是首个针对 F2FS ordered journal mode 的 journaling 方案，通过 metadata-change-based journaling、去中心化 per-inode log lists、epoch-based data/control-plane decoupling 和 fast-forward-to-latest journal apply 四个设计，有效消除了 F2FS checkpointing 的长尾延迟并提供了细粒度崩溃恢复。在 metadata-intensive 和 small-file-intensive 工作负载下表现优异，但在数据密集型场景和大规模文件恢复时改善有限。核心约束在于 GC 与 journal apply 的交互以及底层 F2FS 元数据结构本身的扩展性瓶颈未被解决。
