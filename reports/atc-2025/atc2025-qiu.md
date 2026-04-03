# HotRAP: Hot Record Retention and Promotion for LSM-trees with Tiered Storage

**作者**：Jiansheng Qiu, Fangzhou Yuan, Mingyu Gao, Huanchen Zhang（清华大学交叉信息研究院 & 上海期智研究院）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/qiu
**源文件**：[[atc2025-qiu.pdf]]

---

## 一、背景

LSM-tree 是构建 key-value store 和数据库存储引擎的主流数据结构，广泛应用于 RocksDB、TiKV、CockroachDB 等系统。随着存储硬件的演进，tiered storage（分层存储）架构日益普及——用少量快速 SSD 搭配大容量廉价 HDD 或云存储，以大幅降低存储成本（同等容量下可减少约 77% 的存储开销）。如何在分层存储上优化 LSM-tree 的读写性能，成为一个重要的实际问题。

---

## 二、要解决的问题

现有 LSM-tree 在 tiered storage 上有两种基本方案，各有缺陷：

1. **Tiering 方案**（上层放 fast disk，下层放 slow disk）：写入高效（append-only 特性使最新写入自动落在快速层），但热读数据可能沉在慢盘，无法主动提升到快速层，读性能差。
2. **Caching 方案**（所有层级在慢盘，快盘作缓存）：能缓存热读数据，但 compaction 全在慢盘上执行，写性能受限；且写操作需要在两个层级都执行，带来额外开销和一致性挑战。

在 tiering 方案基础上尝试改进的已有工作（LogStore、MirrorKV、PrismDB 等）存在三个关键限制：

- **限制 1**：以 SSTable/block 为粒度迁移数据，冷数据搭便车占用宝贵的快速层空间。
- **限制 2**：若改为 record 级别追踪热度，元数据量巨大（可能需要 166 GB 内存追踪 1 TB 热数据），超出内存容量。
- **限制 3**：仅通过 compaction 提升热数据，在读密集场景中 compaction 频率低，热数据提升延迟大，可能错过数据的热窗口期。

---

## 三、洞察与设计

**关键洞察**：热度追踪的元数据可以存放在磁盘（fast disk）上而不是内存中——通过将热度追踪结构本身设计为一个小型 LSM-tree（RALT），可以以极低的内存开销（仅数据量的 0.056%）实现 record 级别的精细热度追踪。同时，除了被动等待 compaction，还可以通过主动 flush 机制将热数据及时提升到快速层。

基于此洞察，HotRAP 在 tiering 方案基础上引入三个核心设计：

### 1. RALT（Recent Access Lookup Table）

- 本质是一个存储在 fast disk 上的小型 LSM-tree，记录每个被访问 key 的热度信息
- 每条记录仅存储 key、value 长度（非 value 本身）和热度元数据，物理大小约 25 字节
- 使用 Bloom filter 在内存中判断 key 是否热（14-bit bloom filter，整体假阳率远低于 1%）
- 通过 auto-tuning 算法自动调整热集合大小限制，适应动态变化的工作负载

### 2. Hotness-aware Compaction（热感知压缩）

- 在 FD→SD 的 compaction 过程中，通过 RALT 查询每条记录的热度
- 热记录被写回 FD（retention），冷记录才下沉到 SD
- SD 内部的 compaction 也具有热感知能力，将热记录提升到更高层级
- 修改 cost-benefit score 为 (FileSize - HotSize) / OverlappingBytes

### 3. Promotion by Flush（刷新提升）

- 引入 promotion buffer（64 MiB），缓存从 SD 读取的记录
- 当 buffer 满时，通过 RALT 筛选出热记录，直接 flush 到 L0
- 设计了完整的并发控制机制（Checker 线程 + 版本检查 + updated 标记）确保不会用旧版本覆盖新版本

---

## 四、实现细节

HotRAP 基于 RocksDB 实现，代码开源在 https://github.com/hotrap/HotRAP。

**RALT 实现**：
- 使用 unsorted buffer 作为内存中的写入缓冲（利用热 key 会在 buffer 中被再次命中的特性）
- 四种操作：插入访问记录、检查 key 热度（通过 Bloom filter）、扫描范围内热 key（merge iterator）、计算范围内热集合大小（index block 差值）
- Disk 使用约数据量的 1%，内存使用约数据量的 0.056%
- I/O 开销：读放大约 30，写放大约 20，但因 RALT 不存 value，总 I/O 仅占系统的 5.2%–9.7%

**Auto-tuning 算法**：
- 每条记录维护 counter c 和 tag t，定义 stable = (c > 0 且 t = 1)
- 每访问 R（= FD size）数据量后全局衰减 counter
- 超限时先驱逐 unstable 低分记录，再驱逐 stable 低分记录
- 热集合大小上限 = stable 记录大小 + D_hs（0.05 × FD size），同时不超过 R_hs（0.85 × 最后一层 FD 大小）

**写放大控制**：
- 通过调整 SD 第一层的 size ratio 为 pT（p 为冷数据比例），使额外写放大仅为 1/(2p)
- 在 SD 末尾追加一个 size ratio 为 1/p 的额外层级补偿

**Promotion buffer 并发控制**：
- 插入前检查相关 SSTable 是否正在或已被 compaction（abort rate < 1%）
- Checker 线程在后台处理 immutable promotion buffer，通过 snapshot + Bloom filter 检查 FD 中是否存在更新版本
- MemTable 变为 immutable 时标记与 promotion buffer 中重复的 key 为 updated

---

## 五、实验结果

**实验平台**：AWS EC2 i4i.2xlarge（8 vCPU，64 GiB 内存，1875 GB NVMe SSD 作 FD，gp3 作 SD）。FD:SD 容量比 = 10:100 GB，内存预算 1 GB。

**对比系统**：RocksDB-FD（上界）、RocksDB-tiering、RocksDB-CL（CacheLib）、SAS-Cache、PrismDB。

### YCSB 基准测试（1 KiB 记录，hotspot-5%）

| 工作负载 | vs Tiering 最优 | vs Caching 最优 | vs 所有基线 |
|---------|----------------|----------------|------------|
| Read-only (RO) | 5.2× | ≈ 持平 RocksDB-CL | 5.2× |
| Read-write (RW) | 1.6× | 1.6× | 1.6× |
| Write-heavy (WH) | ≈ 持平 | 2.1× | 2.1× |
| Update-heavy (UH) | ≈ 持平 | 优于 caching | 与 tiering 持平 |
| Uniform（开销测试） | 仅慢 4.0% | - | 低开销 |

### Twitter 生产负载

- 最高达 5.35× 加速（cluster 17）
- 在高比例 sunk + hot record 读场景下达 1.5× 加速
- 低比例场景下也不显著慢于 RocksDB-tiering

### 消融实验

| 组件 | 关闭后影响 |
|------|-----------|
| Hotness-aware compaction | 提升流量增加 6.5×，compaction I/O 增加 35.8%，命中率从 94.8% 降至 72.0% |
| Promotion by flush | RO 场景命中率上升极慢，无法及时捕获热数据 |
| Hotness checking | Uniform 下提升量增加 204×，compaction I/O 增加 168× |

### 大数据集（1.1 TB）

性能趋势与 110 GB 数据集一致，验证了可扩展性。

### Cost breakdown

RALT 仅占 3.7%–11.2% CPU 时间和 5.2%–9.7% I/O。

---

## 六、批判性分析

1. **实验平台单一**：所有实验仅在 AWS EC2 i4i.2xlarge 上进行，FD/SD 的性能差异比（随机读 IOPS 约 8.3:1，顺序带宽约 4.7:1）是特定的。在性能差异更小（如 NVMe vs SATA SSD）或更大（SSD vs 跨区域云存储）的场景下，HotRAP 的收益可能有很大变化，但论文未讨论。

2. **Update-heavy 场景收益有限**：UH 场景下 HotRAP 与 RocksDB-tiering 性能持平，因为频繁更新的热 key 自然会被 flush 到 FD。这实际上暴露了一个问题——HotRAP 的核心价值仅在"读多写少且有热点"的场景才显著，适用范围比摘要暗示的要窄。

3. **Scan 场景完全放弃**：论文在 Discussion 中承认 HotRAP 不优化 range scan，将其留作 future work。但很多 LSM-tree 工作负载（如 OLAP 查询、日志扫描）以 scan 为主，这限制了实际适用性。

4. **Auto-tuning 算法的假设较强**：算法假设热 key 的访问是随机分布的（i.i.d.），在 sequential flooding 等模式下无法工作。虽然论文声称这在实际中不常见，但未提供量化证据。

5. **写放大分析偏乐观**：§3.8 的写放大分析假设可以通过调整 level size ratio 来降低额外写放大，但这改变了原始 LSM-tree 的层级结构，可能对其他操作产生连带影响（如 lookup 需要探测更多层级），论文未充分讨论这一 trade-off。

6. **与 RangeCache 的比较不够公平**：论文用 RocksDB 的 row cache 模拟 RangeCache（因其未开源），这可能低估了 RangeCache 的真实性能。

---

## 七、总结

HotRAP 是一个基于 RocksDB 的 key-value store，通过在 fast disk 上维护轻量级的 on-disk 热度追踪结构（RALT）和双路径提升机制（hotness-aware compaction + promotion by flush），实现了 record 级别的精细热数据管理。在 hotspot 和 Zipfian 等常见倾斜分布下表现出色（最高 5.2× 加速），且在无热点场景下开销极低（< 4%）。主要局限在于不支持 scan 优化、update-heavy 场景收益有限、以及对 sequential 访问模式的适应性不足。
