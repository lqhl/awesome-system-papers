# Fast and Synchronous Crash Consistency with Metadata Write-Once File System

**作者**：Yanqi Pan, Wen Xia（通讯作者）, Yifeng Zhang, Xiangyu Zou, Hao Huang（哈尔滨工业大学深圳校区）；Zhenhua Li（清华大学）；Chentao Wu（上海交通大学）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/pan
**源文件**：[osdi25-pan.pdf](../../papers/osdi-2025/osdi25-pan.pdf)

---

## 一、背景

持久内存（Persistent Memory, PM）技术——如 Intel 3D-XPoint Optane 和 CXL-SSD——具备接近 DRAM 的访问延迟和类似存储介质的持久性。PM 可以通过 CPU load/store 指令（DDR-T 等协议）绕过块层直接访问，并具备持久缓冲区（如 Intel XP Buffer），一旦数据到达 PM 接口即可视为持久化（约 50–300ns）。

这些特性使 PM 文件系统得以追求**同步崩溃一致性**（synchronous crash consistency）：每次文件操作在返回时就已经持久化，无需应用层主动调用 fsync。这对于数据库（如 PostgreSQL 历史上的 fsync 问题）和严格的 NFS 协议场景尤为重要。

然而，现有 PM 文件系统在实现同步崩溃一致性时，仍沿用针对慢速磁盘设计的方法论，造成大量小型、随机、有序的元数据 I/O，严重浪费了 PM 的高带宽。

---

## 二、要解决的问题

### 现有方案的本质缺陷

现有 PM 文件系统的同步崩溃一致性方案分两类：

1. **额外写入类（JFS/CK）**：日志文件系统（PMFS、NOVA 的 journal 部分、SplitFS）将元数据备份到 journal，产生冗余写；事务 checksum（CK）虽消除了一次 ordering point，但仍保留多次随机、无序的元数据原地更新。

2. **有序写入类（LFS/SSU）**：日志结构文件系统（NOVA）以 append 方式写入元数据，避免冗余，但需要 copy-based GC 来回收失效空间；同步软更新（SquirrelFS）避免了 GC，但仍需要在 inode、dentry 等多个元数据对象上顺序发出有序的小 I/O。

作者通过对 PMFS、SplitFS、NOVA 的实测分析（6 种工作负载）发现：

- 三种文件系统分别将 **22.9%–76.5%、63.8%–97.4%、11.3%–75.5%** 的总 I/O 时间花在元数据处理上；
- 随机小元数据 I/O 导致 PM 持久缓冲区（256-byte XP Line）的命中率低，产生 **2.8× I/O 放大**；
- 有序 metadata I/O 引入了等待（ordering point），降低 I/O 并发度；
- GC 在大文件场景下进一步恶化（NOVA 的 GC 占比高达 ~38%）；
- 现有 PM 文件系统实际写带宽不足 PM 理论上限的 **50%**。

**核心 insight**：现有方案都在多个独立的元数据对象（inode、dentry、log entry 等）上分别发出 I/O，这与"最小化元数据 I/O 和 ordering point"的目标根本冲突。

---

## 三、核心设计

### WOFS 模型（Metadata Write-Once File System）

WOFS 的核心思想是：**为每次文件操作生成专属的、checksum 保护的元数据包（package），并以单次 ordering point 一次性写入**。

具体而言：
- 每个 package 包含操作所需的全部元数据字段（相当于 JFS 的 J_M）和一个 header（相当于 J_C，含 magic number、类型、时间戳和 CRC32 checksum），利用事务 checksum 方案以单次 PCOMMIT 写入：`J_M | J_C`。
- 数据写操作先持久化数据块，再写 package，即 `D → J_M | J_C`。
- 崩溃时，通过检查 package checksum 来发现不完整写入并丢弃，从而实现崩溃一致性。

这样，**每次元数据操作只有 1 个 ordering point、约 1 次元数据 I/O**，对比现有方案有 3~N 次的开销（见 Table 1）。

### 四大原子 Package 设计

WOFS 将 Linux 的 15+ 文件系统操作归纳为 CRUD 语义，抽象出 4 种原子 package：

| Package | 大小 | 适用操作 | 主要内容 |
|---------|------|---------|---------|
| Create pkg | 256B | create, link | 64B 静态属性 + 128B（parent ino, linked ino, name） + 64B（parent 属性变更 + header） |
| Write pkg | 64B | write, fallocate | extent 索引 + inode 时间/大小变更 |
| Attr pkg | 64B | chown, chmod 等 | inode 属性变更 |
| Unlink pkg | 64B | rm, unlink | parent 和被删 inode 的属性变更 |

复合操作（如 rename = link + unlink）通过在 package header 中加入 forward-pointer 链接子 package，并赋予额外的 compound 类型标记来保证原子性。

### Package Translation Layer（PTL）

Package 颠覆了传统的 inode/dentry 数据结构，WOFS 引入 **PTL** 来将 package 解析为兼容的传统元数据对象，供上层 VFS 使用：
- **Inode Table**：全局 hash table，将 ino 映射到内存中的 inode 视图；
- **W-node / C-node**：分别维护 write package 的 extent 列表（文件数据索引）和 create package 的 name 列表（目录项索引）；
- PTL 为纯 volatile 结构，在挂载时通过扫描 package 重建，无需持久化（除了用于快速 recovery 的粗粒度 bitmap）。

### 非日志布局与空间回收

WOFS 采用**非日志布局**：package 和数据块以 malloc 方式分散分配于整个 PM，彻底避免了 LFS 必须使用的 copy-based GC。失效的 package（如被 unlink 覆盖的 create pkg）通过 reuse（直接重新分配）回收，不需要数据迁移。

### Coarse Persistence（CP）：快速恢复

为在崩溃后快速定位所有 package，WOFS 引入**粗粒度持久化**：
- 将 package 组织在 4KiB 的 pkg-group 中，每种 package 类型独立一个 pkg-group；
- 一个 bitmap 记录已分配 pkg-group 的地址（一个 bit 对应一个 pkg-group）；
- 新分配 pkg-group 时，bitmap 更新与 package 写入并发执行（`P | m_cp`），不加 ordering point，通过语义正确性保证安全；
- 恢复时只需扫描 bitmap 和对应 pkg-group，无需全 PM 扫描。

---

## 四、实现细节

作者在 **Linux kernel 5.1.0** 上实现了 WOLVES 原型，代码规模 **12,000+ 行 C 代码**。

**空间管理**：两级分配器（tl-allocator），每个 CPU 管理独立的 PM 区域（PM 总量 / CPU 数），用红黑树维护空闲块列表，减少跨 CPU 竞争。

**PTL 实现**：inode table 为带细粒度 per-bucket 锁的全局 hash table；data list（W-node 链表）和 dent list（C-node 链表）以 per-CPU 方式管理，减少锁竞争；上层 file/directory 结构通过 per-file inode lock 保护。

**Intel PM 优化**：
- **Huge Allocation（HA）**：合并小连续 I/O，利用 PM 顺序带宽优势；
- **Read Ahead（RA）**：预读 PM 数据，提升读并发度；
- **vmovntdq（AVX）集成**：解决内核中 movnti 无法完全利用 PM 写带宽的问题（WOLVES-AVX）；
- **带宽调节（bwr）**：采样 I/O 延迟，当延迟超过 3000ns 时插入 delay，缓解高并发下的 PM 硬件竞争。

**可移植性**：WOLVES 还被移植到 CXL-SSD 内存语义模拟平台，验证了 WOFS 模型的通用性。

---

## 五、实验结果

**实验平台**：Intel Optane DIMM，单设备写带宽约 2.26 GiB/s，读带宽约 6.6 GiB/s。

**对比基线**：PMFS（JFS 代表）、NOVA（LFS 代表）、SplitFS（CK/JFS+checksum 代表）、EXT4-DAX、XFS-DAX、MadFS（用户态 PM 文件系统）

### FIO I/O 性能（单线程，4KiB/IO）

| 工作负载 | WOLVES 达到 PM 带宽比例 | vs NOVA | vs PMFS |
|---------|----------------------|---------|---------|
| 顺序写 SW（32GiB） | 97.3%–99.1% | 1.65–9.44× | 1.65–9.44× |
| 随机写 RW（32GiB） | — | 最高 9.44× | — |

### 尾延迟（顺序写，4KiB/IO，单线程）

| 百分位 | WOLVES | NOVA | PMFS | SplitFS |
|--------|--------|------|------|---------|
| 99% | 3.16 μs | 7.12 μs | 6.00 μs | 4.24 μs |
| 99.9% | 12.84 μs | 19.38 μs | 21.00 μs | 951.09 μs |
| 99.99% | 18.92 μs | 23.27 μs | 329.4 μs | 1125.58 μs |

SplitFS/MadFS 在高百分位出现严重尾延迟（偶发的 in-kernel 元数据访问），WOLVES 表现稳定。

### Filebench 宏基准（操作吞吐量，单线程）

| 工作负载 | WOLVES vs MadFS |
|---------|----------------|
| Fileserver | 14.4× |
| Varmail | 61.4× |
| Webserver | 9.14× |
| Webproxy | 35.8× |

### RocksDB（1M KV pairs，无预分配）

WOLVES 在写密集负载（FillSeq, FillRnd, AppdRnd, UpdRnd）上分别达到 569.2、393.8、462.0、430.3 MB/s，实现对 NOVA 的 **1.20–6.73×** 提升。

### 崩溃恢复时间

| 场景 | NOVA | DR | DR-OPT | WOLVES |
|------|------|-----|--------|--------|
| FIO-32G 大文件 | 24.2s | 70.1s | 60.4s | **2.61s** |
| Fileserver | 2.48s | 71.9s | 45.8s | **3.99s** |
| Webserver | 2.52s | 70.5s | 43.1s | **2.75s** |

最坏情况（256GiB PM 满载，~6000 万文件）：WOLVES 只需扫描约 10.9% 的 PM 空间，恢复时间约 **21.6 秒**。

### 元数据 I/O 缩减

WOLVES 相比 PMFS 和 NOVA，每操作元数据 I/O 减少 **70%–17.3×**。

---

## 六、批判性分析

**1. PM 市场前景的不确定性**  
全文以 Intel Optane DIMM 为核心平台，但 Intel 已于 2022 年宣布放弃 Optane 业务。论文虽提及 CXL-SSD 作为延伸，但实验主体仍是 Optane。WOFS 模型对 CXL-SSD 的适配性仍需进一步验证，特别是 CXL-SSD 在延迟和带宽上与 Optane 有量级差异。

**2. 单线程为主的实验设置**  
论文的核心性能数据（RocksDB、Filebench 吞吐、I/O breakdown）大量以单线程结果为主，而多线程性能（图 7）显示 WOLVES 在 ≥9 线程时出现明显性能下降（需要 bandwidth regulator 干预）。作者将此归因于 PM 硬件竞争，但并未与 NOVA-RELAX（放宽一致性的 NOVA）做公平的多线程对比。实际生产环境多为高并发场景，单线程占优的意义需谨慎解读。

**3. PTL 的内存开销**  
PTL 是纯内存结构，WOLVES 在文件关闭时仍保留 3.8–5.12 MiB 的 PTL 内存（NOVA 关闭文件后释放）。论文将其定性为"0.3%–1.6% of workload size"，但对于内存资源受限的场景（如边缘设备），这一持续开销可能成为问题，且论文并未讨论极端文件数量下的 PTL 内存消耗。

**4. 碎片化问题被轻描淡写**  
老化实验（Section 6.8）显示，在极端 4KiB 文件 profile 下，WOLVES 的顺序写吞吐从 2.2 GiB/s 降至 1.70–1.82 GiB/s（约 18% 降幅），随机写更降至 1.31–1.44 GiB/s。论文仅表示"计划未来研究碎片化"，但没有任何去碎片化机制，对于长期运行的生产系统而言是实质性隐患。

**5. Coarse Persistence 的竞争条件**  
CP 允许 bitmap 更新（m_cp）与 package 写入（P）并发执行，逻辑正确性依赖"m_cp 未持久化时，P 必然无效"。这一论证在正文中较为简略，形式化证明见 Appendix A，但并未针对 CP 专门建模。在实际 PM 硬件（如多 channel、NUMA 拓扑）下的正确性仍有待更充分的工具验证。

**6. 与 HTMFS、ZoFS 等系统的对比缺失**  
论文对比了 PMFS、NOVA、SplitFS、EXT4-DAX、XFS-DAX、MadFS，却未包含 HTMFS（利用 HTM 实现强一致性）和 ZoFS（用户态 NVM 文件系统），这两者与 WOLVES 在设计空间上重叠度较高，其缺席显得有些刻意。

---

## 七、总结

WOLVES 基于 WOFS 模型，通过将每次文件操作的元数据压缩为一个 checksum 保护的 package 并以单次 PCOMMIT 一次性写入，从根本上消除了现有 PM 文件系统中大量小型、随机、有序元数据 I/O 的痛点。配合 Package Translation Layer、非日志布局和粗粒度持久化，WOLVES 在 Intel Optane 上实现了接近 PM 带宽理论上限（97.3%–99.1%）的顺序写性能，相比 NOVA/PMFS/SplitFS 有显著提升。

主要局限在于：依赖的 Optane DIMM 已停产（CXL-SSD 适配深度不足）、高并发场景性能下滑、缺乏碎片整理机制，以及 PTL 的持久内存占用。该工作对于 PM/CXL 场景下追求极致写性能和同步崩溃一致性的存储系统研究具有较高参考价值。
