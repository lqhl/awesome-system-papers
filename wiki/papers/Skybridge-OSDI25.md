---
type: paper
name: Skybridge
full_title: "Skybridge: Bounded Staleness for Distributed Caches"
authors: [Robert Lyerly, Scott Pruett, Kevin Doherty, Greg Rogers, Nathan Bronson, John Hugg]
venue: OSDI
year: 2025
tags: [distributed-cache, consistency, bounded-staleness, replication]
source_pdf: "[[osdi25-lyerly.pdf]]"
source_md: "[[osdi25-lyerly]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# Skybridge: Bounded Staleness for Distributed Caches (OSDI 2025)

> **一句话总结**：Skybridge 为 Meta [[TAO]] 复制写入 metadata。7-day checker 中，Wormhole-only 的 2-second write visibility 为 **99.993%**；best-effort Skybridge 为 **99.9993%**，opt-in fail-closed checker 为 **99.99998%**，后者可返回错误而非默认读语义。

## 问题与动机

Meta 全球异步复制（Wormhole + TAO）带来最终一致性但无复制延迟上界——私密群成员可见性、内容审核异步动作等频繁踩 lagging replica。开发者被迫写 40 分钟轮询、脏状态机、有 bug 的分布式锁。更强一致性（线性化、因果）在 Meta 规模下无法默认开启；FlightTracker RYW 只覆盖本用户本区域写入。目标：2 秒 human-scale 有界陈旧度，且可默认对所有 TAO 读启用。

## 关键观察 / 隐含假设

- **观察 1**：Wormhole 强保证（at-least-once、in-order）在 hot shard/过载 publisher 时造成 replication lag 长尾；shard 级 watermark 陈旧会把整 shard 当 stale→thundering herd 打 primary。
  - **依赖假设**：业务读多写少 skew 下，lag 窗口内实际变更的 cache item 是稀疏的——绝大多数「staleness miss」是 false positive。
  - **可能失效场景**：整 shard 持续高频写；failover tier lazy subscribe 本身即 staleness 源。
- **观察 2**：只需复制 write metadata（key + HLC），不需复制数据本体——TAO read-through 自行 upstream fill。
  - **依赖假设**：HLC + NTP skew ε 足以判断 freshness；Skylease lease 能检测 write path gap。
  - **可能失效场景**：Skylease/heartbeat 丢失被误判为 gap→保守 upstream fill（正确但 latency 升）。
- **假设 1**：Replication with gap detection（RGD）：允许乱序、允许可检测 data loss，CRDT 式 add-only metadata set + last-write-wins 仍足以 enforce bounded staleness。
  - **证据强度**：强；设计空间创新点，与 Wormhole 互补而非替代。

## 核心方法

**RGD 语义**：只复制 ⟨key,HLC⟩；已知 gap 时 TAO 保守 refill；乱序 OK（CRDT）。

**架构**：TAO write tier heartbeat → Skybridge write path 聚合成 write window；pull-based replication 优先新 metadata；read path getWrites + bloom filter stream 供 TAO 细粒度 freshness 查询。

**Skylease**：million-scale lease on ZooKeeper/Delos；seal watermark 防 read lease holders 与 open lease 竞态；TAO writer 在 DB commit 前绑定 lease HLC bounds。

**TAO 读路径**：cache HLC vs staleness bound → 不足则查 Skybridge（本地 bloom 预载 lagging shard）。

## 设计取舍

- **取舍 1**：2 秒 bound 是产品/光速延迟折中——非最强一致性但可默认全开。
- **取舍 2**：Bloom filter 可有 false positive（多 upstream fill），无 false negative——保正确性牺牲少量效率。
- **边界条件**：深度绑定 Meta TAO/Wormhole/HLC/MySQL 栈；其他缓存需重做 lease/heartbeat 集成。

## 实验与结果

**指标、基线与边界**：2-second write-visibility latency/consistency；Skybridge fail-closed vs Wormhole-only；7-day checker request workload 等待 sampled write HLC 后 2 seconds 并读所有 TAO tiers/regions（§5.1，Fig.5）。

- Wormhole-only 为 **99.993%**，best-effort Skybridge 为 **99.9993%**，fail-closed checker 为 **99.99998%**；fail-closed 在不能保证时返回 error（§5.1，Fig.5）。
- Wormhole watermark/local bloom/Skybridge 分别证明 **99.96%/99.98%/99.9996%** reads fresh；分析排除无 replication subscription 的 shards，剩余 **0.0004%** 需 upstream（§5.2，Figs.6–7）。
- Skybridge+Skylease footprint 为 TAO 的 **0.54%**，retention **93–109 s**，network **4.8–7.9 GB/s**（§5.3）。
- P99 replication lag 约 **700 ms**、P99.99 约 **1.5 s**（除少数 spikes）（§5.3，Fig.7）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 2-second consistency 随模式不同 | 99.993%、99.9993%、99.99998% | 7-day checker；fail-closed vs Wormhole-only；fail-closed 可报错 | §5.1，Fig.5 | high |
| 大多数 reads 不需 upstream fill | fresh proof 99.96%/99.98%/99.9996% | excludes un-subscribed shards；in-region hop milliseconds | §5.2，Figs.6–7 | high |
| metadata replication 开销小但有 retention 边界 | 0.54%、93–109 s、4.8–7.9 GB/s | production footprint；非无限 staleness coverage | §5.3 | high |
| real-time stream 的 tail lag 有明确范围 | P99 ~700 ms、P99.99 ~1.5 s | physical host time minus replicated window; 非独立 end-to-end proof | §5.3，Fig.7 | high |
| gap detection 是保守安全机制 | indeterminate/missing metadata 时 assume stale 并 refill | design semantic；metadata 而非 data replication | §3.1 | high |

## Critical Analysis

### 论证链条

「shard 级 watermark 太粗 → 只需 metadata oracle → RGD 放松语义换实时复制」对 Meta pain point 针对性强。Wormhole 保 durability/order，Skybridge 补 staleness 长尾，职责分离合理。gap detection + lease 协议是工程核心，逻辑闭合。

### 假设压力测试

- **已证明**：生产规模下 2s bound 可达且开销极小；false positive upstream 可控。
- **可能失效**：跨 region NTP 漂移超预期；Skylease 故障阻塞 write path（高可用设计缓解但未消除）；非 skew workload 下 bloom 收益下降。
- **论文未覆盖**：写密集 shard 的 Skybridge 负载；与 FlightTracker 交互的完整语义组合证明。

### 实验可信度

Meta production 数据是金标准；指标（一致率、fill 率、footprint）贴近运维。外推至非 Meta 系统需谨慎——TAO 图 API、HLC 基础设施是前提。

### 系统性缺陷

系统复杂度高（Skylease + write window + pull replication + bloom）；依赖 MySQL HLC bound 事务 abort；gap 时保守 fill 可能仍触发 cross-region latency；论文对 developer 可见 API 变更着墨少。

## 局限与 Future Work

- **局限 1**：绑定 Meta 栈，通用化需重做 lease/HLC 集成。
- **局限 2**：Bloom false positive 与 gap 保守 fill 仍增加 upstream 负载。
- **Future work 1**：其他 bounded staleness SLO（亚秒/跨产品）下的 footprint/latency trade-off 测量。
- **Future work 2**：failover lazy subscription 与 Skybridge 协同降低冷启动 staleness。

## 相关

- **相关概念**：bounded staleness、eventual consistency、[[TAO]]
- **同类系统**：FlightTracker、Wormhole、Azure Cosmos DB bounded staleness
- **同会议**：[[OSDI-2025]]
