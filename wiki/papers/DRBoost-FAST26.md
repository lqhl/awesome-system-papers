---
type: paper
name: DRBoost
full_title: "DRBoost: Boosting Degraded Read Performance in MSR-Coded Storage Clusters"
authors: [Xiao Niu, Guangyan Zhang, Zhiyue Li, Sijie Cai]
venue: FAST
year: 2026
tags: [erasure-coding, msr-codes, degraded-read, distributed-storage, ceph]
source_pdf: "[[fast2026-niu.pdf]]"
source_md: "[[fast2026-niu]]"
---

# DRBoost: Boosting Degraded Read Performance in MSR-Coded Storage Clusters (FAST 2026)

> **一句话总结**：通过 partial-chunk reconstruction + 双 reuse + reconstruction-friendly coding layout + fragmentation-free storage layout，把 MSR (Clay) codes 的 degraded read 延迟与放大率降低 **1-2 个数量级**（小对象最高 ×213 加速）。

## 问题

MSR 码（如 Clay）有最优 repair bandwidth，但其 vector code 结构强制 sub-packetization 指数增长（如 (20,16) Clay 需 α=1024），导致推荐 chunk 大小达 256 MB（HDD）/ 16 MB（SSD）。而生产 object store 中 90% 对象 < 10 MB，单对象远不够填满一个 chunk；现有 MSR 系统按 chunk 全量重构，degraded read 放大严重，延迟比 normal read 高最多两个数量级。已有方案如 Geometric Partitioning 牺牲 device 利用率与可扩展性，并未根治。

## 核心方法

把 object layout 拆为「coding layout」（对象→编码空间）和「storage layout」（对象→存储空间），互不耦合。三大技术：

- **Partial-chunk reconstruction with data reuse**：定义 sub-stripe（一层独立可纠错的 sub-chunk 集合）；引入 sub-stripe reuse（多丢失 sub-chunk 共享 helper data）和 request reuse（请求自身的 healthy 部分作为 helper）；轻量算法优先 sub-stripe reuse 再求 request reuse。
- **Reconstruction-friendly coding layout**：以 basic layout unit（一个 sub-stripe 内的 major sub-chunks）为基础，加 balanced layout unit（覆盖所有 data node）和 reuse-optimal layout unit（同 zt-1 索引）形成 tiered 结构，按 Algorithm 1 生成分配序列。
- **Fragmentation-free storage layout**：通过 deterministic mapping table 把 coding 空间的碎片化 sub-chunk 在存储空间连续放置；mapping table 在同 (n,k) 配置下全 stripe 共享（如 (20,16) 仅 128KB）。Normal read 直接走 storage 地址绕过 translation。

集成进 [[Ceph]]：扩展 Librados 支持 partial-stripe 读写，修改 EC backend 与 ECSubRead；用 ISA-L 做 MSR 编解码；写路径用 two-phase write 避免小 IO 放大。

## 关键结果

- Synthetic 工作负载下 degraded read 平均延迟下降 ×11.7-×213，放大率下降 ×16-×156.9
- 真实负载（Ali、IBM、FBPhoto、FBVideo）平均 degraded latency 降低 ×2.45-×89.2
- Normal read 不受损（storage layout 抵消 coding layout 的 ×1.25-×1.38 碎片化开销）
- 对比 RS / LRC：在大对象上 degraded latency 改善 ×1.62-×3.12（vs RS）、×1.52-×1.80（vs LRC）

## 相关

- **相关概念**：[[Erasure-Coding]]、[[MSR-Codes]]、[[Clay-Codes]]、[[LRC]]、[[Reed-Solomon]]、[[Degraded-Read]]
- **同类系统**：[[Ceph]]（集成对象）、[[HDFS]]、[[DAOS]]、Facebook F4
- **同会议**：[[FAST-2026]]
