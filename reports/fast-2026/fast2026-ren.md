# Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage

**作者**：Yuanming Ren, Siyuan Sheng, Zhang Cao (The Chinese University of Hong Kong); Yongkun Li (University of Science and Technology of China); Patrick P. C. Lee (The Chinese University of Hong Kong)
**会议**：USENIX FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/ren
**源文件**：[[fast2026-ren.pdf]]

---

## 一、背景

分布式 key-value (KV) 存储是电商、社交网络、在线分析等应用的核心组件。为满足高可用和可扩展的 I/O 需求，KV 存储通常采用多节点分布式部署，并通过副本机制提供容错能力。然而，在生产环境中，提供低延迟保证仍然是一个重大挑战——即使 CPU 负载完美均衡，查询延迟仍会出现波动和尖峰（YouTube 数据中心的研究已证实这一点）。

基于 log-structured merge tree (LSM-tree) 的 KV 存储（如 Cassandra、HBase、RocksDB）被广泛采用。LSM-tree 在后台执行 compaction 来合并 SSTable、删除过期数据，但 compaction 会消耗大量 CPU 和磁盘 I/O 资源，与前台读请求产生严重的资源竞争，导致延迟波动。现有的基于副本的负载均衡方案主要关注分布层的前台任务均衡，忽视了前台任务与存储层后台任务之间的相互影响。

---

## 二、要解决的问题

1. **访问频率均衡 ≠ 读延迟均衡**：即使通过副本将请求频率均匀分配到各节点（最大差异仅 18.9%），节点间的读延迟差异仍可达 4.24×。现有负载均衡策略无法消除这种延迟不均衡。

2. **细粒度时间尺度的延迟波动**：在一分钟窗口内延迟相对稳定（0.5×–2.0× 平均值），但在一秒窗口内 90.8% 的数据点超出 0.5×–2.0× 范围，出现频繁的延迟尖峰。

3. **Compaction 与读任务的耦合矛盾**：Compaction 开启时读吞吐量从 26.3 KOPS 骤降至 7.3 KOPS（资源竞争），但 compaction 又是提升长期读性能的关键——compaction 后读吞吐量从 29.8 KOPS 提升至 40.7 KOPS。简单地限速或推迟 compaction 都不可行。

4. **现有副本选择方案的不足**：Cassandra 的 dynamic snitching 简单选择最快副本导致负载振荡；C3 的客户端副本选择消耗大量 CPU 和网络带宽；DEPART 的 two-layer log 在读密集场景下引入额外读开销。

---

## 三、洞察与设计

**关键洞察**：分布式 LSM-tree KV 存储中的延迟波动根源在于分布层（前台读请求分配）和存储层（后台 compaction）任务之间的紧耦合——仅在单一层面做负载均衡是不够的，必须在两个层面进行整体协同调度，才能在大时间尺度和小时间尺度上同时提供低延迟保证。

基于此洞察，HATS 采用闭环迭代设计，包含三个协同的任务调度操作：

### 1. 粗粒度读任务分配（Coarse-grained Read Task Assignment）
- 每个 epoch（默认 60 秒）周期性执行
- Scheduler 节点（通过 Raft 选举的 seed 节点）通过扩展的 Gossip 协议收集所有节点的读负载（当前状态），计算出均衡的读分配（期望状态）
- 使用贪心算法将读请求从高负载节点迁移到低负载节点（Algorithm 1），时间复杂度 O(MR²/4)
- 客户端按期望状态的概率分布选择 coordinator 节点

### 2. 细粒度读任务协调（Fine-grained Read Task Coordination）
- 在每个 epoch 内，基于瞬时负载动态调整读请求路由
- 为每个副本节点计算统一评分（unified score）：`L/t_{i,j} - Q_{i+j}`，其中 `L/t_{i,j}` 表示节点在当前延迟下一个 epoch 能服务的请求数，`Q_{i+j}` 表示期望服务的请求数
- 评分越高表示节点有更多余力处理额外请求，coordinator 将请求路由到评分最高的副本
- 大时间尺度上收敛到期望状态，小时间尺度上自动偏向 compaction 良好的节点

### 3. Compaction 任务调度（Compaction Task Scheduling）
- 采用 replica decoupling（来自 DEPART）将不同 key range 的副本分离到独立的 LSM-tree
- 按读负载比例分配 compaction 速率：读负载高的 key range 获得更高的 compaction 速率
- 只对第二层及以上的 compaction 限速，最低层保持不限速以缓解新 flush SSTable 的读放大
- 设置 compaction 速率下限（`compaction_throughput / R`）避免饥饿

---

## 四、实现细节

- 基于 Cassandra v5.0 和 Cassandra Java client driver v3.0.0 实现，修改约 6K 行 Java 代码（原代码库 1.3M 行）
- 使用 SOFAJRaft（生产级 Raft 库）实现 scheduler 节点选举
- 状态监控和共享复用 Cassandra 的 Gossip 协议，额外网络开销约 15.2%（R=3, M=100）
- Epoch 长度 L 设为 60 秒，与 Cassandra 默认 compaction 间隔对齐
- 每节点允许 compaction 速率设为 64 MiB/s（Cassandra 默认值）
- 通过 Cassandra 内置的 rate-limiting API 实现 compaction 速率调节
- 保持 Cassandra 核心操作（一致性哈希、故障检测、hinted handoff、read repair）的正确性不变
- 开源代码：https://github.com/adslabcuhk/hats

---

## 五、实验结果

**实验环境**：22 台机器的本地集群（10 节点同构 / 20 节点异构），10 Gbps 网络，Ubuntu 22.04 LTS。同构节点：i5-3570 四核 CPU, 16 GiB DRAM, 128 GiB SATA SSD。预加载 100M 条 1 KiB KV 对，三副本，100 客户端线程。

**基线**：mLSM（multi-LSM，replica decoupling）、C3（自适应副本选择）、DEPART（replica decoupling + two-layer log）

### YCSB 合成工作负载

| 工作负载 | 吞吐量提升（vs 最优基线） | P99 延迟降低（vs 最优基线） |
|----------|---------------------------|------------------------------|
| A (50R/50W) | 1.53× | 56.8% |
| B (95R/5W) | 2.47× | 58.6% (vs C3) |
| C (100R) | 2.67× | 62.2% |
| D (95R/5W latest) | 2.90× | 59.9% (vs DEPART) |
| E (95Scan/5W) | 略低于 DEPART 5.4% | 接近 mLSM |
| F (50R/50RMW) | 2.04× | 88.7% (P999) |

### Facebook 生产工作负载（85% Get, 14% Put, 1% Seek）

| 指标 | HATS | mLSM | C3 | DEPART |
|------|------|------|-----|--------|
| 吞吐量 (KOPS) | 48.8 | 17.1 | 20.2 | 21.5 |
| P99 Get 延迟降低 | — | 83.2% | 78.9% | 68.3% |

### 系统级分析

- **延迟均衡度（CoV）**：HATS 在所有工作负载上 CoV 最低，最高降低 72.5%
- **性能分解**：HATS 的副本选择延迟降低 66.5%–93.5%，磁盘读延迟降低 39.5%–83.0%，compaction 时间降低 81.8%
- **资源使用**：CPU 时间降低最高 47.5%，磁盘 I/O 降低最高 81.7%，网络 I/O 降低最高 64.6%
- **可扩展性**：20 节点异构集群上吞吐量提升最高 2.11×，P99 延迟降低最高 64.3%
- 仅 0.04% 的请求被重定向到远程节点（C3 为 84.9%）

---

## 六、批判性分析

1. **实验规模偏小**：核心实验仅在 10 节点同构集群上进行（扩展实验也仅 20 节点）。生产环境 Cassandra 集群通常数百至数千节点，Gossip 协议的状态收敛速度和 scheduler 节点的全局视图准确性在大规模下可能成为瓶颈，论文对此未做分析。

2. **Scheduler 节点的中心化瓶颈**：HATS 依赖单一 scheduler 节点（通过 Raft 选举）收集全局状态并计算期望状态。虽然论文声称计算开销 O(MR²/4) 可忽略，但在大规模集群中，scheduler 节点需要处理的 Gossip 消息量和状态收敛延迟可能显著增加。论文未讨论 scheduler 故障转移期间的性能退化。

3. **Scan 场景表现不佳**：在 Workload E（95% scan）上 HATS 吞吐量略低于 DEPART 5.4%，这暴露了设计的局限性——HATS 的优化主要针对点查询的副本选择和 compaction 调度，对 scan 操作的优化有限。

4. **对 DEPART 基线的依赖**：HATS 本身复用了 DEPART 的 replica decoupling 技术。公平地说，HATS 的增量贡献是三层调度框架，但 replica decoupling 带来的基线提升（相对于 vanilla Cassandra）被包含在了 HATS 的收益中。论文虽然使用 mLSM 作为基线控制了这一点，但在表述上有时模糊了这一区分。

5. **P50 延迟的代价**：HATS 在 Workload A 下 P50 延迟比 mLSM 高 14.6%，论文将其归因于调度开销。这意味着在低负载或延迟尖峰不是主要问题的场景下，HATS 的调度开销可能得不偿失。

6. **工作负载假设的局限**：实验仅使用 YCSB 和 Facebook 工作负载，缺少对 time-series 数据库、图数据库等其他 LSM-tree 使用场景的验证。Facebook 工作负载虽来自生产 trace，但实验环境（10 节点 128 GiB SSD）与真实 Facebook 规模差距极大。

---

## 七、总结

HATS 是一个面向分布式 LSM-tree KV 存储的整体化自动任务调度框架，通过粗粒度读任务分配、细粒度读任务协调和自适应 compaction 调度三个层次的协同优化，有效缓解了前台读任务与后台 compaction 之间的资源竞争和延迟波动问题。在 YCSB 和 Facebook 生产工作负载上，HATS 相比 C3 和 DEPART 分别实现了最高 2.90× 的吞吐量提升和 88.7% 的尾延迟降低。其主要局限在于对中心化 scheduler 节点的依赖、scan 场景下的有限收益、以及缺乏大规模集群的验证。该框架的设计思路——跨层级整体调度前台与后台任务——具有普遍性，可推广到其他需要平衡前台服务质量与后台维护任务的分布式存储系统。
