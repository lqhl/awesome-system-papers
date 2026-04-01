# Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering

**作者**：Shreesha G. Bhat, Tony Hong, Xuhao Luo, Jiyu Hu, Aishwarya Ganesan, Ramnatthan Alagappan (University of Illinois Urbana-Champaign)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/bhat
**源文件**：[osdi25-bhat.pdf](../../papers/osdi-2025/osdi25-bhat.pdf)

---

## 一、背景

Shared log 是现代数据驱动应用的核心基础设施，广泛用于高频交易、实时搜索、IoT 分析、欺诈检测等场景。其抽象为一个持久化、全局有序的记录序列，上游组件写入数据，下游任务消费并处理。

当前主流的 shared log（如 Scalog、Boki、FlexLog）采用 durability-first 架构：客户端先将记录写入任意 shard，shard 再周期性地与 sequencing layer 协调以确定全局顺序。这种设计带来了弹性扩缩容（seamless elasticity）、灵活数据放置（flexible placement）和良好的可扩展性（scalability）。然而，全局排序的协调开销导致了高 delivery latency，进而拖高了端到端（e2e）延迟——这对实时性要求极高的应用是不可接受的。

---

## 二、要解决的问题

1. **高 delivery latency 是 durability-first 架构的固有代价**：shard 必须先批量积累记录、报告给 sequencing layer、等待全局 cut 确定后，才能将记录交付给下游消费者。这个过程引入了 batching delay 和全局协调开销。

2. **delivery latency 直接拖高了 e2e latency**：下游任务只有在记录被交付后才能开始计算，导致从数据产生到处理完成的端到端延迟很高。

3. **早期 shared log（如 Corfu）的 order-first 方案也有高延迟**：虽然避免了部分批量开销，但仍需多轮通信确定全局顺序，且无法支持弹性扩缩容和灵活放置。

4. **现有系统无法同时满足低 e2e 延迟和弹性/灵活/可扩展性**：应用需要在保留 durability-first 架构优点的同时，大幅降低 e2e latency。

---

## 三、洞察与设计

**关键洞察**：在 durability-first shared log 中，下游任务通常需要对消费的记录进行计算（如聚合、更新索引、回归分析）。如果 shared log 能在全局协调完成之前就预测记录的全局顺序并提前交付，那么下游计算就可以与全局协调并行进行，从而重叠两者的时间开销、降低 e2e latency。

基于这一洞察，论文提出了两个核心贡献：

### SpecLog 抽象

SpecLog 提供与现有 shared log 相同的接口（append、subscribe、trim），但增加了投机交付机制：记录被交付时附带一个 speculative 标记，后续系统会确认或失败该投机。应用只需：(1) 等待确认后再外化输出；(2) 若投机失败则回滚状态。

### Fix-Ante Ordering

Fix-ante ordering 的核心思想是**预先确定全局顺序并强制 shard 遵守**。具体实现：

- **Predetermined cuts**：系统预先生成一系列全局 cut（P1, P2, P3, ...），每个 cut 规定每个 shard 应报告的记录数量（即 quota）。
- **Quota 遵守**：每个 shard 严格按 quota 报告——记录不够则填 no-op，记录过多则延迟到下次报告。
- **位置预测**：因为每个 shard 知道其他 shard 也会严格按 quota 报告，所以可以在本地准确预测自己记录在全局序列中的位置，无需等待 sequencing layer 的实际 cut。

这样，除了极少数情况（整个 shard 故障或无法联系 sequencer），投机预测总是正确的。

---

## 四、实现细节

论文基于开源 Scalog 实现了 Belfast 系统，主要技术点包括：

1. **Rate-based Quotas**：根据 shard 的实际摄入速率设置 quota，使 shard 在正常情况下自然满足 quota，最小化 no-op 和延迟记录。

2. **Lag-Fix 机制**：当某 shard 出现 burst 时，该 shard 高频报告以快速消耗 burst；sequencer 检测到其他 shard 的 lag 后，通知它们加速报告（必要时填 no-op），确保 actual cut 能及时发出。也适用于处理摄入速率突降。

3. **Speculation Lease Windows**：将 predetermined cuts 划分为固定大小的窗口（默认 100 个 cut），quota 变更只在窗口边界生效，避免不同 shard 使用不同 cut 导致的 misspeculation。Shard 的加入/退出也在窗口边界进行。

4. **Staggered Cuts**：当 shard 数量较多（>6）时，将 shard 分组，每个 cut 只等待一个组的报告，降低因个别慢 shard 导致的延迟。

5. **Straggler Mitigation**：sequencer 检测到 straggler shard 后，将其 quota 设为 0（持续数个窗口），其他 shard 不再等待它。

6. **故障处理**：shard 内部使用 primary-backup 复制容错；整个 shard 故障时触发 view change，由存活 shard 代填 no-op，对 pending 的投机发送失败通知，应用回滚后继续。

7. **实现规模**：基于 Scalog 修改，只增加一个 RPC（shard 注册），其他机制（lag-fix、quota change）通过 piggyback 现有 RPC 实现。Tord = 1ms，窗口大小 100 cuts。No-op 合并存储以减小开销。

---

## 五、实验结果

实验在 CloudLab 集群上进行，每台机器配置 Intel 10-Core E5-2640v4 CPU、64GB DRAM、25Gb ConnectX-4 NIC、SATA SSD。记录大小 4KB。

| 指标 | Scalog | Belfast | 提升 |
|------|--------|---------|------|
| Delivery latency (2 shards, 20K ops/s) | ~4ms | ~1.2ms | 3.2x |
| Delivery latency (4 shards, 40K ops/s) | ~4ms | ~1.1ms | 3.5x |
| E2E latency (2 shards, 1.5ms compute) | ~6ms | ~3.7ms | 1.6x |
| E2E latency (4 shards, 1.5ms compute) | ~5.9ms | ~3.6ms | 1.63x |
| Append latency overhead (10 shards) | baseline | +5.8% | — |

其他关键结果：
- **Compute time 敏感性**：计算时间 1.5ms 时收益最大（1.63x），0.5ms 时收益为 1.17x（计算结束后需等确认），50ms 时收益趋近 1（计算远超协调时间）。
- **Lag-fix**：有效应对 burst，无 lag-fix 时 burst 后延迟持续升高。
- **Quota change**：长期速率变化后，Belfast 通过调整 quota 避免持续 lag-fix 带来的 no-op 和 sequencer 负载（比不调整 quota 的变体减少约 2x sequencer 负载）。
- **弹性扩缩容**：加减 shard 无停机，throughput 变化延迟 <100ms（等待窗口边界），e2e latency 始终低于 Scalog。
- **可扩展性**：throughput 随 shard 数线性增长（与 Scalog 一致），仿真实验验证到 40 shards 仍保持 e2e 收益。
- **三个应用**：IoT 入侵检测（1.6x）、欺诈监控（1.42x）、高频交易（1.4x）。
- **故障恢复**：shard 内部副本故障无影响；整个 shard 故障后检测+view change+回滚总时间约 400ms，回滚本身开销极小。

---

## 六、批判性分析

1. **e2e 收益高度依赖计算时间**：当下游计算很短（<0.5ms）或很长（>5ms）时，SpecLog 的收益大幅缩水。论文的 "sweet spot" 要求计算时间与协调时间大致匹配（~1-2ms），这一条件在实际应用中并非普遍成立。论文选择的三个应用恰好落在这个区间内，存在 cherry-picking 的嫌疑。

2. **No-op 开销被轻描淡写**：论文声称 no-op 占比 <5%，但这仅在稳定负载下成立。在实际的生产环境中，负载波动频繁，no-op 可能显著增加存储和网络开销。同时，no-op 虽然被下游忽略，但仍占用了全局序列的位置空间，可能影响日志压缩和空间效率。

3. **Misspeculation 的代价未充分评估**：论文强调 misspeculation "极其罕见"（仅在整个 shard 故障时），但 shard 故障时的回滚成本可能很高——应用需要维护 in-memory undo log、暂停计算、回滚数据库写入。论文的故障实验只展示了一个简单应用的回滚，未评估回滚对复杂有状态应用的实际影响。

4. **Staggered cuts 策略过于简单**：当前实现使用静态分组轮转，论文自己也承认更复杂的策略留给 future work。但在 shard 数量多且负载不均时，简单轮转可能导致某些 cut 等待的 shard 恰好是慢 shard，从而抵消 stagger 的收益。

5. **实验规模有限**：真实系统实验最多 10 shards，超过 10 shards 的结果来自仿真（emulation）。仿真框架省略了实际的数据传输和存储开销，可能高估了大规模下的性能表现。

6. **Linearizability 的代价**：Fix-ante ordering 并未减少 append latency（仍需等待 actual cut），甚至因为 quota 等待机制略微增加了 append latency（5.8%）。论文的核心收益完全来自提前交付，但对于 append-heavy、read-light 的工作负载，Belfast 可能反而比 Scalog 更慢。

7. **高 burstiness 场景的退化**：论文承认在极端 burst 场景下，Belfast 可能需要"关闭 fix-ante ordering 回退到 Scalog 模式"，这实质上意味着系统在最需要低延迟的场景（负载激增）下可能恰好失去了核心优势。

---

## 七、总结

SpecLog/Belfast 提出了一种通过投机执行降低 shared log 端到端延迟的方法：利用 fix-ante ordering 预先确定全局顺序，使 shard 能在全局协调完成前就准确预测记录位置并提前交付给下游消费者，从而将协调延迟与下游计算重叠。系统在保留 durability-first 架构的弹性、灵活性和可扩展性的同时，将 delivery latency 降低 3.2-3.5x、e2e latency 降低 1.4-1.6x。主要局限在于收益高度依赖下游计算时间与协调时间的匹配度，且在极端 burst 或大规模部署下的表现仍需进一步验证。
