---
type: paper
name: Mage
full_title: "Scalable Far Memory: Balancing Faults and Evictions"
authors: [Yueyang Pan, Yash Lala, Musa Unal, Yujie Ren, Seung-seob Lee, et al.]
venue: SOSP
year: 2025
tags: [far-memory, remote-memory, rdma, scalability, memory-offloading, tlb-shootdown]
source_pdf: "[[3731569.3764842.pdf]]"
source_md: "[[3731569.3764842]]"
---

# Scalable Far Memory: Balancing Faults and Evictions (SOSP 2025)

> **一句话总结**:针对多核下 page-based far memory 的严重扩展性崩塌(Hermit 在 10% offload 下掉 75%),提出 always-asynchronous decoupling + cross-batch pipelining + prioritize contention avoidance 三原则,在 Linux 和 LibOS 上各实现 MageLnx / MageLib,batch 应用吞吐提升 **1.2-4.2×**,memcached P99 延迟降 **94.5%**。

## 问题

远程内存(far memory)通过 [[RDMA]]、[[CXL]] 等快速网络把远端 DRAM 当作本地内存的扩展,page-based 方案(kernel 级 paging)因能透明支持老应用而在云厂商广泛部署。但现有系统(Hermit、DiLOS)是为低线程数场景设计的,在现代多核机器(48 线程)上完全不 scale:

- GapBS page rank 在仅 10% offload 下,Hermit 吞吐降 **75%**,DiLOS 降 **50%**——远超 ideal 下的 ~10% 降幅
- 根因:虚拟内存机制是为毫秒级磁盘设计的,现在用在微秒级 RDMA 上水土不服

分析三大瓶颈:
1. **TLB coherence**:跨核 IPI 延迟随线程数爆炸,Hermit 从 1 核到 48 核每 IPI 延迟涨 **33×**,DiLOS 在虚拟化下每 IPI 触发 VMexit 多 1200 cycle
2. **Page accounting**:系统级 LRU 链表在 fault-in 线程和 eviction 线程之间争用,contention 随线程数涨 **9.6-11.4×**
3. **Page circulation**:本地/远端内存分配器全局锁,在 swap-intensive 高线程场景下成为尾延迟来源

## 核心方法

Mage 三条设计原则:

1. **Always-asynchronous decoupling**:把 eviction 逻辑完全剥离到少量专门的 evictor 线程,严格限制 evictor 数量,消除"同步 fallback"机制。把昂贵的 TLB coherence 操作彻底搬出应用的 critical path,fault-in 路径只需拿一个本地 free page 就返回。
2. **Cross-batch pipelining**:把 eviction 的多个子步骤(选 victim → 改 PTE → TLB shootdown → 远端分配 → RDMA write → 回收 page)跨 batch 流水线化,利用原本 idle 的窗口,显著提升 eviction 吞吐。
3. **Prioritize contention avoidance over accuracy**:用 per-CPU sharded 数据结构替代系统级 LRU,牺牲精准的 hot/cold 信息换扩展性——高 load 下吞吐远比命中率更重要。

两个变体:
- **MageLnx**:Linux kernel 实现,方便兼容生态
- **MageLib**:library OS 实现,最大化性能上限

高性能 eviction 路径保证持续供应 free page,使得 fault-in 路径可以只做 RDMA read 而不触发同步 eviction。

## 关键结果

- **Batch 应用**(GapBS、XSBench、MapReduce 类)吞吐提升 **1.2-4.2×** vs Hermit/DiLOS
- **memcached**(延迟敏感)P99 尾延迟降 **50.2-94.5%**
- 在 48 线程 + 50% 内存 offload 下,接近"ideal far-memory"(仅 RDMA 延迟,零软件开销)曲线,把 Hermit 只能达到理想值 14% 的吞吐拉回大部分
- 消除 TLB shootdown 在 critical path 上的 27μs 开销

## 相关

- **相关概念**:[[RDMA]]、[[TLB-Shootdown]]、[[Page-Fault]]、[[Swap]]、[[CXL]]、[[NUMA]]、[[LRU]]、[[Memory-Disaggregation]]
- **同类系统**:[[Hermit]]、DiLOS、Leap、Fastswap、AIFM、Carbink、Canvas
- **同会议**:[[SOSP-2025]]
