# Mako: Speculative Distributed Transactions with Geo-Replication

## 论文基本信息

- **标题**: Mako: Speculative Distributed Transactions with Geo-Replication
- **作者**: Weihai Shen (Stony Brook), Yang Cui (Google), Siddhartha Sen (Microsoft Research), Sebastian Angel (UPenn), Shuai Mu (Stony Brook)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/shen-weihai

## 研究背景与动机

高可用、强一致、支持事务的键值存储系统是许多互联网服务（如 Google Spanner）的基石。这类系统通过跨数据中心复制实现容错、通过分片扩展规模、通过分布式事务保证一致性。

**核心瓶颈**：分布式事务的协调开销极大。单台内存多核机器的事务处理吞吐量比典型分布式事务系统高数千倍。

**趋势**：随着 RDMA、SmartNIC 等 ultra-low latency 网络技术的成熟，数据中心内的网络延迟已大幅降低（甚至接近 CPU-内存延迟）。但在 geo-replicated 场景下，跨数据中心的 WAN 延迟仍然是根本性限制，无法通过硬件优化绕过。

**关键问题**：能否让分布式事务在 geo-replicated 设置下的吞吐量接近单机器多核事务处理？

## 要解决的核心问题

**根本限制**：现有分布式事务协议（如 Spanner 的 2PC）将事务协调（coordination）和复制（replication）紧密耦合，导致事务必须等待复制完成后才能返回客户端。跨数据中心的 WAN 延迟（通常 10-100ms）使得任何复制参与都成为事务完成路径上的必要等待。

**核心挑战**：
1. **Challenge 1（Speculation + Failure）**：如果用 2PC 进行 speculation，当 shard leader 在 2PC 完成前失败时，事务不可恢复，必须中止。但所有依赖它的后续事务也会被迫中止（cascading aborts）
2. **Challenge 2（序列化日志）**：避免复制成为瓶颈需要去除全局序列化，但多 core 下不同 log 间可能写入冲突的条目
3. **Challenge 3（跨 log 排序）**：多个 shard 的 follower replay 时如何保证与 leader 一致的状态

## 主要贡献

1. **将事务协调与复制解耦**：通过 speculative 执行让事务在复制完成前继续进行，同时通过 2PC speculation 避免 unbounded cascading aborts
2. **分布式向量时钟的粗粒度依赖追踪**：无需细粒度记录每个事务间的依赖关系，用向量时钟追踪版本，用 watermark 机制选择性回滚
3. **Per-core Paxos streams**：每个 core 独立的 Paxos 实例，避免跨 core 协调成为瓶颈
4. **Epoch-based failure recovery**：失败恢复时以 epoch 为粒度批量决策哪些事务需要回滚，而非单个事务粒度
5. **端到端实现与评估**：在 Azure 上测试，达到 3.66M TPC-C transactions/second（10 分片下比最优竞品快 8.6×）

## 研究方法与设计

### Mako 总体架构

```
Client
  │ send txn
  ▼
Shard Leaders (co-located in same datacenter via DPDK)
  │ speculative execution + 2PC certification
  ▼
Multi-core Follower Replicas (per-core Paxos streams)
  │ geo-replication in background
  ▼
Other Datacenters
```

**核心创新**：将事务协调和复制分离，使事务可以在 DPDK 加速的同一数据中心 leader 间快速执行（speculatively），而复制在后台进行，不阻塞事务处理。

### Speculative Execution & 2PC Certification

事务分为三阶段：

1. **Execution**：Shard leader 作为协调者执行事务，乐观读取各 shard leader 的最新值，缓冲写入。读取来自 certified（但尚未 replicated）的写操作，不读取未 certified 的写。
2. **Certification（4 轮 RPC）**：
   - **Lock**：向涉及 shard 发送 Lock 请求，尝试获取 WriteSet 的锁
   - **GetClock**：获取各涉及 shard 的最新逻辑时钟，构建事务的 version vector clock
   - **Validate**：验证 ReadSet 中所有 key 的版本是否与读取时一致
   - **Install**：将 WriteSet speculatively 安装到各 shard leader

事务在 certification 完成后变为 CERTIFIED 状态，写操作对后续事务可见。

3. **Replication**：Paxos streams 在后台异步复制各 shard/core 的事务日志

**Client 通知时机**：Client 只在 replication 完成（watermark advancing beyond transaction's version）后才收到响应。

### Version Vector Clock

Mako 的版本是一个向量时钟（n 个 shard 各一个逻辑时钟）：
- 每个 shard 的逻辑时钟单调递增（atomic fetch_and_add）
- 事务的 commit version = max(ReadSet 中所有时钟 + WriteSet 所在 shard 的新时钟)

**关键不变量**：若 T₁（经 T₀）依赖 T₀，则 T₁ 的 version vector clock pairwise 大于 T₀ 的。

### Replication with Paxos Streams

**每个 worker thread 维护独立的 Paxos stream**（batch of transactions，batch size = 400）：
- 不同 shard/core 的 streams 完全无协调
- MultiPaxos 协议（每个 core 一个实例）

**Per-core streams 的必要性**：单条 Paxos stream 在 ≈10 worker threads 后吞吐量就会 plateau（受线程同步开销限制）。

### Record-Replay on Followers

Followers 需要从 per-core logs 重建 leader 状态。

**问题**：复制跳过了跨 shard/core 的协调，缺少依赖信息，replay 可能导致不一致。

**Vector Watermark 机制**：
- 每个 shard 维护 shard watermark（monotonically increasing）
- 各 shard 通过 gossip 定期交换各自的 watermark
- 任意 shard 的 vector watermark = 各 shard 最新 watermark 的 min

**安全 replay 条件**：只有当 transaction's version ≤ vector watermark 时才能 replay（表示其所有依赖都已 replicated）。

### Failure Recovery

**Epoch-based 机制**：

当 shard leader 失败时，CM（Configuration Manager，replicated）检测失败并触发：
1. **Epoch 推进**：广播新 epoch
2. **Closing old epoch**：新选出的 leader 从 peers 获取已复制日志，re-commit 必要条目，用 no-ops 填充不可恢复的 slots
3. **计算 Finalized Vector Watermark (FVW)**：跨所有 shard 的全局一致 cut，表示 old epoch 中"无依赖丢失"的最大版本
4. **选择性回滚**：所有 version 不低于 FVW 的 old epoch 事务被回滚；FVW 及以下的事务被确认

**关键保证**：
- 未受影响 shard 上的事务不受 old epoch 回滚影响
- 单个 shard 失败不会导致系统完全暂停（健康 shard 继续处理新 epoch 事务）
- 回滚是 bounded 的（FVW 确立后不会继续增长）

### Scalability

**向量时钟压缩**：当 shard 数量很大时，per-object version vector clock 成为瓶颈。Mako 使用 K:M 压缩（K 个 shard 合并为 M 个向量条目）。

即使 10,000 shards，每个 vector watermark 仅 40KB（可接受）。

## 关键实现细节

### Synchronous vs. Asynchronous Threading

Mako 使用**异步模型**：健康 shard 在等待 old epoch closing 时不阻塞新 epoch 事务处理，但新事务不能读取"状态不确定"的 old epoch certified 事务。

### Shard Leader Co-location

Mako 假设经常一起访问的 shard 其 leaders 部署在同一数据中心。跨数据中心事务（LLMs serving、Uber ride-sharing）的访问局部性研究支持这一假设。

## 实验结果与分析

### 测试环境
- Azure Cloud
- 多服务器配置（各 shard leader 部署在最优 datacenter）

### 关键结果

#### Throughput

| 配置 | 吞吐量 | vs. 竞品 |
|---|---|---|
| **Mako (10 shards)** | **3.66 MTPC-C/s** | **8.6× 最优竞品** |
| Mako (1 shard) | 0.77 MTPC-C/s | vs. Calvi/Rolis（单 shard）: 50% lower |
| 竞品（最优） | 0.42 MTPC-C/s | (Drtm/Aspectron*) |

**竞品比较**：
- Drtm（OSDI'23）：最强竞品，multi-shard geo-replicated TPC-C 0.42 MTPC-C/s
- Calvin（CIDR'12）：pre-determined ordering 的代表
- Aspectron（SOSP'23）：近期工作

#### Latency

Mako 引入的额外延迟很小（仅在 replication 时间上），与提供同等一致性保证的先前系统 latency 相当。

#### Scaling

Mako 在 1-10 shards 下吞吐量线性扩展。

#### 单机 vs. 竞品（非 geo-replication）

论文坦诚：若不考虑 geo-replication，Mako 比 RDMA-based 单机系统慢 50%。这是为 geo-replication 付出的代价。

### 失败恢复评估

- 单 shard 失败恢复时间：快速（CM + learner co-location 加速）
- 回滚事务数量：bounded（与 FVW 计算正确对应）
- 系统可用性：健康 shard 在失败恢复期间继续服务

## 潜在问题与局限性

1. **Sh/leaders co-location 的假设**：Mako 假设参与同一事务的多个 shard leaders 经常在同一数据中心。但对于全局分布的 multi-shard 事务（如跨大陆的金融事务），跨 DC 延迟仍然会成为 certification 路径上的瓶颈
2. **Vector watermark gossip 的开销**：虽然作者声称 gossip 不阻塞事务处理，但在 shard 数量很大时（100+ shards），watermark 交换的频率和网络开销可能成为问题
3. **Per-core Paxos streams 的协调缺失**：每个 core 的 Paxos stream 完全独立，意味着 cross-core 事务的原子性保证只来自 certification phase 的锁。这在故障恢复时（部分 stream 失败）的一致性保证需要仔细验证
4. **Epoch-based 回滚的激进程度**：FVW 以上的所有事务都回滚，即使某些事务不依赖失败 shard。这与论文声称的"选择性回滚"有出入——实际回滚范围可能比预期更大
5. **非 WAN 场景性能较差**：论文承认 Mako 在非 geo-replication 场景（单数据中心）下性能比 RDMA-based 系统低 50%。这不是 Mako 的设计目标，但可能影响用户选择
6. **DPDK 依赖**：Mako 依赖 DPDK 进行 intra-datacenter 加速，这增加了部署复杂度；且 DPDK 在云环境中的使用可能受限（需要特定实例类型）

## 未来工作方向

1. 支持 WAN-only 部署（无 intra-datacenter DPDK）
2. 与 RDMA 的深度集成（替代 DPDK）
3. 自适应 shard leader placement
4. 更高效的 vector watermark gossip 协议
5. Multi-leader replication 架构探索

## 个人评注

### 优点

1. **洞察深刻**：将事务协调与复制"解耦"的思想是本文的核心——这与过去 15 年"合并"协调和复制的趋势（如 Tapir、Janus）恰恰相反，是一个反直觉但有充分论证的方向
2. **Failure recovery 设计精巧**：Epoch-based 回滚机制解决了"speculation + failure" 的根本张力（2PC speculation 在 leader 失败时不可恢复），通过 FVW 批量决策避免了对每个事务的细粒度追踪
3. **Vector watermark 机制优雅**：用 watermark gossip 而非细粒度依赖图来追踪"哪些事务可以安全 replay"，是一个聪明的近似方案，在效率和正确性之间找到了很好的平衡
4. **端到端实现扎实**：使用 DPDK、Per-core Paxos Streams、CM 的 learner co-location 等工程细节表明这是一个经过深思熟虑的系统设计

### 不足与可疑之处

1. **"8.6× speedup"的比较基准不够透明**：论文将 Mako 与"state-of-the-art systems optimized for geo-replication"比较，但这些系统的配置（shard 数、复制配置、 WAN 设置）是否与 Mako 完全相同？如果竞品没有使用相同数量的 shards 或相同的硬件配置，8.6× 的改善可能部分来自不公平的比较
2. **Perplexity 关于 local vs. geo 的权衡**：论文坦诚在非 geo-replication 设置下 Mako 比 RDMA-based 系统慢 50%。但 Figure 1（abstract 中的架构图）暗示 Mako 对所有 shard leaders 都使用 DPDK，这要求所有 shards 都在同一 DC。如果真实部署中 shard leaders 分布在多个 DC，这个优势会大打折扣
3. **Epoch 回滚范围的实证不足**：论文声称 FVW 以上的回滚是"bounded"，但没有提供具体的量化数据（如失败时平均回滚多少 epoch 的事务）。在极高吞吐量下（3.66M txn/s），即使回滚率很低，绝对数量也可能很大
4. **Watermark gossip 与事务处理的干扰**：虽然论文声称 gossip 在后台进行，但在 10 shards × N cores 的规模下，watermark 交换的消息数量和频率没有报告。在极端负载下，gossip 本身可能成为瓶颈
5. **Single-shard 性能比 Rolis 低 50% 的解释不够充分**：Mako 的单 shard 版本（0.77 MTPC-C/s）比 Rolis（单 shard speculation 系统）低 50%。论文将此归因于"Mako 需要 Paxos replication，即使在单 shard 场景也需要 replication 保证"。但这意味着 Mako 的开销主要来自 replication，而非 speculation 机制本身
6. **没有与 Drtm 的详细比较**：Drtm（OSDI'23）是 8.6× speedup 的基准，但论文对 Drtm 的具体限制和 Mako 如何克服这些限制的讨论不够详细。读者难以理解 Mako 的改进具体来自哪些设计决策
