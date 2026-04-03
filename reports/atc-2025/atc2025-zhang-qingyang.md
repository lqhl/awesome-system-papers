# Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling

**作者**：Qingyang Zhang, Yongkun Li（通讯作者）, Yubiao Pan, Haoting Tang, Yinlong Xu — University of Science and Technology of China, Huaqiao University, Anhui Provincial Key Laboratory of High Performance Computing
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-qingyang
**源文件**：[[atc2025-zhang-qingyang.pdf]]

---

## 一、背景

LSM-tree 是现代 KV 存储（RocksDB、LevelDB、Cassandra 等）的核心数据结构，通过将随机写转化为顺序写来提供高效写入。随着 NVMe SSD 和 Persistent Memory (PM) 等高性能存储设备的发展，业界越来越多地采用**混合存储**方案：将热数据放在昂贵的快速设备（PM、NVMe SSD）上，冷数据放在廉价的慢速设备（SATA SSD、HDD）上，以兼顾性能和成本。

然而，LSM-tree 依赖的 flush 和 compaction 等数据排序操作在混合存储设备上会导致严重的资源利用问题：CPU 和 I/O 资源消耗交织在一起，操作之间存在级联依赖，并发操作竞争系统资源。这些问题在快慢设备性能差异巨大的混合存储场景中被进一步放大，导致资源碎片化和频繁的 write stall。

---

## 二、要解决的问题

论文识别了 LSM-tree 数据排序操作中的**操作耦合**（operation coupling）问题，具体表现为三个方面：

1. **资源消耗交织**（Intertwined resource consumption）：单个 flush 或 compaction 操作同时消耗大量 CPU（序列化、merge sort）和 I/O（数据读写）资源，二者无法独立调度。

2. **操作间级联依赖**（Interdependencies）：某一层的排序操作可能导致下一层超过容量阈值，被动触发新的排序操作，系统无法根据资源可用性主动选择排序的层级和时机。

3. **操作间资源竞争**（Resource contention）：高写负载下多层同时执行排序操作，共享的 CPU 和 I/O 资源产生竞争，降低效率。

在混合存储设备上，这些问题进一步恶化：快设备上排序操作是 CPU bound（CPU 占比超 60%），慢设备上是 I/O bound（CPU 占比不到 30%），导致瓶颈在两类设备间交替出现，平均资源利用率很低。

现有方案的不足：
- **固定差异化数据管理**（MatrixKV 等）：对特定设备做差异化管理，但数据管理方式固定不变，与波动的资源消耗不匹配
- **浅层调度**（ADOC 等）：调整排序操作的频率和位置，但未识别排序操作的资源类型，可能将同类资源密集型操作叠加，加剧瓶颈

---

## 三、洞察与设计

**关键洞察**：数据排序操作中的 CPU 资源消耗主要来自索引排序，I/O 资源消耗主要来自数据读写——二者在资源类型上天然可分离。将索引从数据文件中解耦后，排序操作可以拆分为纯 CPU 密集型任务和纯 I/O 密集型任务，从而独立调度，消除资源消耗交织。

基于此洞察，DecouKV 的核心设计：

**1. 解耦组件**：
- **IndexTable**：基于 skiplist 的可合并结构，在 DRAM 中管理 KV 对的索引（key + 数据地址），支持高效插入和查询
- **Append-Only File (AOF)**：在快设备上以追加方式存储 KV 数据，无需排序；利用快设备的高带宽和并发性，随机访问性能接近顺序访问。AOF 同时替代了 WAL 的功能

**2. 解耦任务**：
- **Index Merge**（CPU 密集型）：在 DRAM 中合并多个 skiplist，完全不涉及 I/O。支持多线程并行合并，使用 Merging Index Set（基于 CAS 的 lock-free set）保证合并过程中查询正确性
- **Data Append**（I/O 密集型）：将 KV 对写入快设备上的 AOF
- **Data Flush**（I/O 密集型）：将达到阈值的 IndexTable 对应数据从 AOF 读出，排序后写入慢设备的 SSTable

**3. 任务调度**：
- **IndexMergeQueue (IMQ)** 和 **DataFlushQueue (DFQ)** 两个队列分别反映 CPU 和 I/O 资源压力
- 通过 Score_IM 和 Score_DF 判断系统处于 CPU-bound 还是 I/O-bound 状态
- 调节 IMTN（index merge trigger num）和 DFTS（data flush trigger size）参数，在 CPU 密集型和 I/O 密集型任务之间动态平衡

**4. 弹性容量高层**：对慢设备上的高层 LSM-tree 放松 amplification factor 限制，减少操作间的级联依赖。通过 DFTS 联动调整高层容量，控制写放大

---

## 四、实现细节

- 基于 RocksDB v9.3.0 实现
- IndexTable 初始容量 max_index_size = 8MB（评估中设为 16MB），每个 entry 包含 key + 8 byte file number + 8 byte offset
- 采用异步插入：IndexTable 记录数据地址后不等待 AOF 写入完成
- Index Merge 多线程并行实现，基于已有 skiplist 合并优化技术，通过修改指针完成合并
- 参数自动调优：
  - IMTN 默认值 2，按 ±2 调整
  - DFTS 默认值 32MB（≈4 个 IndexTable），按 ×2 / ÷2 调整
  - 当 IMQ 和 DFQ 都不拥塞超过 60s，识别为资源空闲，同时减小所有参数提升数据有序性
  - 当两个队列都拥塞，识别为写入超过系统处理能力，触发 write stall
- 消除了 AOF 上的 Bloom Filter 生成和缓存开销
- 崩溃恢复：从 AOF 重建索引，10GB 数据库恢复时间 8.76s（RocksDB 8.12s）
- 源码开源：https://github.com/QingyangZ/DecouKV

---

## 五、实验结果

**硬件**：两颗 20 核 Intel Xeon Gold 5218R，128GB DRAM，128GB Intel Optane DCPMM（快设备），Intel NVMe SSD（快设备），960GB Intel S4520 SATA SSD（慢设备）

**配置**：MemTable 64MB，SSTable 64MB，4 CPU 核心，4 后台 compaction 线程，快设备空间限制为数据集大小的 10%

### Microbenchmark（100GB 数据集，1KB KV）

| 指标 | 对比基线 | 提升 |
|------|---------|------|
| CPU 利用率（Insert） | vs RocksDB/MatrixKV/ADOC | +32.3% / +25.4% / +27.3% |
| CPU 利用率（Update） | vs RocksDB/MatrixKV/ADOC | +47.9% / +36.9% / +39.4% |
| 磁盘利用率（Insert） | vs RocksDB/MatrixKV/ADOC | +17.6%–31.6% |
| 吞吐（Insert） | vs RocksDB | 4.3× |
| 吞吐（Update） | vs RocksDB | 4.6× |
| 吞吐（Read） | vs RocksDB | 1.2× |
| 吞吐（Scan） | vs RocksDB | 1.5× |
| P90 尾延迟（Insert） | vs RocksDB/MatrixKV/ADOC | 降低 71.6%–83.3% |
| P99 尾延迟（Insert） | vs RocksDB/MatrixKV/ADOC | 降低 74.3%–91.4% |

### YCSB Benchmark

| 工作负载类型 | vs RocksDB | vs MatrixKV/ADOC |
|-------------|-----------|-----------------|
| 写密集（Load/A/F） | 2.3–4.9× | 1.4–3.4× |
| 读密集（B/C/D/E） | 1.2–2.3× | 1.2–1.9× |

### 其他结果

- **500GB 大数据集**：写密集负载下 vs RocksDB 5.2× 提升，优势随数据规模增大更明显
- **Nutanix 生产负载**（57% update, 41% read, 2% scan）：1.3–2.0× 吞吐提升
- **NVMe SSD 作为快设备**：1.4–2.4× 吞吐提升
- **内存开销**：与 RocksDB 相比仅略有增加（IndexTable 0.7GB vs MemTable 0.3GB，但 Table Cache 更小）

---

## 六、批判性分析

1. **快设备随机访问假设过强**：论文的核心设计依赖于"快设备随机访问性能接近顺序访问"的假设来证明 AOF 无序存储不影响性能。这在 PM 和高端 NVMe SSD 上成立，但在中低端 NVMe SSD 或 CXL SSD 上未必如此。论文仅测试了 Intel Optane DCPMM 和一款 NVMe SSD，设备覆盖面有限。

2. **10% 快设备空间限制的公平性**：DecouKV 将 AOF 放在快设备上，所有写入操作先落到快设备。对比系统（如 RocksDB 仅放 L0/L1 和 WAL）在快设备上的数据流转模式不同，相同的空间配额下实际获得的快设备带宽利用可能不对等。

3. **P99 尾延迟 Update 无优势**：表 1 显示 DecouKV 的 Update P99 尾延迟（14.480ms）与 RocksDB（16.132ms）接近，远不如 Insert 的改进显著。论文对此仅以"与 Figure 11 的资源利用率波动一致"一笔带过，未深入分析 update 场景下解耦效果受限的原因。

4. **Zipfian 负载下优势减弱**：在高度倾斜的 Zipfian 写密集负载下，PrismDB 的 in-place update 策略表现更好。这说明 DecouKV 的解耦方案对热点数据集中的场景优化不足，但论文未展开讨论这一局限。

5. **弹性容量的写放大控制缺乏量化**：论文声称通过 DFTS 联动调整高层容量可以控制写放大，但实验部分没有给出写放大的具体数值对比，只有定性说明。

6. **恢复时间对比不完整**：仅测试了 10GB 数据库的恢复。DecouKV 需要从 AOF 扫描重建所有索引，随着快设备数据量增长，恢复时间的 scaling 特性未被验证。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 管理的启发**：LLM 推理中的 KV Cache 同样面临 CPU（索引/调度）和 I/O/显存（数据搬运）资源交织的问题。DecouKV 将索引管理与数据管理解耦的思路可以借鉴到 KV Cache 的分层管理——在 GPU HBM、CPU DRAM、SSD 之间调度 KV Cache 时，将 token 索引管理和实际数据搬运解耦。

2. **Checkpoint 系统优化**：分布式训练的 checkpoint 写入场景类似混合存储上的写密集负载。将 checkpoint 的元数据索引（轻量 CPU 操作）与实际参数数据写入（重 I/O 操作）解耦，可以减少 checkpoint 对训练迭代的阻塞。

3. **资源感知调度的通用性**：DecouKV 通过队列长度感知 CPU/IO 压力并动态调参的方法，可以迁移到 GPU 集群的任务调度场景——根据计算资源和通信带宽的实时压力，动态调整计算密集型任务（如 AllReduce）和 I/O 密集型任务（如数据加载）的优先级。

4. **可跟进方向**：在 GPU 显存 + CPU 内存 + SSD 的三级存储层次上，为 LLM 推理的 KV Cache 或 LoRA adapter 设计类似的 index-data 解耦管理方案，配合资源感知的弹性调度。

---

## 八、总结

DecouKV 通过将 LSM-tree 的数据排序操作解耦为 CPU 密集型的索引合并和 I/O 密集型的数据追加/刷写，从根本上解决了混合存储设备上资源消耗交织的问题。配合双队列驱动的自适应任务调度和弹性容量设计，DecouKV 在写密集负载下实现了 2.3–4.9× 的吞吐提升和 74.3%–91.4% 的尾延迟降低。其主要局限在于对快设备随机访问性能的依赖，以及在高度倾斜负载下优势有限。
