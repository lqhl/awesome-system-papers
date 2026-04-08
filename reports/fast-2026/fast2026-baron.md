# McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale

**作者**：Benjamin Baron*, Aline Bousquet*, Eric Metens*, Swapnil Pimpale, Nick Puz, Marc de Saint Sauveur, Varsha Muzumdar, Vinay Ari (Apple)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/baron
**源文件**：[[fast2026-baron.pdf]]

---

## 一、背景

随着移动计算和互联网流媒体的普及，Apple 的用户基础和服务规模持续增长。iCloud、Apple TV、Apple Music、Apple Maps 等服务每天需要处理数十亿请求，存储的数据类型从小型元数据/缩略图（几十 KB）到大型视频文件（数 GB）不等。这要求底层存储系统具备：(1) 高效处理极端对象大小差异的能力；(2) 弹性扩展容量和吞吐量的能力；(3) 跨地理区域的高可用性和持久性保障。

大规模对象存储系统（如 Amazon S3、GCS、Azure Blob Storage）通常依赖数据复制（全量复制或纠删码）来保障可用性和持久性。少数公司采用跨区域地理复制以抵御数据中心级故障。如何在保持高可用性和持久性的同时降低存储成本（即降低复制因子），是大规模对象存储的核心挑战。

---

## 二、要解决的问题

McQueen 1.0 经过十年生产运行，暴露出三个关键瓶颈：

1. **存储成本过高**：McQueen 1.0 结合跨 stamp 全量复制和 (20,2,2) LRC，整体复制因子为 2.40。在 exabyte 规模下，这意味着巨大的硬件和运维成本。
2. **Store 生命周期管理复杂**：每个 store 的容量固定且隔离，客户端资源可能跨多个 store，导致需要管理多个 endpoint、凭证、配额。淘汰老旧 store 需要逐对象迁移，操作缓慢且容易出错。
3. **元数据系统无法全局扩展**：基于 Cassandra 的元数据系统存在热点问题、LIST 操作性能差、不支持操作谓词、缺乏跨 stamp 强一致性，严重阻碍了向统一全局存储系统的演进。

---

## 三、洞察与设计

**关键洞察**：在跨区域地理复制场景中，使用 bitwise XOR 对对象进行分段（segmentation）并将数据段和校验段分散到不同区域，可以在仅维持 1.50 的复制因子下实现单区域故障容忍——相比全量跨区域复制（RF=2.0）大幅降低成本，同时保留了与 LRC 结合后的多层容错能力。

### McQueen 1.0 基础架构

- **Stamp-based 架构**：一个 store 由两个地理分离的 stamp 组成（active-active），每个 stamp 是一个独立的数据中心级存储服务。
- **存储层**：对象存储在 container（4-32 GiB 大文件）中，container 组成 cluster。新写入时 cluster 为 5 副本（replicated），写满后执行 sealing 过程，删除副本并生成 LRC 校验 container（sealed）。
- **Intra-stamp 复制**：使用 (12,2,2) 后升级为 (20,2,2) LRC，12/20 个数据 container + 2 local parity + 2 global parity。
- **Inter-stamp 复制**：异步全量对象复制，RF=2.0。

### McQueen 2.0 核心设计

1. **Cross-Region Segmentation（XOR-5）**：将每个对象切分为 4 个等大数据段 + 1 个 XOR 校验段，分布到 5 个区域。任意 4 段可重建完整对象。整体 RF = 1.2 (LRC) × 1.25 (XOR-5) = 1.50。
2. **统一 endpoint**：单一 DNS 入口点，通过 DNS geo-routing 将请求路由到最近区域的 load balancer，消除客户端管理多 store 的负担。
3. **弹性扩展**：每个区域可包含多个 stamp，通过 stamp weight 和 rebalancer service 动态平衡数据和负载，支持透明地添加/移除 stamp。
4. **ClassVI 元数据系统**：替代 Cassandra，基于 RocksDB 的自研分布式 key-value store，使用 Raft 实现跨区域强一致性，同时支持本地副本的快速 inconsistent read。

---

## 四、实现细节

### PUT 流程
- Client handler 接收请求后，将对象切分为 4 个数据段 + 1 个 XOR 校验段，并行发送到 5 个区域的 segment handler。
- 至少 4/5 段成功存储即视为 PUT 成功；第 5 段以 best-effort 方式异步补充。
- Multipart 对象的每个 part 独立分段处理。

### GET 流程
- Client handler 从 ClassVI 获取元数据（含段位置信息），选择网络延迟最小的 4 个段获取。
- 优先使用 inconsistent read 预取元数据 + 数据，再与 consistent read 结果比对（仅 0.001% 不一致）。
- 段不可用时通过 XOR 重建（计算开销仅 p90 0.3ms）。

### 容错机制
- **Intra-stamp**：(20,2,2) LRC 容忍每个 cluster 最多 4 个 container 故障（86.15% 概率）或 3 个故障。
- **Inter-region**：XOR-5 容忍单区域故障（degraded 模式），两个及以上区域故障则不可用。
- 异步复制进程持续扫描，仅在约 0.01% 对象上需要异步补充段。

### 延迟优化
- **DNS geo-routing**：请求路由到最近数据中心。
- **Metadata prefetch**：inconsistent read + consistent read 并行，prefetch 数据。
- **Segment regional preference**：选择延迟最低的 4 个段（通常避免跨大陆传输，虽需 XOR 重建但 CPU 开销远小于网络延迟）。
- **Load balancer bypass**：stamp 间通信绕过 load balancer，p50/p90/p95 延迟分别降低 22%/32%/26%。

### 迁移
五阶段迁移：客户端配置迁移 → 异步对象迁移 → 校验完整性 → 请求代理 → DNS 切换。数 exabyte 数据在数年内完成迁移，全程零停机。

---

## 五、实验结果

实验基于一个月的生产流量数据。

| 指标 | McQueen 1.0 | McQueen 2.0 |
|------|-------------|-------------|
| 整体复制因子 | 2.40 | 1.50 |
| GET TTFB | 基线 | 略高（需获取远程段） |
| GET 全对象延迟（vs 1.0） | 基线 | +50ms（跨区域网络延迟） |
| PUT 延迟 | 基线 | 相近（并行段写入） |
| 异步复制延迟 | 90% < 10s | 数量级更小（仅 0.01% 对象需要） |
| 段重建计算开销 | N/A | p90 0.3ms |
| LRC degraded read 开销 | N/A | p90 2ms |

**可用性与持久性对比（Table 3 精选）**：

| 配置 | Local MTTDL (年) | Regional MTTDL (年) | Degraded 时间/年 (s) | Unavailable 时间/年 (s) | RF |
|------|------------------|---------------------|----------------------|------------------------|----|
| (12,2,2) + 1.0 | 4.96×10¹⁰ | 4.51×10²³ | 631.15 | 0.0032 | 2.67 |
| (20,2,2) + 1.0 | 8.49×10⁹ | 1.32×10²² | 631.15 | 0.0032 | 2.40 |
| (20,2,2) + XOR-5 | 8.49×10⁹ | 1.31×10²¹ | 1577.82 | 0.0316 | 1.50 |

**Stamp failover 对 GET 延迟影响**：无重建 < 段重建（+10ms）< stamp failover 下重建（p60 以上 +50ms）。

---

## 六、批判性分析

1. **可用性降级被低估**：从 McQueen 1.0 到 2.0，unavailable 时间从 0.0032s/年增加到 0.0316s/年（增加约 10 倍），degraded 时间从 631s 增加到 1578s（增加 2.5 倍）。论文将此呈现为可接受的 tradeoff，但对于 Apple 级别的用户规模（数亿用户），即使短暂的不可用也可能影响大量用户。论文缺乏对实际用户影响的分析。

2. **故障独立性假设过于理想**：Markov 模型假设区域故障是独立事件，但现实中存在相关故障（如网络分区、软件 bug 同时影响多区域、供应链问题）。论文未讨论相关故障对模型准确性的影响。

3. **GET 延迟回退缺乏深入分析**：McQueen 2.0 的 GET 延迟比 1.0 增加约 50ms，论文将其归因于"跨区域网络延迟"，但未给出不同区域组合的延迟分布、长尾延迟的根因分析，也未讨论对延迟敏感型工作负载（如实时视频转码）的具体影响。

4. **成本节省缺乏量化**：论文反复强调 RF 从 2.40 降至 1.50 带来了成本优势，但从未给出具体的成本数字或百分比。考虑到 McQueen 2.0 需要 5 个区域（vs 1.0 的 2 个区域），数据中心基础设施成本、跨区域网络带宽成本、更复杂的运维成本等都是显著的隐性成本。单纯比较 RF 可能高估了实际节省。

5. **ClassVI 元数据系统缺乏独立评估**：作为系统的核心变更之一，ClassVI 仅被简要描述为"类似 BigTable"，没有独立的性能评测、与 Cassandra 的对比、容量上限分析。考虑到元数据系统是 McQueen 1.0 的主要痛点之一，这一缺失令人遗憾。

6. **实验缺乏压力测试和故障注入**：所有结果来自正常生产流量，未报告系统在极端条件下（多区域故障、流量突增、大规模 compaction 同时进行）的行为。

---

## 七、总结

McQueen 是 Apple 自研的 exabyte 级跨地理区域对象存储系统，历经十余年生产验证。其核心演进是从 1.0 的双 stamp 全量复制（RF=2.40）升级到 2.0 的五区域 XOR 分段 + LRC 编码（RF=1.50），在保持"11 nines"持久性 SLA 的前提下大幅降低存储成本。系统通过统一 endpoint、弹性扩展、ClassVI 强一致元数据等设计解决了 1.0 的管理复杂性和扩展瓶颈。主要局限在于 GET 延迟增加约 50ms、可用性略有下降，且论文对成本节省和元数据系统缺乏定量分析。
