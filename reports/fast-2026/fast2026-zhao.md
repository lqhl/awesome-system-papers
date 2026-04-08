# "Range as a Key" is the Key! Fast and Compact Cloud Block Store Index with RASK

**作者**：Haoru Zhao, Mingkai Dong, Erci Xu (Shanghai Jiao Tong University); Zhongyu Wang (Alibaba Group); Haibo Chen (Shanghai Jiao Tong University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/zhao
**源文件**：[[fast2026-zhao.pdf]]

---

## 一、背景

Elastic Block Store (EBS) 是现代云计算的基石服务，为计算实例提供虚拟块设备 (VD)。EBS 内部使用索引（EBS-index）将虚拟设备的逻辑块地址 (LBA) 映射到后端分布式文件系统 (DFS) 中的物理位置。为保证性能，活跃的 EBS-index 需要完全驻留在内存中。

随着用户规模扩大和更大容量存储介质（如 QLC SSD）的采用，EBS-index 已成为主要的内存消耗者。在阿里云，EBS-index 消耗约 57.1% 的节点内存（其中 LBA Index 约 17.2%，Compress Index 约 39.9%）。最严重时，约 10% 的集群面临浪费约 35% 物理存储资源的风险——因为这些数据无法被索引而变得不可用。

现有的替代方案（修改架构、替换索引结构如 B-tree/ART/PGM-Index、采用更大压缩单元）均无法从根本上解决问题：架构变更不能减少索引数据量，SOTA 索引在 EBS 工作负载下表现不如已高度优化的 EBS-index，而随机访问压缩方案既慢又无法减少需索引的信息量。

---

## 二、要解决的问题

1. **内存瓶颈**：EBS-index 以单个 block 为粒度建立索引，导致海量条目占据大量内存，制约物理存储利用率
2. **现有索引结构不适配**：无论是 point index（B-tree、ART 等）还是 range-aware index（interval tree、segment tree 等），都无法高效处理云存储中普遍存在的范围写 (range write) 模式——point index 需要为每个 block 创建条目，range-aware index 不会自动移除被覆盖的旧范围导致内存浪费
3. **Range overlap 处理困难**：新写入的范围可能与已有范围部分或完全重叠，需要高效识别并清理被覆盖的旧范围，同时不能影响写入性能
4. **Range fragmentation**：当范围跨越多个叶节点时被分割存储，增加查询、管理和内存开销

---

## 三、洞察与设计

**关键洞察**：云块存储系统中，时间上相近的独立写请求往往目标在空间上连续的 LBA 区间（Consecutive Write, CW）。阿里云 EBS trace 显示，8 种代表性工作负载中 65.0%–81.5% 的写操作属于此类连续写序列。这一现象的根因在于上层应用（数据库、KV 存储）和存储系统（文件系统 journaling）都倾向于顺序写以匹配块设备特性，而多应用交错中断形成多个 CW。此外，读取 CW 写入的数据时，>85.4% 的读操作从 CW 起始位置开始。因此，应当直接以 block range 而非单个 block 作为索引键（Range-as-a-Key），理论上可减少 58.4%–91.1% 的索引条目。

基于此洞察，论文提出两项配套优化和 RASK 索引结构：

**I/O Compaction**：利用 Segment Cache 作为观察窗口，将时间上相近的写请求重排/合并为 CW，以 CW 粒度更新 LBA Index，减少 58.4%–77.0% 的条目数。

**CU Alignment**：将压缩单元 (CU) 从固定 4-block 扩展到与 CW 对齐，减少 69.1%–91.1% 的 CU 索引条目，且因 >95.7% 的读请求在 CW 起始 4 block 内，读放大可忽略。

**RASK 索引**：采用 ART trie 作为内部节点 + log-structured leaf 的混合结构：
- **Log-structured leaf**：叶内 append-only 更新，将被覆盖范围的清理批量延迟到 GC，避免每次写入都处理 overlap 的开销
- **Ablation-based search**：反向扫描叶节点，用有序的 Unfound List 跟踪目标范围中尚未找到的部分，逐步"消融"，实现 early termination
- **Two-stage GC**：Lightweight GC 快速清理同 left bound 的覆盖范围（平均能回收 73.8% 的可回收条目），Normal GC 用 NonOverlap List 追踪已处理范围的并集来识别所有被覆盖范围
- **Range-conscious split**：选择 NonOverlap List 中不与任何范围相交的边界作为分裂点，84.3% 的分裂不分割任何范围
- **Workload-aware merge/resplit**：追踪碎片化插入次数，超过阈值时合并相邻叶节点并按新的工作负载特征重新分裂，动态适配访问模式

---

## 四、实现细节

- **数据结构**：内部节点用 ART（Adaptive Radix Tree），支持路径压缩和节点大小自适应；叶节点包含 Range Array、Value Array、双向链表指针、8 字节 header（条目计数 + 并发控制信息）
- **叶容量**：默认 16 条目，merge/resplit 阈值为叶容量的 1/4
- **并发控制**：基于 optimistic locking（per-node write lock + version number），读操作通过检查 version number 实现无锁快照读；GC/split/merge 操作通过 header 中的 V_GC/V_split/V_merge 标志位通知并发读重试
- **用户自定义函数**：DivideValue（分裂范围时拆分 value）和 MergeRange（合并范围时合并 value），支持不同应用场景的定制化
- **Delete 操作**：通过插入 tombstone 实现，在 Normal GC 时物理删除
- **跨叶读一致性**：当前设计中跨叶读可能出现轻微不一致（约 0.0394%），但在 EBS 等应用场景中可接受（这些应用当前使用的 point index 也有同样问题）
- **开源**：代码开源于上海交通大学 iPads 实验室 GitLab，阿里云 EBS trace 开源于天池数据集平台

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 5317 (12 cores) / Xeon Platinum 8369B (24 cores)，96–188 GB DRAM

**数据集**：阿里云 EBS（1.8k VD，4 集群，1 周）、腾讯 EBS（10 天）、Meta Tectonic（3 年，7 集群）、Google 存储集群（3 月）

**基线**：10 种 SOTA 索引（B-tree、ART、Wormhole、HydraList、PGM-index、Cuckoo Trie、HOT、Segment Tree、Interval Tree）+ EBS-index (Origin)

| 指标 | RASK vs. 9 种 SOTA 索引 | RASK vs. Origin (EBS-index) |
|------|------------------------|---------------------------|
| 吞吐量 | 2.76–37.8× | 1.15–1.82× |
| 内存占用 | 节省 45.3–98.9% | 仅需 Origin 的 ~19.9% |
| P99 尾延迟 | 降低 23.9–97.6% | 降低 90.9% (P99.99/P99.999 降低 98.8%) |

**多线程扩展性**（24 线程）：吞吐量达基线的 3.08–21.5×，平均延迟降低 85.9–98.3%

**跨厂商验证**：
- 腾讯 EBS：吞吐量 2.35–49.21×，内存降低 27.4–99.3%
- Meta DFS 元数据服务（替换 RocksDB MemTable）：吞吐量最高 7.46×
- Google Flash Cache：吞吐量 1.52–37.52×，内存降低 3.2–99.9%

**技术贡献分解**：
| 技术 | 吞吐量提升 | 内存降低 |
|------|-----------|---------|
| Log-structured leaf | 1.50× | 90.3% |
| Normal GC | +70.6% | - |
| Two-stage GC | +24.1% | - |
| Ablation-based search | +12.6% | - |
| Range-conscious split | +7.56% | 26.0% |
| Workload-aware merge/resplit | -1.90% | 7.70% |

---

## 六、批判性分析

1. **跨叶读一致性被轻描淡写**：论文承认跨叶读可能不一致（约 0.0394%），但以"现有 point index 也有同样问题"来辩护。这是一种"别人也不行所以我可以不行"的论证，对于一个声称要替代 EBS-index 的生产级系统来说不够严肃。论文将一致性修复留作 future work，但在阿里云 EBS 这种关键基础设施中，即使极低概率的不一致也可能导致数据损坏。

2. **单线程为主的评估与生产环境脱节**：除 §7.3 和 §7.6 case 3 外，所有实验都是单线程的，理由是"EBS 内部逻辑是单线程的"。但论文同时声称 RASK 是通用索引，适用于 flash cache、DFS 元数据服务等多线程场景。多线程实验仅在一个 trace 上做了简单的均匀分配，不能充分验证并发安全性和性能。

3. **I/O Compaction 和 CU Alignment 的收益归因不清**：这两项优化是 RASK 部署的前提，但它们本身并不需要 RASK——任何索引都能从更大粒度的索引中获益。论文的对比实验中，baselines 使用的是原始 block 粒度的 trace 还是经过 I/O compaction 后的 trace？从 §7.1 的描述看应该是 compaction 后的，但这意味着 baselines 也享受了 compaction 的好处，RASK 的相对优势主要来自索引结构本身。这一点论文没有明确讨论。

4. **Worst case 场景分析不足**：当写入模式高度随机（平均范围长度 ≤2）时，RASK 比 Origin 慢 6.64%。论文轻描淡写地说"range length > 2 的任务通常能从 RASK 获益"，但没有分析在什么工作负载分布下 RASK 会系统性退化，也没有讨论是否需要自适应地在 RASK 和传统索引间切换。

5. **持久化完全外推**：RASK 是纯内存索引，持久化责任完全交给应用层。对于 EBS 这种需要崩溃一致性的场景，这意味着恢复时需要从 journal 重建整个索引，而 RASK 的 log-structured leaf 使得重建逻辑比简单的 point index 更复杂。论文没有讨论恢复开销。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint/模型权重存储的索引优化**：大模型训练中 checkpoint 写入和模型权重加载产生大量顺序写，与论文发现的 CW 模式高度吻合。RASK 的 range-as-a-key 思路可以直接应用于 checkpoint 存储系统的元数据索引，减少内存开销。

2. **KV Cache 管理的启发**：LLM 推理中 KV Cache 的分配/回收与 EBS 的 block range 管理有结构相似性——都是连续区间的分配、查找和回收。RASK 的 log-structured leaf + two-stage GC 设计可以借鉴到 KV Cache 的内存管理中，尤其是 PagedAttention 类方案中的 block table 管理。

3. **分布式训练中的元数据服务**：论文在 Meta Tectonic trace 上的实验表明，RASK 替换 RocksDB MemTable 可获得最高 7.46× 的吞吐提升。这对于 AI 训练集群中的分布式文件系统（如存储训练数据的 HDFS/CephFS）的元数据服务有直接参考价值。

4. **可跟进的研究方向**：
   - 将 RASK 的 range-as-a-key 思想扩展到 GPU 显存管理（如 CUDA Memory Pool 的分配追踪）
   - 探索 RASK 在 disaggregated memory 架构下的 RDMA-friendly 版本，用于远端内存的地址映射
   - 结合 learned index 思想，用工作负载预测来指导 split point 选择，进一步减少 range fragmentation

---

## 八、总结

RASK 提出了 "Range-as-a-Key" 的索引理念，通过深入分析云存储生产 trace 发现写请求的连续性规律，设计了一套结合 ART trie 内部节点与 log-structured leaf 的高效范围索引。其 ablation-based search、two-stage GC、range-conscious split 和 workload-aware merge/resplit 四项关键技术分别解决了范围重叠和范围碎片化的挑战。在阿里云、腾讯、Meta、Google 四家厂商的生产 trace 上，RASK 相比 10 种 SOTA 索引实现了显著的内存节省（最高 98.9%）和吞吐提升（最高 37.8×）。该工作适用于所有以范围写为主的存储系统场景，但在高度随机写入模式下优势减弱，且纯内存设计意味着持久化和崩溃恢复需要额外考虑。
