---
type: paper
name: Loom
full_title: "Loom: Efficient Capture and Querying of High-Frequency Telemetry"
authors: [Franco Solleza, Shihang Li, William Sun, Richard Tang, Malte Schwarzkopf, et al.]
venue: SOSP
year: 2025
tags: [observability, telemetry, log-storage, indexing, ebpf]
source_pdf: "[[3731569.3764853.pdf]]"
source_md: "[[3731569.3764853]]"
---

# Loom: Efficient Capture and Querying of High-Frequency Telemetry (SOSP 2025)

> **一句话总结**:把 log-based 存储与"按 chunk 稀疏索引"结合,支持 9M records/s 的高频遥测(如 [[eBPF]]、perf、DTrace)无丢数 ingest,同时查询比 InfluxDB 快 7-160×,比 FishStore 快 1.5-17×。

## 问题

性能调试依赖高频遥测(HFT):应用日志、eBPF 事件、perf counter 每秒可产生数百万条记录。现有方案处于三选二困境:
- TSDB(InfluxDB、ClickHouse)查询快,但写路径维护索引消耗大量 CPU,1.4M writes/s 时丢 9%,6M writes/s 时丢 77%。
- Log-based 存储(FasterLog、FuzzyLog、FishStore)能扛 ingest,但查询需扫整日志或依赖 PSF 预定义(无法支持任意时间范围或分布相关查询)。
- 写裸文件 + post-process 脚本:慢、手写 50 行代码、难交互迭代。

## 核心方法

**Key insight**:观察性查询多是参数化的时间范围、aggregation、correlation,无需 record 级精确索引,chunk 级稀疏索引就够——用 zone-map 式的 block summary 过滤无关数据,只扫少量相关 chunk。

- **Hybrid log**:跨内存与持久存储的 append-only log;ingest 路径 CPU/内存占用固定,probe effect 极低。
- **Sparse indexes**:固定大小 chunk(几 MB)内建立时间、source、distributive/holistic aggregation 的轻量索引,layered/multi-layer 追加式构造,不对外暴露构造中的 index 部分 → ingest 与 query 无锁同步。
- **查询执行**:先用 index 过滤出候选 chunk,再 scan。实测只需扫几 MB 未索引内存数据。

## 关键结果

- Ingest 率最高 9M records/s 无丢数,与裸文件写入相当的 probe effect。
- 相比 InfluxDB(丢 38-93% 数据):Loom 不丢数,查询快 7-160×。
- 相比 FishStore(log-based 专用 ingest):ingest 更高,查询快 1.5-17×。
- 动机例:Redis 尾延迟 + eBPF syscall + packet trace 的跨源 correlation,揭示 35M 包中 6 个 mangled packet 与 9M 请求中 6 个慢请求的精确关联(采样 10% 只抓到 1 条慢请求、0 mangled)。

## 相关

- **相关概念**:[[eBPF]]、zone map、time series database、log-structured storage
- **同类系统**:InfluxDB、ClickHouse、FishStore、FasterLog、FuzzyLog
- **同会议**:[[SOSP-2025]]
