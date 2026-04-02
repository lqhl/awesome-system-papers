# Skybridge: Bounded Staleness for Distributed Caches

**作者**：Robert Lyerly, Scott Pruett (Meta → unaffiliated), Kevin Doherty, Greg Rogers, Nathan Bronson (Meta → OpenAI), John Hugg — Meta Platforms Inc.
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/lyerly
**源文件**：[[osdi25-lyerly.pdf]]

---

## 一、背景

Meta 的服务部署在全球数十个地理区域，数据存储在 MySQL 中并分片为数百万个 shard，前端由 TAO（Meta 的分布式图缓存）提供亚秒级读取。为了满足高可用和低延迟的要求，Meta 采用异步复制（通过 Wormhole pub-sub 系统）将数据从 primary region 同步到各 secondary region 的缓存。这种架构意味着系统只提供 eventual consistency，复制延迟可能从毫秒到数小时不等。

Eventual consistency 在 Meta 的场景中造成了实际问题：用户将 Bob 加入群组后 Bob 无法立即参与讨论、内容审查系统因读到过期数据导致服务中断、开发者被迫编写重试循环（最长等待 40 分钟）等。这些问题促使 Meta 寻求一种既能提供有意义的一致性保证又不破坏系统扩展性的方案。

---

## 二、要解决的问题

1. **异步复制的无界 staleness**：Wormhole 提供 at-least-once 和 in-order delivery 的保证，但为了维持这些强保证，遇到 hot shard、overloaded publisher 或网络拥塞时会产生复制延迟，且无上界。

2. **粗粒度的 staleness 检测**：基线实现只有 per-shard 级别的 watermark。当某个 shard 落后于 staleness bound 时，该 shard 上所有缓存项都被视为 stale，导致大量 spurious upstream refill——实际上大部分数据并未变更（Meta 的工作负载高度读偏斜）。这会将 TAO 从缓存退化为代理，增加跨区域延迟，并在 primary DB 上产生 thundering herd。

3. **现有一致性机制的局限**：FlightTracker 提供 read-your-writes 但不覆盖其他用户的写入、跨区域默认不启用；强一致性（linearizability/causal consistency）在 Meta 规模下开销过大；TTL 缓存要么保留过期数据要么产生不必要的 miss。

---

## 三、洞察与设计

**关键洞察**：在 Meta 的读偏斜工作负载中，当复制流延迟时，shard 上绝大多数缓存项实际上并未被写入——系统需要的不是重新复制全部数据，而是一个轻量的"staleness oracle"来精确识别哪些缓存项真正发生了变更。通过放松复制语义（允许已知数据丢失和乱序复制），可以构建一条独立于主复制流的旁路通道，专注于实时传递写入元数据而非数据本身，从而避免与主复制流的相关故障。

基于此洞察，Skybridge 的设计包含以下核心要素：

**Replication with Gap Detection (RGD)** — 一种新的复制语义，具有三个关键属性：
- **只复制写入元数据**（cache key + HLC），不复制实际数据，大幅降低带宽和资源需求
- **允许已知数据丢失**：只要能检测到数据缺失（gap），就可以保守地让缓存从上游 refill，保证正确性
- **允许乱序复制**：写入元数据构成 add-only set CRDT（`<key, HLC>` 元组），天然满足幂等、交换、结合律，复制顺序无关紧要

**架构三组件**：
1. **Write path**：集成在 TAO writer 中，收集所有 DB 写入的元数据，通过 Skylease 租约系统追踪哪些 writer 在写哪些 shard，将 heartbeat 聚合为 write window
2. **Replication layer**：pull-based 模型，subscriber 从 primary region 拉取 write window，优先拉取最新数据，支持从多个 replica 源获取，短连接避免 head-of-line blocking 和负载不均
3. **Read path**：在 TAO reader 上，先用 Wormhole watermark 检查、再用 bloom filter 本地过滤、最后才发 getWrites 请求到 Skybridge，层层过滤确保绝大多数检查在本地完成

---

## 四、实现细节

**Skylease 租约系统**：
- 建立在 ZooKeeper/Delos 等强一致分布式共识系统之上
- TAO writer 必须持有 lease 才能对 shard 写入，且承诺在 lease 期间发送 heartbeat
- 使用 delta compression 减少共识轮次开销，自有 sharding 进行水平扩展，批量写入减少共识次数
- 通过 seal watermark 机制解决 lease 开启与 Skybridge 读取 lease holder 之间的竞态

**Heartbeat 构建**：
- TAO writer 的 Skybridge client 维护 inflight write storage，追踪每个 heartbeat 中未完成写入的计数
- 写 DB 前获取 HLC bounds 并在对应 heartbeat 上加引用计数，写完后释放并记录元数据
- 利用乱序发布避免 straggler write 阻塞其他 heartbeat
- Lease 时长约数十秒，HLC bounds 约数百毫秒

**Bloom filter 优化**：
- Skybridge 为 complete write window 构建 bloom filter 并流式推送给 TAO reader
- TAO 在 shard 复制延迟超过 1.5 秒时开始预加载 bloom filter
- Bloom filter 无 false negative，可安全用于本地判定缓存项是否 fresh
- 只占用极少内存（写入集合稀疏）

**容错设计**：
- Circuit breaker：写路径 lease 获取超时、读路径上游请求过多时 fail-open，避免级联故障
- Priority queue：解决读流量与复制流量之间的 priority inversion，优先保障复制健康
- 支持 fail-closed API 供需要强一致性的产品使用
- 扩展保留（extended retention）：对长期 lag 的 shard 选择性延长索引保留时间

**时钟偏移处理**：使用 NTP 同步，staleness bound 前移 50ms 以补偿时钟偏差。

---

## 五、实验结果

实验在 Meta 生产环境中进行，TAO 运行在全球数十个区域，处理数百万写/秒和数十亿读/秒。

| 指标 | 无 Skybridge | Skybridge (blind/fail-open) | Skybridge (fail-closed) |
|------|------------|---------------------------|----------------------|
| 2 秒 bounded staleness | 99.993% | 99.9993% | 99.99998% |

**流量分析**：

| Staleness 检查层级 | 证明 fresh 的请求占比 |
|---|---|
| 仅 Wormhole watermark | 99.96% |
| + Bloom filter（本地） | 99.98% |
| + Skybridge getWrites（in-region） | 99.9996% |

仅 0.0004% 的请求需要去上游获取 fresh 数据。

**复制性能**：
- P99 跨区域复制延迟约 700ms，P99.99 在 1.5 秒以内（偶有尖峰）
- Skybridge 请求延迟：P50/P95/P99 均在毫秒级

**资源消耗**：
- 整个 Skybridge 生态（读写路径 + regional/global Skylease）仅占 TAO 服务器总量的 **0.54%**
- 索引保留 93–109 秒的最近写入（受内存容量限制）
- 网络带宽 4.8–7.9 GB/s（Wormhole 为 170–300 GB/s）

**Fail-open 原因分布**：

| 原因 | 占比 |
|------|------|
| 长期 shard lag（超出 Skybridge 保留时间） | 95.9% |
| 无复制订阅（load-based subscription） | 3.3% |
| Skybridge 复制延迟 | 0.3% |
| Write path 缺少 heartbeat | 0.2% |
| Skybridge 请求错误 | 0.2% |

---

## 六、批判性分析

1. **Fail-open 语义削弱了保证的实际强度**：标题和摘要强调 99.99998% 的 2 秒 bounded staleness，但这是 fail-closed 模式的数字。默认的 blind 模式为 99.9993%，差了一个数量级。更重要的是，fail-open 意味着在系统压力最大时（exactly when consistency matters most）反而放弃一致性保证——这本质上是一种概率性保证而非真正的 bounded staleness。论文对此轻描淡写。

2. **95.9% 的 fail-open 源自长期 shard lag，是系统性问题而非长尾**：论文将 Skybridge 定位为解决长尾延迟的方案，但 fail-open 的绝对主因是超出 Skybridge 内存保留时间（仅约 100 秒）的 shard lag。这意味着 Wormhole 的复制问题比论文暗示的更加严重和系统性。增加保留时间是关键改进方向，但论文仅在 future work 中简短提及。

3. **缺乏端到端用户体验量化**：论文反复用用户体验问题（Alice/Bob 群组、内容审查宕机）来论证动机，但评估完全是系统级指标（consistency rate、latency、traffic），没有量化 Skybridge 部署前后用户可见问题的实际减少幅度。

4. **与 FlightTracker 的关系阐述不够充分**：论文提到 RYW + bounded staleness 形成"compelling semantic"，但未深入分析两者的交互——例如 FlightTracker 的 RYW session 信息是否可以帮助 Skybridge 减少 bloom filter 查询，或两个系统是否存在重复覆盖的场景。

5. **Skylease 的可靠性是单点**：论文描述了一个真实的 Skylease 故障场景（buggy TAO release 导致 lease 爆炸、OOM crash、大规模 fail-open），修复方案是加 rate limit。但 Skylease 建立在强一致共识之上，本身就是系统中最脆弱的组件，论文未充分评估其在各种故障模式下的行为。

6. **NTP 50ms 补偿的充分性存疑**：论文承认 NTP 偏差可达数百毫秒，但只前移了 50ms。如果实际偏差超过 50ms，系统会静默违反 bounded staleness（论文自己在脚注中承认了这一点）。对于声称 99.99998% 一致性的系统，这个风险似乎被低估了。

---

## 七、AI Infra / MLSys 视角

1. **分布式推理服务的缓存一致性**：大规模 LLM serving 系统（如 vLLM、TensorRT-LLM）正在向多节点、多区域部署演进。KV cache 的分布式管理面临类似的 staleness 问题——例如 prefix cache sharing、prompt cache 在多节点间的同步。RGD 语义（只复制元数据、允许 gap、乱序复制）可以直接应用于这类场景。

2. **Feature store 的一致性保证**：ML 推理依赖 feature store 提供实时特征，feature freshness 直接影响模型质量。Skybridge 的 bounded staleness + bloom filter 方案可以为 feature store 提供低开销的 freshness 保证，特别适合读偏斜的在线推理场景。

3. **模型版本管理和配置分发**：在大规模 AI 系统中，模型权重更新、配置变更（如 safety filter 更新）的全局分发也面临 eventual consistency 问题。Skybridge 的 lease + heartbeat 机制可以为这类控制面操作提供 bounded staleness 保证。

4. **值得跟进的研究方向**：
   - 将 RGD 语义应用于分布式 KV cache（如 Mooncake、MemServe 等 disaggregated LLM serving 系统）中的 cache coherence 问题
   - 探索 staleness-aware scheduling：在知道某些 replica 可能 stale 的情况下，如何在 inference router 层面做更智能的请求路由

---

## 八、总结

Skybridge 是 Meta 为其分布式缓存 TAO 构建的 bounded staleness 系统，通过引入 Replication with Gap Detection 这一新的复制语义，在主复制流（Wormhole）之外建立了一条轻量的旁路复制通道，专注于实时传递写入元数据。系统利用 bloom filter 和分层检查机制，使 99.9996% 的读请求无需上游查询即可确认数据新鲜性，将 TAO 的 2 秒一致性从 99.993% 提升至 99.99998%（fail-closed 模式），且仅消耗 TAO 0.54% 的服务器资源。其核心贡献在于证明了通过放松复制保证（允许数据丢失和乱序）反而能在整体上提供更可靠的一致性——这是分布式系统设计中"弱化局部保证以强化全局保证"思路的一个出色实践。主要局限是内存容量限制了索引保留时间（约 100 秒），无法覆盖长期 lag 的 shard。
