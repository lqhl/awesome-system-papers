# Liquid-State Drive: A Case for DNA Block Device for Enormous Data

**作者**：Jiahao Zhou, Mingkai Dong, Fei Wang, Jingyao Zeng, Lei Zhao, Chunhai Fan, Haibo Chen（上海交通大学）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/zhou-jiahao
**源文件**：[fast2025-zhou-jiahao.pdf](../../papers/fast-2025/fast2025-zhou-jiahao.pdf)

---

## 一、背景

全球数据量呈指数级增长，2020 年产生 64.2 ZB 数据，预计 2025 年达到 181 ZB，但全球存储容量仅约 6.7 ZB。传统存储介质（HDD、磁带）密度有限，无法满足海量数据存储需求。DNA 存储以其超高密度（10⁹ GB/mm³，比磁带高 8 个数量级）、极长寿命（可达数百年）和低维护成本，成为存储 ZB 级数据的潜在候选方案。近年来 DNA 合成和测序技术快速发展，成本下降和性能提升速度甚至超越摩尔定律，使 DNA 存储在未来数十年内有望成为现实。

Block 存储接口作为最通用的存储抽象，是将 DNA 存储集成到硅基计算系统中的关键。然而，现有 DNA 存储研究主要集中在 key-value 风格的存储上，完整的 DNA block device 设计仍未被充分探索。

---

## 二、要解决的问题

1. **Block 更新代价极高**：DNA 不支持原地修改（in-place update），必须通过先擦除再写入实现。DNA 的擦除粒度（spot）比读粒度（SC）大 10³ 倍，读粒度又比写粒度（strand）大 10⁶ 倍。原地更新一个 block 需要读取整个 spot 中所有数据、擦除 spot、再写回，开销巨大。

2. **PB 级元数据管理困难**：采用 out-of-place update 需要维护 DNA Translation Layer（DTL）做地址映射。对于 EB 级数据，DTL 本身达到 PB 级，必须存储在 DNA 中。但 DTL 每次写操作都需更新，而 DNA 更新代价极高，嵌套翻译层也无法解决此问题（递归产生同等规模的索引需求）。

3. **GC 元数据管理开销大**：Out-of-place update 需要垃圾回收（GC），而 GC 所需的 reverse translation table 和 valid bitmap 同样达到 PB 级。将这些结构存储在 DNA 中，频繁访问和维护的开销极为可观。

---

## 三、洞察与设计

**关键洞察**：DNA 存储硬件的读写粒度存在极端不对称性——写粒度为单条 strand（约 300 nt），读粒度为整个 SC（包含百万条 strand，约 24 MiB），擦除粒度为整个 spot（包含数千个 SC）。可以利用这种不对称性，将翻译层拆分为两级：GB 级的 L0 DTL 存储在 SSD 上（几乎无访问开销），PB 级的 L1 DTL 存储在 DNA 中但通过 strand 级写入和 SC 级读取来实现低成本增量更新。

基于此洞察，论文提出 **LiqSD（Liquid-State Drive）** 系统，包含三项核心设计：

1. **Dual DTL（双层翻译表）**：将存储分为三层——data layer、L1 DTL、L0 DTL。L0 DTL（GB 级）存于 SSD，映射 logical section address → physical section address；L1 DTL（PB 级）存于 DNA，映射 LBA → PBA。L1 DTL 以 SC 为物理 section，每个 entry 存为一条 strand，更新时插入新 strand（patch）而非修改，利用 strand 级写粒度实现低成本更新。

2. **Symbiotic Metadata（共生元数据）**：将 GC 所需的 reverse translation table 和 valid bitmap 与物理数据 block 共存于 DNA 中——reverse translation entry 存在每个物理 block 最后一条 strand 的 OOB 空间中，valid bit 通过 invalid strand（一条保留 strand）的存在与否来表示。GC 时读取数据 block 即可同时获取元数据，无需额外 DNA 访问。

3. **Delayed Invalidation（延迟失效）**：更新 block 时不立即读取 L1 DTL 来获取旧 block 的 PBA 并标记无效，而是推迟到下次读取 L1 DTL 时，通过 merge patches 和 chain GC patches 来识别和失效 obsolete blocks。配合定制的 GC 策略（GC patch 记录 old PBA 和 new PBA 以追踪迁移链）和分离式缓存（LBA cache + L1 DTL cache + PBA cache）来处理延迟失效引入的不一致性。

---

## 四、实现细节

- **硬件模拟器**：基于 DNA 存储模拟器实现，模拟 strand 的合成、测序和错误注入（替换、删除、插入），精确反映读写放大指标。未做 wet lab 实验。
- **编码方案**：使用 rotation code 满足生化约束，40% 冗余率的 Reed-Solomon Code 纠错。
- **参数配置**：strand 长度 296 nt，payload 246 nt，每个 SC 100 万条 strand，每个 SC 可存 6,211 个 block（4 KiB），每个 spot 含 2,000 个 SC，每个 chip 24 个 spot，共 10 个 chip。
- **L1 DTL**：每个 physical section 含 25 万个 entry，最多容纳 50 万个 patch。
- **SSD 元数据**：write pointer、written patch counter、valid SC/PS bitmap、free/full/work spot list、latest TS recorder，对于 1 EB 数据仅约 5 GiB。
- **缓存**：120 MB，SSD 上实现，LRU 策略，分为 LBA cache（write-back）、L1 DTL cache（write-through）、PBA cache（read-only）。
- **Crash consistency**：每次 DNA 操作前在 SSD 写 redo log，利用 DNA 操作的幂等性保证崩溃一致性。
- **验证**：在 lightweight Ext4 + FUSE + LiqSD 存储栈上成功运行 Vim。
- 源码开放：https://ipads.se.sjtu.edu.cn/projects/liqsd

---

## 五、实验结果

### Microbenchmark

| 指标 | LiqSD | Coarse-DTL | No-DTL |
|------|-------|------------|--------|
| 顺序写放大 | ~1.006 | 1.0 | 1.0 |
| 随机写放大 | ~1.006 | ~90,731 | ~12,276,148 |
| 随机更新写放大 | ~1.006 | ~90,731 | ~12,276,148 |
| 顺序读放大 | 略 >1 | 1.0 | 9,278 |
| 随机读放大 | ~6,200 | ~9,278 | ~9,278 |

- LiqSD 写操作 extra read ratio 几乎为零，No-DTL 和 Coarse-DTL 在随机写/更新时有巨大额外读开销。

### Real-world Traces

| Trace | LiqSD 写放大 | No-DTL 写放大 | LiqSD 读放大 | No-DTL 读放大 |
|-------|-------------|--------------|-------------|--------------|
| Alibaba Cloud | ~1.016 | ~1.2×10⁷ | ~43 | ~2.1×10⁷ |
| MSR Mds | ~1.010 | ~1.2×10⁷ | ~87 | ~8.1×10⁶ |
| MSR Proj | ~1.014 | ~1.2×10⁷ | ~55 | ~5.3×10⁸ |
| MSR Prxy | ~1.010 | ~1.2×10⁷ | ~75 | ~1.6×10⁹ |
| ECFS | ~1.010 | ~1.2×10⁷ | ~4.1 | ~493 |

- 写放大最高降低 7 个数量级，读放大最高降低 6,206× 和 7×。
- Delayed invalidation 对比 eager invalidation：读放大最多降低 15,194×，写放大基本持平。
- GC 开销：写放大在高负载下增加约 1.3×–2.7×，读放大基本不受影响。
- 空间开销仅 3.1%（L1 DTL 2.5% + GC 元数据 0.6%）。

### 延迟估算

- 当前技术下读一个 block 约 49 分钟，写一个 block 约 74 分钟。

---

## 六、批判性分析

1. **纯模拟评估，无实际 wet lab 验证**：论文承认仅基于模拟器评估，未进行任何生物实验。虽然读写放大指标理论上独立于具体硬件进步，但模拟器中的错误模型、strand 合成/测序行为是否准确反映真实 DNA 操作仍存疑。系统在实际 DNA 介质上是否能工作，缺乏实证支持。

2. **实用性距离极大**：当前技术下读写延迟为数十分钟级别（读 ~49 min，写 ~74 min），这使得系统对任何需要交互式访问的场景都不可用。论文对此避重就轻，将讨论集中在"放大率"这一相对指标上，而非绝对性能。

3. **评估 baseline 设置有利于 LiqSD**：No-DTL 采用最朴素的 in-place 更新设计，Coarse-DTL 使用 24 MiB 粗粒度 block。这两个 baseline 过于简单，缺少更合理的中间方案（如 log-structured 写入但不使用 dual DTL 的变体）作为对比。LiqSD 相对这些极端 baseline 的巨大改进（数个数量级）可能夸大了其实际贡献。

4. **Obsolete block 迁移的隐含成本**：Delayed invalidation 导致 GC 无法区分 valid 和 obsolete blocks，可能迁移大量无用数据。论文声称"我们总是选择 non-invalid block 最少的 spot"来减轻此问题，但未给出 obsolete block 比例的定量分析，也未讨论在何种 workload 下这一问题会恶化。

5. **SSD 依赖**：尽管论文定位为 DNA block device，但系统实际上重度依赖 SSD 存储 L0 DTL、缓存和各种 bitmap。SSD 寿命仅约 5 年，需要定期迁移。论文声称可从 L1 DTL 重建 L0 DTL，但这需要读取整个 PB 级的 DNA 数据，恢复时间可能极为漫长。

6. **缺乏与现有 DNA 存储系统的深入对比**：只与自己构造的 naïve baseline 对比，未与 Sharma et al. [MICRO'23] 等已发表的 DNA block storage 方案做定量对比。

---

## 七、总结

LiqSD 是首个完整的 DNA block device 设计，通过双层翻译表（dual DTL）、共生元数据（symbiotic metadata）和延迟失效（delayed invalidation）三项技术，解决了 DNA 存储中 block 更新代价高和 PB 级元数据管理困难的问题。在模拟评估中，写放大最多降低 7 个数量级，读放大最多降低 6,206×，空间开销仅 3.1%。然而系统完全基于模拟器验证，当前 DNA 读写延迟（数十分钟级）使其仅适用于极冷数据的归档场景，离实际部署仍有相当距离。论文的核心价值在于为 DNA 存储系统软件栈的设计提供了有益的探索和经验。
