# SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup

**作者**：Riwei Pan (City University of Hong Kong), Yu Liang (ETH Zurich), Lei Li, Hongchao Du (City University of Hong Kong), Tei-Wei Kuo (Delta Electronics & National Taiwan University), Chun Jason Xue (Mohamed bin Zayed University of Artificial Intelligence)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/pan
**源文件**：[[atc2025-pan.pdf]]

---

## 一、背景

移动设备已成为个人数据存储的重要载体（2023 年全球售出约 13.4 亿部智能手机），云备份应用（Dropbox、OneDrive、厂商内置备份等）被广泛用于保护用户数据。为减少网络流量，部分应用采用 delta 同步技术——通过哈希计算（SHA256、MD5 等）识别文件修改的部分，仅上传变化数据。

然而，delta 同步的核心瓶颈在于哈希计算的高 CPU 开销。在 Google Pixel 8 上备份 15GB 数据的实测表明，哈希操作额外引入 170% 的执行延迟和 224% 的 CPU 能耗。即使采用多线程并行哈希，4 线程的能耗仍为仅读取基线的 2.3 倍。这使得移动设备面临两难：要么牺牲同步效率（全量上传），要么牺牲用户体验（CPU 资源竞争和电池消耗），导致用户不得不降低备份频率（如每周一次）。

---

## 二、要解决的问题

1. **哈希计算开销过高**：现有 delta 同步方案（HashSync、rsync、WebR2sync+、QuickSync、NetSync）均需要对整个文件进行哈希计算来定位修改范围，在资源受限的移动设备上造成过高的 CPU 占用和能耗。

2. **Copy-on-Write 方案的文件碎片化问题**：基于 CoW 的快照/版本化文件系统（如 XFS reflink、BtrFS）虽可无哈希地区分新旧数据，但会导致严重的文件碎片化，降低顺序读性能，且需要持续分配额外存储空间保存文件数据副本。

3. **多应用版本管理冲突**：移动设备可能安装多个云备份应用（内置 + 第三方），各自有独立的备份进度，需要在不互相干扰的情况下追踪各自的文件差异。

4. **向后兼容性**：需在现有移动文件系统（F2FS）上实现，不改变磁盘布局，兼容全球超 65 亿台现有移动设备。

---

## 三、洞察与设计

**关键洞察**：如果云备份应用能够知道自上次备份以来每次写操作的 offset 和 length，就可以直接定位修改数据范围，完全不需要哈希计算。文件系统天然能拦截并记录这些写操作元数据，且开销极低。

基于此洞察，SolFS 设计为一个轻量级的操作日志版本化文件系统，核心由三部分组成：

**1. Per-file Mergeable Operation Logging (MLogging)**：为每个文件维护一棵 in-memory mlog tree（基于 extent tree），记录写操作的 offset 和 length。关键优化包括：
- **可合并日志**：相邻或重叠的 mlog 自动合并，控制日志数量增长
- **mlog 指针缓存**：对顺序写/追加写提供 O(1) 的更新路径
- **按需加载**：文件打开时不从磁盘加载历史 mlog，仅维护新增 mlog
- **紧凑日志格式**：利用 length 的最高位作标志，将小范围 mlog 的 offset 和 length 压缩到 4 字节
- **动态粒度调整**：当 mlog 数量超过阈值（5000），从字节级切换到页级粒度

**2. Mlog Versioning（版本化机制）**：
- 引入 versioned inode chain，每次备份时插入新版本 inode，新 mlog tree 记录此后的修改
- 版本号由备份驱动（而非写操作驱动），多个备份应用通过各自的版本号独立追踪文件差异
- 通过引用计数（ver_link）实现版本化 inode 的压缩回收
- 四个额外属性（ino_ver、ver_link、ino_flag、next_ino）存储在 extended file attributes 中，不改变 F2FS 磁盘布局

**3. Hash-free Delta Synchronization**：
- 备份时，应用提供上次备份的版本号，SolFS 遍历版本 inode chain 中对应区间的 mlog，合并为 extent tree 表示累积修改范围
- 应用可直接上传修改范围的数据，或对修改范围内数据施加哈希进一步减少流量
- 协作式版本管理：本地与云端交换版本号而非 checksum 列表

---

## 四、实现细节

SolFS 在 F2FS 上实现为内核模块，关键实现要点：

- **内核数据结构**：mlog tree 使用 `kmem_cache_alloc` 分配，存储在 F2FS 的 inode info 中。每个 mlog entry 占 4 或 8 字节（紧凑/标准格式）
- **异步持久化**：专用 worker thread 通过共享列表处理脏 mlog tree 的持久化，不阻塞应用 I/O 关键路径
- **ioctl 接口**：提供三个新接口——`delta_open`（注册上下文、阻塞写、刷脏页和 mlog）、`delta_getdiff`（递归获取累积修改范围）、`delta_close`（释放资源、解除写阻塞）
- **崩溃一致性**：
  - All-or-nothing 机制：利用 F2FS 的写顺序保证（数据先于元数据），通过 ino_flag 脏标志检测不一致
  - Inode chain 操作期间禁用 F2FS checkpointing，操作完成后恢复，确保 inode 连接的原子性
- **支持的文件操作**：write、fallocate、truncate、mmap（PROT_WRITE）、rename（标记为全文件修改）
- **选择性哈希策略**：当 mlog 覆盖整个文件时，对该文件使用 rolling checksum（类似 WebR2sync+），其余情况直接上传修改数据
- 源码开源：https://github.com/MIoTLab/SolFS

---

## 五、实验结果

**实验平台**：Google Pixel 8（Android 14，Linux kernel 5.15）；云服务器为 Ubuntu 20.04，Intel i9-14900K 24 核，32GB 内存。

### 微基准测试（10MB 文件，网络带宽 ~100 Mbps）

| 指标 | HashSync | Rsync | WebR2sync+ | SolFS |
|------|----------|-------|------------|-------|
| 随机更新同步时间降低 | baseline | - | - | **88.8%** |
| 更新 1MB 数据的网络流量 | baseline | - | - | 仅 **12.3%** |
| 客户端+服务端计算开销降低 | baseline | - | - | **92%** |

### 真实移动应用工作负载

| 应用 | 数据量 | 同步时间改善 |
|------|--------|------------|
| Facebook | 220MB | ~71% |
| Twitter | 112MB | ~71% |
| Capcut | 220MB | ~71% |
| Dropbox | 843MB | ~71% |
| **平均** | - | HashSync 89s → SolFS 29s，降低 **71%**，CPU 使用率降低 **~70%** |

### 系统开销

| 指标 | 结果 |
|------|------|
| I/O 性能影响 | < 1.5%（相对 F2FS，平均 99.2%） |
| CPU 开销增加 | 8.3% → 8.5% |
| 内存开销（9 个 trace，18 小时模拟） | 470KB（字节级 mlog） |
| 存储开销 | 比内存小 33%（紧凑 mlog） |
| 版本 inode 搜索时间（depth=10） | 7.6ms |
| mlog tree 转换（10K mlogs） | ~10ms |
| mlog 加载与合并（10K mlogs） | ~30ms |

---

## 六、批判性分析

1. **工作负载局限性**：实验中文件大小仅 10MB，与论文提到的用户平均存储 118GB 数据形成鲜明对比。大文件场景下 mlog 数量可能急剧增长，动态粒度切换到页级别后的网络流量增加未被充分评估。

2. **真实应用评估深度不足**：四个应用仅各使用 5 分钟，产生的工作负载可能无法代表长期使用模式。论文声称「随机写主导移动平台」，但仅提供了短时间快照作为证据。

3. **选择性哈希的退化场景被轻描淡写**：当文件被大范围修改或 mlog 覆盖全文件时，SolFS 退化为与 WebR2sync+ 相当的性能，但论文未量化这种退化场景的发生频率。

4. **多应用并发备份的评估缺失**：论文的设计目标之一是支持多备份应用，但所有实验均假设「仅一个备份应用」（论文原文：we assume that users upload files using only one cloud backup APP）。版本 inode chain 深度增长、compaction 开销在多应用场景下的表现完全未验证。

5. **崩溃一致性的代价**：All-or-nothing 机制在崩溃时会丢弃整个版本 inode chain 并要求全量上传，这对于大文件可能是很高的代价。论文以「系统崩溃是罕见事件」一笔带过，但移动设备的意外关机并不罕见。

6. **安全性考虑缺失**：mlog 通过 ioctl 暴露文件修改范围信息给任意应用，可能泄露用户行为模式（如哪些文件在何时被修改、修改量大小），论文未讨论访问控制机制。

---

## 七、总结

SolFS 提出了一种巧妙的思路：通过在文件系统层记录写操作的 offset 和 length（而非文件数据本身），实现无哈希的 delta 同步，将移动云备份的计算开销降低 90% 以上，同步时间缩短 71%–88%，且对 F2FS 的 I/O 性能影响不到 1.5%。其设计在低开销、向后兼容性和多应用支持方面考虑周全，但评估主要局限于小文件和单应用场景，多应用并发、大文件、崩溃恢复等关键场景的验证不足。
