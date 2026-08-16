---
type: paper
name: WriteGuards
full_title: "WriteGuards: Distributed Storage Support for Strongly Consistent Caches"
authors: [Ziming Mao, Atul Adya, Jonathan Ellithorpe, Rishabh Iyer, Matei Zaharia, Scott Shenker, Ion Stoica]
venue: OSDI
year: 2026
tags: [distributed-cache, linearizability, distributed-storage, fencing]
source_pdf: "[[osdi26-mao-ziming-writeguards.pdf]]"
source_md: "[[osdi26-mao-ziming-writeguards]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# WriteGuards：为强一致缓存提供存储端写保护（OSDI 2026）

> **原题**：WriteGuards: Distributed Storage Support for Strongly Consistent Caches

> **一句话总结**：WriteGuards 让存储按键范围保存一个当前 owner 的不透明 token，并拒绝携带旧 token 的延迟写；基于这个很小的存储接口，CLINK、CRINK-R 和 CRINK-L 可以在不逐次访问存储的情况下，从内存返回线性一致（linearizable）的读结果。

## 问题与动机

普通 lookaside cache 很快，但写入完成后，cache 中的旧值不会自动变成最新值，所以一般只能给最终一致性。write-through cache 看起来更容易做强一致：让所有写都经过 cache，写前驱逐旧值，写成功后再放入新值。但只要 cache 会动态 reshard，这个做法仍然有一个容易忽略的竞态（§4、图 5）：

1. 旧 owner `P1` 发出带 OCC version check 的写，写请求长时间停在网络、运行时或队列中。
2. auto-sharder 把该键的范围交给新 owner `P0`。
3. `P0` 从存储读到版本 `V1`，并准备缓存它。
4. `P1` 的旧写随后到达，OCC 检查仍然成功，把存储更新成 `V2`；`P0` 却继续返回 `V1`。

论文把它称为延迟写异常（delayed-writes anomaly）。问题不在“新 owner 是否拿到了 cache ownership”，而在“旧 owner 是否还可能在 storage commit”。生产系统确实会遇到长达数十秒甚至数分钟的网络、[[Garbage-Collection|GC]] 或 runtime stall，而正常 key reassignment 可以只用约 20 ms，因此不能靠“转移前等一会儿”获得严格正确性（§4.1）。

已有方案各有明显代价：每次读都去存储查 version 会失去 cache 的延迟优势；每个 key 第一次读先做 metadata write 会把写放到读路径；Chubby sequencer/reader lease 需要逐 key 状态并把 lease service 接到写路径；Chrono 一类 timestamp bound 依赖存储的时间戳语义，而且一次写会让 cache 在一段时间内不可读；假设写延迟存在固定上界则只能得到近似正确性（§4.2、§10.1）。

## 关键观察 / 隐含假设

- **观察 1：需要 fencing 的是 storage commit，而不是 cache entry。** 新 owner 只要先让存储拒绝所有旧 ownership epoch 的写，再读取并缓存数据，就能关闭 delayed-write race。
  - **依赖假设**：受保护 key space 的每个写都携带 guard，并由存储在 commit 前检查；绕过 cache/guard 的 writer 会破坏证明。
- **观察 2：ownership 已经按 range 管理，guard 也可以按 range 管理。** 一个 guard 可以覆盖大量 key，不需要为数十亿 key 保存逐 key lease 或 sequencer（§5）。
  - **依赖假设**：cache slice 和 storage tablet 不必同样分片，但 client 能发现 tablet boundary，并把一个 slice 拆成若干 `SetGuard`。
- **观察 3：线性一致 cache 的证明可以拆成三类 writer。** previous owner 由 WriteGuard 排除，current owner 由本地 operation overlap tracking 排除，future owner 由 continuous ownership check 排除（§6.3–§6.4）。
  - **依赖假设**：auto-sharder 提供 Assignment Consistency，并能判断从取得 `SliceHandle` 以后 ownership 是否从未中断。
- **观察 4：读多写少时，可以把协调留在 assignment 和 write 路径。** cache hit 只做本地 ownership check；hot key 的多副本写才执行同步 invalidation（§6.5）。
  - **依赖假设**：生产 workload 的写频率、crash 频率和 reshard churn 都不高。高频写会持续阻止 cache population，使读退化到 storage latency。

## 核心方法

### WriteGuard 存储原语

存储增加两个动作：`SetGuard(range, guardValue)` 把某个键范围关联到一个不透明 token；每次写再比较请求 token 与当前 range token，只有相等才允许继续。tablet server 用内存 interval map 保存这些 token。guard 是软状态，不需要写入持久化日志，写路径也只多一次条件检查（§5.1、图 6）。

一个 cache slice 可能跨多个 storage tablet。新 owner 先按 tablet boundary 把 slice 切成子范围，为每个子范围生成独立且唯一的 UUID，再分别调用 `SetGuard`。若命中了过期的 tablet layout，存储返回 `TabletLayoutChanged`，client 刷新 boundary 后重试；若调用 timeout，则必须换一个新 token 再试，不能复用无法确定是否安装过的 token（§5.1、§6.2.1）。

正确性不只来自“token 不同”，还来自三个顺序规则（§6.2.2）：

1. `SetGuard` 必须在同一个连续 ownership period 内开始并结束，成功后才创建 `GuardHandle`。
2. 同一 ownership period 内，覆盖同一个 key 的 `SetGuard` 不能并发。
3. 每一次调用和重试都使用全新 token。

这使所有可用于 cache 的 relevant guards 按 key 形成与 storage installation 一致的全序。旧 owner 的写只能携带旧 token，所以新 owner 创建 `GuardHandle` 后，旧写一定被拒绝（图 7）。

storage reshard 的处理有重要细节。tablet split 时，新 tablet 继承原范围的 guard；merge 后，各子范围保留不同 guard。论文也承认 merge 可能积累很多 interval，尚未实现上界控制。prototype 在 tablet migration 时**不迁移 guard，而是直接清空软状态**：这会让当前 owner 和旧 owner 的非空 token 都不匹配，先拒绝写；当前 owner 收到 mismatch 后安装新 guard 并重试。因此牺牲短暂写可用性，但不允许旧写悄悄通过（§5.2、§6.3.1）。

### CLINK：进程内强一致 cache

CLINK 把值以原生对象形式放在 application pod 地址空间。只有当前被分配该 key 的 pod 才能返回本地 cache hit；任意 pod 仍可直接读 storage，因此未获得 ownership 时不是“不能读”，而是“不能从 cache 读”（§6）。

CLINK 维护三张表：`GuardMap` 保存 range 对应的 `GuardHandle`，`CacheMap` 保存值及创建它时使用的 guard，`OpMap` 记录对每个 key 尚未完成的读写以及是否和写重叠。它用 Latest State Invariant（LSI）定义透明性：只有当 cache value 等于 storage 最新 committed value 时，才能放入或返回 cache（§6.1）。

读 miss 时，CLINK 可以直接访问 storage，但只有同时满足三项条件才缓存结果：操作开始时已有 guard，操作期间没有本 owner 的写与它重叠，并且读取结束时仍连续持有 ownership。写开始前先驱逐 cache，并把所有重叠 operation 标为不可缓存；写成功后也要再次检查 LSI。写 timeout 或 `WriteGuardMismatch` 表示可能存在一个本 owner 发出的 delayed write，CLINK 会清除旧 handle、安装全新 guard，再从头重试（算法 2–4）。

这个证明分成两个时间点。LSI-at-entry 保证放入 cache 时结果是最新值；LSI-at-serve 在每次命中时检查 continuous ownership，并靠本 owner 写前驱逐，保证从放入到返回之间值没有改变。previous/current/future owner 三类 mutation 都被覆盖，所以 cache hit 可继承 storage 的 linearizability（§6.4）。

### hot key 多副本

auto-sharder 先把 hot key 隔离成单独 slice，再做 asymmetric replication。一个 replica 是 primary，负责 WriteGuard 和所有写；其余 replica 只读。写采用两阶段 invalidation：primary 先通知全部 replica 驱逐 key 并标成 uncacheable，收到所有 ACK 后才写 storage，最后再发送 finish message 恢复 cacheability。replica membership 一旦改变，所有成员都放弃该 range 的 cache，直到新 ownership epoch 建立（§6.5）。

这条路径只用于少量 hot key，避免让所有普通写都承担 reader-lease recall；代价是 replica 越多，写的同步尾延迟越高。

### CRINK-R 与 CRINK-L：远程版本

CRINK-R 把 CLINK 作为独立 write-through cache service 部署，值、ownership 和 consistency logic 都在远端 cache tier 中。多个 client 可以共享它，但每次访问仍要承担网络、序列化和排队成本（§7.1、图 9）。

CRINK-L 把一致性 metadata 与 value 分离：小型 version service 维护强一致 version 和 assignment，value 放在 Redis 一类普通 lookaside cache。读时 client 并行查询 version service 与 value cache，version 相同才返回 cached value，否则回 storage；写经过 version service commit，value 可以异步更新，因为 version mismatch 会阻止旧值被当成线性一致结果（§7.2、图 10）。这种分层允许 value tier 独立扩容，也允许同一 cache 同时提供 eventual 和 linearizable read API。

## 实现

作者实现了约 12,000 行 Scala 的 strong-ownership auto-sharder，以及约 6,000 行 C++ 的 CLINK/CRINK。底层使用 TiDB 7.5.1：TiKV 增加 717 行 Rust，TiDB SQL layer 增加 229 行 Go，PD 增加 57 行 Go，完整存储改动约耗费一个人月（§8）。这说明接口小，但并不表示其他数据库可直接复用同一实现。

## 设计取舍

- **range metadata 换精确粒度**：guard 数量与 slice/tablet intersection 有关，不与 key 数量线性增长；merge、热点隔离和频繁 boundary 变化却可能让 interval map 碎片化。
- **软状态换简单恢复**：storage restart/migration 不需复制 guard；当前写会被拒绝并重装 token，但恢复期间写可用性下降。
- **读路径无远程协调换严格写入口**：cache hit 极快；所有受保护写必须经过 primary 并携带正确 guard，legacy writer 不能偷偷绕过。
- **单 owner 换多读副本协议**：普通 key 不做副本协调；hot key 写必须等待所有 reader replica invalidation。
- **与 shard policy 解耦换新的 storage contract**：存储不理解 application ownership，但必须实现 range installation、commit-time guard check、layout-change error 和精确失败语义。
- **高可用依赖低 crash/churn**：planned restart 可提前迁移；unplanned crash 仍要等 lease expiry，论文根据生产 crash 频率估算整体影响很低，不是证明任何一次 key 都持续可写。

## 实验与结果

- **延迟主结果**：生产 cluster 使用 9 个 TiKV pod、6 个 TiDB pod、3 个 PD pod和 6 个 application pod；TiKV 每个 30 vCPU/15 GB，application pod 每个 16 vCPU/16 GB，网络 RTT 为个位毫秒。Meta、Twitter 与 Databricks Unity Catalog trace 中，CLINK 的 P90 为 0.5–4.2 μs，Storage 为 4.8–10.3 ms；最显眼的端点是 10.3 ms 对 4.2 μs。Version baseline 每次读查 storage version，P90 仍为 3.3–9.0 ms（§9.1、§9.4.1、图 12a）。
- **远程 cache 结果**：CRINK-R/CRINK-L 的 P90 为 0.65–3.2 ms，Chrono 为 2.3–5.5 ms。论文汇总为 CRINK 相对 direct storage 最多低 3.6–5.2 倍，相对现有 strong remote cache 低 2.2–2.4 倍。Chrono baseline 使用论文建议的 5 s attempt timestamp，一次写会在这段时间内降低 cacheability，因此结论依赖该参数（§9.1、§9.4.1、图 12a）。
- **吞吐与 guard 开销**：CLINK 读吞吐近似线性扩展，约每核 100 万 ops/s，24 cores 达 22.8 M QPS；prototype 没有 lock-free index、kernel bypass 等 cache 优化。write-only workload 把 storage CPU 压到 75% 时，有无 WriteGuard 的 throughput 和 write latency 在图中没有可测差异，但论文没有给出更细的置信区间或长期运行误差（§9.2–§9.3、图 11）。
- **写频率边界**：Unity Catalog trace 中，分散到不同 key 的 write QPS 增加时 CLINK 基本稳定；单 key adversarial workload 中，cache hit rate 下降后读回到 2–2.8 ms 的 storage latency，P99/P90/P50 分别在 80/200/400 write QPS 附近突增。这说明“低延迟强一致 cache”并不适合持续更新的单个 hot key（§9.4.2、图 12b–c）。
- **reshard 结果**：在 0.5% traffic churn 下，assignment 在少于 20 ms 内调整，CLINK 图中保持 100% availability 和约 4–8 μs 的低延迟；三个生产 service 的每分钟 load movement 通常少于 0.2%。这覆盖常规小幅 churn，不覆盖同时迁移大量 range、控制平面 partition 或 storage/cache 两层相关故障（§9.4.3、图 13a、图 14–15）。
- **多副本写代价**：读流量上升时 auto-sharder 可逐步增加到 5 个 replica；P90 write latency 从 1 个 replica 的约 6.5 ms 上升到 5 个的约 15 ms。作者为触发该实验人为调低 pod capacity，因为标准 16-core pod 要在单 key 超过 80 M QPS 才需要 5 副本，结果代表极端读热点而非普通 key（§9.5、图 13b–c）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| range fencing 能阻止 reshard 后的 delayed write | relevant guard 全序与唯一 token 的协议证明；TiDB commit path 实现 guard check（§5–§6） | 依赖 Assignment Consistency、连续 ownership 和所有 writer 遵守协议；没有系统化 fault injection | 中到强 |
| CLINK 可从 application memory 返回线性一致结果 | LSI-at-entry/serve 证明；三类 writer 分别被 guard、overlap tracking、lease check 排除（§6.4） | storage 本身的 transaction correctness 不由 CLINK 证明；多 key transaction 交互说明较少 | 强 |
| 读路径移除 storage coordination 能显著降低 tail latency | 三种 production trace 上 P90 0.5–4.2 μs，对 Storage 4.8–10.3 ms（图 12a） | 单一 TiDB/auto-sharder stack、单数据中心、cache hit 的 steady state | 强 |
| WriteGuard 对 storage 写路径开销很小 | 75% CPU 的 write-only test 中 throughput/latency 无可测退化（图 11b） | 只测 prototype 和一种负载；未报告置信区间、range-map 极端碎片或多 key transaction | 中 |
| 常规 reshard 不会破坏可用性 | 0.5% churn 中 100% availability；生产 churn 通常少于 0.2%/min（图 13a、图 14） | 没有 mass reshard、network partition、controller split-brain 或 simultaneous tablet failure | 中 |

## 批判性分析

### 论证链条

论文从一个具体执行序列证明“exclusive cache owner”仍然不够，再把正确性所需能力压缩为 range token check，随后分别证明 guard 顺序和 cache LSI。这个链条比只展示性能更有说服力。TiDB 实现也证明接口可以落地。较弱的一步是把单 key、单数据中心的协议证明外推成“通用强一致 cache 生态”：不同数据库的 transaction commit、tablet recovery 和 legacy write path 仍需逐一审计。

### 假设压力测试

最危险的假设是所有写入口都受控。只要 batch job、运维工具或旧 client 可以不带 guard 写同一 key，新的 cache owner 就可能读到以后会被改写的值。第二个压力点是 auto-sharder：assignment split-brain、过期 `IsStillAssigned` 或 lease implementation bug 会直接破坏 proof。第三个压力点是高写 hot key；论文自己的图 12c 已显示，80 write QPS 就足以先击穿 P99 cache latency，方案会正确但不再快。

### 实验可信度

评测使用 production cluster、三类真实 trace、显式基线、write stress、reshard 和 replica sensitivity，并报告负面边界，整体证据较强。可是 linearizability 主要靠 paper proof，不是由 Jepsen/Porcupine 一类 history checker 验证；没有注入 delayed packet、SetGuard timeout、owner crash、tablet migration 与 split 同时发生的交错。`100% availability` 也只来自 0.5% 的温和 churn，不能解释罕见相关故障。

### 系统性缺陷

WriteGuards 的接口简单，但 trusted computing base 横跨 auto-sharder、cache client、TiDB SQL layer、PD 和 TiKV。guard 是软状态使 crash handling 简单，却让每种 storage lifecycle event 都必须保证“清空只会拒绝写，绝不会恢复旧 token”。此外，merge 会保留不同子范围 guard，论文没有解决 interval metadata 长期膨胀；multi-key transaction 应在何时、以何种原子性检查多个 range guard也没有完整讨论。所谓 loosely coupled 主要是 storage 不理解 shard policy，并不等于 cache 与 storage correctness contract 很弱。

## 局限与后续工作

- 用 delayed-packet、GC stall、SetGuard timeout、owner crash、tablet split/merge/migration 和 controller partition 的组合故障注入，配合 linearizability checker 验证 history。
- 明确 multi-key transaction、range write、snapshot read 与 guard validation 的原子语义，并在冲突跨多个 tablet 时测试 partial failure。
- 给 interval map 增加可证明安全的合并和上界控制，测长期 split/merge 后的 metadata、lookup latency 与 recovery cost。
- 在 TiDB 之外实现至少一种不同架构的 store，验证 `SetGuard` contract 是否真能移植。
- 评估 cross-datacenter ownership transfer；论文只说明可能减少 WAN read，没有给出 partition 下 consistency/availability 设计。
- 为 legacy/bypass writer 加访问控制或强制 client capability，避免未带 guard 的写进入受保护 key range。

## 相关

- **同会议**：[[OSDI-2026]]
