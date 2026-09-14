---
type: paper
name: WriteGuards
full_title: "WriteGuards: Distributed Storage Support for Strongly Consistent Caches"
authors: [Ziming Mao, Atul Adya, Jonathan Ellithorpe, Rishabh Iyer, Matei Zaharia, Scott Shenker, Ion Stoica]
venue: OSDI
year: 2026
tags: [strong-consistency, distributed-cache, write-fencing, auto-sharding, linearizability]
source_pdf: "[[osdi26-mao-ziming-writeguards.pdf]]"
source_md: "[[osdi26-mao-ziming-writeguards]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-18
---

# WriteGuards：支持强一致缓存的分布式存储机制（OSDI 2026）

> **原题**：WriteGuards: Distributed Storage Support for Strongly Consistent Caches

> **一句话总结**：动态迁移 key range 时，旧 owner 的延迟写入可能在新 owner 已缓存旧值后提交；WriteGuards 让存储层按范围检查 owner token，CLINK 因此能在内存中提供线性一致读，实测将 P90 读延迟从 4.8–10.3 ms 降至 0.5–4.2 µs，远程 CRINK 相比既有一致缓存降低约 2.2–2.4×。

## 问题与动机

分布式存储能提供强一致读，但每次访问都要承担网络往返、序列化和事务处理开销。传统 lookaside cache 虽快，通常只提供最终一致性；写入之后，缓存可能继续返回旧值。对权限、会话状态和在线决策等关键路径，这种陈旧读会造成错误结果。

论文关注写穿缓存和动态 auto-sharding 的组合。key range 从旧 pod 转移到新 pod 时，旧 pod 可能有一个长时间滞留的写请求。新 pod 从存储读到旧版本并缓存后，滞留写请求仍可能通过存储层的版本检查，最终把新缓存变成陈旧值（§4.1）。

## 关键观察 / 隐含假设

- **观察 1：所有权在缓存层转移，不足以阻止旧写入。** 生产网络可能出现约 90 秒的滞留包，而 key reassignment 可在约 20 ms 内完成（§4.1、图 5）。
  - **依赖假设**：写请求会携带可由存储层验证的 fencing value，且存储能对 key range 维护这类状态。
  - **可能失效场景**：若底层存储无法原子地执行 guard 检查与写入，或写路径绕过支持 WriteGuard 的入口，安全性无法成立。
- **观察 2：缓存主要需要按范围协调，而非逐 key 协调。** auto-sharder 已经以连续 key range 管理 lease 和副本分配（§2.3）。
  - **依赖假设**：同一 range 内的所有 pod 对 assignment epoch 达成一致，且范围级元数据规模远小于逐 key 状态。
  - **可能失效场景**：极端碎片化、频繁 split/merge 或大量独立热 key 会增大 GuardMap 和 SetGuard 操作数量。
- **假设 1：非计划故障足够少。** 论文报告 86 个生产服务中约每 750–2000 次重启才发生一次非计划重启；故障时 lease 过期可能造成几十秒不可用（§2.3.2、图 4）。证据强度：中；这是生产观测，但主要来自作者使用的服务集合。

## 核心方法

WriteGuards 是存储层的软状态映射：`SetGuard(range, token)` 为范围安装 token，每次写入携带 token，tablet server 仅在 token 匹配时接受写入（§5）。旧 owner 的延迟写入携带旧 token，因此会被拒绝。token 作用于范围而非单个 key，避免为数十亿 key 保存逐 key lease 状态。

CLINK（Consistent Linked In-memory Key-value cache）把缓存放在应用 pod 内。新 owner 先获取稳定的 SliceHandle，再按存储 tablet 边界拆分 range，安装新的 WriteGuard；只有安装成功且连续持有 assignment，才建立 GuardHandle（§6.2.1）。缓存命中前检查连续 ownership，防止未来 owner 已接管后继续返回旧值。

CLINK 以 Latest State Invariant 为核心：缓存值必须等于存储中的最新已提交值。写入开始时立即驱逐缓存，并标记重叠的读操作；只有在读期间没有当前 owner 写入、已有 WriteGuard 保护旧 owner，且 ownership 未中断时，结果才重新进入缓存（§6.3–§6.4）。热点 key 可在多个 pod 上复制，但写入需要两阶段失效协议。

CRINK 提供远程部署。CRINK-R 将 CLINK 直接作为远程写穿缓存；CRINK-L 将一致性版本服务与普通 Redis 类值缓存分离，读时并行取得版本和值，版本不匹配则回源存储（§7）。后者允许独立扩展值缓存，并能为已有最终一致缓存增加线性一致读语义。

## 设计取舍

- **存储层改动换取读路径无协调**：TiDB 增加范围 guard 表和条件检查；读缓存命中不需要访问存储，但底层存储必须理解 token，且 guard 状态在 tablet 重启后需要重新安装。
- **写入期间牺牲缓存命中率**：CLINK 对写入涉及的 key 先驱逐缓存，重叠读结果通常不可缓存。高写入率或单热点 key 会把读延迟推回存储水平。
- **范围级元数据换取可扩展性**：范围减少元数据，但 SetGuard 需要跟踪 tablet splitpoint；频繁范围变化可能带来重试和状态碎片。
- **强 ownership 带来故障可用性代价**：计划重启可提前迁移，崩溃则需等待 lease 过期。论文的低影响结论依赖非计划故障稀少。

## 实验与结果

- TiDB 使用 9 个 TiKV、6 个 TiDB 和 3 个 PD pod；应用侧使用 6 个、每个 16 vCPU/16 GB 的 pod。评测覆盖 Meta、Twitter 和 Databricks Unity Catalog 生产 trace（§9.1）。
- CLINK 随 CPU 近线性扩展，在 24 个 core 上达到 22.8M QPS，约 1M ops/core（§9.2、图 11a）。
- WriteGuard 在写密集、存储 CPU 利用率 75% 的测试中对吞吐和写延迟没有可测负面影响（§9.3、图 11b）。
- CLINK 的读延迟为 P90 0.5–4.2 µs；直接访问存储为 4.8–10.3 ms。CRINK-R/CRINK-L 为 0.65–3.2 ms，优于 Chrono 的 2.3–5.5 ms（§9.4.1、图 12a）。
- Unity Catalog trace 中读占 99.4%、对象约 23 KB；单 key 的合成压力测试显示写入达到 80/200/400 QPS 时，P99/P90/P50 才分别出现存储级延迟（§9.4.2、图 12c）。
- TiDB 修改约 717 行 Rust、229 行 Go 和 57 行 Go，约一人月完成；缓存实现约 6000 行 C++，auto-sharder 约 12000 行 Scala（§8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| WriteGuards 可阻止 ownership 迁移后的延迟写入 | §5.3–§6.4、算法 1–4 | TiDB、范围 guard、写穿缓存 | 强 |
| CLINK 可提供内存级线性一致读 | LSI 证明、图 12a | 生产 trace；依赖强 ownership 和所有写入经过 CLINK | 中 |
| WriteGuard 本身不会形成明显写路径瓶颈 | §9.3、图 11b | 写密集 workload、75% 存储 CPU 利用率 | 中 |
| CRINK 优于 Chrono | §9.4.1、图 12a | 远程缓存、特定 TiDB 集群和 trace；Chrono 使用 5 秒 timestamp 参数 | 中 |

## 批判性分析

### 论证链条

安全性论证从 token 安装顺序、连续 ownership 和 LSI 组成，链条基本闭合。关键跳步是系统实现必须保证所有写入都经过带 token 的路径；论文对绕过缓存的外部写入、权限控制和多客户端写入口没有展开。实验证明了延迟和吞吐，但没有直接注入分钟级网络滞留写入来验证异常处理。

### 假设压力测试

CLINK 的优势依赖读多写少。论文在单 key 写入压力下展示了命中率下降，但没有给出大量 key 同时高写入时 GuardMap、OpMap 和驱逐开销。范围级 guard 依赖低 churn；若 auto-sharder 频繁迁移小范围，SetGuard RPC 和 tablet 边界重试可能成为新的控制面瓶颈。

CRINK-L 的版本和值并行读取降低了值缓存的耦合，但每次读仍有远程网络和版本服务依赖。版本服务故障、版本更新与值缓存更新的具体恢复策略未被充分评测。

### 实验可信度

Meta、Twitter 和 Unity Catalog trace 覆盖了不同读写比例和对象大小，且包含多 key 组合请求，优于只用合成 trace 的验证。基线包含直接存储、逐读版本检查和 Chrono。不过核心结果集中在单数据中心 TiDB，跨数据中心、真实故障注入、更多存储后端和极端 resharding 频率仍未覆盖。

### 系统性缺陷

强 ownership 的崩溃恢复会造成范围级不可用，论文将其归因于故障稀少，未分析故障相关性或大规模滚动故障。缓存复制的两阶段失效增加了写尾延迟。WriteGuard 是软状态，存储节点重启后虽不破坏正确性，却会使缓存暂时不可缓存。论文也未详细讨论 guard 元数据的长期碎片、监控告警和运维接口。

## 局限与后续工作

- **局限 1**：实现只基于 TiDB，WriteGuard 与其他分布式存储的 tablet 迁移、事务提交顺序和 API 语义是否兼容仍需验证。
- **局限 2**：实验主要在单数据中心进行，跨 WAN 的 guard 安装、故障恢复和读写延迟没有量化。
- **后续工作 1**：注入延迟写入、GC 停顿、网络分区和 tablet 迁移，测量从 ownership 变更到安全恢复的可用性与 P99 延迟。
- **后续工作 2**：在高 churn 和高写入 trace 下比较范围 guard、逐 key guard 和按受影响 key 安装 guard 的元数据及控制面成本。
- **后续工作 3**：为 CRINK-L 的版本服务设计多副本故障模型，验证版本服务不可用或回滚时是否仍保持线性一致性。

## 相关

- **相关概念**：[[Linearizability]]、[[Cache Consistency]]、[[Write Fencing]]、[[Auto-Sharding]]
- **同类系统**：[[Chrono]]、[[Chubby]]、[[Slicer]]、[[Centrifuge]]
- **同会议**：[[OSDI-2026]]
