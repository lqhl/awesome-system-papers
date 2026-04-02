# DJFS: Directory-Granularity Filesystem Journaling for CMM-H SSDs

**作者**：Seung Won Yoo, Joontaek Oh (UW-Madison), Myeongin Cheon, Bonmoo Koo (KAIST), Wonseb Jeong, Hyunsub Song, Hyeonho Song, Donghun Lee (Samsung Electronics), Youjip Won (KAIST)
**会议**：USENIX FAST 2025
**链接**：https://www.usenix.org/conference/fast25/presentation/yoo
**源文件**：[[fast2025-yoo.pdf]]

---

## 一、背景

现代服务器核心数快速增长（数百核），大量应用（KV 存储、数据库、邮件服务器等）并发运行在同一文件系统分区上，journaling 模块成为性能瓶颈。与此同时，CXL（Compute Express Link）技术带来了新型存储设备 CMM-H（CXL Memory Module-Hybrid）SSD，支持以 cache-line 粒度（64 字节）通过 CXL.mem 协议访问，也支持通过 CXL.io 的传统块级 I/O。CMM-H 的延迟低至 0.6μs（cache-line 级），带宽也远高于传统 SSD，但其性能高度依赖内置 DRAM cache 命中率——随机写吞吐量在工作集超过内置 DRAM 大小时可下降 74 倍。

已有多种文件系统 journaling 优化方案（per-core、per-partition、per-file、concurrent commit），但在 CMM-H 这种高速存储上，transaction lock-up 问题变得更加突出，而此前的工作大多忽略了这一问题。

---

## 二、要解决的问题

1. **Transaction lock-up 问题被放大**：当 journal commit 延迟因更细粒度的 journaling（从 4KB 到 64B）而缩短时，lock-up 时间反而占比更高（从 6% 增至 18%）。原因是 commit 提前开始，但内存中的文件操作延迟不变，lock-up 结束时间不变，导致 lock-up 区间变长。在单一全局 running transaction 的设计下，lock-up 阻塞所有元数据更新。

2. **细粒度 journaling 收益不如预期**：将 JBD 从 block 粒度改为 cache-line 粒度后，commit 延迟降低约 50%，但整体吞吐量仅提升不到 20%。

3. **已有多 transaction 方案各有缺陷**：per-core 方案 transaction conflict 频繁；per-partition 方案需改变磁盘布局；per-file 方案粒度太小，无法受益于 group commit；concurrent commit 方案增加 commit 延迟。

---

## 三、洞察与设计

**关键洞察**：通过分析 8 个广泛使用的应用（Exim、RocksDB、SQLite、MySQL、Git、Mercurial、VMware、HDFS）的文件更新模式，发现三个共性属性——(D) 每个应用/线程在自己的专属目录下工作，(U) 文件内容更新伴随文件的创建/删除（即需要更新父目录），(S) 相关文件属于同一目录。这意味着**目录是 journaling transaction 的天然边界**：以目录为粒度定义 transaction，既能将相关操作聚合在同一 transaction 中享受 group commit 收益，又能让不同目录的 transaction 独立运行、并行 commit，从根本上减少 lock-up 和 conflict。

基于此洞察，DJFS 的核心设计包含三大机制：

1. **Path-based Transaction Selection**：根据文件操作的路径参数确定所属目录，将更新的元数据插入该目录的 running transaction。对于 hard link 等多链接文件，以路径参数指定的目标目录为准。

2. **Transaction Coalescing**：当单个文件操作（如 `rename()`）涉及多个目录时，将多个目录的 transaction 合并为一个，由 inode 号较小的作为 master，其他为 subordinate。通过按 inode 号升序获取 spinlock 避免死锁。

3. **Transaction Conflict Resolution**：区分 R-to-R（running 对 running）和 R-to-Cmt（running 对 committing）两类冲突。R-to-R 通过 coalescing 解决；R-to-Cmt 通过延迟 running transaction 的 commit 直到 committing transaction 持久化来保证顺序。每个 inode 维护两个 container transaction 指针用于冲突检测。

DJFS 仅 journal 文件元数据（inode、filemap、directory entry），使用 bitmap-based differential logging（64 字节粒度），通过 CXL.mem 写入 journal 区域，检查点通过 CXL.io 块级写入完成。

---

## 四、实现细节

- **基于 EXT4 + Linux Kernel 5.18** 实现。

- **Log Record 设计**：三种元数据类型：inode（256B 物理日志）、index block 和 directory block（64B 差分日志 + bitmap）。仅写入实际修改的 cache-line 区域，节省 journal 空间。

- **In-memory Transaction 结构**：包含 log record 集合、关联的 page cache entry 集合、inode 号、outstanding operation 计数、subordinate transaction 列表、conflict transaction 列表。每个 transaction 结构 240 字节。

- **On-disk Transaction**：transaction header + log records + commit record（8B magic number），存储在单一环形 journal 区域中。

- **Journal 区域大小**：仅 100MB（远小于 Z-Journal 的 172GB 或 JBD 的 1GB），设计上足够小以被 CMM-H 内置 DRAM 缓存，保证 cache-line 级访问性能。

- **Checkpoint**：checkpoint 时暂停创建 running transaction，先提交所有 running transaction，再将脏元数据页写回原位。

- **Crash Recovery**：扫描 journal 区域 → 识别已 commit 但未 checkpoint 的 transaction → checkpoint → 重建文件系统元数据。使用 shadow counter 机制保证计数器的 crash consistency。

---

## 五、实验结果

**实验平台**：88 核 Intel Sapphire Rapids（2×44）、128GB 内存、2TB CMM-H 原型设备。

**对比方案**：JBD(mem)、FastCommit、Z-Journal、CJFS、iJournaling。

### 吞吐量（80 线程）

| Workload | DJFS vs FastCommit | DJFS vs JBD(mem) | DJFS vs Z-Journal | DJFS vs CJFS | DJFS vs iJournaling |
|---|---|---|---|---|---|
| Varmail | 4.5× | 4.3× | 4.3× | 3.1× | 5.7× |
| MDTest | 2.5× | — | — | — | — |
| Exim | 3.7× | — | — | — | — |
| RocksDB-fillsync | ~0.95× (略低于 FastCommit) | — | — | — | — |

### Transaction Lock-up 时间（Varmail, 80 线程）

| 方案 | Lock-up |
|---|---|
| FastCommit | 211μs |
| JBD(mem) | 120μs |
| CJFS | 65μs |
| Z-Journal | 39μs |
| DJFS | 26μs |
| iJournaling | 0.2μs |

### fsync() 延迟（Varmail, 80 线程）

| 方案 | 延迟 | Transaction 大小 |
|---|---|---|
| DJFS | 0.2ms | 1.6KB |
| iJournaling | 0.16ms | 5.2KB |
| FastCommit | 0.56ms | 1.8KB |
| JBD(mem) | 0.9ms | 18.3KB |
| CJFS | 3.6ms | 324.0KB |
| Z-Journal | 8.3ms | 32.6KB |

### 内存消耗

DJFS transaction 结构占 10.4–22.1MB（比 JBD/CJFS 大两个数量级，但作者认为在服务器级内存下可接受）。Log record 内存小于 250KB。

### Crash Recovery

通过 CrashMonkey 验证，涵盖 rename、link、creat/unlink/mkdir/rmdir 等场景，每个场景 1000 个 test case 全部通过。恢复时间约 2.5 秒（Varmail, 80 线程）。

---

## 六、批判性分析

1. **RocksDB 上 DJFS 略差于 FastCommit**：论文承认在 RocksDB-fillsync 上 DJFS 比 FastCommit 慢约 5%，原因是 shadow copy 的冗余创建。但论文对此轻描淡写——RocksDB 是极为重要的实际工作负载，这一回退不可忽视。DJFS 的优势集中在元数据密集型工作负载（Varmail、MDTest、Exim），而对数据密集型 workload 的适用性存疑。

2. **三个属性的普适性存疑**：论文基于 8 个应用总结出 Property D/U/S，但这些应用大多是传统服务端软件。现代容器化微服务、数据库分片、分布式存储等场景下，多个进程/线程可能交叉访问同一目录，Property D 不一定成立。论文未讨论这类场景下的退化行为。

3. **CMM-H 原型设备的代表性**：全部实验基于 Samsung CMM-H 原型设备，这是一个尚未大规模商用的 CXL SSD。论文未讨论 DJFS 在其他 CXL 设备（如 CXL memory expander）或未来 CXL 3.0 设备上的适用性。结论的可推广性受限于单一硬件平台。

4. **内存开销被低估**：DJFS 的 transaction 结构占用高达 22MB，虽然绝对值不大，但比 JBD 大两个数量级。论文用"given the size of main memory in the server"一笔带过，但未分析在目录数更多的真实场景（如包管理器解压数万个目录）下的扩展趋势。

5. **Checkpoint 的串行化代价**：DJFS checkpoint 时需要暂停所有 running transaction 的创建并提交所有 running transaction——这实质上是一个全局 barrier。论文未量化 checkpoint 对持续吞吐量的影响，尤其是在 journal 区域仅 100MB 的情况下，checkpoint 频率可能较高。

6. **Z-Journal 在 RocksDB 上 panic**：论文提到 Z-Journal 在 RocksDB 上出现 deadlock/panic 而无法测试，但仍在其他 workload 上与之比较。这使得对比的完整性存疑。

---

## 七、AI Infra / MLSys 视角

1. **Edge AI 场景的启发**：论文提到 AI applications at edge devices 作为动机之一。在 edge 设备上运行 LLM 推理时，模型权重的加载、KV cache 的持久化、checkpoint 的写入都涉及大量文件系统元数据操作。DJFS 的 per-directory transaction 思路可以为 edge AI 的存储栈优化提供参考。

2. **CXL 存储在 AI 基础设施中的潜力**：CMM-H 这类支持 cache-line 粒度访问的 CXL SSD，可以用于扩展 GPU/CPU 的内存容量（如 KV cache offloading、tensor swapping）。DJFS 揭示了一个关键问题：naive 地使用更细粒度 I/O 不一定带来性能提升，系统软件层面的重新设计（如 transaction 粒度选择）同样重要。这对设计 CXL-aware 的 AI 存储系统有借鉴意义。

3. **可迁移的设计思路——workload-aware transaction 划分**：DJFS 通过分析应用访问模式来选择 transaction 粒度的方法论，可以迁移到 AI training checkpoint 系统。例如，分布式训练中不同 rank 的 checkpoint 文件天然隔离，可以用类似 per-directory 的方式并行 commit，减少 checkpoint 写入对训练迭代的阻塞。

4. **Future work 方向**：(a) 将 DJFS 的 per-directory journaling 思路应用于 AI 推理引擎的模型文件管理（多模型并发加载/卸载）；(b) 研究 CXL SSD 上的 checkpoint/restore 优化，利用 cache-line 级访问减少 checkpoint 粒度；(c) 探索 DJFS 在容器化 AI 工作负载（多个模型服务共享文件系统）下的性能表现。

---

## 八、总结

DJFS 提出以目录为粒度的文件系统 journaling 方案，通过 path-based transaction selection、transaction coalescing 和 conflict resolution 三大机制，在 CMM-H CXL SSD 上实现了 per-directory 的并行 journal commit。在元数据密集型工作负载上相比 FastCommit 提升 2.5×–4.5×，核心优势在于大幅减少 transaction lock-up 和 conflict。主要局限是在数据密集型工作负载（RocksDB）上无优势甚至略有回退，且对 CMM-H 硬件特性依赖较强，内存开销和 checkpoint 全局 barrier 的扩展性需进一步验证。
