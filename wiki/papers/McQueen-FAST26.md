---
type: paper
name: McQueen
full_title: "McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale"
authors: [Benjamin Baron, Aline Bousquet, Eric Metens, Swapnil Pimpale, Nick Puz, et al.]
venue: FAST
year: 2026
tags: [object-store, geo-replication, erasure-coding, production, apple]
source_pdf: "[[fast2026-baron.pdf]]"
source_md: "[[fast2026-baron]]"
---

# McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale (FAST 2026)

> **一句话总结**：Apple 自研的 geo-distributed 对象存储，已生产部署 10+ 年、存 EB 级数据、日处理数十亿请求；2.0 版用「intra-region (20,2,2) LRC + cross-region 5-way XOR 校验」把 replication factor 从 2.40 压到 1.50。

## 问题

iCloud、Apple TV、Apple Music、Apple Maps 等服务对底层 object store 有三个硬性需求：(1) 对象大小从 KB 缩略图到 GB 级视频跨 5+ 个量级；(2) 用户和数据规模持续增长，必须可扩展；(3) 高可用 + 高耐久。

McQueen 1.0（2013 年部署）解决了这些需求但有三大瓶颈：

- **存储成本高**：(20,2,2) LRC + 跨 stamp 全量复制 → replication factor 2.40
- **Store lifecycle 复杂**：每个 store 容量固定且隔离，客户端要管理多个 endpoint/credential/quota；下线老 store 要逐对象迁移
- **Metadata 全局可扩展性差**：基于 Cassandra 的元数据有热点、LIST 性能差、缺乏跨 stamp 强一致

## 核心方法

**McQueen 1.0** 架构：每个 store = 两个跨地域 stamp（active-active），stamp 内 storage layer 用 [[Local-Reconstruction-Codes|LRC]] (12,2,2) 后升 (20,2,2)，跨 stamp 异步全量复制。对象按 256 KiB chunk stream 到 5-replica container（基于 ZAB 风格 transaction log + Raft 选主），写满后 sealing 算 parity，老 container immutable。Coordinator 负责 placement（按 disk/host/rack failure domain 隔离）、compaction、repair。

**McQueen 2.0** 关键改进：
- **Cross-region segmentation**：每个对象切成 4 个等大 data segment + 1 个 bitwise XOR parity segment，分布到 5 个 region。任一 region 故障可用 XOR 重建，replication factor 从 2.40 → **1.50**。
- **ClassVI**：自研 BigTable-like 元数据系统，[[RocksDB]] 本地引擎 + Raft 强一致；read 默认本 region 单副本读以降延迟，trade off 是 eventual consistency。
- **Unified endpoint**：单一 DNS 名按 region 解析最近 load balancer，client 不再感知多 store。Rebalancer 按 stamp 容量权重 + 文件级 sealed container copy 跨 stamp 平衡负载。
- **两层 rate limiter**：deployment-level（segmentation 前）+ stamp-level（segmentation 后）。

## 关键结果

- 生产数据：存储多个 EB、日处理 billions 请求，覆盖 5 个 region、每 stamp 约 500 PiB raw 容量
- Replication factor：2.40 → 1.50（XOR-5 替代 2x cross-region replication）
- McQueen 2.0 GET TTFB 仅比 1.0 高一点（异地 segment fetch），PUT latency 持平
- 99.99995% 的 GET metadata 走 inconsistent local read，零额外延迟
- 跨 region segment 重建 p90 计算开销 0.3 ms；intra-stamp LRC 重建 p90 2 ms，>p50 时 degraded read 增加 30 ms-数百 ms

## 相关

- **相关概念**：[[Erasure-Coding]]、[[Local-Reconstruction-Codes]]、[[Geo-Replication]]、[[Raft]]、[[XOR-Parity]]
- **同类系统**：[[S3]]、Azure Storage、Google Colossus、[[Ceph]]、Facebook f4
- **同会议**：[[FAST-2026]]
