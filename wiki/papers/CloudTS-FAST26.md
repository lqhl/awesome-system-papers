---
type: paper
name: CloudTS
full_title: "An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems"
authors: [Kai Zhang, Tianyu Wang, Zili Shao]
venue: FAST
year: 2026
tags: [time-series, cloud-storage, metadata, object-storage, monitoring]
source_pdf: "[[fast2026-zhang-kai.pdf]]"
source_md: "[[fast2026-zhang-kai]]"
---

# An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems (FAST 2026)

> **一句话总结**：CloudTS 把监控类时序系统的 metadata 与数据解耦放进 [[S3]]，用 Patricia-trie 全局 tag 字典 + 二维 bitmap (TTMapping) 解决 tag 冗余（实测 70%+ tag 跨 partition 重复），相比工业界广泛使用的 Cortex 平均提速 **1.37×**（生产环境 1.43×），并显著优于 Apache Parquet 与 JSON Time Series。

## 问题

[[Prometheus]]/Cortex/[[InfluxDB]]/TimescaleDB 等监控时序系统正在迁云，[[ByteDance]] 等大厂每天处理百亿级 timeseries（容器/微服务诞生消亡产生大量短命 series）。把本地 time-partitioned 数据块直接搬上 [[S3]] 引入两类问题：(1) **读放大**：Cortex 这类把整个 block 文件转成 object，即使只取一小段也得拉整块；Apache Parquet 列式存储独立处理每列，定点访问某 timeseries 的某段时间也得读冗余行；JTS（JSON Time Series）每个 series 一个 object，tag-based query 需要扫所有 object，扩展性差。(2) **元数据冗余**：tag 占总 metadata 80%+，约 73% 重复（region/cluster 等通用 tag 90%+ series 共用），每个时间分区独立存一遍极度浪费。云存储的高延迟更放大这些问题，让 query 性能远低于本地。

## 核心方法

CloudTS 把 metadata 与 data 分离，分别放进 metadata object 和 TSObject，由 CloudWriter 上传、CloudQuerier 查询。

**TagDict（§3.2）**：全局 Patricia trie-like 字典，把所有 tag pair（如 `node="node01"`）建成共享前缀树，叶子分配全局唯一 encoding。**双向 lookup**（tag pair ↔ encoding）通过反向指针避免重复 trie 遍历。每个 time partition 维护一份只含本分区出现 tag 的 **time-partition tag array**（按频率排序），减少 search space。

**TTMapping（§3.3）**：每个 time partition 一个二维 bitmap，行 = timeseries ID，列 = tag 列。set bit 表示该 series 含该 tag。给定 series 查 tag 走行扫描，给定 tag 查 series 走列扫描，bidirectional index 一表搞定。**TMMC 压缩**：bitmap 极稀疏（实测 0.7% set bit），改造 [[CSR]] 格式只保留 `ind` 和 `ptr` 数组，把空间复杂度从 $O(M \times N)$ 降到 $O(M+N)$。

**Timeseries Group**：基于 tag 频率分布把 series 分组，让 TTMapping 拆成多个小子矩阵，互斥的 tag set 形成对角块结构，并发查询时多组并行访问。

**TSObject（§3.4）**：每个 time partition + 每个 series group 一个 cloud object，内部按 series ID 和时间排序的 compressed chunk 排列。区别于 Parquet rowgroup 单纯切分，TSObject 还根据 tag similarity 把相关 series 聚到一起，连续读减少读放大并榨取云对象存储带宽。

## 关键结果

- 真实生产环境 full-system evaluation 比 Cortex 平均加速 **1.43×**；TSBS benchmark 上跨 query pattern 平均 **1.37×**。
- 显著优于 Apache Parquet 和 JTS。
- 元数据空间从 $O(M \times N)$ 降到 $O(M+N)$，对百万级 series 量级特别明显。
- 数据集分析显示 70%+ tag 跨多 series 重复、region/cluster 类 tag 90%+ 共用——验证了优化动机。

## 相关

- **相关概念**：[[Time-Series]]、[[Object-Storage]]、[[Inverted-Index]]、[[Patricia-Trie]]、[[CSR]]
- **同类系统**：[[Prometheus]]、Cortex、[[InfluxDB]]、TimescaleDB、ModelarDB、Apache Parquet、JTS
- **同会议**：[[FAST-2026]]
