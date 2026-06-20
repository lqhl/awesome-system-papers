---
type: paper
name: HATS
full_title: "Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage"
authors: [Yuanming Ren, Siyuan Sheng, Zhang Cao, Yongkun Li, Patrick P. C. Lee]
venue: FAST
year: 2026
tags: [lsm-tree, kv-store, cassandra, load-balancing, compaction, tail-latency]
source_pdf: "[[fast2026-ren.pdf]]"
source_md: "[[fast2026-ren]]"
---

# Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage (FAST 2026)

> **一句话总结**：在 [[Cassandra]] 上测得「请求频率均衡 ≠ 读延迟均衡」（节点间最高差 **4.24×**），且秒级窗口内 **90.8%** 时间偏离均值 0.5–2×；根因是 distribution 层 replica selection 与 storage 层 [[Compaction]] 异步争用未协同——HATS 用 epoch 级 Gossip 粗调度 + unified score 细调度 + 按读热度分配 compaction rate 的闭环，在 YCSB 读密集负载上 P99 降 **58.6%–59.9%**、吞吐 **2.41–2.90×**（vs [[C3]]/[[DEPART]]），Facebook trace Get P99 降 **78.9%**。

## 问题与动机

分布式 [[LSM-Tree]] KV（[[Cassandra]]、[[ScyllaDB]]、[[TiKV]] 等）要在动态负载下保证低 [[Tail-Latency]]，难点横跨 **distribution 层**（[[Consistent-Hashing]]、replica routing、coordinator 排队）与 **storage 层**（[[MemTable]] flush、[[Compaction]]、page cache 争用）。现有 replica-based load balancing（[[C3]]、Rein、Prequal 等）主要优化 distribution 层 foreground read 分配，默认 background compaction 由各节点独立异步触发，与 read 在 CPU/磁盘带宽上形成不可预测的干扰。

作者以 Cassandra v5.0 为 case study，claim 两个被低估的根因：

1. **延迟不平衡独立于请求分布**：即便副本均匀分流把节点间请求频率差压到 18.9%，读延迟仍可能差 4.24×；YouTube 数据中心研究也表明 CPU 均衡不等于延迟均衡。
2. **Read–compaction 紧耦合且不可单边牺牲**：开启 compaction 后集群 read throughput 从 26.3 跌至 7.3 KOPS（**3.6×** 跌幅），但长期不 compact 又因 SSTable 层数膨胀导致读放大——必须在同一控制环里共调度。

论文提出 **HATS**（Holistic and Automated Task Scheduling），目标是在大时间尺度（epoch，默认 60s）和小时间尺度（单请求）同时抑制延迟抖动，且不破坏 Cassandra 一致性语义。

## 关键观察 / 隐含假设

- **观察 1**：副本均匀分配请求频率后，节点间平均读延迟仍严重失衡（最高节点比最低高 **4.24×**）。
  - **依赖假设**：同质硬件集群、三副本、read consistency level = 1；负载为 Zipf(θ=0.99) 读密集（YCSB-B）；节点数 10、预载 100M 条 1KiB value。
  - **可能失效场景**：异构集群中「延迟差」可能部分来自算力/磁盘差异而非调度；强一致性（需读多副本）时单副本选择空间收窄，粗/细调度收益下降（Exp#9 已显示 consistency level 3 时增益缩小）。

- **观察 2**：读延迟在 **秒级** 窗口剧烈波动——最高延迟节点上 90.8% 的 1s 窗口偏离 30 分钟均值 0.5–2×，而分钟级窗口相对稳定。
  - **依赖假设**：混合读写触发瞬时 foreground I/O 与异步 compaction；dynamic snitching 等现有机制只做局部最快副本选择，缺乏全局预期负载视角。
  - **可能失效场景**：纯读、无 background task 的稳态可能不需要双粒度调度；若 compaction 被 offload 到专用节点（Hailstorm、Nova-LSM），storage 层争用假设弱化。

- **观察 3**：Compaction 与 read 存在可测的 inverse relationship——开启 compaction 后 2 分钟内 read throughput 跌 **3.6×**，但 10 分钟 compact 后关闭 compaction 的稳态吞吐比从未 compact 高 **36.6%**（29.8→40.7 KOPS）。
  - **依赖假设**：LSM compaction 消耗大量 CPU 与磁盘 I/O；Cassandra 内置 rate limit 可在争用极端时部分恢复 read，但无法按 key range 读热度定向 compact。
  - **可能失效场景**：[[DEPART]] 的 two-layer log 在 scan-heavy（YCSB-E）场景避开 LSM split/sort，HATS 的 per-LSM-tree compaction 调度反而略逊（吞吐低 5.4%）；B+-tree 等非 LSM 系统的 background maintenance 机制不同，不能直接套用。

- **观察 4**：「选最快副本」会导致 load oscillation 并抬高尾延迟（[[C3]] 的核心论点）；C3 靠 client-side rate control 缓解，但仍需频繁远程重定向（Exp#6 中 **84.9%** read 被 redirect）。
  - **依赖假设**：coordinator 本地读无网络开销，长期会吸附最多流量；需要 global expected state + local instantaneous score 联合决策。
  - **可能失效场景**：网络极快、副本地理分散时，本地优先假设变弱；R=2 时调度自由度低于 R=3。

- **假设 1**：平均 read latency $T_i$ 与 epoch 长度 $L$ 的比值 $L/T_i$ 可近似节点在 epoch 内可服务的请求容量，用于区分 high-load / low-load。
  - **证据强度**：**中**——在 10 节点实验中与 CoV 改善、吞吐提升一致，但是启发式容量模型，未建模队列深度非线性、GC pause、Java heap 压力。

- **假设 2**：必须采用 [[DEPART]] 的 **replica decoupling**（每节点 R 个副本拆成 R 个独立 LSM-tree）才能做 per-key-range compaction rate 分配。
  - **证据强度**：**强**——设计核心依赖；decoupling 额外开销仅 0.4% write time（引自 DEPART），但所有 baseline 也启用 decoupling 以保证公平，无法单独量化 HATS 调度 vs decoupling 的边际贡献。

## 核心方法

HATS 在 Cassandra 读写路径上嵌入 **闭环三步调度**，每 epoch（$L=60$s，对齐默认 compaction 周期）迭代执行：

### 1. Coarse-grained Read Task Assignment（§4.2）

回应观察 1 的跨节点延迟失衡与 workload skew：

- **状态监控**：各节点经扩展的 [[Gossip]] 协议上报每个 key range 副本的平均 read latency（4B）与请求计数（$4 \times R$ bytes），附带本地递增 version。
- **Scheduler node**：在 seed nodes 间用 [[Raft]] 选 leader 担任 scheduler，避免单点瓶颈；收集全集群 current state 矩阵 $\mathbf{C}_{M \times R}$，按 $\Delta_i = L/T_i - \sum_j C_{i-j,j}$ 划分 high-load / low-load，贪心转移请求形成 expected state $\mathbf{E}$，再 Gossip 下发（附 Raft term + epoch number）。
- **Client 路由**：读请求按 $E_{i,j}/\sum_j E_{i,j}$ 概率选 coordinator 副本，实现 epoch 级全局负载再平衡。Gossip 额外开销在 $M=100, R=3$ 时约 **15.2%**。

### 2. Fine-grained Read Task Coordination（§4.3）

回应观察 2 的秒级抖动与观察 4 的 oscillation：

- Coordinator 维护瞬时延迟 $t_{i,j}$（网络 + storage，来自 dynamic snitching EWMA，weight=0.5）。
- **Unified score**：$L/t_{i,j} - Q_{i+j}$，其中 $Q$ 为 expected state 下的预期负载；score 最高者承接请求。大时间尺度上本地副本通常 score 最高，负载收敛到 $\mathbf{E}$；小时间尺度上刚 compact 好的副本 storage latency 低、score 升，与 compaction 调度对齐。
- 仅 **0.04%** read 需远程 redirect（vs mLSM 6.2%、C3 84.9%、DEPART 19.3%），显著降低 replica selection 开销（Workload C 上 selection 延迟降 **93.5%** vs C3）。

### 3. Compaction Task Scheduling（§4.4）

回应观察 3 的 read–compaction 权衡：

- 每节点总 compaction rate 上限 **64 MiB/s**（Cassandra 默认），仅对 level-1 及以上限速；最底层 flush compaction 不限速以防新 SSTable 读放大。
- 按 expected state 中各 key range 读比例 $E_{i,j}/Q_i$ 分配各 LSM-tree 的 compaction 带宽；高读热度 range 优先 compact 以降低 read amplification，低读 range 推迟。
- **饥饿避免**：Compaction rate 低于阈值时回退 Cassandra FCFS，保证 write-heavy、低读 range 仍有进展。

实现：Java 6K LoC 改 Cassandra v5.0 + client driver v3.0.0；Raft 用 SOFAJRaft。Write 路径保持原样（WAL + MemTable + flush），HATS 不绕过 write 一致性协议。

## 设计取舍

- **取舍 1：双粒度调度 vs 复杂度**。CoarseSchedule 单独提升吞吐（Workload B +67.2%）但对 P99 几乎无效（仅 −4.1%）；必须叠加 FineSchedule 才显著降尾延迟（−24.4%–40.4%）。收益是 holistic 覆盖；代价是 client 需感知 expected state、coordinator 需维护 score，Workload A 的 P50 比 mLSM 高 **14.6%**（调度开销）。
- **取舍 2：Raft scheduler + Gossip 状态扩散 vs 去中心化**。避免 scheduler 单点故障，但依赖 2–3 个 seed node 的 Raft 维护；全 seed 失效时需 Cassandra 重新指定 seed。Gossip 异步传播带来最多一个 epoch 的状态滞后。
- **取舍 3：Replica decoupling 绑定 vs 通用性**。Per-key-range compaction 必须多 LSM-tree，继承 DEPART 的存储布局；scan-heavy 场景下 DEPART two-layer log 的 append-only 设计更优，HATS 在 YCSB-E 吞吐略低 **5.4%**。
- **取舍 4：按读热度分配 compaction vs write-heavy range 延迟**。高写低读 range compaction 被主动推迟，靠最低速率保底；极端写偏斜下 secondary replica 的 LSM-tree 可能积累更多层——论文用下界速率缓解但未量化长期空间放大。
- **边界条件**：读一致性 level 越高，replica selection 空间越小（level 3 时增益仍存但缩小）；epoch $L$ 在 5–120s 间吞吐变化仅 **1.025×**，鲁棒但默认 60s 最优；适用于 replication-based eventual/strong follower-read 架构，不改造 write quorum 逻辑。

## 实验与结果

- **Testbed**：22 机，10 节点同质集群（quad-core i5-3570、16GiB、128GiB SATA SSD、10Gbps）+ 2 客户端（各 50 线程）；预载 100M 记录（24B key + 1000B value），R=3，read CL=1，write CL=3。
- **Micro（Exp#1，YCSB A/B/C）**：HATS 逐步叠加 Coarse→Fine→Compaction；FineSchedule 是 P99 改善主力；完整 HATS 在 A/B 上比 FineSchedule 再降 P99 **49.0%** / **9.8%**，提吞吐 **32.4%** / **5.7%**。
- **Macro YCSB（Exp#2）**：HATS 在 A/B/C/D/F 吞吐最高，峰值 **2.90×**（D vs mLSM）；P99 最多降 **62.2%**（C）；E（95% scan）与 mLSM 持平、略低于 DEPART。
- **Facebook production trace（Exp#3）**：85% Get / 14% Put / 1% Seek，动态 QPS；总吞吐 **48.8 KOPS**（**2.85×** mLSM）；Get P99 降 **83.2%**（vs mLSM）、**78.9%**（vs C3）；Put/Seek P99 偶高于 C3（C3 吞吐更低、磁盘压力小）。
- **延迟均衡（Exp#4）**：节点间读延迟 CoV：Workload C 从 mLSM **0.40** 降至 HATS **0.11**（**−72.5%**）。
- **秒级稳定性（Exp#5）**：Workload B 最高延迟节点上，偏离 0.5–2× 窗口比例：mLSM **91.6%** → HATS **8.7%**。
- **路径分解（Exp#6）**：Replica selection 50.8ms vs C3 776.6ms；磁盘读 73.4ms vs DEPART 431.7ms（two-layer log 开销）。
- **资源（Exp#7）**：CPU time / disk I/O / network I/O 最多降 **47.5%** / **81.7%** / **64.6%**；内存与 baseline 相近。
- **扩展（Exp#8）**：20 节点异构集群，HATS 吞吐仍最高 **2.11×**（C），P99 最多降 **64.3%**（A）。
- **敏感性（Exp#9–12）**：Consistency level 1→3 时相对 DEPART 吞吐增益从 **42.9%** 降至 **24.5%**；Zipf/uniform 键分布、512B–2KB value、100–200 客户端线程下 P99 仍最低（最多 **−56.8%**）。

## Critical Analysis

### 论证链条

测量（请求均衡≠延迟均衡 + 秒级抖动 + read/compaction 逆相关）→ 诊断（distribution 层调度与 storage 层 background task 脱节）→ 三件套（Gossip 粗分配 + unified score 细路由 + 读比例 compaction）→ 在统一 replica decoupling 平台上与 C3/DEPART/mLSM 对比。Microbenchmark 逐步叠加验证各组件必要性，Exp#4–6 直接回指 §3 的三个 motivation 图，链条在 **Cassandra + 三副本 + 读密集/混合负载** 设定下较闭合。

薄弱跳步：(1) 所有强 baseline 共享 replica decoupling，论文未给出「vanilla Cassandra + HATS 调度」的独立曲线，难以分离调度算法与存储布局重构的贡献；(2) 从节点平均 $T_i$ 到请求级尾延迟的映射缺少 queueing 理论或反例分析；(3) Facebook trace 的 Put/Seek 尾延迟退化被解释为「C3 负载更轻」，但未证明 HATS 在写密集生产租户上仍占优。

### 假设压力测试

- **生产规模与故障**：实验集群 10–20 节点、5 次重复；Gossip 状态在 $M=100$ 时开销 15.2% 可接受，但千节点数据中心上 scheduler 聚合 $M \times R$ 矩阵的时效性与 Gossip 收敛延迟未被验证——论文未讨论。
- **多租户 / 一致性混合**：固定 read CL=1、write CL=3；强一致性多读场景（TiKV follower read CL=3）增益递减已有 Exp#9，但是否影响线性一致性语义边界——论文声称不破坏 correctness，未形式化证明 score-based reroute 与 quorum 交互。
- **Compaction 与空间放大**：按读热度推迟低读 range compact 可能在长期写偏斜下增大 secondary replica 的 LSM 深度；饥饿避免用最低速率，但论文未报告 24h+ 稳态下的磁盘占用与读放大曲线。
- **异构与 straggler**：20 节点异构实验显示结论仍成立，但仅追加 10 台弱/强混合机器；极端 straggler（慢盘、网络分区）下 Raft scheduler 切换与 Gossip 版本冲突行为未测。
- **非 LSM 或 offload compaction**：Hailstorm、RubbleDB、Tebis 等将 compaction 移出或同步到副本，HATS 的「共调度」前提可能不再成立——论文在 related work 中承认方向不同，但未量化对比。

### 实验可信度

- **Benchmark 代表性**：YCSB + Facebook trace 建模（含 sine-wave QPS、Pareto value size）优于纯合成；但 50M ops/run、2 分钟 burst 式压测与长期生产 cron/job 混合仍有差距；仅 5 runs（作者承认理想情况应更多）。
- **Baseline 公平性**：mLSM/C3/DEPART 均重实现到 Cassandra v5.0 并统一启用 replica decoupling，消除版本差异，对比可信；未包含 vanilla Cassandra dynamic snitch 或 ScyllaDB 原生调度，绝对加速比可能高估相对生产默认配置的收益。
- **Ablation**：Coarse / Fine / Compaction 三步拆分充分支撑「双粒度缺一不可」；缺少单独关闭 compaction 比例分配（均匀 rate limit）的对照，难以量化「按读热度分配」相对均匀限速的边际收益。
- **指标覆盖**：侧重 throughput、P50/P99/P999、CoV；未报告 recovery 时间、节点故障期间调度行为、hinted handoff/read repair 与 HATS 交互——论文称保留 Cassandra 故障恢复，但未实验验证。

### 系统性缺陷

- **Scheduler 依赖**：Raft leader 挂在 seed node 子集；seed 全挂时需运维介入重配，论文未讨论大规模 DC 的 seed 管理策略。
- **客户端耦合**：Client driver 需理解 expected state 并调整 coordinator 选择概率；第三方 client 或 gRPC 代理层需改代码才能受益，迁移成本高于纯 server-side snitching。
- **可观测性**：6K LoC 调度逻辑嵌入 Gossip/compaction 路径，论文未描述 metrics、tracing 或调试接口；生产排障时 coarse/fine 决策是否可解释——论文未讨论。
- **Java GC / JVM 噪声**：同质 16GiB 机器跑 Cassandra Java 栈，秒级延迟 spike 可能混有 GC；HATS 降低平均资源占用但未隔离 JVM 因素。
- **Write path**：明确不调度 write；写密集租户的主要瓶颈（memtable flush stall、compaction debt）仅间接通过 read-weighted compaction 缓解，write SLO 未单独评估。

## 局限与 Future Work

- **局限 1**：强依赖 replica decoupling 与 replica selection，artifact 说明对不支持多 LSM-tree 或无法灵活选副本的部署不适用。
- **局限 2**：Scan-heavy（YCSB-E）场景输给 DEPART 的 two-layer log；说明 HATS 的 LSM-native compaction 调度不能替代针对 scan 优化的存储布局。
- **局限 3**：统计显著性基于 5 runs；作者承认动态生产环境应增加重复次数与更长观测窗口。
- **Future work 1**：在千节点规模测量 Gossip 扩展性与 scheduler 状态陈旧度对 P99 的影响——需 production-scale trace replay + 故障注入。
- **Future work 2**：与 compaction offload（[[RDMA]]、disaggregated compaction）结合时，是否仍需 fine-grained score，或 coarse epoch 分配就足够——需跨架构 A/B。
- **Future work 3**：为 write-heavy key range 建立可观测的 compaction debt 指标，替代固定最低速率，避免长期空间放大——需 24h+ 写偏斜实验验证。

## 相关

- **相关概念**：[[LSM-Tree]]、[[Compaction]]、[[Tail-Latency]]、[[Gossip]]、[[Raft]]、[[Consistent-Hashing]]、[[Replica-Selection]]、[[MemTable]]
- **同类系统**：[[Cassandra]]、[[DEPART]]、[[C3]]、[[mLSM]]、[[ScyllaDB]]、[[TiKV]]、[[RocksDB]]
- **同会议**：[[FAST-2026]]
- **对比**：[[C3]] 侧重 adaptive replica selection + client rate control 但忽视 compaction 共调度；[[DEPART]] 侧重 replica decoupling + two-layer log 优化写/compaction 成本，distribution 层读均衡弱于 HATS