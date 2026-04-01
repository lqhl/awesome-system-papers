# Fast and Synchronous Crash Consistency with Metadata Write-Once File System

**作者**：Yanqi Pan, Wen Xia (通讯作者), Yifeng Zhang, Xiangyu Zou, Hao Huang (哈尔滨工业大学深圳); Zhenhua Li (清华大学); Chentao Wu (上海交通大学)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/pan
**源文件**：[osdi25-pan.pdf](../../papers/osdi-2025/osdi25-pan.pdf)

---

## 一、背景

持久内存（Persistent Memory, PM）技术（如 3D-XPoint、CXL-SSD）提供了接近 DRAM 的低延迟和数据持久性。PM 文件系统可以通过 CPU load/store 直接访问数据，绕过传统块层，实现快速同步 I/O。这使得 PM 文件系统能够追求**同步崩溃一致性（synchronous crash consistency）**——每个文件操作在返回时即保证持久化，无需显式 fsync，从而大幅简化应用层的崩溃一致性工作（对数据库和 NFS 尤为重要）。

现有 PM 文件系统采用两类崩溃一致性方法：
1. **带额外写入的方法**：如 Journaling（PMFS）和 Transactional Checksum（SplitFS），通过冗余写入保证一致性
2. **不带额外写入的方法**：如 Log-Structured（NOVA）和 Synchronous Soft Update（SquirrelFS），通过精心排序元数据更新来保证一致性

---

## 二、要解决的问题

现有崩溃一致性方法在 PM 上产生大量**小粒度、随机、有序**的元数据 I/O，导致严重性能瓶颈：

1. **随机元数据 I/O 导致持久缓冲区 miss**：PM 持久缓冲区（如 Intel 的 XPBuffer）的刷新粒度为 256 字节（XPLine），与小元数据不匹配，导致 I/O 放大。实验表明 PMFS 产生 2.8× 元数据 I/O 放大。

2. **有序元数据 I/O 限制并行性**：多个 ordering point 要求等待前序 I/O 完成，降低 PM I/O 并发度。PMFS 在 transaction write 和 commit 上花费 6.73%–49.2% 的元数据 I/O 时间。

3. **GC 等额外 I/O 加剧开销**：NOVA 的 copy-based GC 导致平均每个块 I/O 约 13 次元数据访问，带来 ~38% 的 GC 开销。

总体而言，现有 PM 文件系统在元数据 I/O 上消耗了总 I/O 时间的 11.3%–97.4%，在顺序写场景下只能达到 PM 写带宽的不到 50%。

---

## 三、洞察与设计

**关键洞察**：现有崩溃一致性技术难以优化跨多个元数据对象（inode、log entry、dentry 等）的 I/O 编排，根源在于文件系统传统上将元数据分散管理。如果为每个文件操作生成专用的聚合元数据（类似于 journal 的 J_M），并附加 checksum header（类似于 J_C），就可以将元数据一次写入（m_op = J_M | J_C），只需一个 ordering point：D → J_M | J_C。

基于这一洞察，论文提出 **Metadata Write-Once File System (WOFS)** 模型：

### 核心设计

**1. Package 抽象（§4.2）**：将文件操作的元数据聚合为 checksum-protected package，定义四种原子 package：
- **Create pkg**（256 字节）：create、link 等创建 inode 的操作
- **Write pkg**（64 字节）：write、fallocate 等分配数据块的操作
- **Attr pkg**（64 字节）：chown、chmod 等修改属性的操作
- **Unlink pkg**（64 字节）：rm、rmdir 等减少链接的操作

对于 rename 等复杂操作，使用 compound package（多个原子 sub-package 通过 forward-pointer 链接），无需额外 ordering point。

**2. Package Translation Layer (PTL, §4.3)**：将 package 解析为兼容的 inode、文件、目录抽象。PTL 维护 pkg-node（C-node/W-node/A-node）组织为 inode table、data list、dent list，为上层 VFS 提供标准文件系统接口。

**3. Non-log Layout（§4.4）**：不采用 log 布局，而是类似 malloc 的方式在 PM 上分配 package/数据块。空间回收通过因果顺序推理确定哪些 package 已失效，直接 reuse（而非 copy-based GC）。

**4. Coarse Persistence 快速恢复（§4.5）**：分配 4KiB 的 pkg-group 容纳多个 package，并在分配时持久化 bitmap 标记。恢复时只需扫描 bitmap 定位 pkg-group，检查 package 完整性，重建 PTL。bitmap 更新与 package I/O 无需排序（P | m_cp），不引入额外 ordering point。

---

## 四、实现细节

WOLVES 作为 WOFS 原型，在 Linux Kernel 5.1.0 中实现，约 12,000+ 行 C 代码。

- **空间管理**：采用两级分配器（tl-allocator），每个 CPU 管理 PM_Size / NumOfCPU 的连续区域。数据块用红黑树管理空闲列表，package 在 pkg-group 内用 64-bit bitmap 管理（64 = 4096/64）。
- **Bitmap 开销**：仅占 ~0.012% PM 空间（4 种 package 类型各一个 bitmap）。
- **目录抽象**：每个目录 inode 部署 128-slot hash table 组织 dent list。
- **文件写入**：
  - Non-overlap write：movnti 写数据 → write pkg 一次 PCOMMIT → 更新动态数组
  - Overlap write：COW 方式处理，根据重叠关系回收/修改旧 W-node
  - Append write：直接追加到已分配块，仅原子更新 write pkg header 的 8 字节 size 字段
- **Huge Allocation (HA)**：对 append-like 写入分配 2MiB huge block，减少 PM buffer 污染
- **Read Ahead (RA)**：用 prefetcht0 按 256 字节（XPLine）步长预取，与数据拷贝重叠执行
- **并发模型**：遵循因果序并发协议，独立 package 可并行持久化；因果相关的 package 串行执行
- **恢复流程**：按 create → unlink → write → attr bitmap 顺序扫描，重建 inode table、dent list、data list，通过时间戳和操作语义确定因果顺序，回收过期 package

---

## 五、实验结果

**实验平台**：16-core Intel Xeon Gold 5218, 128GiB DRAM, 2×256GiB Intel Optane PM (non-interleaved), Linux 5.1.0

**对比系统**：PMFS, NOVA, NOVA-RELAX, SplitFS, MadFS, EXT4-DAX, XFS-DAX, SquirrelFS, SoupFS, HUNTER

| 指标 | 结果 |
|------|------|
| **PM 带宽利用率** | SW 下达到 97.3%–99.1% PM I/O 带宽（2.20–2.24 GiB/s） |
| **顺序写吞吐** | RW 下比其他系统高 1.65–9.44× |
| **元数据操作** | FxMark 创建/删除/重命名操作吞吐最高 |
| **Filebench** | 在 Fileserver/Varmail/Webserver/Webproxy 下均达最高 OPS |
| **RocksDB** | Sequential Fill 1.26–6.73×, Random Fill 1.36–5.21×, Random Append 1.26–3.93×, Random Update 1.20–4.46× |
| **LevelDB** | 写密集型负载（LoadA/E/RunA）改善最显著 |
| **尾延迟** | 99.9% 分位 12.84μs vs NOVA 19.38μs / PMFS 21.00μs / SplitFS 951μs |
| **元数据 I/O 减少** | ipmctl 实测比 PMFS 和 NOVA 减少 70%–17.3× 的元数据 I/O |
| **恢复时间** | FIO-32G: 2.61s (vs NOVA 24.2s); Fileserver: 3.99s (vs NOVA 2.48s) |
| **最坏场景恢复** | 256GiB PM 约 6000 万文件，~21.6s |
| **内存开销** | PTL 占 0.3%–1.6% 工作负载大小 |
| **空间开销** | 128GiB 4KiB I/O 仅需 0.0015%–0.7% 空间 |
| **老化后性能** | SW 1.70–1.95 GiB/s, RW 1.31–1.44 GiB/s，仍优于 NOVA 和 PMFS |
| **vs Soft Update** | 比同步 SSU 和异步 ASU 均高 21%–52%（有 fsync 场景） |
| **MS-SSD 泛化** | 在 Samsung Memory Semantic SSD 上同样达最高写吞吐 |

---

## 六、批判性分析

1. **崩溃一致性验证不充分**：论文声称使用了形式化逻辑模型证明正确性（附录 A），但实际的运行时验证仅测试了 3 个工作负载各 1000 个随机崩溃点。对于一个新的文件系统模型，这远不够全面——没有使用 CrashMonkey 等成熟的崩溃测试框架，也没有测试并发场景下的崩溃恢复。

2. **Compound package 的正确性担忧**：forward-pointer 机制在并发和嵌套场景下的安全性分析不够充分。论文仅展示了 rename（2 个 sub-package）的案例，但对更复杂的组合操作（如并发 rename + unlink）缺乏讨论。

3. **恢复时间并非全面优于 NOVA**：Table 6 显示在 Fileserver 场景下 WOLVES 恢复时间 3.99s 反而慢于 NOVA 的 2.48s，论文对此未做解释。在 FIO-32G 场景下 WOLVES 恢复快是因为 NOVA 自身的工程缺陷（大文件需多次扫描 inode-log），而非 WOLVES 设计的优越性。

4. **MadFS 和 SplitFS 的对比公平性存疑**：MadFS 在多个工作负载下无法成功运行，SplitFS 无法在 RocksDB 上运行。论文将这些归为"best efforts"，但缺失的数据点削弱了比较的说服力。

5. **Append write 的 checksum 绕过**：§5.2 中 append write 仅更新 write pkg header 的 8 字节 size 字段而不重算 CRC32，通过"先清零再校验"的方式验证。这实际上弱化了 checksum 保护——如果 append 期间崩溃导致 size 字段部分写入，8 字节原子写依赖于硬件保证，论文未讨论非 Intel PM 平台上是否仍成立。

6. **并发可扩展性限制**：Figure 7 显示线程数 ≥9 时性能下降，论文归因于 PM 硬件争用并用插入延迟（bandwidth regulator）缓解，这本质上是在限流而非解决根本问题。在未来更高核数的系统上这个问题会更严重。

7. **没有碎片整理机制**：论文承认 non-log layout 会导致碎片化但留作 future work。在长期运行的生产场景中，碎片累积可能导致性能持续退化。

---

## 七、总结

WOFS 提出了一种新的文件系统元数据管理范式：将每个文件操作的元数据聚合为 checksum-protected package 并一次写入，最小化元数据 I/O 次数和 ordering point，从而在 PM 上实现接近硬件带宽上限的同步崩溃一致性。其原型 WOLVES 在多种基准测试和真实应用中显著优于现有 PM 文件系统。该工作的核心价值在于打破了传统文件系统分散管理元数据的范式，但其崩溃正确性验证的深度、并发可扩展性、以及长期碎片化问题仍有待更充分的评估。
