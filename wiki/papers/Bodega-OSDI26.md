---
type: paper
name: Bodega
full_title: "Bodega: Localized Linearizable Reads at Anywhere Anytime via Roster Leases"
authors: [Guanzhou Hu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: OSDI
year: 2026
tags: [consensus, linearizability, leases, geo-replication, key-value-store]
source_pdf: "[[osdi26-hu-guanzhou.pdf]]"
source_md: "[[osdi26-hu-guanzhou]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 随时随地提供本地 Linearizable Read（OSDI 2026）

> **原题**：Bodega: Localized Linearizable Reads at Anywhere Anytime via Roster Leases

> **一句话总结**：Leader Lease 只能在 leader 本地读、Quorum Lease 遇到 write 会退化；Bodega 用 roster 记录任意 key 的 responder subset，并以 all-to-all roster lease 保证 replica-local state 新鲜，在 WAN moderate-write workload 中把平均 read latency 相对既有协议改善 5.6–13.1×，同时维持接近 Paxos 的 write path。

## 问题与动机

geo-replicated consensus 为容灾把 replica 分散到多个 region，read-majority workload 却常被迫访问远端 leader/quorum。Follower read 很快但通常只能 sequential/eventual consistent；linearizable client 必须确认本地 state 未落后于并发 write。

Leader Lease 把该确认集中到 leader，非 leader client 仍远程；Quorum Lease 可让更多 node 本地读，但 write interference 会迫使 lease holder 等待/验证，低比例 write 也破坏 locality。Bodega 寻找 design point：任何指定 node 可长期本地 linearizable read，write 不要求静止期。

## 关键观察 / 隐含假设

- **观察 1**：leadership 本质是“谁可对哪些操作响应”的 metadata；local read 不必把完整 leader 职责迁移，只需对 key 的 responder assignment 达成一致（§1、§3）。
  - **依赖假设**：key space 与 client locality 足够稳定，可维护紧凑 roster coverage。
  - **可能失效场景**：极高 key churn、scan/transaction 跨大量 key，或 client location 完全随机。
- **观察 2**：传统 lease 是 all-to-one grant；把 grant generalized 为 all-to-all roster lease，可让 write quorum 覆盖所有 responder 并维持 local freshness（§3–4）。
  - **依赖假设**：clock/lease expiration 的标准 bound 成立，write 使用 responder-covering quorum。
  - **可能失效场景**：长 partition/clock fault、responder 数太多使每次 write fan-out 成本过高。
- **假设 1**：read-heavy workload 愿意用更高 write latency 换 region-local read，且 read/write key preference 可用于 smart coverage。
  - **证据强度**：中强。YCSB/write-ratio sweep 支撑，transactional workload 未覆盖。
- **假设 2**：failure 后等待 lease expiration 的 availability gap 可接受。
  - **证据强度**：中。failure experiment 有量化，但 WAN/production clock anomaly 更复杂。

## 核心方法

roster 是复制状态机内的一致 metadata，把每个 key/range 映射到允许直接回答 read 的 responder node 集合。它 generalize single leader：leader 仍驱动 write ordering，但任意 region replica 可因 roster 身份提供本地 read。

roster lease 由参与 node 相互授予，grantor 保证 lease 有效期间不会完成绕过相应 responder 的 conflicting write；responder 在自己的较早 expiration 前可确信 local value 已覆盖所有完成 write。write quorum 必须覆盖 roster responder，因而 local read 不需再联系 leader/quorum。

optimistic holding 在 write 到来时尽量保留 responder lease，early accept notification 提前告知 responder write decision，缩短 interference window。smart roster coverage 只给热点/有地域偏好的 key 增加 responder，避免所有 write 永久 fan-out 到所有 region；lightweight heartbeat renew lease。roster change 本身走 consensus，两 message round 可 proactive 调整。

## 设计取舍

- **read locality 换 write fan-out**：responder 越多、key coverage 越广，本地 read 越多，write quorum/latency 越高。
- **lease 换故障恢复等待**：common case 无 read RTT，partition/failure 时必须等 expiration 以保持 linearizability。
- **key-level roster 换 metadata/control complexity**：能适配地域热点，需监测 preference、版本化 roster 并避免 churn。
- **non-intrusive Paxos extension**：write 只需 responder-covering quorum，便于采用；transaction/multi-key semantics 不在主要范围。

## 实验与结果

- Summerset async-Rust KV store 实现 Bodega、Leader/Quorum Leases、EPaxos、PQR，并对比 etcd/ZooKeeper；CloudLab 两个 WAN site、五个 client location，使用 YCSB 与 write-ratio sweep（§6）。
- moderate write interference 下，Bodega 平均 client read latency 相对 prior linearizable protocol 改善 5.6–13.1×（摘要、§6.1、图 9）。
- throughput–latency curve 中 Bodega 因多数 read local，在相近 load 下 latency 比 Quorum Lease 好约 1.5×，throughput upper bound 约 3.4k ops/s（§6.1、图 10）。
- failure experiment 中，传统 lease expiration 可导致约 3 s zero throughput；Bodega proactive roster change 的模拟 gap 约 100 ms，并获得相对 Leader Lease 2.2× throughput（§6.4）。
- YCSB 中 Bodega 接近 sequential-consistent etcd/ZooKeeper；后两者在 read-heavy case 约 0.3 ms 与 10×以上 normalized throughput，但不提供同等 linearizability baseline（§6.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Bodega 在 write 存在时仍可 region-local linearizable read | §3–5 protocol invariant 与 lease proof | non-transactional command、bounded lease assumptions | 强 |
| WAN read latency 显著优于既有 linearizable protocol | §6.1、图 9：平均改善 5.6–13.1× | CloudLab WAN、moderate write、YCSB-like workload | 强 |
| read locality 没有摧毁 write performance | §6.1/6.3：write performance on-par、ratio sweep | smart roster coverage、所选 responder | 中 |
| proactive roster change 缩短 failure gap | §6.4：约 3 s vs 100 ms、2.2× throughput | simulated failure probability/lease timing | 中 |

## 批判性分析

### 论证链条

论文从 leader/quorum lease 的 responder 限制抽象出 roster，all-to-all lease 与 responder-covering write quorum直接支撑 local read correctness，机制清晰。评测也展示 read/write frontier，而非只给 read speedup。相对 sequential etcd/ZooKeeper 的接近性能是补充，不能当一致语义下 baseline。

### 假设压力测试

若每个 region 都想对所有 key 本地读，roster 退化为 write 必达所有 replica，availability 和 write latency 恶化；smart coverage 的价值取决于 key/location skew。clock drift、[[Garbage-Collection|GC]] pause 和 asymmetric partition 会延长 conservative lease，故障期间 proactive change 仍必须证明旧 lease 已安全失效。跨 key transaction 还需统一 snapshot，单 key roster 不足。

### 实验可信度

baseline 广、WAN/YCSB/write ratio/failure/roster sensitivity 均覆盖，protocol code 公开，证据较强。CloudLab 规模小于 production geo database，未报告 large roster/key metadata memory、clock skew injection、multi-leader reconfiguration storm 和 long-duration tail。5.6–13.1×主要来自消除 WAN RTT，region topology 变化会直接改变倍数。

### 系统性缺陷

roster control plane 需安全地根据 access distribution 调整，频繁变化会增加 log entry、lease traffic 与 cache invalidation。错误 assignment 或 stale metadata 可能影响 linearizability，observability/audit 很重要。lease-based protocol 还需处理 process pause、suspend/resume 与 time source，论文主要在受控环境评测。

## 局限与后续工作

- **局限 1**：主要针对 non-transactional single-key operation，multi-key snapshot 未解决。
- **局限 2**：local read 与 write fan-out 的成本随 roster coverage 增长。
- **局限 3**：CloudLab 规模与 clock/failure model 不足以代表 production extremes。
- **后续工作 1**：在 Zipf skew/location churn 下在线优化 roster，报告 metadata、write amplification 与 P99 read 的 Pareto frontier。
- **后续工作 2**：注入 clock drift、STW pause、asymmetric partition 与 concurrent roster change，model-check linearizability 并测 availability gap。
- **后续工作 3**：扩展 transaction read timestamp/roster semantics，用 Jepsen history 验证 multi-key linearizable snapshot。

## 相关

- **相关概念**：[[Linearizability]]、[[Lease]]、[[Paxos]]、[[Geo-Replication]]
- **同类系统**：[[EPaxos]]、[[etcd]]、[[ZooKeeper]]、[[PQR]]
- **同会议**：[[OSDI-2026]]
