---
type: paper
name: DisCoGC
full_title: "Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance"
authors: [Runhua Bian, Liqiang Zhang, Jinxin Liu, Jiacheng Zhang, Jianong Zhong, et al.]
venue: FAST
year: 2026
tags: [garbage-collection, log-structured, ssd, write-amplification, bytedance]
source_pdf: "[[fast2026-bian.pdf]]"
source_md: "[[fast2026-bian]]"
---

# Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance (FAST 2026)

> **一句话总结**：在字节 ByteStore + ByteDrive 的两层 append-only 存储栈里把 compaction-only GC 换成 discard + compaction 混合，针对高顺序写 + 频繁覆盖的 workload 把 write amplification 砍 25%、TCO 砍约 20%。

## 问题

ByteStore 是字节自研的 SSD-based 分布式 append-only 存储底座，承载 ByteDrive（块存储）、TOS（对象）、NAS、ByteGraph、ByteNDB 等服务。ByteDrive 把随机写转成 append-only 写到 LogFile，需要周期性 GC 回收 stale data。

原方案是 compaction-only GC：把 LogFile 里的有效数据搬到新 LogFile，然后删旧的。但这有一个根本权衡：

- **空间放大** vs **写放大**负相关：激进 GC 降空间，但写放大暴涨 → SSD 寿命缩短 + 前台 I/O 抖动
- 量化代价：空间放大和写放大每月让 ByteDance 多花数百万美元 TCO

字节生产 trace 分析（online / SAR / offline 三类负载）发现 SAR（搜索/广告/推荐索引、AI 模型下载/推理）和 offline（Spark 等分布式计算）有强顺序写（>50% 写连续 >256 KiB）+ 秒级频繁覆盖，导致 LogFile 上出现长连续的 stale 区段。这种 garbage 用搬数据的 compaction 处理纯属浪费。

## 核心方法

DisCoGC = **Discard + Compaction 混合 GC**。Discard 直接释放 LogFile 上 stale range 占的物理空间，不搬有效数据。架构上 discard 自顶向下穿透 Volume / Segment / LogFile / UFS（自研 ChunkServer 上的 [[Userspace-Filesystem]]）四层，但有四个挑战要解：

1. **Boundary loss（边界丢失）**：层间 allocation unit 不对齐（EC stripe vs cluster vs 4 KiB 块 + sector header 32 B / 4064 B data），discard 范围两端凑不齐对齐单元就丢空间。
   - **Boundary extension**：新 discard 范围向已 discard 的相邻范围多伸几 MiB 重叠回收边界
   - **Discard-friendly EC stripes**：把 EC stripe unit 配成 `n × 4 × 4064 B` 与 cluster 对齐
2. **MetaPage 更新开销**：每次 discard 都要改 UFS MetaPage 写 SSD + 占 CPU
   - 对同一 LogFile 的 discard 请求做 batching + 限制 discard 并发/IOPS
3. **LogFile/chunk 碎片化** → metadata 膨胀：定期跑 compaction 合并碎片
4. **SSD trim IOPS 受限**：SSD 不及时回收 → 内部 GC 激进 → 前台抖动
   - **Trim filter** 优先大范围 trim
   - **Trim merger** 把小 trim 合成大 trim，更省 SSD 的 trim IOPS 预算

## 关键结果

- 生产集群（混合负载）：空间放大降 10% 同时 write amplification 降 25% → **TCO 降约 20%**
- 高顺序写 + 频繁覆盖（SAR/offline 类）：TCO 降 >25%
- 随机/碎片化负载（online 类）：TCO 也降 2-5%（鲁棒性 OK）
- 性能无回退（latency 不增）
- 给出 deployment guideline：先看 trace 顺序性 + 覆盖率决定是否启用 DisCoGC

## 相关

- **相关概念**：[[Garbage-Collection]]、[[Write-Amplification]]、[[Log-Structured-Storage]]、[[Erasure-Coding]]、[[TRIM]]、[[Compaction]]
- **同类系统**：[[ByteStore]]、[[ByteDrive]]、[[RocksDB]]
- **同会议**：[[FAST-2026]]
