# Skybridge: Bounded Staleness for Distributed Caches

**作者**：Robert Lyerly, Kevin Doherty, Greg Rogers, John Hugg（Meta Platforms Inc.）；Scott Pruett（unaffiliated，前 Meta）；Nathan Bronson（OpenAI，前 Meta）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, 2025，Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/lyerly
**源文件**：[osdi25-lyerly.pdf](../../papers/osdi-2025/osdi25-lyerly.pdf)

---

## 一、背景

Meta 的服务栈在全球多个地理区域运行，底层是数百万个 MySQL shard 副本，前端是名为 TAO 的分布式内存缓存（类似 Memcached/Redis，但提供图 API）。为了满足严格的低延迟和高可用要求，Meta 使用 **异步复制**（通过 Wormhole pub-sub 系统）来同步各地区的副本。异步复制提供最终一致性（eventual consistency），但没有对最大复制延迟（staleness）给出任何界限。

这在工程实践中造成了反复出现的痛点：缓存可能长时间持有过期数据，而产品开发者不得不通过重试循环、有竞争条件的状态机等脆弱的方式来应对。Meta 已经部署了 FlightTracker 提供 read-your-writes（RYW）一致性，但 RYW 只针对用户自身的写入，且默认不跨 region，仍不足以解决问题。

---

## 二、要解决的问题

1. **无界 staleness 导致产品 bug**：异步复制无法保证写入在多长时间内对读请求可见。例如，Alice 将 Bob 加入私密群组，但 Bob 所在 region 的缓存副本延迟复制，导致 Bob 无法参与群组。更严重的情况下，内容审核系统因此发生级联故障导致宕机。

2. **传统复制系统的强保证反而制造延迟**：Wormhole 提供 at-least-once 且有序投递，这些强保证在热 shard 或过载 publisher 时会造成大量复制积压（replication lag），P99.99 表现差。

3. **无法对 staleness 设置有效上界**：产品工程师询问「最大跨 region 复制延迟是多少？」，基础设施团队无法给出有意义的答案，因为延迟从毫秒到数小时不等。

4. **更强一致性（线性一致性、因果一致性）在 Meta 规模下无法默认启用**：通信和同步开销太大。

---

## 三、核心设计

Skybridge 是一套**带外复制流（out-of-band replication stream）**，专门为分布式内存缓存提供有界 staleness（bounded staleness），与主复制管线（Wormhole）互补。

### 核心语义：Replication with Gap Detection（RGD）

Skybridge 定义了一种新的复制语义：
- **允许乱序复制（out-of-order replication）**
- **允许已知数据丢失（known data loss）**

只需要能区分「已知没有写入」和「可能有写入但尚未收到」两种状态，就足以支持 bounded staleness 查询。这与 Wormhole 的严格有序、at-least-once 完全不同，从而绕开了产生大延迟的根本原因。

### 三大组件

**1. Skylease（分布式租约服务）**

- 基于 Paxos 的租约服务，追踪哪些 TAO writer 持有哪些 DB shard 的写入权。
- 租约使用 Hybrid Logical Clock（HLC）边界划定。
- 提供 watermark：当 watermark 推进到某时间点 T，意味着该时间点之前的所有写入都已被追踪。
- Regional Skylease 追踪 in-region 的 writer-shard 映射；Global Skylease 追踪每个 shard 的 primary region 归属。
- 使用 delta 压缩减少存储写入量，防止状态爆炸。

**2. Skybridge 服务（写入路径 + 复制层）**

- **写入路径**：TAO writer 在写 DB 前调用 Skybridge client，获取当前 lease 并生成 HLC 边界。写入完成后，将写入元数据（HLC 和对象 ID）打包进 heartbeat 发给 Skybridge。Skybridge 聚合来自所有 leaseholder 的 heartbeat，构建 complete write window（对于某个时间窗口的完整写入集合）。
- **复制层（cross-region replication）**：Skybridge 采用 publisher-subscriber 模型，跨 region 复制 write window。用 pull 模型让订阅者主动拉取，支持乱序拉取和容错重试。短连接流（seconds-long streams）代替长连接流，避免 head-of-line blocking 和负载不均。

**3. TAO 读路径集成（Staleness Oracle）**

- **Bloom filter**：Skybridge 将近期写入的对象 ID 打包成 bloom filter，主动推送到 TAO 读端 host。读请求先用 bloom filter 判断缓存项是否在近期被写入过（没命中则无需进一步查询）。
- **getWrites 查询**：bloom filter 命中时，TAO 向本地 Skybridge 发起精确查询，确认该对象 HLC 版本是否在 Skybridge 记录的写入窗口内。
- **Wormhole watermark**：若 Wormhole 正常追上，直接用其 watermark 判断数据是否新鲜。

三层依次检查：Wormhole watermark → bloom filter → getWrites，逐层提升覆盖率，同时控制开销。

---

## 四、实现细节

- **HLC 协调**：TAO writer 在写 DB 前从 heartbeat storage 获取 HLC 边界；MySQL 会 abort 边界外的事务，保证写入落在正确的 heartbeat 区间内。
- **Inflight write storage**：每个 DB shard 维护 heartbeat 列表和 inflight write 计数，确保有 outstanding write 的 heartbeat 不会被提前发出（防止 incomplete heartbeat）。
- **乱序发布**：heartbeat 可以不按顺序发布，不被 straggler write 阻塞。
- **Circuit breaker**：写路径和读路径均有熔断保护。Skylease 不可用时 fail-open；Skybridge rate limit 超出时 fail-open，触发告警通知工程师。
- **Extended retention**：对长期 lag 的 shard 动态扩展 Skybridge 的内存保留窗口。
- **Clock skew 补偿**：staleness threshold 向前移 50ms 以应对 NTP 的时钟误差（~hundreds of ms）。
- **Priority queue**：Skybridge host 使用优先队列确保 replication > bloom filter 推送 > getWrites 流量，防止 read traffic 饿死 replication，避免 metastable failure。
- **Fail-closed API**：产品可以选择 fail-closed 模式，若 TAO 无法保证 bounded staleness 则返回错误，保留部分 rate limit 配额给 fail-closed 请求。

---

## 五、实验结果

实验在生产环境（tens of regions，每秒数十亿读请求、数百万写请求）中进行，使用 staleness checker（注入写入后 2 秒读取，验证可见性）评估。

| 场景 | 2-second 一致性 |
|------|----------------|
| 无 Skybridge（仅 Wormhole） | 99.993%（偶尔跌破 99.985%） |
| Skybridge blind（best-effort） | 99.9993% |
| Skybridge fail-closed | **99.99998%** |

- **Fail-open 原因分解**（Table 1）：
  - Long shard lag（lag 超 Skybridge 内存保留窗口）：95.9%
  - No replication stream（低流量 shard 无 load-based subscription）：3.3%
  - Skybridge replication lag：0.3%
  - Missing write-path heartbeat：0.2%
  - Skybridge request error：0.2%

- **流量分析**（Figure 6，排除无 replication subscription 的 shard）：
  - Wormhole watermark 可证明 99.96% 请求是新鲜的
  - +host-local bloom filter 覆盖到 99.98%
  - +in-region Skybridge getWrites 查询覆盖到 **99.9996%**
  - 只有 0.0004% 的请求需要走 upstream

- **复制延迟**（Figure 7a）：
  - P99 复制延迟约 700ms
  - P99.99 约 1.5s（偶有毛刺）

- **查询延迟**（Figure 7b）：Skybridge getWrites 请求 P50/P95/P99 均在毫秒级

- **资源占用**：整个 Skybridge 生态（读/写路径 + regional/global Skylease）仅占 TAO server footprint 的 **0.54%**，保留约 93–109 秒的近期写入，拉取带宽 4.8–7.9 GB/s（而 Wormhole 需要 170–300 GB/s）

---

## 六、批判性分析

**问题定义与实验结论的不一致**：论文声称要解决 unbounded staleness，目标是 2-second bounded staleness。但实验显示 fail-closed 模式下一致性为 99.99998%，而 fail-open（blind）只有 99.9993%。这意味着对大多数用户来说，staleness 并不是"有界"的，而是"大概率有界"。论文把这个 gap 解释为 rate limit，但 rate limit 恰恰是为了保护可用性而主动引入的——这本质上是在用"可用性"换"一致性"，与论文最初的问题陈述形成张力。

**最大的 fail-open 来源被轻描淡写**：95.9% 的不一致来自 "Long shard lag"，即 Skybridge 内存不够覆盖长期滞后的 shard。这意味着解决这 95.9% 的根本方法不是 Skybridge 的算法设计，而是加内存或加磁盘。论文在 Limitations 部分提了 disk spill，但并未量化有多少 shard 会超出保留窗口，也没有分析这些 shard 的业务影响。

**3.3% 的 "No replication stream" 问题**：load-based subscription 是一个已知的系统性设计缺陷，导致低流量 shard 完全没有 bounded staleness 保护。论文承认这一问题但并未提出解决方案，且没有讨论这些 shard 的数量规模或业务风险。

**实验基线不够充分**：实验只与"无 Skybridge"进行对比，没有与其他 bounded staleness 系统（如 PolarDB-SCC、Spanner）在类似场景下做比较。可以理解 Meta 生产环境的特殊性，但缺少工程量与收益的对比基准，难以评估 Skybridge 的设计选择是否最优。

**Metastable failure 风险被低估**：论文详细描述了优先队列解决 priority inversion 的方法，但这本质上是用工程 patch 修补了一个潜在的系统性问题——read path 流量可能饿死 replication。这种 patch 的鲁棒性在流量突变或异常场景下存疑。

**Clock skew 的简单处理**：仅通过向前移 50ms 来应对 NTP 的 hundreds-of-ms skew，这在极端情况下（如 NTP 异常漂移）可能不够。Meta 自己也提到在研究 PTP，说明现有方案并不完善。

---

## 七、AI Infra / MLSys 视角

Skybridge 与 AI Infra 的直接关联有限（它是社交网络服务的缓存一致性系统），但以下 insight 对 AI 系统研究有参考价值：

**Staleness 在 AI Infra 场景的类似问题**：分布式训练中的 parameter server、推理服务的 KV cache 跨副本同步、以及特征存储（feature store）的一致性，都面临类似的"最终一致 vs. 性能"的 trade-off。Skybridge 的 RGD 语义（允许已知数据丢失、乱序复制，只需区分"确定没有更新"和"可能有更新"）是一个有趣的设计点，在异步 SGD、参数异步更新等场景中有类比意义。

**Bloom filter 作为 staleness oracle**：将 Bloom filter 主动推送到读端以快速过滤"不需要验证新鲜度"的请求，是一种极其轻量的 approximate staleness checking 技术。这在推理服务的 KV cache 失效检测、特征存储的快速一致性检查中可以借鉴。

**小型带外系统作为一致性增强器**：Skybridge 仅占主系统 0.54% 的资源即实现了显著的一致性提升。这种"以极小代价增强语义"的架构思路，对于 AI 系统中在不改变主训练/推理流水线的前提下增强某类保证（如梯度版本一致性、模型权重 staleness bound）具有启发性。

---

## 八、总结

Skybridge 是 Meta 为 TAO 分布式缓存设计的有界 staleness 系统，通过引入新型 Replication with Gap Detection（RGD）语义，绕开了传统强保证复制系统造成长尾延迟的根本原因，以带外补充复制流的方式将 TAO 的 2-second 一致性从 99.993% 提升至 99.99998%（fail-closed 模式）。系统资源占用极小（仅 TAO 的 0.54%），已在 Meta 生产环境默认启用。主要局限在于：内存容量决定了保留窗口，超长 lag shard 无法覆盖；低流量 shard 因无 replication subscription 而完全无保护；fail-open 模式下 bounded staleness 并非严格有界。
