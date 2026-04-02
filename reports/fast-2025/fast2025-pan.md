# Don't Maintain Twice, It's Alright: Merged Metadata Management in Deduplication File System with GogetaFS

**作者**：Yanqi Pan, Wen Xia (Harbin Institute of Technology, Shenzhen); Erci Xu (Alibaba Group); Hao Huang, Xiangyu Zou, Shiyi Li (Harbin Institute of Technology, Shenzhen)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/pan
**源文件**：[fast2025-pan.pdf](../../papers/fast-2025/fast2025-pan.pdf)

---

## 一、背景

去重文件系统（DedupFS）通过将去重逻辑嵌入文件系统内部，能够透明地为应用提供数据去重服务，同时简化实现复杂度。传统 DedupFS 使用密码学哈希（如 SHA-1）计算 fingerprint（FP），计算开销高达 65%。随着持久内存（Persistent Memory, PM，如 Intel Optane DCPMM）和超低延迟 SSD（ULL SSD，如 Z-SSD）等新型存储设备的出现，FP 计算的瓶颈从 I/O 转向 CPU，使得非密码学哈希（如 xxHash、wyHash）加内容比较的方案成为可能，将冗余识别开销降低到 20% 以下。

然而，即便计算开销大幅降低，现有 DedupFS（如 Light-Dedup、NV-Dedup、DeNOVA）的性能仍然无法令人满意，与理想上界之间存在显著差距。

---

## 二、要解决的问题

作者通过 motivational study 发现，在非密码学 FP 加速计算之后，**去重元数据维护**成为新的性能瓶颈，占 I/O 时间的 18%–38%。具体问题包括：

1. **双重元数据维护开销**：DedupFS 需要同时维护文件系统的 L2P（logical-to-physical）映射和去重特有的 FP2P（fingerprint-to-physical）映射，后者需要独立的 crash consistency 保障。
2. **I/O 放大**：FP2P 条目的粒度（如几十字节）与存储 I/O 粒度（如 PM 的 256 字节、SSD 的 4–16KiB）不匹配，导致写放大。
3. **I/O 并行性受限**：为保证 crash consistency，DedupFS 强制 FP2P 条目必须在 L2P 条目之前持久化（ordering），阻塞了后续 I/O，限制了并行度。

---

## 三、洞察与设计

**关键洞察**：去重的 FP2P 条目和文件系统的 L2P 条目共享相同的物理块号（PBN），可以合并为一个 LBN-FP-PBN（Logical-Fingerprint-Physical, LFP）映射。这样去重元数据可以随文件系统元数据在单次 I/O 中一起持久化，复用文件系统成熟的 I/O 路径和 crash consistency 机制，无需额外的 ordering 点。

过去 LFP 方案不被采用的原因是：密码学 FP 太大（20 字节），空间开销高达 2.25×，且计算仍是瓶颈。但随着非密码学 FP（8 字节）的普及，LFP 在去重率 <80% 时甚至能节省元数据空间，同时性能收益显著。

**GogetaFS 核心设计**：

1. **LFP 映射**：将 FP 嵌入文件系统 L2P 条目中，形成统一的 LFP 条目。去重元数据的持久化和 crash consistency 完全复用文件系统机制。
2. **Overflow FP Table (OFT)**：处理 extent 与 block 粒度不匹配问题。对于连续数据块，FP 存储在 OFT（一个 PBN-to-FP 映射数组）中，LFP 条目中置 NIL FP。OFT 是 lock-free 的，支持并行更新，且不引入额外 ordering 点。
3. **Global LFP Table (GLT)**：聚合所有 LFP 条目转换为 FP2P 条目，使用动态哈希表按 FP 索引，支持跨文件去重。GLT 无 crash consistency 要求（可从 LFP 条目重建），因此可灵活部署在 DRAM 或存储中。
4. **多场景变体**：针对内存充足（全 DRAM GLT）、内存受限（部分 GLT 驻 PM + Hybrid 设计）、内存稀缺（全 PM 静态哈希表 SHT）三种场景提供不同 GLT 实现。

---

## 四、实现细节

GogetaFS 基于 NOVA（PM 文件系统）和 F2FS（SSD 文件系统）实现。

**基于 NOVA 的实现**：
- **LFP 条目**：复用 `nova_write_entry` 中的 4 字节 crc32 校验和 + 4 字节 padding，存储 8 字节 wyHash FP（fast mode）；或只用 padding 存高 4 字节 FP（secure mode，保留校验和）。
- **OFT**：在 NOVA superblock 旁预留，作为 FP 数组，通过 `clwb` 批量刷新（无 `sfence` ordering）。
- **GLT**：使用 relativistic hash table，RCU 锁保护。每个 GLT 条目额外带 8 字节 hint（用于投机预取）和 8 字节计数器。
- **去重识别器**：借用 Light-Dedup 的 LRBI 机制，采用 wyHash + 投机预取加速内容比较。
- **Recovery**：正常关机时 dump GLT 到 PM 文件；故障恢复时集成到 NOVA 的 `nova_set_file_bm` 中重建 GLT。

**基于 F2FS 的实现**：
- 扩展 F2FS block index entry 存储 FP，无需 OFT（F2FS 每个条目只映射一个块）。
- 预取函数替换为 `sb_breadahead`（SSD 不支持字节寻址）。
- 内存受限场景采用 Hybrid 变体（key 驻内存，value 按需从 SSD 加载）。

代码量：F2FS 适配仅需约 50 LOC。

---

## 五、实验结果

**平台**：Intel Xeon Gold 5218 (16 cores)，512GiB Intel Optane DCPMM，128GiB DRAM，CentOS (kernel 5.1.0)。SSD 实验使用 FEMU 模拟 Z-SSD。

**对比系统**：Light-Dedup, NV-Dedup, DeNOVA, NOVA, SmartDedup, HFDedup, F2FS。

| 实验 | 关键结果 |
|------|---------|
| FIO 写吞吐 (PM) | GogetaFS 比 Light-Dedup 高 5.6%–35.0%，接近甚至超过 NOVA（2MiB I/O 时 FP 计算与 PM I/O 重叠降低 buffer 竞争） |
| 真实负载 (PM) | CP/OSLab/Mails/WebVMs 下比 Light-Dedup 高 8%–32%，2MiB I/O 下改进更显著（因高效删除：仅失效单个 LFP 条目 vs. 512 个 FP2P 条目） |
| 去重元数据开销 | GogetaFS 去重元数据开销比 Light-Dedup 低 75.4%–92.8% |
| I/O 放大 | 4KiB I/O 下 GogetaFS 去重引起的额外读/写字节接近 0（Light-Dedup 为 132–289/115–174 字节） |
| 内存受限场景 | GogetaFS 变体始终优于 Light-Dedup；GogetaHybrid 在低内存时更优，GogetaFS 在高内存时更优 |
| 内存稀缺场景 | GogetaSHT 比 GogetaFS(NoMem) 高 1%–10%，但 NOVA 仍快 10%–36%（低去重率时） |
| 故障恢复 | 比 Light-Dedup 快 9.5%–30.8%（无需额外扫描 FP2P 表） |
| SSD (F2FS) | 显著优于 SmartDedup/HFDedup/Light-Dedup，达 F2FS 的 79%–99.6% 性能 |

---

## 六、批判性分析

1. **secure mode 的 4 字节 FP 空间严重不足**：secure mode 仅使用高 4 字节 FP，碰撞概率大幅提高（2^32 空间 vs. 2^64），但论文仅通过 t-test 声称性能差异不显著就一笔带过。这实际上影响的是正确性（false positive 导致数据损坏），而非性能。论文未分析 secure mode 下的碰撞率和数据完整性风险。

2. **OFT 空间永久预留的合理性存疑**：论文以"仅 0.2% 空间开销"论证预留 OFT 的可行性，但这是对**所有**物理块预留，即使大部分场景可能不存在连续块写入。对于存储容量本就紧张的场景（如论文讨论的移动设备），这一开销值得更仔细的权衡。

3. **PM 平台的局限性被淡化**：实验主要基于 Intel Optane DCPMM，但该产品已停产。论文虽然在 §6.7 补充了 SSD 实验（FEMU 模拟的 Z-SSD），但模拟环境与真实 ULL SSD 的差距未讨论。GogetaFS 在 SSD 上仅达 F2FS 的 79%–99.6%（去重率为 0% 时），说明在 SSD 上 LFP 的收益有限。

4. **并发控制的乐观策略存在隐患**：GLT 的乐观并发控制（插入前再次检查 FP 是否存在）在高重复率 + 高并发下可能导致大量重试，但论文未分析这一 worst case 的性能影响。

5. **静态哈希表（SHT）不支持扩展**：论文明确承认"table extension is not currently supported"，但对于长期运行的系统，数据增长不可避免。预分配 2× 容量是一种妥协，对容量规划提出了较高要求。

6. **对比基线的公平性**：Light-Dedup 配置了 "no delay flushing" 以确保正确性，这可能不是其最优配置。而 GogetaFS 默认使用 fast mode（关闭校验和），两者的 reliability 保证并不对等。

---

## 七、总结

GogetaFS 提出了 LFP（Logical-Fingerprint-Physical）映射，将去重的 FP2P 条目与文件系统 L2P 条目合并，复用文件系统成熟的 I/O 路径和 crash consistency 机制，消除了去重元数据的独立持久化开销。在 PM 平台上，GogetaFS 比现有 DedupFS 提高 5.6%–35.0% 的 I/O 吞吐量，去重元数据开销降低 75%–93%。该方案的核心前提是非密码学 FP 足够小（8 字节）使得 LFP 空间开销可接受，适用于配备新型快速存储设备的去重场景。主要局限在于对文件系统的侵入式修改增加移植成本，以及 PM 平台（Optane DCPMM）的前景不明。
