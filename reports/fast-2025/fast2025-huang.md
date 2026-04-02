# HaSiS: A Hardware-assisted Single-index Store for Hybrid Transactional and Analytical Processing

**作者**：Kecheng Huang (The Chinese University of Hong Kong), Zhaoyan Shen (Shandong University), Zili Shao (The Chinese University of Hong Kong), Feng Chen (Indiana University Bloomington), Tong Zhang (Rensselaer Polytechnic Institute & ScaleFlux Inc.)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/huang
**源文件**：[[fast2025-huang.pdf]]

---

## 一、背景

HTAP（Hybrid Transactional and Analytical Processing）是数据库领域的重要研究方向，要求系统同时高效服务 OLTP（低延迟事务处理）和 OLAP（高吞吐分析查询）两类工作负载。然而，OLTP 偏好行存储格式（如 B+-tree 索引的行页），OLAP 偏好列存储格式（如 Parquet），两者的存储格式需求天然冲突。

现有 HTAP 系统普遍采用**多索引设计**——同时维护行索引和列索引，通过 ETL 或日志传输在两者之间迁移数据。这种设计已有大量工业实践（TiDB、ByteHTAP、PolarDB-IMCI、SAP HANA 等），但带来了数据新鲜度和性能方面的根本性挑战。

与此同时，带有内置透明压缩功能的计算存储设备（Computational Storage Drives, CSDs）已经商业化（如 ScaleFlux CSD-3310），为存储管理软件提供了新的设计空间。

---

## 二、要解决的问题

1. **数据新鲜度问题**：多索引设计中，行存到列存的数据迁移是异步操作，OLAP 查询的数据延迟从数十毫秒到数分钟不等。虽然可以让 OLAP 直接访问行存索引，但会带来严重的读放大，收益不一定大于损失。

2. **OLTP/OLAP 性能干扰**：跨索引数据迁移是 I/O 密集操作，产生大量写放大，导致前台 OLTP/OLAP 服务的 I/O 竞争和性能下降。迁移负载随 OLTP 更新强度增加而加重，形成恶性循环。

3. **存储空间浪费**：多存储设计需要维护数据的多个副本（行存 + 列存），增加了存储开销。

核心矛盾：现有方案在数据新鲜度、OLTP 性能、OLAP 性能三者之间无法同时取得最优。

---

## 三、洞察与设计

**关键洞察**：具备透明压缩能力的 CSD 允许软件有意使用稀疏填充的 4KB LBA 块（例如 1KB 实际数据 + 3KB 零填充），而 CSD 的压缩引擎会将这些低熵数据高效压缩，不会浪费物理存储空间。这意味着逻辑存储空间的使用可以与物理存储空间消耗完全解耦，从而使得之前因空间浪费而不可行的稀疏数据布局变得实际可用。

基于这一洞察，HaSiS 提出了**单索引单存储**的 HTAP 设计，用一棵增强的 B+-tree 同时服务 OLTP 和 OLAP，彻底消除跨索引数据迁移。具体包括三大设计：

1. **页大小与写放大解耦**：传统 B+-tree 中写放大与页大小成正比，因此 OLTP 数据库通常用小页（8-16KB），但这对 OLAP 不利。HaSiS 利用 CSD 的透明压缩，将全局日志（global log）的增量更新暂存在稀疏的 delta page 中，通过两阶段异步 compaction 合并到大页（128KB column page），实现大页存储而不显著增加写放大。

2. **稀疏页内列打包（Sparse Intra-page Column Packing）**：在每个 128KB B+-tree 页内采用 PAX 格式按列存储，并将同列数据对齐到 4KB LBA 边界的 mini-page 中，零填充剩余空间。CSD 压缩保证这些稀疏页不浪费物理空间，而 OLAP 扫描时只需读取涉及的 mini-page，大幅降低读放大。

3. **每页聚簇的多版本记录**：利用预分配的 LBA 空间，delta page 可以临时保存多版本记录，实现 MVCC 而不需要额外的元数据或索引，不影响 OLAP 扫描性能。

此外，HaSiS 设计了**混合缓冲池（Hybrid Buffer Pool）**，让 OLAP 查询绕过缓冲池（因 OLAP 查询局部性差），避免缓冲池污染；采用基于失效的缓存策略管理 hybrid page 的生命周期。

---

## 四、实现细节

- **Hybrid Page 结构**：每个 hybrid page 包含一个 128KB 的 column data page（PAX 格式）和一个 16KB 的 delta page。Column data page 内部按列划分为多个 mini-page，每个 mini-page 对齐 4KB LBA 边界。Delta page 以行格式存储最近的事务更新。

- **Global Log 与两阶段 Compaction**：
  - 事务写入先追加到全局日志的 open segment 中（支持 blind update，不需要加载原始页到内存）
  - **Minor compaction**：将 sealed segment 中的日志记录按键排序，合并到对应 hybrid page 的 delta page
  - **Major compaction**：当 delta page 满时，将其记录合并到 column data page 中

- **Mini-page 设计**：每个列的数据被组织为 4KB 对齐的 mini-page。OLAP 扫描只需读取目标列涉及的 mini-page，而非整个 128KB 页。多个 mini-page 可以批量读取以提升效率。

- **多版本并发控制**：当 AP 扫描正在访问某 hybrid page 时，新的 TP 写入通过分配额外的 delta page 临时保存新版本，扫描完成后再合并。

- **分区并行**：支持基于记录数量的 B+-tree 分区，细粒度分区（如 25K 记录/分区）可减少锁竞争，提升并行度。

- 实现语言未明确说明，原型已开源在 GitHub（https://github.com/ericaloha/Hasis）。

---

## 五、实验结果

**实验平台**：22-core Intel Xeon E5-2696 v4 (2.2GHz), 64GB DDR4, 7.68TB ScaleFlux CSD-3310 SSD, Ubuntu 20.04, Linux 5.15, Ext4。

**工作负载**：基于 CH-Benchmark（TPC-C + TPC-H）的翻译 SQL 请求。

### 与 TiDB 对比

| 指标 | HaSiS | TiDB |
|------|-------|------|
| OLAP 数据延迟 | 17.31µs ~ 121.5µs（稳定） | 30.1µs ~ 2,676.3µs（大幅波动） |
| Insert/Update 延迟 | 比 TiDB 仅高 3.77%/3.66% | 基线 |
| Lookup/Scan_TP 延迟 | 比 TiDB 低 6.90%/1.21% | 基线 |
| Scan_AP 延迟 | 比 TiDB 低 6.64% | 基线 |
| 物理存储空间 | 74.1 GB | 231.5 GB（HaSiS 节省 67.98%） |

### 与专用存储引擎对比

| 指标 | HaSiS vs RS | HaSiS vs CS | HaSiS vs Parquet |
|------|-------------|-------------|-----------------|
| OLTP 吞吐 | 差距在 5.11% 以内 | — | — |
| OLTP 延迟 | 差距在 5.82% 以内 | — | — |
| Scan 性能 | 吞吐高 49.36%，延迟低 26.92% | — | — |
| OLAP 查询延迟 | — | 开销 < 7.71% | 开销 < 7.12% |

### 其他关键结果

- **性能隔离**：随 AP:TP 比例从 1/50000 增到 1/1000，HaSiS 的 OLTP 吞吐和 OLAP 响应时间保持稳定，RS 和 CS 均出现明显波动
- **可扩展性**：10~50 客户端线性扩展（110.7 KOPS → 168.9 KOPS）
- **物理 I/O 放大**：HaSiS 仅为 RS 的 37.4%、CS 的 42.5%、TiDB 的 69.5%
- **CSD vs 普通 SSD**：性能几乎相同，但普通 SSD 上存储空间消耗超过 2 倍（168.7GB vs 71.2GB）

---

## 六、批判性分析

1. **硬件依赖性是核心风险**：HaSiS 的设计强依赖于 CSD 的透明压缩特性。Table 2 显示在普通 SSD 上存储空间膨胀至 2.37 倍，这意味着在没有 CSD 的环境下该设计的核心优势消失。论文声称"HaSiS 不依赖 ScaleFlux 的特定硬件实现"，但实际上依赖透明压缩这一尚未广泛普及的 CSD 特性，商业可用性有限（论文仅提及 ScaleFlux、DapuStor、IBM FCM 三个厂商）。

2. **基线对比不够公平**：TiDB 以分布式模式部署（TiDB + TiKV + PD + TiFlash），但 HaSiS 是单节点原型。分布式系统固有的网络和协调开销被纳入了对比，这对 TiDB 不公平。虽然论文排除了 Raft 日志传播延迟，但 TiDB 的多组件架构本身的开销难以完全剥离。

3. **工作负载代表性有限**：论文将 TPC-C/TPC-H 的 SQL 查询翻译为键值操作，绕过了数据库查询优化器和执行引擎。这使得评估只测试了存储引擎层的 I/O 性能，而非端到端的 HTAP 性能。真实 HTAP 场景中查询规划、连接操作等上层开销可能改变性能格局。

4. **Compaction 的尾延迟未充分讨论**：论文展示了 200 分钟测试中 compaction 的"稳定触发模式"，但未报告 compaction 期间的 P99/P999 延迟。对于延迟敏感的 OLTP 应用，尾延迟可能是关键指标。

5. **数据集规模偏小**：实验使用 500 个 warehouse 的 TPC-C 数据集，物理存储约 74GB。对于现代 HTAP 场景（TB 到 PB 级），该规模的实验结论能否外推存疑。

6. **稀疏页布局对压缩比的假设过于乐观**：论文假设零填充的稀疏数据能被 CSD 高效压缩，但如果实际数据本身的压缩比已经很高（如文本数据），额外的零填充带来的压缩收益可能不如预期。论文未分析不同数据类型和压缩比下的表现。

---

## 七、总结

HaSiS 提出了一种基于 CSD 透明压缩的单索引 HTAP 存储设计，通过将页大小与写放大解耦、稀疏列打包、页内多版本管理三个核心机制，用一棵增强的 B+-tree 同时服务 OLTP 和 OLAP 工作负载，实现了接近即时的数据新鲜度。相比 TiDB，HaSiS 在数据新鲜度、存储空间和 I/O 放大方面有显著优势，OLTP/OLAP 性能与专用引擎相当。主要局限在于强依赖 CSD 硬件特性、评估规模偏小、以及作为存储引擎原型缺乏完整数据库系统的端到端验证。
