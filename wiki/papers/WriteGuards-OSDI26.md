---
type: paper
name: WriteGuards
full_title: "WriteGuards: Distributed Storage Support for Strongly Consistent Caches"
authors: [Ziming Mao, Atul Adya, Jonathan Ellithorpe, Rishabh Iyer, Matei Zaharia, et al.]
venue: OSDI
year: 2026
tags: [distributed-cache, linearizability, distributed-storage, fencing]
source_pdf: "[[osdi26-mao-ziming-writeguards.pdf]]"
source_md: "[[osdi26-mao-ziming-writeguards]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# WriteGuards：为强一致缓存提供分布式存储支持（OSDI 2026）

> **原题**：WriteGuards: Distributed Storage Support for Strongly Consistent Caches

WriteGuards 在存储写路径上按 key range 检查 owner fencing token，阻止 reshard 后旧 owner 的延迟写入，从而让 CLink/Crink 缓存无需在每次读时访问存储也能提供 linearizable reads。

## 问题与动机

lookaside cache 快但通常只有 eventual consistency；write-through cache 若在 ownership transfer 后立刻从存储装载数据，旧 owner 仍在网络中的 write 可能随后到达并使新 cache 静默过期。等待最大写延迟、逐 key lease 或每次读做版本检查分别牺牲 availability、scalability 或 latency。

## 关键观察 / 隐含假设

### 关键观察

- delayed-write anomaly 的本质不是缓存失效广播，而是 ownership epoch 之后旧 writer 仍能在 storage commit。
- storage 只需把 key range 映射到 opaque token，并在写入时做一次条件检查；不必理解 cache 的 shard policy。
- auto-sharder 已按 range 管理数十亿 keys，guard 采用相同粒度可避免逐 key metadata。

### 隐含假设

- 所有写都经过当前 primary/cache protocol，不能绕过 guard 直接写 storage。
- auto-sharder 能让所有 pods 对 assignment 和 primary 达成一致，range split/merge 与 guard 更新原子协调。
- 工作负载读多写少；强一致 cache 的两阶段 invalidation 不会被高频 hot-key write 主导。

## 核心方法

### WriteGuard 原语

storage 保存 range→token 的软状态。新 owner 在开始服务缓存读前安装新 token；旧 owner 携带旧 token 的迟到写被拒绝。tablet reshard 时 guard metadata 随范围迁移，read path 不检查 guard。

### CLink

in-process linked cache 将 native object 放在 application 地址空间。每个 key 至多一个 outstanding write，写前/后执行两阶段 invalidation；连续 ownership 且无并发写时，本地 cache hit 等价于 linearizable storage read。

### Crink-R 与 Crink-L

Crink-R 在共享远端 tier 保存 version 和 value；Crink-L 只保存 version，可配合 Redis 等普通 lookaside cache。两者牺牲本地函数调用延迟，换取多租户共享与更统一的容量管理。

## 设计取舍

- range guard 极大降低 metadata，却使 hot key 隔离、range churn 与 false sharing 依赖 auto-sharder。
- read 无协调实现最低 latency，但 write 需要 primary、guard 与 invalidation 协议。
- loosely coupled storage API 简单，却要求底层 store 增加新的条件写原语。
- 单数据中心范围避免 WAN failure/partition 的复杂语义；跨地域只是潜在扩展。

## 实验与结果

- 基于 TiDB、Meta/Twitter trace 与 Databricks Unity Catalog workload，CLink 将 P90 read latency 从直接 storage 的 10.3 ms 降至 4.2 µs，改善约三个数量级（§9.4，图 12）。
- Crink-R/Crink-L 的 P90 read latency 相比直接 storage 低 3.6–5.2 倍，相比其他 strongly consistent remote cache 低 2.2–2.4 倍；远端网络仍使其慢于 CLink。
- 75% storage CPU utilization 的 write-only stress test 中，加入 WriteGuards 后 throughput 与 write latency 没有可测退化，支持“单次条件检查开销低”的主张。
- 在 0.5% traffic churn 的 reshard workload 中，CLink 保持 100% availability 和低 read latency；生产 churn 通常少于 0.2%，但异常 mass resharing 未被覆盖。
- hot-key write 增加时，CLink 在 cache population 期间回退 storage；单 key 达 80 write QPS 时 P99 开始 spike，说明方案适合 read-dominant workload。
- unplanned pod restart 导致的 write unavailability 观测低于 0.001%；该数字依赖 proactive planned reshard 与 Databricks auto-sharder 行为。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| range fencing 足以阻止 delayed writes | 新 owner 安装 token，storage 拒绝旧 token | write-only 压测无可测 throughput/latency 损失 | 所有写必须经过 protocol |
| in-process cache 可提供 linearizable 低延迟读 | CLink ownership 与两阶段 invalidation | P90 从 10.3 ms 降至 4.2 µs | 读多写少、单数据中心 |
| remote consistent cache 也可受益 | Crink 分离 version/value tier | P90 优于替代方案 2.2–2.4 倍 | 每次读仍承担网络 RTT |
| range metadata 支持动态 reshard | guard 与 auto-sharder slice 对齐 | 0.5% churn 时 100% availability | 未测试大规模 correlated churn |

## 批判性分析

### 论证链条

论文先构造 delayed-write execution 说明普通 invalidation 不足，再给出小型 storage primitive，并以三个 cache architecture 展示其通用性。TiDB 实现与多 trace 性能将 correctness mechanism 和实际收益联系起来。

### 假设压力测试

若 legacy client 绕过 cache 直写，或 assignment 暂时分叉，guard token 未必覆盖所有 race。write-heavy hot key 会持续阻止 cache population，CLink 退化为 storage read；跨区域网络 partition 下 owner fencing 与 availability 取舍更尖锐。

### 实验可信度

基线、生产 trace、write stress 和 reshard sensitivity 较完整。linearizability 主要由协议推理支持，缺少 Jepsen 类故障注入；TiDB 和 auto-sharder 代码未覆盖 crash 的所有交错，也未给出 mass failure 的尾部行为。

### 系统性缺陷

WriteGuards 把一个 cache correctness requirement 推入 storage API，生态采用需要多个数据库分别实现并验证。所谓 loose coupling 只隔离 shard policy，并未消除 cache 对 range transaction、token durability 和 write rejection semantics 的依赖。

## 局限与后续工作

- 用故障注入/linearizability checker 覆盖 owner crash、network partition、tablet split 与 guard recovery。
- 扩展到 cross-datacenter store，明确 consistency–availability 选择。
- 评估 mass reshard、极端 hot-key write 和绕过 cache writer 的防护。
- 在 TiDB 之外验证 WriteGuard API 的可移植性与 transaction 交互。

## 相关

- [[Linearizability]]
- [[Distributed-Cache]]
- [[Fencing-Token]]
- [[TiDB]]
