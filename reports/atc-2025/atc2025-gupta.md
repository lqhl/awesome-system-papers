# Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale

**作者**：Sushant Kumar Gupta, Anil Raghunath Iyer, Chang Yu, Neel Bagora, Olivier Pomerleau, Vivek Kumar, Prunthaban Kanthakumar（Google LLC）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/gupta
**源文件**：[atc2025-gupta.pdf](../../papers/atc-2025/atc2025-gupta.pdf)

---

## 一、背景

低延迟消息传递是广告服务、动态定价、零售库存管理、欺诈检测、在线游戏等实时系统的核心需求。随着数据规模爆炸式增长，这些系统往往地理分布在全球数十个集群中，每个集群中的 consumer 数量从数千到数万不等，全球总计可达数十万个 replica。这些实时系统依赖消息传递子系统来传输从数据源提取的更新数据，并需要保证有序传递（in-order sequencing）和至少一次传递（at-least-once delivery），同时允许 consumer 按自己的节奏拉取消息，避免过载。

---

## 二、要解决的问题

1. **现有 push-based 系统（如 RabbitMQ、Wormhole）的局限**：push 模式会阻塞 consumer 的关键 CPU 核心，难以支持异构 consumer 各自不同的消费速率。

2. **Kafka 的 consumer fan-out 瓶颈**：Kafka 基于 broker 本地磁盘存储，单个 partition 的读写吞吐受限于 SSD 带宽（约 4.84 Gbps）。论文实验显示，当 consumer 数量超过一定阈值后，producer 写入速率下降，consumer 总吞吐量在约 14 Gbps 后出现退化。即使使用 HDFS 替换本地文件系统，64 MB block size 下大量 tail-read 仍会造成吞吐瓶颈。

3. **Pulsar 的 segment 过大问题**：Apache Pulsar 依赖 BookKeeper，其 128 MB 的 segment 在大量 consumer tail-read 时同样面临吞吐问题。

4. **全局有序约束下的 hot-spotting**：当需要全局总顺序（global total order）时，即使在单个 partition 内也会出现热点，传统 broker 内存缓存无法解决网络拥塞问题。

总结：**缺乏一个能同时支持大规模 consumer fan-out 和低延迟有序消息传递的消息系统。**

---

## 三、洞察与设计

**关键洞察**：有序字节传递不需要在网络上按顺序传输——可以将文件分成小的固定大小 chunk（4 KB），利用 Remote Memory Access (RMA) 进行乱序并行读取，在客户端侧重新组装后按序交付给 consumer。这样就能绕过服务端吞吐瓶颈，通过水平扩展 cache replica 来充分利用集群 NIC 带宽。

### 核心设计

**多层存储架构**：
- **Colossus（分布式文件系统）** 作为持久化主存储层，是 single source of truth
- **CliqueMap（RMA 内存缓存）** 作为二级存储层，仅存储最近写入的"热"数据
- 二者并行运行，所有消息字节被复制到两层

**文件分块与缓存**：
- 文件被切分为 4 KB 的 chunk（匹配消息大小和集群 fabric MTU），以 key-value 对形式存储在 CliqueMap 中
- key = hash(Colossus 文件绝对路径, chunk 序号)，value = chunk 字节
- 分为 data cache（存文件 chunk）和 metadata cache（存文件长度和锁）

**读取路径（RMA 优先）**：
1. Consumer/Reader 通过 RMA 从 metadata cache 轮询文件长度变化
2. 先进行 relaxed read（从任意 replica 读取，可能返回 stale 数据）
3. 若返回字节数不足，再做 consistent read（从 2/3 replica 读取）
4. Cache miss 则 fallback 到 Colossus

**跨集群路由**：
- 使用 Prim 算法构建最小生成树（copy tree），优先优化带宽成本，同时最小化树深度和 fan-out
- 沿 copy tree 的每一跳有独立的 reader/writer job 对，各自按需水平扩展
- 自动化 outage 处理：BFS 算法惩罚故障节点，重建 copy tree

**写入路径**：
- Producer 先写 Colossus（原子操作），再异步 shadow 到 data cache
- 完整 chunk 并行写入，部分填充 chunk 串行写入保证字节前缀正确性
- 通过 metadata cache 中的 lease 锁解决 dueling writers 问题

**延迟 Colossus 读取**（Algorithm 1）：优先从 data cache 读取，仅当 cache 落后超过可容忍延迟（1s）时才 fallback 到 Colossus，避免不必要的磁盘读取。

---

## 四、实现细节

- **底层缓存系统**：CliqueMap，支持 r=3.2 replication，使用 consistent hashing 分布 key，set-associative mapping 分配 bucket，支持 RMA 读和 RPC 写
- **Data cache 配置**：chunk TTL 1 分钟，GC 阈值 80% 容量，least-recently-modified 淘汰策略，预分配 slab 和 bucket，启用 chaining 防止强制驱逐
- **Metadata cache 配置**：TTL 24 小时，容量需求小
- **调度器**：使用 Slicer 做 sharding（弱一致性模型，优先可用性），cluster-local 调度器由 producer 通知触发
- **消息流分片**：每个消息流 120-way sharded，每个 shard 包含一组按时间排序的消息文件
- **形式化验证**：使用 TLA+ 建模，验证了 safety（consumer 按序接收字节）和 eventual progress（consumer 最终接收所有字节），在两种配置下分别检查了 8570 万和 1206 万个 distinct states
- **代码规模**：核心系统 17,500 行 C++ 代码（非测试），与 Google Ads 集成额外 7,600 行，总开发投入 8 SWE-years
- **网络**：集群内使用 PonyExpress 提供高效软件 RMA，跨集群使用 B4 网络

---

## 五、实验结果

实验环境：Google Borg 共享环境，每个 cache replica 1 CPU + 8 GB RAM，consumer 1 CPU + 4 GB RAM，reader/writer 2 CPU + 4 GB RAM。

### Experiment 1（固定 cache replica 数量，9 data + 6 metadata）

| 实验 | 场景 | 关键结果 |
|------|------|----------|
| 1(a) Ideal | 平滑扩展至 7,950 consumer | p99 延迟约 500ms（其中 producer 缓冲+flush 120ms，网络传输 180ms，consumer 轮询+读取 100ms，每跳处理仅 25ms）；峰值 data cache 读带宽 70 Gbps；峰值 QPS 4.5M；无 Colossus fallback |
| 1(b) Abrupt spike | 0→4,000 consumer 瞬间拉起 | 读 QPS 激增导致写操作 backpressure，延迟升至约 1s，持续约 150s 后自动恢复 |
| 1(c) Multi-hop spike | 4 个集群各 4,000 consumer 同时拉起 | p99 延迟大部分 <600ms，峰值 1.8s，上游延迟影响下游整个子树 |
| 1(d) Fault tolerance | 逐步终止 cache replica | 单点故障无影响；同一 key-shard 两个 replica 故障导致 60K/s Colossus fallback，延迟峰值 2s；worker 终止对延迟影响可忽略（50ms 内重调度） |

### Experiment 2（启用水平自动扩展，初始 18 data + 6 metadata）

| 实验 | 场景 | 关键结果 |
|------|------|----------|
| 2(a) Smooth scaling | 1,000→20,000 consumer 平滑扩展 | **峰值读带宽 1.8 Tbps**；metadata cache QPS 峰值 19.2M；data cache 从 18 扩至 481 replica；p99 延迟 <2.5s |
| 2(b) Abrupt scaling | 0→6,500 consumer 瞬间拉起 | data cache 扩至 406 replica；p99 延迟峰值 >3s，7 分钟后恢复至 <1.5s |
| 2(c) Backlog recovery | producer 停机 15 分钟后恢复 | 峰值带宽 >1.6 Tbps，持续 2 分钟后降至 600 Gbps |

### 生产环境表现（Google Ads）

- 部署在数十个生产集群
- p95/p99/p999/p9999 延迟分别为 500ms/630ms/730ms/5.71s
- Colossus 机会性读取命中率 96%
- 相比前代系统，RMA 的引入使服务端 CPU 用量降低超过三分之一

---

## 六、批判性分析

1. **实验基线不充分**：论文仅在 Introduction 中对 Kafka 做了一个简单的 consumer scaling 实验（3 brokers, 9 partitions），但未在同等硬件条件下与 Kafka、Pulsar 进行全面的端到端对比。Fast ACS 运行在 Google 内部基础设施（Colossus、CliqueMap、PonyExpress、B4）之上，这些组件本身就具有极强的能力，缺乏对等比较使得很难判断性能优势来自系统设计还是底层基础设施。

2. **对 Google 基础设施的深度绑定**：系统依赖 Colossus、CliqueMap、PonyExpress、Slicer、Borg 等 Google 内部组件，几乎不可能在 Google 之外复现。论文声称"ideas can be adapted to enhance consumer scalability of existing systems"，但这些 idea 的可迁移性未经验证。

3. **延迟分解存疑**：p99 延迟 500ms 中，producer 缓冲占 120ms，consumer 轮询 100ms，这些是可配置参数而非系统固有延迟。声称"每跳仅 25ms 处理延迟"但未清晰区分网络排队与实际处理开销。

4. **扩展实验中 metadata cache 超额扩展严重**：Experiment 2(a) 中 metadata cache 从 6 扩至 81 replica（超出预期 68%），原因是 key-value 分布不均。论文承认 CliqueMap 仅支持 r=3 replication factor，但未深入分析这一限制的影响和解决方案。

5. **TLA+ 验证的规模很小**：最大配置仅为 4 chunks × 4 bytes × 2 writers，与生产环境的规模相差数个数量级。虽然 model checking 在小规模下通过是有意义的，但论文未讨论这一验证覆盖范围的局限性。

6. **Abrupt spike 场景表现欠佳**：Experiment 2(b) 中 0→6,500 consumer 导致 p99 延迟超过 3 秒，恢复需要 7 分钟。对于广告服务等延迟敏感场景，这种恢复时间可能影响 SLA。论文将此归因于 cache scaling 过程中的不稳定性，但未提出有效的预热或预分配策略。

7. **代码复杂性带来的运维成本被轻描淡写**：论文在 Experiences 部分提到 deadlocks "particularly challenging to debug"，latency spikes "lasting several hours"，bad machines "without clear symptoms"，但对这些实际生产问题的解决方案描述模糊。8 SWE-years 的开发投入也说明系统复杂度很高。

---

## 七、AI Infra / MLSys 视角

1. **RMA 用于分布式推理/训练的参数分发**：Fast ACS 证明了 RMA 在读密集型 fan-out 场景中的显著优势（CPU 节省超 1/3）。在大模型推理场景中，KV cache 的分发、模型权重的广播同样是读密集型 fan-out 操作，可以借鉴 RMA + 内存缓存的思路减少服务端 CPU 开销。

2. **多层存储 + 延迟 fallback 策略**：Algorithm 1 的延迟 Colossus 读取思路可迁移到推理系统的 KV cache offloading 场景——优先从 GPU/CPU 内存读取热数据，仅当缓存延迟超过阈值时才从 SSD/远端存储读取，兼顾延迟和成本。

3. **Chunk 级别的并行乱序读取 + 客户端重组装**：这一模式对分布式 checkpoint 的恢复有启发。大模型 checkpoint 通常很大，可以将 checkpoint 分 chunk 存储在多个节点的内存缓存中，恢复时并行乱序读取后在客户端重组装，减少恢复延迟。

4. **Copy tree 路由优化**：跨数据中心的模型分发（如联邦学习中的模型广播）可以借鉴 MST copy tree + 自动 outage 处理的设计，在带宽成本、延迟、容错之间找到平衡。

5. **值得跟进的方向**：
   - 将 RMA 内存缓存思路应用于 disaggregated inference 中的 KV cache 共享层，多个推理实例通过 RMA 共享 KV cache pool
   - 探索 chunk 粒度的自适应缓存策略（而非固定 TTL），根据 access pattern 动态调整，类似于 PagedAttention 的思路

---

## 八、总结

Fast ACS 是 Google 为大规模实时系统（特别是 Google Ads）设计的文件级有序消息传递系统。其核心创新在于利用 RMA 内存缓存层（CliqueMap）实现低延迟 tail-read，通过 4 KB chunk 分块和并行乱序读取绕过单点吞吐瓶颈，配合 Colossus 作为持久化 fallback 保证正确性。系统已在生产环境部署，支持数千 consumer per cluster、Tbps 级集群内读带宽，p99 延迟在数百毫秒级别。主要局限在于对 Google 内部基础设施的深度依赖使得方案难以外部复现，以及在突发负载下的恢复时间（数分钟）对极端 SLA 要求的场景可能不够。
