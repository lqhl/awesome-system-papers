---
type: paper
name: Tiga
full_title: "Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks"
authors: [Jinkun Geng, Shuai Mu, Anirudh Sivaraman, Balaji Prabhakar]
venue: SOSP
year: 2025
tags: [distributed-transactions, geo-replication, clock-sync, consensus, oltp]
source_pdf: "[[3731569.3764854.pdf]]"
source_md: "[[3731569.3764854]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Tiga：使用同步时钟加速地理分布式事务（SOSP 2025）

> **原题**：Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks

> **一句话总结**：合并 concurrency control 与 consensus，用同步时钟 proactive ordering，多数事务 **1 WRTT** 提交，MicroBench/TPC-C 吞吐 **1.3–7.2×**、中位延迟 **1.4–4.6×** 优于 Tapir/Janus/Calvin+。

## 问题与动机

Geo-replicated OLTP 需 strict serializability + fault tolerance，传统「2PL/OCC + Multi-Paxos」叠层导致多 WRTT。Consolidated 协议（Tapir、Janus）乐观按 arrival order 处理，跨区到达顺序不一致时 fast path 失败（Fig. 1 cyclic dependency）。

现代时钟同步（Huygens、chrony）可达 μs–ms 精度，为 proactive timestamp ordering 创造机会，但 Liskov 原则要求「performance 依赖时钟、correctness 不依赖」。

## 关键观察 / 隐含假设

- **观察 1**：跨区 OWD 可测，coordinator 分配 future timestamp（含 headroom），servers hold 至本地时钟越过 timestamp 再处理，可 rectified 到达顺序不一致。
  - **依赖假设**：时钟 skew << WRTT headroom（10s ms 级）；消息延迟多数情况下 < headroom。
  - **可能失效场景**：丢包重传、partition 导致迟到；时钟漂移超 headroom。
  - **证据强度**：强——GCP chrony <5ms error 下高性能。
- **观察 2**：timestamp ordering 单独只保证 serializability，非 strict serializability；需 cross-shard leader 协调避免 timestamp inversion。
  - **依赖假设**：per-shard leader 协调开销在 full replication co-located 时可忽略（LAN）。
  - **可能失效场景**：partial replication 下 leader 跨 WAN，blocking 增加 0.5 WRTT。
  - **证据强度**：强——TLA+ 证明 + technical report。
- **假设 1**：物理时钟 inaccuracy 时 slow path（1.5–2 WRTT）覆盖全部 correctness corner cases。
  - **证据强度**：中——形式化证明，生产长尾时钟故障数据少。

## 核心方法

**Tiga**：consolidated protocol。

1. Proactive ordering：multicast 时赋 future timestamp
2. Servers 按 timestamp serialize；迟到走 slow path
3. Per-shard leader 就 timestamp 达成一致，防 inversion
4. Full replication + leader co-location → 多数 **1 WRTT**

## 设计取舍

- **取舍 1**：依赖时钟同步基础设施，部署在弱时钟环境性能退化但不错误。
- **取舍 2**：合并层使协议复杂，工程与验证成本高（TLA+ 缓解）。
- **边界条件**：OLTP key-value + stored procedure one-shot tx；interactive tx 需 decomposition 扩展。

## 实验与结果

- MicroBench（低 contention）：吞吐 **1.3–7.2×**，中位延迟 **1.4–4.6×** vs 2PL+Paxos、Tapir、Janus、Calvin+、Detock、NCC
- TPC-C：**1.6–3.5×** 吞吐、**1.5–3.7×** 延迟 vs 剩余强 baseline
- 时钟：GCP chrony **4.54ms** error 已足够

## 批判性分析

### 论证链条

「arrival order 不一致 → fast path 失败」是 Tapir/Janus 清晰痛点；proactive ordering 用成熟时钟技术回应，逻辑优雅。形式化证明支撑 correctness claim。

### 假设压力测试

- Partial replication + 高冲突 workload slow path 比例？
- Banking/booking 类 strict serializability 需求下 slow path 延迟 SLA？
- 与 Spanner TrueTime 比较：Spanner 也用时钟但 2PC 结构不同，head-to-head 缺。

### 实验可信度

GCP 真实部署 benchmark 可信。Skew sensitivity 有扫。缺大规模 production trace driven workload。

### 系统性缺陷

论文未讨论：clock 被恶意操纵的 security；跨 cloud 时钟同步质量参差；客户端 clock 不信任模型。

## 局限与后续工作

- **局限 1**：partial replication 高冲突时 graceful degradation 量化不足。
- **局限 2**：协议实现复杂度高。
- **Future work 1**：自适应 headroom，按 live OWD 分布在线调节。

## 相关

- **相关概念**：strict serializability、consensus、clock synchronization、geo-replication
- **同类系统**：Google Spanner、Tapir、Janus、Calvin
- **同会议**：[[SOSP-2025]]
