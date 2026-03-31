# Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering

**作者**：Shreesha G. Bhat, Tony Hong, Xuhao Luo, Jiyu Hu, Aishwarya Ganesan, Ramnatthan Alagappan（University of Illinois Urbana-Champaign）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会）
**链接**：https://www.usenix.org/conference/osdi25/presentation/bhat
**源文件**：[osdi25-bhat.pdf](../../papers/osdi-2025/osdi25-bhat.pdf)

---

## 一、背景

Shared log 是高速交易、实时搜索、IoT 分析、欺诈检测等现代数据驱动型应用的核心基础设施。它提供了一个持久化、全局有序的记录序列，允许多个上游组件并发写入、多个下游任务按序消费。

以 Scalog 为代表的新一代"durability-first"shared log 解决了早期 order-first 设计（如 Corfu）的三大缺陷——无法无缝扩缩容、数据放置不灵活、sequencer 成为扩展瓶颈。其做法是：客户端先将记录写到自选的 shard，shard 周期性地批量上报本地已持久化记录数量给 sequencing layer，由后者决定全局 cut（即跨 shard 的全局顺序），再将 cut 下发给各 shard。Boki、FlexLog 等系统也采用了类似的 durability-first 设计。

---

## 二、要解决的问题

**高 delivery latency 导致高端到端（e2e）latency。**

在 Scalog 的设计中，records 只有在 shard 完成如下步骤后才能交付下游：
1. 客户端将记录写到 shard，shard 主备复制完成（持久化）；
2. Shard 批量上报到 sequencing layer（batching delay）；
3. Sequencing layer 汇总所有 shard 的报告，通过 Paxos 确定并下发 global cut；
4. Shard 根据 cut 分配全局 position，才能将记录交付给下游消费者。

问题根源有两层：
- **批量上报引入 batching delay**：shard 每个 ordering interval（T_ord）才上报一次；
- **Shard 具有"自由意志"**：每次上报多少记录完全由 shard 自主决定，其他 shard 事先无从预知，因此无法在全局协调完成之前准确预测自己的记录会被分配到哪些全局 position。

这两点使得 delivery latency 是 durability-first 架构的**固有代价**，而非实现层面的问题。高 delivery latency 直接导致下游计算推迟启动，从而使应用 e2e latency 居高不下，无法满足高频交易、实时欺诈检测等对毫秒级响应的要求。

---

## 三、核心设计

### SpecLog 抽象

SpecLog 在现有 shared log 接口的基础上引入**推测交付（speculative delivery）**。与 Scalog 相比，唯一的差异在于 `deliver` 回调新增了一个 `is_spec` 标志：

```
append(r, shard)         → 追加记录
subscribe(i, opt_pred)   → 订阅记录
deliver(r, pos, is_spec) → 交付记录（is_spec 指示是否为推测位置）
confirm_spec(k)          → 确认 k 之前的 position 推测正确
fail_spec(k)             → 通知 k 之后的 position 推测失败，下游需回滚并重算
```

Shard 一旦将记录持久化，便立即以**预测的全局 position** 将其交付给下游，无需等待全局协调。之后当真实 global cut 到来时，再对比预测是否正确：正确则发 confirm，否则发 fail 并提供正确顺序。应用只需在收到 confirm 前避免将结果外化，并在 fail 时回滚未确认的状态变更。

### Fix-Ante Ordering

fix-ante ordering 是使推测几乎总能准确的关键机制。核心思想：**事先预定（predetermine）全局顺序，强制各 shard 遵守。**

Fix-ante order 由一系列**预定 global cut** P₁, P₂, P₃, … 组成，每个 cut Pᵢ 规定了第 i 轮中每个 shard j 必须持久化并上报的记录数量（称为**quota** qᵢⱼ）。由于所有 shard 都知道其他 shard 的 quota，每个 shard 可以在全局协调之前准确计算出自己的记录将被分配的 position 区间。

各 shard 满足 quota 的三种情形：
1. **记录数恰好等于 quota**：直接上报全部记录；
2. **记录数少于 quota**：填充 no-op 记录补足 quota（no-op 被下游忽略）；
3. **记录数多于 quota**：将多余记录推迟到下一轮上报。

Sequencing layer 等到所有 non-zero-quota shard 都上报完毕，才发送对应的 actual cut。只要 shard 遵守了 quota，actual cut 就与预定的 cut 相同，推测就成立。仅在极少数情况（整个 shard 故障，或 shard 无法联系 sequencer）下，shard 才无法遵守 quota，导致推测失败；此时系统仍能保证正确性。

值得注意的是：fix-ante ordering **不**意味着"顺序先于持久化"——持久化依然先于顺序确定。fix-ante 只是为 durability-first 架构提供了一种提前预知顺序的方式。

---

## 四、实现细节

### Belfast 系统

Belfast 基于开源 Scalog 修改实现（代码公开）。新增 1 条 RPC（shard 注册），其他所有机制（lag-fix、quota change 等）通过 piggyback 到现有 RPC 实现。关键参数：window size = 100 cuts，T_ord = 1ms，超过 6 个 shard 时启用 staggered cuts。

**Rate-based quotas**：sequencing layer 根据 shard 的上报频率估算 ingestion rate，将 quota 设置为每 T_ord 内 shard 的平均到达记录数，使 shard 自然满足 quota。

**Lag-fix 机制**：应对突发流量（burst）和骤降（drop）。当某 shard 上报频率异常高时，sequencing layer 检测到其他 shard "lag"，立即通知 lagging shard 填 no-op 并额外上报，使 sequencer 能够及时发出后续 actual cut，避免 burst 期间的 append 和 confirm latency 升高。

**Speculation lease window**：quota/cut 的调整只在 window 边界（每 W 个 cut）生效，确保所有 shard 在同一 window 内使用相同的预定 cut，避免因 quota 更新时机不一致产生 misspeculation。Window size = 100 时同步开销仅占 T_ord 的 0.07%。

**弹性伸缩（shard 增删）**：shard 的加入或退出也在 window 边界执行，由 sequencing layer 在新 window 的 cut 中加入或删去对应 shard 的 quota，确保无 downtime 且无 misspeculation。

**Straggler 缓解**：sequencer 检测到 straggler shard 后，在下一个 window 将其 quota 设为 0，允许其他 shard 在不等待 straggler 的情况下推进。之后逐步恢复其 quota 并观察表现。

**Staggered cuts（多 shard 场景）**：将 shard 分成 g 组，第 i 个 cut 只等待第 i mod g 组的 shard 上报，从而在 shard 数量较多时降低 append 和 confirm latency。

**故障处理**：shard 内部副本故障由 primary-backup 复制层透明处理。整个 shard 故障时触发 view-change：sequencer 指定存活 shard（S_A）填写失败 shard（S_F）在当前 window 余下部分的 no-op，其他 shard 继续推进；新 window 起直接排除 S_F。Clients 对 confirmed-gp 之后的推测回滚并重算，回滚开销相比故障检测时间可以忽略不计。

---

## 五、实验结果

**实验环境**：CloudLab 集群，Intel 10-Core E5-2640v4，64GB DRAM，25Gb ConnectX-4 NIC，SATA SSD。Sequencing layer：1 leader + 2 followers（Paxos）。每个 shard：1 primary + 1 backup。记录大小 4KB。

| 指标 | 结果 |
|------|------|
| Delivery latency vs. Scalog | Belfast 提前 3.2×–3.5× 交付记录 |
| 平均 e2e latency（2/4 shards） | Belfast 比 Scalog 低 **1.6×** |
| P99 e2e latency（2/4 shards） | Belfast 比 Scalog 低 1.4×–1.17× |
| Append latency overhead（10 shards）| 仅 **5.8%** |
| 应用层 e2e latency（3 应用） | Belfast 比 Scalog 低 **1.40×–1.60×** |

**Compute time vs. e2e benefit**：当 compute time ≈ ordering time（约 1.5ms）时 benefit 最大（1.63×）；compute time 极短（0.5ms）或极长（50ms）时 benefit 缩小，但 Belfast 始终优于 Scalog。

**Lag-fix 效果**：burst 到来时 no-lf 变体 latency 显著升高且恢复缓慢；Belfast with lag-fix 能在 burst 后迅速恢复低 latency。

**弹性伸缩**：与 Scalog 相同，Belfast 可无缝增删 shard 且 throughput 线性扩展，e2e latency 同时降低。

**应用实验**（IoT Intrusion Detection / Fraud Monitoring / High-Frequency Trading）：均实现了 1.40×–1.60× 的 e2e latency 降低；整个 shard 故障时触发 view change，回滚开销远小于故障检测耗时，恢复后 latency 迅速回到正常水平。

---

## 六、批判性分析

**1. "极少数情况下才 misspeculate"的边界被淡化处理。** 论文强调 fix-ante ordering 在极端情况（整个 shard 故障）才会失败，但实际生产中 shard 故障并不少见，尤其在云环境下网络分区、机器重启频率较高。论文展示的故障实验仅覆盖"2-way 复制下单 shard 全部失败"的场景，缺少多个 shard 同时失败、或 shard 频繁进出的压力测试，无法充分验证 misspeculation 的实际发生率和恢复成本。

**2. 回滚代价的评估过于乐观。** 论文声称"in-memory state 较小，回滚成本可忽略不计"，依据是未确认的记录数量少。但论文仅以欺诈检测（更新少量数据库行）为例，对于需要维护大量中间状态的下游计算（如复杂的窗口聚合、ML 模型权重更新），回滚可能开销不小，且论文未给出系统性的回滚成本分析。

**3. 实验规模较小，缺乏 WAN 或混合部署场景。** 所有实验在单一 CloudLab 集群的局域网内进行，节点间 RTT 极低。在 WAN 场景（T_ord 更大、抖动更高）下，fix-ante ordering 与 free-will 的对比结论是否仍成立？论文没有回答。

**4. No-op 的实际比例未充分量化。** 论文提到 no-op 占比 < 5%，但这是在稳定工作负载下的测量。在 skewed 场景（某些 shard 的 ingestion rate 远低于其他 shard），no-op 填充会显著增加存储写放大和 sequencing layer 的处理压力，论文未提供这类极端场景的数据。

**5. 与 LazyLog 的对比未对等。** 论文仅在 related work 中通过文字描述排除 LazyLog，称其假设"大多数读取与写入在时间上解耦"，但并未提供实验对比。鉴于 LazyLog 同样来自同一课题组并发表于 SOSP 2024，一个直接的实验对比可信度更高。

**6. 应用移植复杂性被低估。** 论文描述应用只需"minimal changes"，但实际上需要实现正确的 rollback 语义（暂停计算、逆序撤销状态变更、恢复计算），对于有副作用的下游操作（如发送告警、外部 API 调用）无法简单回滚，这一局限仅被顺带提及。

---

## 七、AI Infra / MLSys 视角

**与 AI Infra 的相关性**：shared log 是实时特征工程流水线、在线推理日志收集、流式训练数据摄取等 AI 基础设施的潜在底层；fix-ante ordering 对降低这些场景中的数据摄取到消费的 e2e latency 有直接价值。

**可迁移的技术与 insight**：

- **预定顺序 + 推测执行的范式**：在 AI 推理系统中，batch scheduler 面临类似问题——请求何时被处理是不确定的，如果能提前"预定"某个请求的执行 slot，就能让依赖该请求结果的后续操作提前准备。fix-ante ordering 的思想可以启发 continuous batching 或 speculative decoding 场景中的调度优化。

- **No-op 填充保持结构稳定性**：类似于分布式训练中的 padding，以牺牲少量吞吐换取 barrier 对齐。Belfast 的经验表明这种开销通常可控（< 5%），为 AI 训练通信层的类似设计提供了参考数据点。

- **Speculation lease window 的 quota 管理**：可迁移到 LLM 推理的 SLA 管理——为每个服务等级预分配"quota"，并在 window 边界统一调整，避免 SLA 切换时的不一致。

**值得跟进的 future work**：

- 如何将 fix-ante ordering 扩展到 geo-distributed 场景（WAN delay 不稳定），是否可以通过自适应 window size 来应对高抖动？
- 对于 AI 训练的梯度聚合（AllReduce）或参数服务器场景，fix-ante 的"预定顺序"能否减少 straggler 等待时间，同时避免 coordination round trip？
- Misspeculation 的 rollback 语义与 LLM 推理中的 speculative decoding rollback 的统一抽象值得探索。

---

## 八、总结

本文提出 SpecLog 抽象与 fix-ante ordering 机制，使 durability-first shared log（以 Scalog 为代表）在保留其弹性、灵活性和可扩展性的同时，实现了约 1.6× 的 e2e latency 降低。核心思路是通过预定全局 cut 配额、约束各 shard 的上报行为，从而在全局协调完成前即可准确预测 record 的全局位置，实现推测交付与下游计算的有效重叠。Belfast 是其完整实现，包含 rate-based quota、lag-fix、speculation lease window、staggered cuts 等工程机制以应对现实中的突发、速率变化和 straggler 问题。主要局限在于：应用回滚语义有一定侵入性，故障导致 misspeculation 的恢复代价在大规模/高故障率场景下未充分评估，且所有实验限于局域网单集群环境。
