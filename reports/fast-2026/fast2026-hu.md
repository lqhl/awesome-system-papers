# PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases

**作者**：Qingda Hu, Xinjun (Jimmy) Yang, Feifei Li, Junru Li, Ya Lin, Yuqi Zhou, Yicong Zhu, Junwei Zhang, Rongbiao Xie, Ling Zhou, Bin Wu, Wenchao Zhou（Alibaba Cloud Computing）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/hu
**源文件**：[[fast2026-hu.pdf]]

---

## 一、背景

云原生关系型数据库（如 AWS Aurora、Azure Hyperscale、Alibaba PolarDB）广泛采用存算分离架构，计算资源可以弹性伸缩，但存储成本仍然是用户的核心关切。数据压缩是降低存储成本的直观方案，但在大规模 RDBMS 中实现高空间利用率的同时保持低 I/O 延迟，面临根本性的工程挑战。

现有压缩方案分为软件压缩和硬件压缩两类。软件压缩（B+-Tree、LSM-Tree、日志结构块存储）提供灵活的压缩参数，但要在字节级索引粒度和空间管理开销之间取舍。硬件压缩（CSD、FPGA 加速器）能消除软件开销，但受限于固定的 4KB 输入大小和不可变的压缩算法。

---

## 二、要解决的问题

1. **软件压缩的性能开销**：细粒度索引（字节级）能提高空间利用率，但引入复杂的空间管理开销。粗粒度索引（4KB 级）管理简单但空间浪费严重——实验显示 4KB 索引粒度比字节级多消耗约 80.5% 的空间。B+-Tree 天然有约 20%~50% 的页面碎片，LSM-Tree 有严重的 GC 开销，日志结构块存储存在 I/O 放大。

2. **硬件压缩的灵活性不足**：CSD 受限于 NVMe 兼容性要求的固定 4KB 输入大小和出厂后不可修改的压缩算法；FPGA/CPU 加速器同样算法固定。不同工作负载需要不同的压缩参数（冷数据用大块+复杂算法，热数据用小块+简单算法），硬件方案无法适应。

3. **大规模部署的稳定性和可扩展性**：主机级别的资源竞争（CPU/内存被 host-based FTL 消耗）和驱动故障会导致全节点故障；集群级别不同用户数据压缩比差异大，导致逻辑空间与物理空间分配不均衡。

---

## 三、洞察与设计

**关键洞察**：将压缩分为软件层和硬件层两个阶段，软件层负责将数据压缩到 4KB 对齐的块（提供灵活的输入大小和算法选择），硬件层（CSD）利用已有的 FTL 机制将 4KB 块进一步压缩到字节级（实现零额外软件开销的细粒度索引）——这样软件层只需管理简单的 4KB 对齐块，而字节级索引的复杂性完全由硬件 FTL 的 GC 机制免费承担。

### 双层压缩架构

- **软件层**：将 16KB 数据库页面压缩为多个 4KB 对齐块，使用 bitmap allocator + hash table index 管理空间映射。支持三种压缩模式：normal compression（默认，页面对齐 I/O）、no compression（非对齐 I/O 或用户指定不压缩的页面）、heavy compression（归档操作，将整个范围作为一个压缩单元）。
- **硬件层（PolarCSD）**：实现 gzip level 5 算法，扩展传统 page-mapping FTL 支持变长索引条目（从 4KB 对齐 LBA 映射到字节级 PBA），每个映射条目增加 12-bit 的 length 和 offset 字段（从 5 字节增加到 8 字节）。逻辑容量 7.68TB，物理 NAND 至少 3.2TB，对应平均压缩比 2.4。

### DB-oriented 优化

- **Opt#1 绕过 redo log 压缩**：redo log 写入是事务提交延迟的关键路径。PolarStore 使用 Intel Optane SSD 存储 redo log，完全绕过软硬件压缩。Optane 的有限容量刚好匹配 redo log 小且可频繁回收的特性。
- **Opt#2 自适应算法选择（lz4/zstd）**：传统认为 zstd 压缩比高但解压慢。但在双层压缩下，zstd 相对 lz4 的压缩优势从算法层的 58.9% 降至仅 9.0%（因为硬件 gzip 的 Huffman 编码能有效二次压缩 lz4 输出，但对已包含 Huffman 编码的 zstd 输出收益甚微）。同时 4KB I/O 对齐创造了新机会：即使 zstd 仅比 lz4 少压缩 1 字节，也可能节省整个 4KB I/O 块。PolarStore 在页面写入时逐页评估两种算法，基于 `benefit/overhead > 300B/µs` 阈值动态选择。
- **Opt#3 Per-page log**：利用 CSD 的逻辑-物理空间解耦特性，为每个 16KB 页面分配额外的 4KB log 空间，后台预合并该页面的 redo log。当 RO 节点 LSN 落后导致 log cache 溢出时，可以单次 4KB 读取获取所有必要 log，而非多次随机读取。在传统 SSD 上这会带来 25% 的空间放大，但 CSD 的空间解耦使逻辑空间分配不等于物理空间消耗。

---

## 四、实现细节

### PolarCSD 演进

- **PolarCSD 1.0**：open-channel 架构（host-based FTL），每设备需 15.36GB 主机内存用于 FTL（7.68TB × 8B/4KB），12 设备/服务器共需约 184.32GB。每设备需约 2 个物理 CPU 核心。18 个月内出现 26 次慢 I/O（≥1 秒），其中 6 次超过 10 秒且持续 10 分钟以上。原因：内存竞争（12 次）、CPU 竞争（9 次）、内核驱动 bug（5 次长时间故障）。
- **PolarCSD 2.0**：回归 device-managed FTL（嵌入式 ARM 核心），消除主机资源竞争，故障域缩小到单设备。NAND 容量增至 3.84TB（4TB NAND + 4% over-provisioning），逻辑空间增至 9.6TB。L2P 映射条目从 8 字节优化到 7 字节（物理偏移粒度从 1 字节粗化到 16 字节）。升级到 PCIe 4.0。

### 集群级调度

启用 TRIM 操作修正物理空间监控不准确问题（平均偏差 3%）。实现 compression-aware scheduling：将存储节点在逻辑空间-物理空间二维平面上划分为 A/B/C/D 四个区域，在压缩比过高和过低的节点之间迁移 chunk，使集群内 >90% 节点的压缩比收敛到目标范围。

### 部署规模

- 超过 500 台存储服务器、6000+ PolarCSD 1.0 设备
- 超过 1200 台存储服务器、14400+ PolarCSD 2.0 设备
- 总管理数据超过 100PB

---

## 五、实验结果

### 空间利用率与成本

| 集群 | 硬件 | 软件压缩 | 压缩比 | 物理成本/GB | 逻辑成本/GB |
|------|------|---------|--------|------------|------------|
| N1 | Intel P4510 | 无 | - | 1.00 | 1.00 |
| C1 | PolarCSD 1.0 | 禁用 | 2.35 | 1.45 | 0.62 |
| N2 | Intel P5510 | 无 | - | 0.91 | 0.91 |
| C2 | PolarCSD 2.0 | 启用 | 3.55 | 1.32 | 0.37 |

C2 实现约 60% 存储成本削减。

### 性能（Sysbench，16 线程）

- C1（PolarCSD 1.0，仅硬件压缩）相比 N1 有约 10% 性能下降
- C2（PolarCSD 2.0，双层压缩+所有优化）与 N2 性能基本持平（吞吐量仅低 2.1%）

### Ablation Study（C2 集群，OLTP-Read-Write）

| 配置 | 相比基线吞吐量变化 |
|------|------------------|
| PolarCSD 2.0（仅硬件） | -7.4% |
| +dual-layer（zstd） | -19.6%（相对硬件-only） |
| +bypass redo | 恢复到 -8.9%（相对硬件-only） |
| +lz4/zstd 选择 | 恢复到 -2.1%（相对基线） |

### Per-page log 效果

RO 节点 LSN 落后场景下，线程数 <128 时 P95 延迟降低 28.9%~39.5%。

### 与其他方案对比

PolarDB（启用压缩）在 Sysbench OLTP-Read-Write 下性能显著优于 InnoDB table compression 和 MyRocks，因为后两者在计算节点消耗用户付费的 CPU 资源做压缩，而 PolarStore 在共享存储层透明压缩。

---

## 六、批判性分析

1. **CSD 硬件的通用性问题**：PolarCSD 是阿里巴巴定制硬件，论文未充分讨论其他云厂商或中小规模部署如何复现此方案。双层压缩的核心优势依赖于变长 FTL 映射这一非标准硬件特性，推广性有限。

2. **Optane 依赖的可持续性**：Opt#1 依赖 Intel Optane SSD 存储 redo log 以绕过压缩。Intel 已于 2022 年宣布退出 Optane 业务，论文使用 P4800X 和 P5800X 均为停产产品。虽然其他低延迟存储设备（如 CXL 内存）可替代，但论文未讨论这一关键供应链风险。

3. **压缩比数字的解读需谨慎**：3.55 的整体压缩比来自生产环境混合数据，但论文未给出数据类型分布（文本 vs 数值 vs 二进制）。不同数据集的压缩比变化范围很大（2.12×~3.84×），用户实际体验可能与宣传数字偏差较大。

4. **实验基线不够公平**：与 InnoDB table compression 和 MyRocks 的对比中，PolarStore 的优势很大程度来自存算分离架构（压缩在存储层、不消耗计算节点资源），而非压缩技术本身。对比应在相同架构下进行才有意义。

5. **PolarCSD 1.0 的篇幅分配**：论文用大量篇幅描述了 1.0 的失败经验和 2.0 的改进，这虽然有工程价值，但 1.0 的核心问题（host-based FTL 资源消耗过大）在学术界早已被充分认识，insight 的新颖性有限。

6. **Per-page log 的适用条件**：Opt#3 仅在 RO 节点 LSN 严重落后时才有效果，且线程数超过 128 后由于 CPU 瓶颈效果消失。论文未量化生产环境中该场景的实际发生频率。

---

## 七、AI Infra / MLSys 视角

1. **CSD 对 AI 推理系统的借鉴**：PolarStore 的双层压缩思路可迁移到 LLM 推理场景中的 KV cache 压缩。KV cache 同样面临空间效率 vs 访问延迟的矛盾，软件层做 token-level 量化 + 硬件层做透明压缩的组合值得探索。

2. **自适应算法选择的启发**：Opt#2 发现在多层压缩下，简单算法（lz4）经过后续层压缩后与复杂算法（zstd）的差距大幅缩小。类似现象可能存在于 AI 系统的多级缓存/量化中——例如，粗粒度量化后再经过硬件压缩，可能与精细量化的最终效果接近。

3. **Compression-aware scheduling 对分布式训练的启示**：不同模型分片的压缩比差异（如 attention 层 vs FFN 层的激活值）可能导致分布式训练中存储节点负载不均，类似的 compression-aware 调度策略可用于 checkpoint 存储的负载均衡。

4. **可探索的研究方向**：将 PolarStore 的空间解耦思想应用于 AI 训练的 checkpoint 系统——利用 CSD 的逻辑-物理解耦实现 checkpoint 的透明压缩和增量存储，减少 checkpoint 对训练吞吐量的影响。

---

## 八、总结

PolarStore 是阿里巴巴 PolarDB 的压缩存储系统，通过软件-硬件协同设计的双层压缩架构，在软件层实现灵活的 4KB 对齐压缩，在硬件层（PolarCSD）利用 FTL 实现零开销的字节级索引。配合三项面向数据库的优化（绕过 redo log 压缩、自适应 lz4/zstd 选择、per-page log），在超过 100PB 的生产部署中实现 3.55 的压缩比和约 60% 的存储成本削减，且性能与未压缩集群基本持平。其核心局限在于依赖定制 CSD 硬件和已停产的 Optane SSD，方案的可移植性有待验证。
