---
type: paper
name: HARE
full_title: "Cache-Centric Multi-Resource Allocation for Storage Services"
authors: [Chenhao Ye, Shawn (Wanxiang) Zhong, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: FAST
year: 2026
tags: [resource-allocation, multi-tenant, cache, fairness, drf]
source_pdf: "[[fast2026-ye.pdf]]"
source_md: "[[fast2026-ye]]"
---

# Cache-Centric Multi-Resource Allocation for Storage Services (FAST 2026)

> **一句话总结**：HARE 是首个把 cache 整合进多资源分配的 cache-centric 算法——用「harvest/redistribute 两阶段」搜索 cache 划分，把节省下来的 I/O/网络/DB 单元再均衡分给所有租户，在 HopperKV (Redis+DynamoDB) 上提升 1.9×，BunnyFS (NVMe FS) 上提升 1.4×，并在 cache 不敏感时退化为 [[DRF]]。

## 问题

云端 multi-tenant 存储服务要管的资源越来越多：除了 I/O、网络，还有 DynamoDB read/write unit 这类按 API 计费的软件资源，再加上 [[Redis]]/Memcached 这种共享 cache 容量。已有方法不够：
- **Equal partition** 公平但低效。
- **[[DRF|Dominant Resource Fairness]]** 假设资源需求相互独立，但 cache 一变，miss ratio 跟着变，所有 cache-correlated 资源（I/O、网络、DB read unit）的需求都会非线性变化——cache 不能塞进 DRF 的线性 demand vector。
- **现有 cache partition 框架**（Memshare、CoPart 等）只调 cache 大小，不感知其他资源；Memshare 提某个租户性能甚至会牺牲他人公平性。

需求：cache + 多种 cache-correlated 资源的统一分配框架，保证 sharing incentive（每个租户至少拿到 1/x baseline 性能）。

## 核心方法

**HARE = Harvest + Redistribute 两阶段**：
- 输入：每租户 miss ratio curve (MRC)、demand vector、cache-saving constant α_i（用来表示某资源在 cache hit 时节省多少；α=1 完全省，α=0 cache-independent）。
- **Harvest 阶段**：迭代地在两个租户间「以 cache 换 I/O/网络/RU」做 trading deal——给 t2 一块 cache → t2 的 miss 减少 → t2 释放部分资源；t1 失去 cache 需要补偿。两者差额是 harvest。每轮选系统级 dominant 资源（最稀缺的 harvest）做最大化交易，直到无 profitable deal。
- **Redistribute 阶段**：把 harvest 按 t 现有占比加权分给所有人，等比抬高吞吐。
- **降级到 [[DRF]]**：所有租户 cache 敏感度一致时，HARE 不做交易，退回 DRF（带 conserving redistribution）。

**HopperKV**：把 [[Redis]] 改成 DynamoDB 的 cache。Redis Module 暴露 HOPPER.GET/SET 等 API，记录 actual 与 hypothetical（如果命中/未命中各自的）资源用量；用 ghost cache 在线估 MRC；allocator daemon 周期性重算分配并设 rate limiter。

**BunnyFS**：microkernel 风格的本地 NVMe 文件系统，HARE 同时分配 page cache + I/O 带宽 + worker 线程 CPU。复用 HopperKV 的核心机制，验证 HARE 跨场景通用。

## 关键结果

- HopperKV：在所有租户共享同一 dominant resource 时，DRF 没收益、Memshare 牺牲公平性，HARE 单独取得 1.6× 吞吐；real-world trace 上最高 1.9×。
- BunnyFS：相对 baseline 最高 1.4×。
- 算法本身复杂度 O(n) per iteration，运行时间在微秒级，不是性能瓶颈。
- 公平性：HARE 收敛到 normalized throughput min 最大化的点（fairness space 中颜色最深处）；保证 ≥ baseline、≥ DRF。

## 相关

- **相关概念**：[[DRF|Dominant Resource Fairness]]、Miss-Ratio-Curve、[[Redis]]、Multi-Tenant-Resource-Allocation
- **同类系统**：Memshare、CoPart、ElastiCache
- **同会议**：[[FAST-2026]]
