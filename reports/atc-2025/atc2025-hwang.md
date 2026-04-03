# Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs

**作者**：Inhwi Hwang (Seoul National University), Sangjin Lee (Chung-Ang University), Sunggon Kim (Seoul National University of Science and Technology), Hyeonsang Eom (Seoul National University), Yongseok Son (Chung-Ang University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/hwang
**源文件**：[[atc2025-hwang.pdf]]

---

## 一、背景

Zoned Namespace (ZNS) SSD 是一种新型存储设备，将物理地址空间划分为固定大小的 zone，每个 zone 必须顺序写入且需显式 reset 才能复用。ZNS SSD 将数据管理责任（如 GC）转移到 host 端，从而减少 SSD 内部的 DRAM 使用和 over-provisioning 空间，解决 log-on-log 问题并缓解 I/O 干扰。

ZNS SSD 分为 large-zone 和 small-zone 两类。Small-zone ZNS SSD 的每个 zone 映射到单个 die，提供更多的 active zone（如多达 384 个），带来更高的灵活性和性能隔离，但单个 zone 的内部并行度（intra-zone parallelism）较低，需要利用多个 active zone 的 zone-level parallelism 来发挥设备性能。

Log-structured File System (LFS) 天然适合 ZNS SSD 的 append-only 写入模式。F2FS 是目前最具代表性的支持 ZNS SSD 的 LFS，但其设计基于传统 CNS SSD，在 ZNS SSD 上面临 metadata 管理和 active zone 利用率不足等问题。

---

## 二、要解决的问题

现有 LFS（以 F2FS 为代表）在 ZNS SSD 上存在三个核心问题：

1. **CNS-based metadata 设计导致无法独立使用 ZNS SSD**：F2FS 的 metadata（如 SIT、NAT）采用 block-aligned、fixed location 的 in-place update 方式，ZNS SSD 不允许随机写和原地更新，因此必须额外搭配一块 CNS SSD 来存储 metadata，增加了存储系统成本。简单的 zone-pair 交替写方案会导致性能下降达 9.32× 和写放大增加达 7.8×。

2. **Active zone 利用率低下**：F2FS 为每个 log stream 只分配一个 zone，6 个 log stream 最多使用 6 个 active zone，严重浪费了 small-zone ZNS SSD 提供的数百个 active zone。即使采用静态均匀分配策略（如每个 log stream 分配 64 个 active zone），当 I/O 流量在各 log stream 之间不均匀时，低流量的 log stream 浪费 active zone，高流量的 log stream 又无法获得足够的资源。

3. **SSD 内部资源冲突**：Small-zone ZNS SSD 的 zone 与 die/channel 之间采用细粒度映射。当多个 zone 共享相同的 die 或 channel 时，会产生资源冲突：channel-level 冲突导致 19% 的性能下降，die-level 冲突导致超过 50% 的性能下降。LFS 在分配 zone 时未考虑这些映射关系。

---

## 三、洞察与设计

**关键洞察**：在 ZNS SSD 上，LFS metadata 的生命周期可以按照与 segment 的关系分为两类——immutable metadata（如 segment summary）一旦写入就不会更新，其生命周期与所属 segment 完全一致；mutable metadata（如 SIT、NAT）则频繁更新且生命周期独立于 segment。这一分类使得可以分别采用最优的 append-only 策略管理两类 metadata，从而在 ZNS SSD 上实现高效的 standalone 文件系统。

基于此洞察，Z-LFS 提出三个核心策略：

### Strategy #1: ZNS-tailored Metadata Management

- **Immutable metadata**（如 segment summary）直接 append 到对应 segment 末尾，与 segment 共享同一 zone。好处是：GC 时 metadata 随 segment 一起清理，无需额外的 metadata GC；metadata 位置固定在 segment 末尾，无需跟踪位置。
- **Mutable metadata**（如 SIT、NAT）采用 delta logging 方式：仅收集修改过的 entry（delta），聚合到 4KB log block 中，写入 dedicated delta log area（circular log）。当 delta log area 半满时，触发异步 merge 操作，将 delta 与 merge area 中的 metadata table 合并。SIT 和 NAT 各自维护独立的 delta log area 和 merge area，避免因更新频率不同导致的不必要 merge 开销。

### Strategy #2: Speculative Log Stream Management

- Z-LFS 将 zone 组织为 superzone（连续的多个 zone），log stream 以 superzone 为单位分配 active zone。
- 采用 quota-based 方式：定义总可用 active zone 数 A = min(A_peak, A_avail/2)，根据各 log stream 在时间窗口内的写请求占比，按比例分配 active zone quota。
- 动态 scale up/down：高流量 log stream 从 free list 获取更多 superzone；低流量 log stream 将 superzone demote 到 inactive list，后台回收。
- Data 和 node log stream 分别独立投机，因为二者通常不同时写入（node 主要在 checkpoint 时写入）。

### Strategy #3: Conflict-aware Zone Allocation

- Superzone 由连续的 zone 组成（数量等于 channel 数，如 16 个），确保 superzone 内无 channel-level 冲突。
- 映射到相同 die 的 superzone 归入同一 interference group (IG)。分配时优先从不同 IG 选择 superzone，避免 die-level 冲突。
- Data 和 node log stream 维护独立的 IG allocation list，允许二者使用同一 IG 中的 superzone（因为不并发写入），进一步提高 active zone 利用率。

---

## 四、实现细节

Z-LFS 基于 F2FS 在 Linux kernel 5.17.4 上实现，是纯软件方案，不需要修改 ZNS SSD 硬件。

**Metadata 分类**：
- Immutable: Segment Summary (SS)——存储 segment 内 block 的反向映射信息，write-once never-updated
- Mutable: Segment Information Table (SIT) 和 Node Address Table (NAT)——分别记录 segment 中 valid block bitmap 和 node block 地址，频繁更新

**Delta logging 架构**：
- Delta log area：一对 zone 组成的 circular log（MDlog₀, MDlog₁）
- Merge area：一对 metadata table（MD₀, MD₁），交替更新确保 crash consistency
- 每个 delta entry 包含修改内容及其在 metadata table 中的位置 (pos)
- Log block 带 version number，用于 crash recovery 时判断有效性

**Superzone 与 segment 组织**：
- Superzone 内的 segment 被拆分为多个 subsegment，scatter 到 superzone 内的各个 zone
- Subsegment 大小为 128KB，逻辑连续但物理分散
- Round-robin 方式在 superzone 之间选择 segment 写入

**Crash consistency**：
- Roll-back + roll-forward 恢复机制，与 F2FS 一致
- Immutable metadata 通过 checkpoint 确保一致性
- Mutable metadata 通过扫描 delta log area 的 log block、比较 log version 与 checkpoint version 来恢复
- 恢复后重新初始化 active zone pool 和 IG allocation list

**空间开销**：Delta log area + merge area 共约占 ZNS SSD 总容量的 0.02%。

---

## 五、实验结果

**实验平台**：i7-13700K (16 物理核), 32GB 内存, Samsung PM1731a ZNS SSD (40,704 zones, 96MB/zone, 3.92TB, max 384 active zones) + 等效 CNS SSD (Samsung PM1733)

**对比系统**：F2FS (+CNS SSD), F2FS_SS (static striping, +CNS SSD), eZNS, eZNS with F2FS (+CNS SSD), ZenFS (+CNS SSD)

### Micro-benchmark (FIO, 16 threads, 4KB)

| 指标 | vs F2FS | vs F2FS_SS | vs eZNS+F2FS |
|------|---------|------------|--------------|
| Sequential write | 12.4× | 1.47× | 3.5× |
| Random write | 25.2× | 1.30× | 3.5× |
| Sequential read | 1.50× | 1.22× | - |
| Random read | ~1.0× | ~1.0× | ~1.0× |
| GC throughput | 3.3× | - | ~1.0× |

### Write latency (random write)

| 系统 | 平均延迟 | P99.9 尾延迟 |
|------|---------|------------|
| F2FS | 626 µs | 47 ms |
| F2FS_SS | 31.9 µs | 103.9 µs |
| eZNS+F2FS | 89.4 µs | 39 ms |
| Z-LFS | 24.5 µs | 45.3 µs |

### Metadata-intensive (MDtest, file creation)

Z-LFS vs F2FS 提升达 27.7×，vs F2FS_SS 达 11.4×，vs eZNS+F2FS 达 1.6×。

### Macro-benchmark (Filebench)

| 工作负载 | vs F2FS | vs F2FS_SS | vs eZNS+F2FS |
|---------|---------|------------|--------------|
| Fileserver | 7.21× | 1.60× | 2.47× |
| Varmail | 33.44× | 6.30× | 2.04× |
| Webserver | 2.09× | 1.62× | ~1.0× |
| Videoserver | 13.7× | 1.62× | 3.33× |

### RocksDB (db_bench)

| 工作负载 | vs ZenFS | vs F2FS | vs F2FS_SS | vs eZNS+F2FS |
|---------|---------|---------|------------|--------------|
| fillseq | 25.0× | 7.83× | 1.20× | 1.27× |
| fillrandom | 9.28× | 7.83× | 1.20× | 1.55× |
| overwrite | 9.01× | 8.12× | 1.19× | 1.52× |
| readrandom | ~1.0× | ~1.0× | ~1.0× | ~1.0× |

### 额外开销

- 内存开销：比 F2FS 多 250-380 MB（delta logging memory buffer），但有上限且绝对值较小
- 写放大 (WAF)：与 F2FS_SS 相当，delta logging 未引入显著额外写放大
- 空间开销：仅占 ZNS SSD 总容量的 0.02%

---

## 六、批判性分析

1. **实验环境局限性大**：所有实验仅在单一型号的 ZNS SSD (Samsung PM1731a) 上进行，且论文中对 SSD 内部资源结构的推断（16 channels, 128 dies, round-robin 映射）完全基于性能测试的逆向工程，而非厂商文档。如果其他 ZNS SSD 的 zone-to-resource 映射不遵循 round-robin 规则，conflict-aware zone allocation 可能完全失效。论文未讨论如何检测和适应不同的映射策略。

2. **单租户限制被轻描淡写**：Z-LFS 独占所有 active zone 资源进行投机分配，在多租户场景下（云存储的典型场景）其核心优势将大打折扣。论文在 Discussion 部分仅用一句话提到"留作 future work"，但 ZNS SSD 在数据中心的主要应用场景恰恰是多租户的。

3. **与 eZNS 的对比不够公平**：Z-LFS 是文件系统级方案，可以直接获取每个 log stream 的写入强度信息；而 eZNS 是设备接口层方案，天然缺乏文件系统语义。将两者直接比较性能，实际上是在比较"有文件系统语义信息" vs "没有文件系统语义信息"的差距，而非方案本身的优劣。论文也提到了 cross-layer coordination 可以解决这个问题，但将其定性为"增加复杂度"而未做实验验证。

4. **Active zone scaling 的投机准确性缺乏分析**：论文展示了 Z-LFS 在三个固定 phase（hot→warm→cold）的理想化工作负载下能匹配最优静态配置，但未分析实际工作负载下投机的准确率、收敛速度、以及误判时的性能惩罚。时间窗口大小的选择也未做敏感性分析。

5. **Large-zone ZNS SSD 的适用性声明有所夸大**：论文在 Discussion 中声称 Z-LFS 可以适用于 large-zone ZNS SSD，但同时承认 speculative log stream management 和 conflict-aware zone allocation 这两个核心技术在 large-zone ZNS SSD 上"可能没有收益"。也就是说，Z-LFS 的三个核心贡献中有两个不适用于 large-zone 场景，仅剩 append-only metadata management 有效。

6. **缺少端到端应用延迟指标**：实验主要报告吞吐量，仅在 random write 场景下报告了平均/尾延迟。对于 varmail 等延迟敏感型工作负载，缺少延迟分布数据。

---

## 七、总结

Z-LFS 是一个针对 small-zone ZNS SSD 优化的 log-structured 文件系统，基于 F2FS 实现。其核心贡献是三个协同设计：基于 metadata 生命周期分类的 append-only metadata 管理（消除对额外 CNS SSD 的依赖）、基于写入强度投机的动态 active zone 分配（最大化 zone-level parallelism）、以及基于 SSD 内部资源映射的 conflict-aware zone 分配（减少 die/channel 冲突）。实验表明 Z-LFS 在各类工作负载上相比 F2FS 和 eZNS+F2FS 有显著性能提升。主要局限在于方案高度依赖对特定 SSD 内部结构的假设，且仅在单租户环境下验证。
