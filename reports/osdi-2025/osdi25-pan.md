# WOLVES: Metadata Write-Once File System for Fast and Synchronous Crash Consistency

## 论文基本信息

- **标题**: Fast and Synchronous Crash Consistency with Metadata Write-Once File System
- **作者**: Yanqi Pan, Wen Xia, Yifeng Zhang, Xiangyu Zou, Hao Huang (Harbin Institute of Technology), Zhenhua Li (Tsinghua), Chentao Wu (Shanghai Jiao Tong)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/pan

## 研究背景与动机

持久内存（PM）技术（如 3D-XPoint、CXL-SSD）提供了接近 DRAM 的性能和类似存储的持久性，可通过 CPU load/store 直接访问，绕过传统块层。PM 文件系统利用这一特性追求同步崩溃一致性——即每个文件操作返回时即已持久化，无需应用层显式调用 fsync。

现有 PM 文件系统遵循两类方法来实现同步崩溃一致性：

1. **Journaling (JFS)**：将元数据写入日志区域，再进行 commit flag 的原子写入，最后执行无序的 in-place 更新。代表：PMFS、SplitFS（带 transactional checksum 的 JFS）。
2. **Log-Structured File System (LFS)**：追加式写入元数据，通过 GC 回收空间。代表：NOVA。
3. **Synchronous Soft Update (SSU)**：通过精心排序多个元数据对象的更新来避免额外写入。代表：SquirrelFS。

作者通过基准测试发现，这些方法中处理崩溃一致性的元数据 I/O 占据了总 I/O 时间的 22.9%–76.5%（JFS）、63.8%–97.4%（CK）、11.3%–75.5%（LFS），原因是：随机元数据 I/O 导致持久缓冲区缺失、排序 I/O 限制了 PM I/O 并发、GC 机制进一步加剧了元数据 I/O 数量。

## 要解决的核心问题

**核心问题**：现有 PM 文件系统的崩溃一致性机制产生了大量小、随机、有序的元数据 I/O 和排序点，这些开销严重浪费了 PM 的带宽潜力。

具体来说：
- 随机元数据 I/O 造成持久缓冲区命中率缺失，引发 I/O 放大（PMFS 实测达到 2.8 倍放大）
- 有序元数据 I/O 导致等待前面的数据传输完成，限制了 PM I/O 并发
- 元数据 I/O 数量增加进一步恶化了 GC 开销（NOVA 中每个块 I/O 平均产生约 13 次元数据访问）

## 主要贡献

1. 对现有 PM 文件系统崩溃一致性技术的深入分析，揭示了元数据 I/O 主导开销（>70%）的根本原因
2. 提出**元数据 Write-Once 文件系统（WOFS）模型**：将每个文件操作的元数据生成为一个带校验和的 package，仅用单一排序点写入一次
3. 一系列使 WOFS 实用化的技术：package 生成、package 翻译层（PTL）、非日志布局与空间回收、基于粗粒度持久化的快速恢复
4. 在 Linux 内核中实现了 WOLVES 原型，并在 Intel Optane PM 和 emulated Memory-Semantic SSD 上进行了评估

## 研究方法与设计

### WOFS 核心设计

**Package 概念**：WOFS 将每个文件操作的元数据聚合为一个带 header（commit flag）的 package，包含：
- **J_M**：文件操作必要的元数据字段（如 creat 操作的文件名属性）
- **J_C**：commit flag，包含 magic number、type、timestamp、CRC32 校验和

**工作流程**：
- 元数据操作（如 create）：生成 package → 用单个 PCOMMIT 写入（J_M|J_C）
- 数据操作：先持久化数据（D），再写入引用数据的 package（D→J_M|J_C）

**四种原子 Package**：
| Package 类型 | 大小 | 用途 |
|---|---|---|
| Create pkg | 256B | 创建新 inode（create、mkdir、link） |
| Write pkg | 64B | 分配新数据块（write、fallocate） |
| Attr pkg | 64B | 修改 inode 属性（chmod、chown、truncate） |
| Unlink pkg | 64B | 减少 inode 链接数 |

**复合 Package**：复杂操作（如 rename = link + unlink）由多个原子 package 组成，通过 forward-pointer 链接。

### Package 翻译层（PTL）

WOFS 的 package 设计颠覆了传统文件系统的 inode、dentry 等元数据对象。PTL 负责将 package 解析为兼容的文件/目录抽象：
- **Inode Table**：从 create pkg 和 attr pkg 的 pkg-node 组合重建 inode
- **Low-level File Abstraction**：为每个文件维护 W-node 链表
- **Low-level Directory Abstraction**：维护 C-node 链表用于目录项搜索

### 非日志布局与空间回收

WOFS 在 PM 上采用类似 malloc 的非日志布局分配空间，回收时通过 reallocation 而非 copy-based GC：
- Create pkg：由后续 unlink pkg 使其失效
- Write pkg：overwrite 或 truncate 导致失效
- Attr pkg：新 attr pkg 使旧 pkg 失效
- Unlink pkg：在对应 create pkg 被 reallocated 后才能回收
- 复合 package：等所有原子 package 失效后才回收

### 快速恢复

**问题**：非日志布局使 package 分散在 PM 各处，快速定位 package 是个难题。

**Coarse Persistence（CP）方案**：分配 4KiB 的 pkg-group 来容纳多个 package，并将 pkg-group 的地址用 bitmap 持久化（每个 bit 对应一个 group）。恢复时扫描 bitmap 定位 pkg-group，再探查有效 package，最后重建 PTL。

**安全性**：CP 保证 package 拥有与崩溃前相同的因果顺序，而非提交顺序。

## 关键实现细节

WOLVES 在 Linux Kernel 5.1.0 上实现，约 12,000+ 行 C 代码：

1. **数据布局**：4KiB 块粒度管理，前两个块保留给 superblock 和 bitmap
2. **两级分配器（tl-allocator）**：每个 CPU 一个分配器，管理连续区域；package 分配时先分配一个 pkg-group，再用 64-bit bitmap 管理其内部空间
3. **并发模型**：遵循因果序并发协议，独立 package 可并行持久化
4. **其他优化**：
   - **Huge Allocation (HA)**：追加写使用 2MiB huge block
   - **Read-ahead (RA)**：读取时预取 256B XPLine stride
   - **WOLVES-AVX**：集成 vmovntdq 优化非时序存储

## 实验结果与分析

### 测试环境
- 16-core Intel Xeon Gold 5218, 128GiB DRAM, 2×256GiB Intel Optane PM（Linux 5.1.0）

### 崩溃一致性
- 使用形式化逻辑模型证明，提供 3 种代表性工作负载的 1000 个随机崩溃点测试，全部恢复到最新一致状态

### I/O 性能
- **顺序写（SW）**：WOLVES 稳定达到 2.20–2.24 GiB/s，占原始 PM 带宽的 97.3%–99.1%
- **随机写（RW）**：相比 NOVA/PMFS/SplitFS 等达到 1.65–9.44 倍吞吐量提升
- **尾延迟**：WOLVES 在 99.99% 分位点（18.92μs/op）显著优于 NOVA（23.27μs）和 PMFS（329.4μs）
- **并发扩展**：1–8 线程下 WOLVES 优于所有竞品；线程 ≥9 时因 PM 硬件争用导致性能下降（已知问题）

### 端到端应用（RocksDB）
WOLVES 在 RocksDB 上达到 1.20–6.73 倍吞吐量提升。

### 对其他 PM 平台的可迁移性
移植到 emulated Memory-Semantic SSD 上同样有效，验证了 WOFS 的通用性。

## 潜在问题与局限性

1. **测试平台单一**：所有实验均在 Intel Optane PM 上进行；作者自己承认 Optane 已停产，未来 CXL-SSD 等新 PM 平台的特性和性能表现需要验证
2. **并发扩展受限**：PM 硬件争用限制了高并发场景的性能，这是 PM 本身的硬件限制，而非设计缺陷，但论文对此着墨不多
3. **复合 package 的 forward-pointer 设计**：rename 等复合操作依赖 forward-pointer 检测不完整写入，若双指针机制缺失可能影响原子性（论文选择了避免此设计以对齐 64B cacheline）
4. **形式化验证范围有限**：只测试了 3 种工作负载和 1000 个崩溃点，对于生产环境中的复杂工作负载覆盖是否充分值得商榷
5. **只支持 SSD-like PM**：WOLVES 依赖于持久化存储的特性，对于纯 DRAM+NVM 的混合场景可能需要调整

## 未来工作方向

1. 将 WOFS 适配到更多 PM 平台（CXL-SSD、Compute Express Link 内存等）
2. 探索用户空间文件系统的 WOFS 实现（类似 SplitFS 的 DAX 路径）
3. 支持更多文件操作类型和复杂复合操作
4. 针对多核并发的 PM 带宽优化

## 个人评注

### 优点

1. **分析扎实**：论文对现有方法的元数据 I/O 开销进行了细致的量化分析（Figures 2a-c），数据说服力强
2. **设计优雅**：将元数据聚合为 package 的思想简单但有效，将多个排序点减少为单一排序点是一个核心创新
3. **工程实现完整**：12,000+ 行内核代码，包含完整恢复机制、崩溃验证、形式化证明
4. **CP 恢复机制巧妙**：通过 bitmap 而非 dump-restore 方式实现快速恢复，避免了每次 unmount 时 dump 的开销

### 不足与矛盾之处

1. **"可达 97.3%–99.1% PM 带宽"的表述略显夸大**：该数字仅在 SW（顺序追加写）工作负载下达成，RW（随机写）场景下优势主要体现在与其他文件系统对比，而非绝对带宽利用率
2. **Figure 6 的数据解读需谨慎**：图中 WOLVES 在 SR/RR（顺序/随机读）上的表现优势部分来源于 Read-ahead 优化技术，并非 WOFS 本身的设计优势；没有 RA 的情况下 WOLVES 的读性能与其他 PM 内核文件系统相当
3. **并发性能部分有注水**：论文 7b 中 WOLVES 在 9+ 线程后性能下降，这实际上是一个相当严重的限制，但论文在 abstract 中并未提及，而是在 evaluation 部分轻描淡写
4. **PMFS 的 I/O 放大倍数计算存疑**：论文声称 PMFS 的元数据 I/O 从理论 2.9 GiB 增加到实测 8.0 GiB（2.8 倍），但这个"理论值"的计算假设并不明确（见 §6 对 ipmctl 工具的使用），缺乏与直接测量的对比验证
5. **SquirrelFS 对比不够充分**：论文在 §6.11 中将 WOLVES 与 SquirrelFS（同步 soft update）进行比较，但仅给出一个 ∼30% 性能提升的数字，没有详细的 micro-benchmark 数据支撑
