---
type: paper
name: Loom
full_title: "Loom: Efficient Capture and Querying of High-Frequency Telemetry"
authors: [Franco Solleza, Shihang Li, William Sun, Richard Tang, Malte Schwarzkopf, Andrew Crotty, David Cohen, Nesime Tatbul, Stan Zdonik]
venue: SOSP
year: 2025
tags: [observability, telemetry, log-storage, indexing, ebpf]
source_pdf: "[[3731569.3764853.pdf]]"
source_md: "[[3731569.3764853]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# Loom: Efficient Capture and Querying of High-Frequency Telemetry (SOSP 2025)

> **一句话总结**：hybrid log + chunk 级稀疏索引，**9M records/s** 无丢数 ingest，查询比 InfluxDB 快 **7–160×**、比 FishStore 快 **1.5–17×**，probe effect 接近写裸文件。

## 问题与动机

高频遥测（[[eBPF]]、perf、DTrace）可达 **数百万 records/s**。三难：TSDB 写路径索引重→丢数/高 probe；log storage 无索引→查询慢；裸文件→脚本 post-process 慢。工程师查 outlier 需 complete capture + interactive query + low probe effect 三者兼得。

## 关键观察 / 隐含假设

- **观察 1**：HFT 查询多为时间范围、aggregation、跨 source correlation，chunk 级 zone-map 式稀疏索引足够，无需 record-dense 索引。
  - **依赖假设**：chunk 内 scan 成本可接受（几 MB unindexed tail）。
  - **可能失效场景**：点查极高选择性、需单 record 精确定位且延迟极严。
  - **证据强度**：强——多类 observability query 实验。
- **观察 2**：ingest 与 query 不共享可变索引结构——未完成索引对 query 不可见，避免同步。
  - **依赖假设**：扫描几 MB 未索引内存 tail 延迟可接受。
  - **可能失效场景**：极高 query 并发 + 极高 ingest 时 tail 变大。
  - **证据强度**：中——设计合理，tail 大小 bound 未长期验证。
- **假设 1**：固定小内存 footprint + 无协调多线程可使 probe effect 与 raw file 相当。
  - **证据强度**：强——与 raw file 对比实验。

## 核心方法

**Hybrid log**（内存+持久）append ingest。

**多层稀疏索引**：time、source、aggregation（distributive/holistic）over fixed-size chunks。

Query 扫相关 chunk；ingest 异步构建索引层。

## 设计取舍

- **取舍 1**：inexact chunk 索引换 ingest 吞吐，查询需扫 chunk 内部。
- **取舍 2**：专用 observability 算子，非通用 SQL。
- **边界条件**：单机 host telemetry；非跨 region 集中式 log analytics 首选。

## 实验与结果

**指标与基线**：在 Redis/RocksDB case study 中，以 record drop、query latency 和应用吞吐下降衡量；对比 FishStore、InfluxDB，以及仅用于查询的预加载 InfluxDB-idealized（§6）。

- Ingest：**9M records/s** 无丢数
- vs InfluxDB：丢 **38–93%** 数据，查询慢 **7–160×**
- vs FishStore：ingest 更高，查询快 **1.5–17×**
- Probe effect ≈ raw file；资源占用低于 TSDB

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Loom completes high-frequency capture in the case studies | 0% dropped for Loom/FishStore; InfluxDB drops 38.2–90.1% Redis and 87.9–92.8% RocksDB (§6.1, Fig.10–11) | continuous ingest with concurrent queries | high |
| Sparse indexes accelerate Redis correlation queries | against InfluxDB-idealized 14–97× and FishStore 1.5–10× in P1/P2 (§6.1, Fig.12) | case-study workloads; not uniform across all queries | high |
| Hierarchical index supports RocksDB aggregations | 0.5–3.2s; 7–160× vs InfluxDB-idealized and 8–17× vs FishStore (§6.1, Fig.13) | P2 aggregates only 3% data | high |
| Probe effect approaches raw-file capture | 4.83%/4.74M ops/s vs raw file 4.10%/4.87M (§6.2, Fig.14) | RocksDB phase 3, no concurrent query | high |
| Combined indexes help long lookback queries | 120s window under 5s vs timestamp-only 150–160s (§6.4, Fig.16–17) | high-latency syscall query | high |

## Critical Analysis

### 论证链条

三难 tradeoff 图（Fig. 1）清晰，Loom 定位「log ingest + enough index」准确。与 zone map/TSDB 思想有渊源但 co-design 针对 HFT。

### 假设压力测试

- 分布式 multi-host 关联查询未覆盖。
- Chunk 大小选择对 skewed query 的影响？
- 长期运行磁盘空间 vs FishStore 压缩策略。

### 实验可信度

两真实 workload，对比 InfluxDB/FishStore/raw file 三角可信。9M/s 是峰值，持续负载下 CPU 曲线未详。

### 系统性缺陷

论文未讨论：多租户隔离；敏感 telemetry 加密；与 OpenTelemetry 标准 schema 演进兼容。

## 局限与 Future Work

- **局限 1**：单机 focus，跨机 correlation 需上层系统。
- **局限 2**：点查极致延迟非目标。
- **Future work 1**：adaptive chunk size，按 query 历史调节索引粒度。

## 相关

- **相关概念**：observability、[[eBPF]]、telemetry、log-structured storage
- **同类系统**：InfluxDB、FishStore、ClickHouse
- **同会议**：[[SOSP-2025]]
