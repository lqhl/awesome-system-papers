# Cost-efficient Archive Cloud Storage with Tape: Design and Deployment

**作者**：Qing Wang¹*, Fan Yang²*, Qiang Liu², Geng Xiao², Yongpeng Chen¹, Hao Lan¹, Leiming Chen², Bangzhu Chen², Chenrui Liu², Pingchang Bai², Bin Huang², Zigan Luo², Mingyu Xie², Yu Wang², Youyou Lu¹, Huatao Wu²†, Jiwu Shu¹,³†（¹清华大学, ²华为云, ³闽江大学）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/wang
**源文件**：[[fast2026-wang.pdf]]

---

## 一、背景

全球数据量以前所未有的速度增长（2024 年每日产生约 402.74 百万 TB），其中大量数据（医学影像、备份、视频素材、日志等）很少被访问但必须长期保留。归档存储（archive storage）因此成为云服务的重要组成部分，AWS、GCP、阿里云、华为云等主流云厂商均提供归档存储服务。

磁带作为一种古老但仍在演进的存储介质，相比 HDD 具有显著的 TCO 优势：单位 GB 价格低 50% 以上、寿命长一倍（10 年 vs. 5 年）、能耗更低、存储密度更高，且有清晰的技术路线图（2024-2034 年容量年均增长 32%）。然而，磁带库（tape library）具有独特的硬件特性：drive 数量远少于 cartridge（如 1000 盒磁带仅配 4 个 drive）、挂载磁带耗时约 80 秒、顺序访问导致 seek 开销大。这些特性使得构建基于磁带的大规模分布式存储系统面临全新挑战。

---

## 二、要解决的问题

1. **Drive thrashing**：磁带库中 drive 数量极其有限（4 个 drive 服务 1000 盒磁带），频繁切换磁带会导致 drive 长时间处于挂载/卸载状态，无法充分利用 360 MB/s 的原始带宽。仅切换后连续访问 23.2 GB 数据，有效带宽就会减半。

2. **磁带内随机读取开销大**：磁带由数百个 wrap 组成，随机访问需要反复倒带/快进，seek 时间显著。元数据访问如果分散在磁带上，会严重影响读取性能。

3. **磁带池聚合带宽受限**：有限的 drive 数量限制了磁带池的峰值带宽，如果同步服务用户请求，低带宽会直接暴露给用户。

4. **垃圾回收开销**：磁带是 append-only 的，删除对象后无法原地回收空间，需要 GC。如果同一磁带上的对象生命周期差异大，GC 需要大量读写有效数据。

5. **纠删码导致读放大**：传统 intra-object EC 将单个对象分散到多盒磁带，读取时需要访问 m 盒磁带的 m 个 drive，加剧 drive thrashing。

---

## 三、洞察与设计

**关键洞察**：归档存储的 SLA 允许小时级延迟（restore 需要 3-12 小时），这意味着对磁带池的所有读写都可以异步化。异步化后，系统可以在 HDD 缓冲池中积攒大量请求，然后批量调度，使磁带的访问模式与其硬件特性（顺序写、批量读、避免频繁换带）对齐。

基于这一洞察，TapeOBS 采用「全异步磁带池 + HDD 缓冲池」架构：

- **HDD Pool 作为暂存区**：容量约为磁带池的 4%，所有用户写入先落 HDD pool（高可用），再异步刷到磁带池；restore 请求也是先异步从磁带拷贝到 HDD pool，再服务用户读取。
- **批量调度（Bulk Scheduling）**：
  - **写入方向**：按对象的预估删除时间（基于 expiration time）分组（3 个月粒度），相似生命周期的对象写入同一磁带，降低 GC 开销。
  - **读取方向**：将 restore 请求按 deadline 收集、按 partition 分组、按物理位置排序后批量下发，减少 drive thrashing 和 seek time。
- **Dedicated Drives**：将 4 个 drive 静态分为 2 个 write drive、1 个 read drive、1 个 internal drive（consistency checking / EC repair / GC），避免不同任务的访问模式互相干扰导致 drive thrashing。
- **Batched Erasure Coding (b-EC)**：在 service layer 聚合多个对象后发起一次 PLog append，实现 inter-object EC。单个对象只存在于一两盒磁带上，读取时需要的 drive 数大幅减少。TapeOBS 使用 12+2 EC 配置，冗余率仅 1.17。
- **Tape-tailored Local Storage Engine**：
  - **Virtual Database (VDB)**：利用 head server 上的两块 NVMe SSD，MetaStore 存储所有 sub-PLog 元数据（每个 256B，10PB 磁带库仅需 <50GB SSD 空间），DataStore 作为持久写缓冲。避免了磁带上的随机元数据访问。
  - **Tape Library Scheduler (TLS)**：SCAN 算法按物理位置重排 sub-PLog 读取顺序，减少 seek 时间；flow control 对齐 I/O 提交速率与 drive 速度，避免 drive 选择低速模式导致性能退化。

---

## 四、实现细节

- **PLog 抽象**：华为云存储基础设施的基本存储单元，append-only，内部通过 replication 或 EC 实现高可用。每个 PLog 有 64-bit unique ID（plog-id），通过 `pt-id = plog-id % N` 映射到 partition，partition view 决定 EC group 中的磁带分布。
- **b-EC 实现**：service layer 在内存中聚合多个对象（如 5 个对象共 1.5GB），创建单个 PLog 并一次 append，PLog-Client 水平切分为 12 个 data chunk + 2 个 parity chunk 分发到 14 个磁带架。使用华为自研的 LDEC 算法（基于 XOR 和 Galois 域乘法的 MDS array code）。
- **VDB 的 KV Store**：预分配 key array 和 value array（固定大小 KV），DRAM 中维护 hash table 索引。Crash-consistent：key 写入原子性、value 通过 DIF（每 4KB 数据附带 8B plog-id + offset + 4B checksum）自校验、key-value 可交叉验证、recovery 时扫描 key array 重建 hash table。
- **元数据分区**：磁带满时将 MetaStore 中的元数据 dump 到磁带的 metadata partition（利用硬件分区特性），加速 SSD 故障后的恢复。
- **Flow Control**：TLS 周期性读取 drive buffer 大小估算 drive 速度（DS），通过 rate limiter 将 I/O 提交速率对齐到 DS。当待提交数据 <100MB 时绕过 rate limiter。
- **Write Drive 固定磁带**：MDC 保证每个磁带库只有两个 active partition 包含它，plog-id 分配限定在这两个 partition，使 write drive 持续 append 同一盒磁带直到写满。

---

## 五、实验结果

TapeOBS 于 2022 年底开始灰度发布，2024 年正式服务客户。部署规模：每个磁带池 14 个磁带架，单池总容量 140PB，当前已存储数百 PB 原始用户数据。

| 指标 | 数值 |
|------|------|
| 磁带库配置 | 1000 cartridges × 10,742 GB = 10.24 PB, 4 drives × 360 MB/s |
| EC 配置 | 12+2，冗余率 1.17 |
| HDD/Tape 容量比 | 约 4:100 |
| TCO 对比（10 年，100PB 起步，50% 年增长） | Tape CapEx 低 2.68×, OpEx 低 16.11×, 总 TCO 低 4.95× |
| 磁带池写吞吐（24h 均值） | 118.81K ops/min（≈831.67 GB/min） |
| 磁带池读吞吐（24h 峰值） | 5.85K ops/min |
| 写延迟（stripe = 7MB） | 中位数 18.51ms, P99 27.75ms（写到 SSD DataStore 即完成） |
| HDD 池利用率 | 稳定在 ~71.6%（水位线 75%） |

**工作负载特征**：
- 对象大小高度偏斜：<500MB 的对象占 93.81% 存储空间，50-100MB 区间占 69.95%
- 操作比例极度倾斜：最大客户写操作占 99.999888%，读仅 0.000112%，删除几乎为 0
- 5 个最大客户中有 2 个从未发起读请求

**故障统计**（约 1.25 年，<200 个磁带库）：共 17 次磁带库相关故障，其中 drive 软件 bug 4 次、drive 故障 4 次、drive 无法识别磁带 4 次、drive 未找到 1 次、机械臂卡住 2 次、head server 与磁带库断连 2 次。

---

## 六、批判性分析

1. **单可用区（single-AZ）部署的局限被轻描淡写**：论文仅在部署章节一笔带过 TapeOBS 是 single-AZ 服务，但对于归档存储而言，跨 AZ/跨区域容灾是核心需求。磁带的物理特性（不可远程访问、搬迁成本高）使得跨 AZ 方案极为困难，论文回避了这一关键问题。

2. **TCO 分析假设过于简化**：10 年 TCO 对比假设初始 100PB、50% 年增长，但未考虑 HDD 池的额外成本（占磁带池 4%）、head server / SSD / 网络设备成本、运维人力成本差异，也未考虑 HDD 价格持续下降的趋势。4.95× 的 TCO 优势可能被高估。

3. **b-EC 的 degraded read 代价被淡化**：论文承认 b-EC 使 degraded read 数据量从 S 增加到 S×m（m=12），增加 12 倍，仅以"degraded read 频率低"为由认为可接受。但磁带的 MTBF 和 drive 故障率（17 次故障/1.25 年/<200 库）表明故障并不罕见，degraded read 的实际影响值得更深入分析。

4. **Dedicated drives 的资源浪费未量化**：论文承认这是 primary limitation，提到可以按小时粒度重分配 drive，但这只是"could"而非已实现。在归档工作负载中读请求极少（0.000112%），专门分配 1 个 read drive 的必要性存疑。

5. **生命周期分组的准确性依赖用户设置 expiration time**：论文假设用户会为 bucket/object 设置 expiration time，但未讨论未设置 expiration 的场景如何处理，也未给出实际有多少比例的数据有明确的 expiration time。

6. **Flow control 的根因分析不够深入**：论文发现 drive 在 I/O 提交速率不稳定时会选择低速模式，但仅基于推测（"we think the reason is..."），未与 drive 厂商确认或分析 drive firmware 行为。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 归档的潜在场景**：大规模训练产生大量 checkpoint，训练完成后大部分 checkpoint 很少被访问但需保留用于复现和审计。TapeOBS 的 lifetime-based placement 和 b-EC 设计可直接适配这一场景——checkpoint 天然具有相似的生命周期，且单个 checkpoint 通常在数十到数百 GB 级别，与 TapeOBS 当前的对象大小分布吻合。

2. **分层存储对 AI 训练数据管理的启发**：TapeOBS 的「HDD 缓冲池 + 磁带池」异步分层架构，可借鉴到训练数据管理中。大量预处理好的训练数据可以按 epoch 使用频率分层：活跃数据存 SSD/HDD，完成训练的数据集异步归档到廉价存储（磁带或 cold object storage）。批量调度的思路可用于优化大规模数据集在不同存储层之间的迁移。

3. **值得跟进的研究方向**：
   - 如何为 AI 工作负载设计 tape-aware 的 checkpoint 管理系统，结合模型训练的 checkpoint 策略（频率、保留策略）与磁带的批量写入特性
   - 探索磁带在大规模 embedding / feature store 冷数据归档中的应用，这类数据量巨大但查询模式与传统归档不同（可能有批量 restore 需求）

---

## 八、总结

TapeOBS 是华为云基于磁带构建的归档存储服务，通过三个核心设计原则——全异步磁带池、最小化 drive thrashing、避免磁带内随机读取——将磁带的硬件特性与云存储需求对齐。其关键创新包括 HDD 缓冲池实现的批量调度（lifetime-based placement 降低 GC、request reordering 减少 thrashing）、batched EC 减少读取时的 drive 需求、以及 SSD-based 本地存储引擎消除磁带上的元数据随机访问。系统已存储数百 PB 数据，TCO 相比 HDD 方案降低约 5 倍。主要局限在于 single-AZ 部署、dedicated drives 的潜在资源浪费、以及 b-EC 在故障场景下的读放大。
