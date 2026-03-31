# Mako: Speculative Distributed Transactions with Geo-Replication

**作者**：Weihai Shen (Stony Brook University), Yang Cui (Google), Siddhartha Sen (Microsoft Research), Sebastian Angel (University of Pennsylvania), Shuai Mu (Stony Brook University)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/shen-weihai
**源文件**：[osdi25-shen-weihai.pdf](../../papers/osdi-2025/osdi25-shen-weihai.pdf)

---

## 一、背景

互联网服务的核心基础设施（如 Google Spanner）依赖高可用、强一致的事务性存储系统。为了在数据中心故障时保持可用性，数据需要跨数据中心 geo-replication；为了应对不断增长的数据量，数据被划分为多个 shard，跨 shard 的访问通过分布式事务保证一致性。

然而，当前分布式事务系统的吞吐量与单机多核数据库（如 Silo）相比相差悬殊——可达数千倍的差距。根本原因在于：事务协调（2PC）涉及的网络延迟比 CPU-内存延迟高出三个数量级，而在 geo-replication 场景中，这一问题无法通过 RDMA 等硬件加速手段解决，因为跨数据中心的 WAN 延迟是物理限制，不可回避。

---

## 二、要解决的问题

**核心矛盾**：geo-replication 下的分布式事务，既要满足高可用性（容忍数据中心故障）、强一致性（可串行化），又要实现接近单机多核数据库的高吞吐量，三者在传统架构下难以兼得。

**现有设计的根本局限**：Spanner、FaRM 等系统将分布式事务协议叠加在 replication 协议之上，使得事务的 commit 决策必须等到 replication 完成，WAN 延迟直接成为事务处理的瓶颈。Tapir、Ocean Vista、Janus 等系统试图将两者合并为单一协议，但在 WAN 设置下仍然受制于高延迟。Calvin 通过预确定事务顺序将 replication 移出关键路径，但其日志回放速度无法匹配多核并发处理。

**具体问题**：
1. 如何在存在故障的情况下，使用 2PC 进行安全的投机执行，同时避免无界的级联 abort？
2. 如何避免将所有事务结果序列化为单一顺序日志（避免性能瓶颈）？
3. 多个 per-core 日志流中的冲突 entry 如何在 follower 上保证确定性重放？

---

## 三、核心设计

**关键洞察**：将事务协调（2PC）与 geo-replication 进一步解耦——不等 replication 完成就推进事务执行，通过 speculation 掩盖 WAN 延迟。

**Mako 的工作流程**：

1. **Execution**：Shard leader 作为协调者，乐观读取相关 shard 的数据，本地缓冲写集（WriteSet），不触发 replication。

2. **Certification（投机 2PC）**：在 shard leaders 间执行 4 轮 RPC（Lock / GetClock / Validate / Install）完成 OCC 认证，将事务标记为 CERTIFIED 并投机性地安装写入（speculative install）。此时没有任何 replication 发生，结果对后续事务可见。

3. **Replication（后台并行）**：每个 shard 的每个 worker thread 维护独立的 Paxos stream，并行地将已认证事务的日志复制到 follower，与新事务的投机执行完全并行。

4. **Replay**：Follower 收到 Paxos stream entry 后，通过 vector watermark 机制检查依赖是否已全部 replicate，再进行确定性重放。

**版本 vector clock**：每个事务被赋予一个 vector clock（各 shard 逻辑时钟的组合），用于粗粒度追踪事务间的 read 依赖关系——若 T₁ 读了 T₂ 的写入，则 T₁ 的 vector clock 必须 pair-wise 大于 T₂。这一不变式保证了 rollback 的正确性和 follower 重放的安全性。

**Vector watermark**：分布式 watermark 数组，每个 shard 维护自身的 shard watermark（取所有 worker stream 已复制事务 clock 的最小值），定期全局 gossip。Follower 仅当事务的 vector clock 低于当前 vector watermark 时，才能安全重放该事务。客户端在事务 vector clock 推进到 watermark 之后才收到响应。

**Epoch 机制（故障处理）**：当 shard leader 故障时，Configuration Manager（CM）触发 epoch 推进，所有 shard 协作计算 Finalized Vector Watermark（FVW），低于 FVW 的事务保留，高于 FVW 的事务回滚。健康 shard 不等 FVW 计算完成就可继续执行新 epoch 事务，故障影响面最小化。

---

## 四、实现细节

- **实现语言**：C++，约 10K 行新代码，基于 Silo（单机 OCC 数据库引擎）、eRPC（kernel bypass 网络加速）、Janus framework（replication 基础）
- **开源地址**：https://github.com/stonysystems/mako
- **Shard 内并发**：扩展 Silo 的 OCC 协议为分布式 OCC，per-core 日志 + per-core Paxos stream，消除 single-stream 的同步瓶颈
- **批处理**：每个 stream entry 包含约 400 个事务（批大小可调），平衡 RPC 开销与延迟
- **Vector clock 压缩**：当 shard 数量较多时（>320），支持 K:M 策略将 K 个 shard 的 clock 压缩为 M 个 entry，牺牲部分故障恢复效率换取可扩展性
- **Learner 机制**：在与 leader 同数据中心部署 learner 副本（不参与投票），加速 leader 故障切换，避免 leader 迁移到远端数据中心
- **Thomas's write rule**：Follower 重放时采用 last writer wins，并行重放无需额外协调
- **单读写事务优化**：单 shard 事务无需 RPC，性能直接接近 Silo
- **总副本数**：每个 shard 1 leader + 1 learner + 2 follower = 4 副本（实验配置）

---

## 五、实验结果

**实验平台**：Azure，每台 VM 32 核 Intel vCPU，128 GB RAM，Mellanox 4 Lx 网卡（16 Gbps），数据中心内延迟 20–30 µs，注入 50 ms RTT 模拟 WAN。

**Baseline**：Calvin, D2PC, TAPIR, Spanner-like 2PC over Paxos, Janus, Silo, Meerkat, Rolis, OCC+OR（共 9 个对比系统）。

**主要结果（TPC-C，10 shards × 24 threads/shard）**：

| 系统 | 吞吐量 | 备注 |
|------|--------|------|
| **Mako** | **3.66 M TPS** | 最高 |
| Calvin | 426 K TPS | 慢 8.6× |
| Janus | ~几十 K TPS | — |
| 2PC over Paxos | ~几十 K TPS | — |
| Silo（单机，无 rep.） | 1.66 M TPS | 参考上界 |

**延迟（microbenchmark，单 shard，轻负载）**：

| 百分位 | Mako | Janus | Calvin |
|--------|------|-------|--------|
| P50 | 60 ms | 50.5 ms | 166 ms |
| P90 | 64 ms | 50.7 ms | 202 ms |
| P99 | 66 ms | 51.3 ms | 212 ms |

- Mako P50 延迟中：~50 ms WAN RTT + 3.5 ms 批处理 + 6.5 ms watermark 推进
- TPC-C 下（10 shards，batch 600）P50 延迟约 121 ms

**Cross-shard 事务影响**：纯单 shard 时 60.3 M TPS，全 cross-shard 时降至 1.1 M TPS（降幅 98.2%）

**故障恢复**：单 shard 故障后约 10 秒（heartbeat timeout）恢复到故障前水平；健康 shard 在故障期间可继续执行（Mako vs Mako-epoch 对比显示 epoch-based 方案健康 shard 全程阻塞）

**Vector clock 可扩展性**：全尺寸 VC 在 320 shards 前性能线性，超过后退化；Fixed-64 VC 和单时间戳均可近线性扩展至 512 shards

---

## 六、批判性分析

**实验条件的选择性**：

- **Baseline 不公平问题**：论文对 Janus、D2PC、TAPIR、Calvin 在多 shard 场景下禁用了 cross-shard 事务（因为这些系统在 240 shards 规模下会崩溃），而 Mako 仍然执行 cross-shard 事务。这使得 8.6× 的性能优势对比对象在实际上是"残障版"的竞争者，说服力存疑。

- **延迟对比的双重标准**：Janus 在轻负载下 P50 仅 50 ms（接近 1 WAN RTT），而 Mako 是 60 ms；论文强调 Mako 的吞吐量优势时使用高负载测试，强调延迟优势时却使用轻负载测试。在高负载下 2PC 延迟是 Mako 的 10×，但这是因为高负载导致大量 abort，并非纯延迟差异。

- **单机对比存在落差**：论文 §3 称目标是让 geo-replicated 分布式事务吞吐接近单机多核数据库。但实验显示，即使在 10 shards 场景下，Mako（3.66 M TPS）与无 replication 的 Silo × 10 估算值（~16.6 M TPS）仍有 4× 以上差距，与原始目标距离不小，论文对此轻描淡写。

- **WAN 模拟的可信度**：使用注入延迟模拟 WAN（50 ms RTT），而非真实跨数据中心部署。Azure 虚拟化环境下实测数据中心内延迟已高达 20–30 µs（正常应为个位数 µs），论文承认这是 Azure 虚拟化的问题，但这也意味着所有 baseline 在真实物理集群上的性能可能有所不同。

**设计假设的局限性**：

- **Leader 共置假设**：Mako 性能高度依赖"相关 shard 的 leader 在同一数据中心"这一假设。论文 §7.5 已展示当 leader 分散到两个数据中心后，cross-shard 事务吞吐急剧下降。在真实 geo-distributed 场景下，这一前提很难保证。

- **2PC 的内在局限**：使用投机 2PC 意味着协调者故障会导致相关事务不可恢复，必须通过 epoch 机制批量回滚。虽然论文证明了回滚的有界性，但 epoch 切换期间的停顿（Phase 1 阶段健康 shard 的请求积压、排队等待）在高并发场景下的表现缺乏深入分析。

- **静态分片**：论文明确表示当前实现使用静态分片，动态 resharding 留给 future work。这在实际生产环境中是重大限制，Spanner 的 auto-sharding 能力是其工程价值的核心部分。

- **只读事务优化缺失**：当前实现不支持 follower 直接服务只读事务（这是 Spanner 的重要优化），虽然论文说明了兼容路径，但未实现意味着只读负载同样需要走 leader，限制了读扩展性。

---

## 七、AI Infra / MLSys 视角

Mako 是一篇分布式数据库系统论文，与 AI Infra 的直接关联有限，但其核心思想对某些 ML 系统场景有启发价值：

**投机执行 + 后台 replication 的模式迁移**：AI 训练系统中，parameter server 或分布式 checkpoint 机制面临类似的延迟-一致性权衡。Mako 的"先执行、后持久化、异步回填"模式与 gradient accumulation + 异步 allreduce 有结构相似性——如何在容错的前提下最大化 GPU 利用率，可以借鉴 Mako 的 vector watermark 思路来追踪哪些参数更新已被安全持久化。

**分布式 KV 存储对 LLM 推理的意义**：高吞吐的 geo-replicated 事务性 KV 存储对于需要强一致性的 LLM serving 基础设施（如存储用户会话状态、multi-turn 对话历史、tool call 结果缓存）有潜在价值。Mako 的吞吐量（3.66 M TPS）相比现有系统的量级提升，意味着有可能在不牺牲一致性的前提下支持大规模 AI 应用的状态管理。

**Vector clock 的轻量级可扩展性设计**：MLSys 中的分布式训练/推理调度系统同样需要追踪跨节点的依赖关系（如 pipeline parallelism 中 micro-batch 的依赖）。Mako 的 K:M 压缩 vector clock 思路——在 clock 精度与 overhead 之间权衡——可以迁移到大规模推理集群的依赖追踪场景。

---

## 八、总结

Mako 是一个面向 geo-replication 优化的高吞吐、可串行化、分布式事务 KV 存储。其核心贡献是将事务协调（2PC）与 geo-replication 彻底解耦，通过投机执行掩盖 WAN 延迟，并设计了 vector clock + vector watermark 机制实现安全、有界的级联回滚。在 Azure 上以 10 shards × 24 threads 的配置实现了 3.66 M TPS，超过最佳现有 geo-replicated 系统 8.6×。主要局限在于依赖 leader 共置假设、不支持动态分片、只读事务优化缺失，以及实验中对部分 baseline 的非对称测试条件。
