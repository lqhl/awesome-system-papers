# Mako: Speculative Distributed Transactions with Geo-Replication

**作者**：Weihai Shen (Stony Brook University), Yang Cui (Google), Siddhartha Sen (Microsoft Research), Sebastian Angel (University of Pennsylvania), Shuai Mu (Stony Brook University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/shen-weihai
**源文件**：[[osdi25-shen-weihai.pdf]]

---

## 一、背景

高可用、强一致的事务型存储系统（如 Google Spanner）是众多互联网服务的基石。为了容忍数据中心级别故障，数据需要跨地域复制（geo-replication）；为了支持不断增长的数据量和请求量，数据需要分片（sharding）。然而，分布式事务的协调开销（尤其是跨地域通信延迟）使得当前系统的吞吐量远低于单机多核事务数据库——差距可达数千倍。

近年来，RDMA、SmartNIC 等快速网络技术虽然可以在单数据中心内显著降低延迟，但在跨地域场景下，广域网延迟（通常数十到数百毫秒）是物理限制，硬件加速无法解决。这使得跨地域分布式事务系统面临根本性的吞吐瓶颈。

---

## 二、要解决的问题

1. **事务协调与复制的紧耦合**：现有系统（如 Spanner、FaRM）在 2PC 的每个关键步骤后都同步执行 geo-replication，导致复制延迟成为事务处理的关键路径。即使 TAPIR、Janus 等系统尝试将协调和复制合并为单一协议，复制仍然阻塞事务完成。
2. **增加并发无法提升吞吐**：与一般直觉不同，事务系统中增加并发请求会加剧冲突，导致吞吐反而下降（实验显示 abort rate 可达 98%）。
3. **跨分片投机执行的级联回滚问题**：如果投机执行的事务在复制完成前失败，所有直接和间接依赖它的事务都需要回滚，可能导致无界级联 abort，甚至需要暂停整个系统。

---

## 三、洞察与设计

**关键洞察**：事务协调和复制应该进一步解耦而非合并——完全解耦后，系统可以在前台投机执行事务（不等待复制完成），在后台异步复制，从而用投机执行掩盖跨地域复制带来的高延迟开销。

基于这一洞察，Mako 的核心设计包括：

**架构**：数据分片后，每个分片有 leader-follower 架构，leader 之间通过 DPDK 快速网络连接（通常部署在同一数据中心）。事务在 shard leader 间投机执行和认证（使用 2PC），不涉及跨数据中心通信。认证后写入投机可见，复制在后台通过 per-core Paxos stream 并行进行。

**分布式向量时钟**：为粗粒度地追踪事务间依赖关系，Mako 为每个事务分配一个 version vector clock（维度等于分片数）。关键不变量：若事务 T1 传递依赖于 TN，则 T1 的向量时钟在逐分量比较中严格大于 TN。这使得回滚时可以精确识别受影响的事务。

**向量水位线（Vector Watermark）**：每个分片独立维护 shard watermark（所有 worker 线程中 Paxos stream 最小的已复制时钟值）。分片间周期性 gossip 交换水位线，组成全局向量水位线。follower 只有在事务版本低于向量水位线时才安全 replay，保证依赖的事务都已持久化。

**Epoch 机制处理故障**：当 shard leader 失败时，Configuration Manager 推进 epoch，各分片关闭旧 epoch 并计算 Finalized Vector Watermark (FVW)。高于 FVW 的事务被回滚，低于 FVW 的保留。健康分片不需要等待故障分片恢复即可继续处理新 epoch 事务，实现有界回滚。

---

## 四、实现细节

- **基于 Silo 构建**：每个 shard leader 的本地存储引擎基于 Silo（OCC 协议），扩展为分布式 OCC 变体。
- **事务认证四步骤**：Lock（并行锁 WriteSet）→ GetClock（获取向量时钟）→ Validate（检查 ReadSet 冲突）→ Install（投机安装写入）。本质是 2PC 的 prepare/commit，但不在此阶段做复制。
- **Per-core Paxos Stream**：每个分片的每个 worker 线程维护独立的 MultiPaxos 复制流，批量提交（默认 batch size = 400），避免线程同步开销（单流在 ~10 线程后吞吐饱和）。
- **Thomas Write Rule replay**：follower 使用 last-writer-wins 规则并发 replay，无需额外协调。
- **向量时钟压缩**：分片数过大时（>320），使用 K:M 压缩策略将多个分片时钟合并，以常数大小向量时钟支持大规模部署，代价是故障时回滚范围扩大。
- **Learner 加速恢复**：在 leader 同一数据中心部署 learner（不参与投票的副本），故障时快速接管。
- **网络层**：使用 eRPC (DPDK) 加速数据中心内通信；Janus 框架用于复制。
- **代码规模**：~10K 新增 C++ 代码。开源于 https://github.com/stonysystems/mako 。

---

## 五、实验结果

实验在 Azure 上进行，每台 VM 32 vCPU、128GB RAM、Mellanox 4 Lx 加速网络（16Gbps）。注入 50ms RTT 模拟跨数据中心延迟。

### TPC-C 基准测试（10 shards, 每 shard 24 线程）

| 系统 | 吞吐 (TPS) | 对比 Mako |
|------|-----------|----------|
| **Mako** | **3.66M** | 1× |
| Calvin | 425K | 8.6× 落后 |
| 2PC (Spanner-like) | ~40K | ~90× 落后 |
| D2PC | 38.5K | ~95× 落后 |
| Janus | 10.4K | ~350× 落后 |

- 单分片 Mako: 0.96M TPS（Calvin 单分片 42.5K，22.5× 落后）
- Rolis（单分片）比 Mako 单分片高 39%，但无法扩展到多分片

### 微基准测试（10 shards, 5% 跨分片访问）

| 系统 | 吞吐 (TPS) |
|------|-----------|
| **Mako** | **16.7M** |
| OCC+OR | 0.52M（Mako 的 1/32） |

### 延迟（10 shards, TPC-C, batch=600）

| 百分位 | Mako | Janus | Calvin |
|--------|------|-------|--------|
| P50 | 60ms | 50.5ms | 166ms |
| P95 | 65ms | 50.8ms | 206ms |

### 故障恢复

- 健康分片在单分片故障期间仅短暂受影响（Phase 1: eRPC 超时 ~5ms + 心跳超时 ~10s），Phase 2 恢复后吞吐回到正常水平
- 对比 Mako-epoch（组提交策略）：故障期间健康分片吞吐降为 0

### 因素分析（单分片 → 10 分片完整 Mako）

| 阶段 | 吞吐 (M TPS) | 开销 |
|------|-------------|------|
| Silo 基线 | 1.66 | - |
| +多版本 | 1.48 | -11.1% |
| +分布式事务 | 0.47 | -68.1% |
| +复制 | 0.36 | -22.5% |
| +Replay | 0.36 | 0% |

---

## 六、批判性分析

1. **延迟并未降低**：Mako 的核心贡献在吞吐量，但延迟方面并无优势。P50 延迟 60ms（含 50ms WAN RTT），比 Janus 的 50ms 还高 20%。论文标题强调 "speculative" 暗示性能全面提升，但实际上投机执行只提升吞吐，不降低延迟——客户端仍须等待复制完成才能收到响应。

2. **跨分片比例对性能影响极端**：Figure 9 显示，从 0% 到 100% 跨分片事务，吞吐从 60.3M 下降到 1.1M（降幅 98.2%）。这意味着 Mako 的高吞吐数字严重依赖于工作负载的数据局部性。在 TPC-C 中跨分片比例仅 5-10%，但许多真实应用（如社交图谱、金融交易）的跨分片比例可能远高于此。

3. **基线比较不公平**：论文承认对 Janus、D2PC、TAPIR、Calvin 禁用了跨分片事务，理由是这些系统原型无法支持大量分片。这使得 Mako 在执行跨分片事务时与纯单分片系统对比，对基线极度不利。更合理的做法应该是在相同分片数和跨分片比例下比较。

4. **Epoch 回滚的实际影响被低估**：虽然 Mako 声称回滚有界，但在高吞吐场景下（3.66M TPS），心跳超时 10 秒意味着故障检测前可能已有数千万条投机事务需要评估。论文未量化 FVW 计算和回滚的实际开销。

5. **向量时钟压缩的代价**：压缩后故障时整个系统可能受影响（论文自己承认），但未给出压缩场景下的故障恢复实验数据，只展示了正常路径的扩展性。

6. **Azure 网络延迟异常高**：论文注释承认数据中心内延迟 20-30µs（远高于裸金属 RDMA 的个位数微秒），这对 Mako 有利（因为 Mako 的设计目标是掩盖高延迟），但对基于 RDMA 的基线不利。

7. **仅支持 one-shot 事务**：Mako 不支持交互式事务（interactive transactions），这是一个重要的功能限制。论文中 Meerkat 的比较也承认了这一点，但未充分讨论这一限制对实际应用的影响。

---

## 七、AI Infra / MLSys 视角

1. **分布式 KV Store 在 AI 推理中的角色**：大规模 AI 推理服务（如 KV cache 共享、模型路由状态管理）需要跨数据中心的强一致性存储。Mako 的投机执行+解耦复制思路可以应用于这些场景——例如在全球分布的 LLM 推理集群间同步 prefix cache 或 session 状态，在不牺牲一致性的前提下提升吞吐。

2. **训练 checkpoint 的异步持久化**：Mako 将"执行"和"持久化"解耦的思想与大模型训练中的异步 checkpoint 技术（如 DeepSpeed、Gemini）类似。两者都面临同一核心问题：投机执行后如何高效回滚。Mako 的向量水位线机制可能启发更精细的 checkpoint 依赖追踪。

3. **向量时钟压缩**：在大规模分布式训练/推理系统中（数千个 worker），全局依赖追踪面临类似的扩展性问题。Mako 的 K:M 压缩策略（有损但保序）可以迁移到 pipeline parallelism 的依赖管理或 disaggregated inference 的状态同步。

4. **可跟进方向**：将 Mako 的架构适配到 disaggregated inference 场景（prefill/decode 分离，KV cache 跨节点迁移），其中 "事务" 对应一次 KV cache 的读写操作，"分片" 对应不同的 KV cache 分区。

---

## 八、总结

Mako 是首个通过彻底解耦事务协调与 geo-replication 来实现高吞吐的分布式事务 KV 存储。其核心创新在于投机执行 2PC（不等待复制）、分布式向量时钟追踪依赖、向量水位线保证安全 replay、以及 epoch 机制实现有界故障回滚。在 Azure 上的评估显示 TPC-C 吞吐达 3.66M TPS（10 shards），比最先进 geo-replicated 系统高 8.6×以上。主要局限在于延迟无改善、强依赖数据局部性、仅支持 one-shot 事务，以及故障恢复的实际开销未充分量化。
