---
type: paper
name: LESS
full_title: "LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage"
authors: [Keyun Cheng, Guodong Li, Xiaolu Li, Sihuang Hu, Patrick P. C. Lee]
venue: FAST
year: 2026
tags: [erasure-coding, distributed-storage, repair, reed-solomon, hdfs]
source_pdf: "[[fast2026-cheng.pdf]]"
source_md: "[[fast2026-cheng]]"
---

# LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage (FAST 2026)

> **一句话总结**：通过把多层 extended sub-stripe 叠加在一个 Reed-Solomon 编码 stripe 之上，构造可配置 sub-packetization $2 \le \alpha \le n-k$ 的 MDS 编码 LESS，在 HDFS 上把 single-block repair 时间相比 SOTA 的 [[Clay-Codes]] 降低最高 83.3%、full-node recovery 降低 36.6%。

## 问题

[[Erasure-Coding]] 是分布式存储（HDFS、Ceph、Facebook f4）取代 replication 的主流容错方案，但单块修复需读 $k$ 个完整 block，repair I/O 高。已有 repair-friendly 编码各有 trade-off：

- **MSR 编码**（如 Clay）minimizes repair I/O，但要求**指数级 sub-packetization** $\alpha = (n-k)^{\lceil n/(n-k)\rceil}$，导致大量非连续 I/O seek。
- **LRC** 减少 repair I/O 但 non-MDS（多占空间）。
- **小 sub-packetization MDS 编码**（Hitchhiker、HashTag）只优化 data block 不优化 parity，或者参数受限。

随着 InfiniBand / [[RDMA]] / [[CXL]] 让网络飞速发展，I/O 性能（尤其 random access）成为 repair 的真正瓶颈。需要一种 MDS、general $(n,k)$、systematic、$\alpha$ 小且可配置、对所有 block 都均衡降低 repair I/O 的编码。

## 核心方法

LESS 的核心思想是**层叠 extended sub-stripe**：把 $n$ 个 block 划分为 $\alpha+1$ 个 block group，每个 sub-block 同时属于两个 extended sub-stripe（除了最后一个 $X_{\alpha+1}$ 隐式形成）。每个 extended sub-stripe 独立用 Vandermonde-based [[Reed-Solomon-Code]] 编码，能容忍 $n-k$ 个 sub-block 失败。

关键构造步骤：
1. **Grouping**：把 $n$ 个 block 平均切成 $\alpha+1$ 组。
2. **Layering**：组织 $n\alpha$ 个 sub-block 进入 $\alpha+1$ 个 extended sub-stripe，使每个 sub-block 恰属两个。
3. **MDS 编码**：选 $n\alpha$ 个不同的 coding coefficient（用 primitive element 的乘法构造），让前 $\alpha$ 个 stripe 的 parity-check equation 之和自动满足第 $\alpha+1$ 个，形成 implicit RS stripe。

**Single-block repair**：失败 block $B_i \in G_z$ 总是落在某个 extended sub-stripe $X_z$ 内，只读 $X_z$ 的 $|X_z|-n+k$ 个 sub-block 即可重构，不需要跨 stripe。**Multi-block repair**：当多个失败 block 共享一个 block group 时，仍可走同一 $X_z$，最多支持 $\lfloor (n-k)/\alpha \rfloor$ 块同组失败。

LESS 是 systematic、MDS、支持 general $(n,k)$ 的 RS 扩展，三者兼得且 $\alpha$ 在 $[2, n-k]$ 内可调，提供 data access 与 I/O seek 的连续 trade-off。

## 关键结果

- HDFS 实测：相比 Clay codes 单块修复时间降 **83.3%**，full-node recovery 降 36.6%。
- 对所有 data 和 parity block 实现**均衡** I/O 降低（非偏向 data block 的 Hitchhiker / HashTag）。
- $(6,4,2)$ LESS 单块修复 6 个 sub-block，比 (6,4) RS 节省 25% repair I/O；$(14,10,2)$ 双块修复同组比 (14,10) RS 节省 25%。
- 开源在 https://github.com/adslabcuhk/less。

## 相关

- **相关概念**：[[Erasure-Coding]]、[[Reed-Solomon-Code]]、[[Sub-Packetization]]
- **同类系统**：[[Clay-Codes]]、[[Hitchhiker]]、[[HashTag]]、[[Azure-LRC]]、[[Elastic-Transformation]]
- **同会议**：[[FAST-2026]]
