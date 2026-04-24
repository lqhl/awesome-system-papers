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
---

# Skybridge: Bounded Staleness for Distributed Caches (OSDI 2025)

> **一句话总结**：Skybridge 作为带 gap-detection 的带外复制流，为 Meta 的 TAO 分布式缓存提供 2 秒有界陈旧度，把 TAO 的 2 秒一致率从 99.993% 提升到 99.99998%，仅消耗 TAO 0.54% 的服务器资源。

## 问题

Meta 的服务栈靠异步复制（Wormhole pub-sub 流 + TAO 图缓存）来全球扩展，这带来了最终一致性，但不保证复制延迟的上界。业务侧频繁受害：Alice 把 Bob 加入私密群，Bob 却因读到 lagging replica 而进不去；内容审核异步动作读到落后的副本产生雪崩重试乃至宕机。开发者要手搓重试循环、脏状态机和带 bug 的分布式锁来绕这些坑。

把主复制通道改得更强是非起步项——更严的顺序、更强的持久化都会放大现有的延迟长尾，恰恰是热分片、过载发布者和拥塞网段这些场景。论文要回答：能不能**默认**为所有读请求提供**有意义的陈旧度上界**（比如 2 秒），同时保持服务栈的低延迟和高扩展性？

## 核心方法

Skybridge 作为一条**独立的带外复制流**运行，只负责「哪些 key 最近写过」这个元信息，真正的数据填充仍然交给 TAO 原有的 upstream fill 路径。这让 Skybridge 的体积远小于主流 Wormhole 通道，并得以绕开其常见的 lag 来源。

系统建立在一个新的语义上，作者称为 **replication with gap detection (RGD)**：write-metadata 作为 add-only set CRDT 复制，支持**乱序分发**和**可检测的数据丢失**。只要能判定「我有/没有完整数据」，缓存侧就能安全回落到 upstream 拉取。TAO 读请求流程为：先比对 Wormhole watermark 判断 shard 是否 lagging；若 lagging，查询 Skybridge 问 key 最近是否写过。为避免每次都查询 Skybridge，Skybridge 对每个 window 构建 Bloom filter 并向 lagging shard 对应的 TAO host 流式预推，让大部分新鲜性判定本地完成。

写入端用 leasing 系统 **Skylease**（基于 [[Zookeeper]]/[[Delos]] 的共识层）来追踪「某时刻某 shard 由哪些 TAO writer 负责」，以此在聚合 heartbeat 成 complete write window 时能检测 gap。跨区传输用 pull-based、短生命周期流，避免长流 head-of-line blocking 并给订阅者自由决定优先级。实现上还加了 priority queue 来防止 `getWrites` 流量挤掉复制流量造成 metastable failure。

## 关键结果

- TAO 默认 2 秒一致率：99.993% → **99.9993%** (blind)；fail-closed 模式下达 **99.99998%**
- Skybridge 只占 TAO 服务器数的 **0.54%**，网络带宽 4.8–7.9 GB/s vs Wormhole 170–300 GB/s
- P99 复制延迟约 700 ms，P99.99 约 1.5 s，窗口保留 93–109 秒
- 99.9996% 的读请求可通过 watermark + 本地 Bloom filter + Skybridge 查询直接证明新鲜，只有 0.0004% 需要 upstream
- 同时用 2-秒等待实现了 primary-only 和 causal reads 的轻量等价 API

## 相关

- **相关概念**：bounded staleness、CRDT、HLC (hybrid-logical clock)、Bloom filter、lease
- **同类系统**：FlightTracker（Meta RYW）、Azure Cosmos DB bounded staleness、Spanner timestamp bounds、PolarDB-SCC
- **相关实体**：TAO（Meta graph cache）、Wormhole、MySQL
- **同会议**：[[OSDI-2025]]
