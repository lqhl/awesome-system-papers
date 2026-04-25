---
type: paper
name: DMTree
full_title: "DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design"
authors: [Guoli Wei, Yongkun Li, Haoze Song, Tao Li, Lulu Yao, et al.]
venue: FAST
year: 2026
tags: [disaggregated-memory, range-index, rdma, tree-index, fingerprint]
source_pdf: "[[fast2026-wei.pdf]]"
source_md: "[[fast2026-wei]]"
---

# DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design (FAST 2026)

> **一句话总结**：在 [[Disaggregation|disaggregated memory]] 上，DMTree 通过 compute-side collaborative design 把 fingerprint 表和锁卸到 compute server 之间，利用空闲的 [[RDMA]] 资源缓解 memory server 的 IOPS/带宽瓶颈，对 SOTA range index 取得最高 5.7× 吞吐提升。

## 问题

[[Disaggregation|Disaggregated memory]] (DM) 把 compute 与 memory 拆成独立资源池，靠 one-sided [[RDMA]] 通信。已有 range index（B+-tree、ART、LSM-tree、learned index、CHIME、FP-B+-tree）都采用 private compute-side caching：每台 compute server 缓存一份内部节点。这种设计陷入 RDMA 资源利用困境——

- **B+-tree / learned index**（Sherman、ROLEX）连续存储一段 KV，点查需读整个 leaf 节点 → 带宽瓶颈，仅达 expected search 的 16.3-18.8%。
- **ART**（SMART）精确定位单个 KV → IOPS 瓶颈，scan 仅 Sherman 的 35.5%。
- **CHIME / FP-B+-tree** 通过 fingerprint/hash 兼顾两者，但还是要额外 RDMA 读 fingerprint 表和加锁 → 写性能仅 expected 的 23.9-45.4%。

关键观察：memory server 的 NIC 是瓶颈，而 compute server 之间的 RDMA 资源被严重低估。

## 核心方法

DMTree 基于 FP-B+-tree，引入两条核心设计——

**Compute-side collaborative cache**：
- 私有内部树缓存（仅 cache bottom-level internal node，更新少）。
- **共享 fingerprint 表**：每个 leaf 的 fingerprint 表存在某个 compute server 作为 primary，其它 server 持 cached copy。点查时先从 peer compute 读 fingerprint，再去 memory server 取目标 entry，把 IOPS 压力从 memory server 转到 compute 之间。
- 用 **consistent hashing** 分配 primary 所有权，支持 compute server 弹性 scale 与故障恢复。
- 一致性：每个 KV/internal entry/fingerprint 表加 8-byte version ID + CRC，版本号不匹配触发 cache invalidation。

**Compute-side collaborative concurrency**：
- Lock 字段也跟着 primary fingerprint 表存在 compute server，用 RDMA_CAS 跨 compute 加锁。
- **Embedded unlocking**：写回 fingerprint 表时把 lock byte 设为 0，借 RDMA NIC 的顺序写特性把 unlock 与写表合成一次 RDMA_WRITE。
- Update 操作的 5 次 RDMA 中有 3 次（lock、读 fingerprint、unlock）从 memory server 转到 compute 间。
- 读写冲突用 optimistic locking + CRC 检测。

附加优化：scan 时用 fingerprint 过滤空 entry；read delegation + write combining 把 batch 限制在阈值内。

## 关键结果

- 与 Sherman、ROLEX、SMART、dLSM、CHIME 比较，最高 5.7× 吞吐。
- Search/insert/update/scan 全面接近或达到 "expected" 性能（用单 RDMA 上限定义）。
- YCSB A-F 全工作负载领先，特别在 Zipfian 分布下提升明显。
- 设计原则同样适配 [[CXL]] 场景，软件并发开销将取代 IOPS 成为新的瓶颈点。
- 源码开源 https://github.com/muouim/DMTree。

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]、[[CXL]]、Fingerprint Index、Consistent-Hashing
- **同类系统**：Sherman、SMART、CHIME、ROLEX、dLSM、FP-B+-tree
- **同会议**：[[FAST-2026]]
