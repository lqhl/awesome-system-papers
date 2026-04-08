# OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search

**作者**：Hao Guo, Youyou Lu（清华大学）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/guo
**源文件**：[[fast2026-guo.pdf]]

---

## 一、背景

近似最近邻搜索（ANNS）是多模态数据检索和 RAG 的核心技术。在十亿级数据场景下，基于磁盘的图索引（on-disk graph-based index）因其性能和成本效率成为主流方案。这类索引将向量组织为有向图，存储在 SSD 上，内存中仅保留 PQ 压缩向量用于图导航。

现实系统需要持续插入新向量以保持搜索结果的时效性。当前最先进的可更新磁盘图索引 DiskANN 采用 **buffered insert** 策略：先将插入吸收到内存索引中，积累到阈值后批量 merge 到磁盘索引。

---

## 二、要解决的问题

Buffered insert 在 merge 阶段存在三个严重问题：

1. **搜索性能剧烈波动**：merge 需要搜索磁盘索引为插入向量找邻居，造成严重的磁盘读带宽争抢，中位搜索延迟升至 1.54×
2. **内存消耗极高**：merge 需要同时维护内存索引和缓冲的磁盘更新。在十亿级索引中，merge 3% 的向量就需要 125GB 内存
3. **merge 时间过长**：merge 占整个时间线 30% 以上，且增大 batch size 收效甚微——瓶颈在 in-memory merge 阶段，每个向量的邻居搜索无法有效批处理，吞吐上限约 3000 QPS

---

## 三、洞察与设计

**关键洞察**：Buffered insert 的 batch merge 并不能有效降低插入开销，因为每个向量的邻居搜索本质上无法批处理（需要逐一搜索磁盘索引），batch 只是合并了磁盘写而非计算。既然 batch 收益有限，不如直接逐条插入磁盘索引（direct insert），将插入开销均匀分摊到整个时间线上，从而避免 merge 阶段的性能波动和内存峰值。

基于此洞察，OdinANN 采用 **direct insert** 替代 buffered insert，核心设计包括两项技术：

### GC-Free Update Combining（§3.2）

图索引的记录是定长的，这使得 out-of-place 更新后旧记录可以直接复用，无需逻辑 GC。OdinANN 在磁盘上做空间超配（space overprovision），每个 page 预留多个空闲 record slot。插入时，将更新后的记录写入同一 page 的空闲 slot，多个 record 更新合并为一次 page 写入。

记录分配遵循三条优先级规则：
- **Rule #1（empty rule）**：优先使用全空 page，无需额外读
- **Rule #2（on-path partial-empty rule）**：使用搜索路径上的半空 page（已在缓存中），避免额外 I/O
- **Rule #3（overprovision rule）**：分配新 page

默认设置 m = ⌊n/2⌋，空间消耗和写放大均为 2×。

### Approximate Concurrency Control（§3.3）

利用 ANNS 的近似特性放松隔离级别：
- **搜索**：仅保证每条记录的一致性快照，而非整个图的原子性读取
- **插入**：使用近似邻居快照，避免 OCC 式的反复验证

两项优化进一步提升并发：
- **Optimization #1**：将磁盘 I/O 移出临界区，使用 write-back page cache + 后台 I/O 线程异步刷盘
- **Optimization #2**：Delta neighbor pruning，将大多数剪枝操作从 O(R²) 降至 O(R)，仅检查新插入邻居与已有邻居的三角不等式

---

## 四、实现细节

OdinANN 基于 DiskANN 代码实现，使用 io_uring 替代 libaio 作为 I/O 引擎。

**数据结构**：
- 磁盘上：定长记录的邻接表（每记录包含向量 + 出边 ID），最大出度 R（100M 数据集 R=96，1B 数据集 R=128）
- 内存中：PQ 表（32B/向量）、ID-to-location 和 ID-to-tag 哈希表（16B/向量）、location-to-ID 每页定长数组（4B/记录 + 4B/页），总计约 58B/向量

**删除**：采用 buffered delete，仅在内存记录删除 ID（4B/向量）。两遍扫描 merge：第一遍加载被删除向量的邻居 ID，第二遍流式替换并剪枝。merge 触发条件为删除比例达 10% 或搜索 I/O 放大达 1.1×。

**搜索质量保障**：动态候选池（dynamic candidate pool），保持池中至少 l 个未删除向量，自动扩大池大小补偿被删除向量。

**一致性**：使用快照 + journaling，merge 时创建索引快照，两次 merge 之间用 journal 记录增量更新，通过一致性前缀实现恢复。

---

## 五、实验结果

**硬件**：2×28 核 Intel Xeon Gold 6330, 512GB DDR4, 1× Samsung PM9A3 3.84TB SSD, Ubuntu 22.04

**数据集**：SIFT100M（128 维 uint8）、DEEP100M（96 维 float）、SIFT1B（128 维 uint8, 10 亿向量）

**对比系统**：DiskANN（buffered insert）、SPFresh（cluster-based）

### SIFT100M（插入 100M 向量）

| 指标 | OdinANN vs DiskANN | OdinANN vs SPFresh |
|------|------|------|
| P50 延迟 | 低 13.3%，波动 1.07× vs 2.44× | 低 51.7% |
| P90 延迟 | 低 34.6% | 低 36.5% |
| P99 延迟 | 低 19.5% | 低 28.4% |
| 吞吐 | 高 1.15× | 高 1.99× |
| 精度 | 99.1%\~100% of DiskANN | 高 ~15% |
| 峰值内存 | 仅 29.3% of DiskANN | 86.8% of SPFresh |

### SIFT1B（800M 基础索引 + 插入 200M）

| 指标 | OdinANN |
|------|------|
| 搜索吞吐 | 5000 QPS |
| 插入吞吐 | 1100 QPS |
| 中位搜索延迟 | ~3ms，一致稳定 |
| P50 延迟 vs DiskANN | 85.7% |
| P50 延迟 vs SPFresh | 62.1% |
| 峰值内存 | 83.8GB vs DiskANN >200GB |

### Breakdown 分析（SIFT100M, 100K 插入）

| 配置 | 插入吞吐 | 插入 P50 延迟 |
|------|------|------|
| Baseline（in-place + 基础并发） | ~390 QPS | ~140ms |
| +Async（I/O 移出临界区） | ~390 QPS | ~113ms（80.8%） |
| +OP（空间超配） | ~2000 QPS | ~38ms（5.12× 吞吐） |
| +Prune（delta 剪枝） | ~2000 QPS | ~11.1ms |

空间放大实测 1.98×（SIFT）/ 2.29×（DEEP），接近理论值 2×。近似并发控制导致的索引质量损失仅为 ~4.5% 额外页访问。

---

## 六、批判性分析

1. **空间换时间的代价被低估**：论文宣称 2× 磁盘空间换 128GB 内存是划算的（$100 SSD vs $200+ DRAM），但这个比较忽略了 SSD 寿命和写放大对 SSD 磨损的长期影响。Direct insert 的持续随机写模式可能显著缩短 SSD 寿命。

2. **实验中搜索线程数差异**：OdinANN/DiskANN 使用 32 搜索线程，SPFresh 在 SIFT 上仅用 16 线程、DEEP 上仅用 8 线程。这使得吞吐对比对 SPFresh 不利，公平性存疑。

3. **插入吞吐仍然较低**：OdinANN 在十亿级数据集上插入吞吐为 1100 QPS，insert latency ~11ms。论文引用 real-world 目标为 ~10ms 来论证可接受性，但未讨论在更高插入压力下的表现退化。

4. **精度下降趋势未充分讨论**：Figure 6(e)/7(e) 显示 OdinANN 和 DiskANN 的精度随插入量持续下降（从 ~0.97 降到 ~0.82），但论文未讨论长期运行下精度是否会降到不可接受的水平，以及是否需要定期 rebuild。

5. **删除场景评估不完整**：Figure 12 中 DiskANN 在相同时间内仅替换 50M 向量（vs OdinANN 的 100M），但 merge 频率不同（6% vs 20%），这使得直接比较的公平性存疑。

6. **Delta pruning 的 fallback 频率未报告**：delta pruning 在无法剪枝时回退到 O(R²) 全量剪枝，但论文未报告 fallback 的频率。如果 fallback 比例高，实际收益会打折扣。

---

## 七、AI Infra / MLSys 视角

1. **向量数据库是 RAG 的关键基础设施**：OdinANN 解决的核心问题——在线插入时保持搜索性能稳定——直接影响 RAG 系统的用户体验。LLM 应用中知识库的持续更新需要高效的在线向量索引更新能力。

2. **Direct insert 思路可迁移**：将"均匀分摊开销"替代"批量 merge"的思路可以借鉴到其他 AI Infra 场景，如 KV cache 的管理、checkpoint 写入、模型参数的增量更新等。

3. **近似并发控制的启发**：利用 AI 系统本身的近似容错性来放松一致性要求、提升并发，这个思路值得在更多场景探索——例如分布式推理中的 KV cache 同步、embedding 索引的跨节点一致性等。

4. **值得跟进的方向**：
   - 将 direct insert 与 GPU 加速的向量距离计算结合，解决 CPU 侧剪枝瓶颈
   - 探索 direct insert 在分布式向量数据库中的扩展，多节点间如何协调近似并发控制
   - 结合 LLM 生成的 embedding 特性（如维度分布、更新模式）优化图结构维护策略

---

## 八、总结

OdinANN 提出用 direct insert 替代 buffered insert 来实现磁盘图索引的在线更新，通过 GC-free update combining（空间超配 + out-of-place 更新合并）和 approximate concurrency control（利用近似特性放松隔离 + delta pruning）两项核心技术，在十亿级数据集上实现了稳定的搜索性能（P50 延迟波动仅 1.07×）、更低的内存消耗（DiskANN 的 29.3%\~41.9%），代价是 2× 磁盘空间和约 4.5% 的索引质量损失。该工作证明了对于磁盘图索引，直接插入比批量合并更适合在线场景，但长期精度衰减和 SSD 写入寿命问题仍需关注。
