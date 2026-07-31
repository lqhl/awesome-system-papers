---
type: concept
aliases: [Non-Uniform-Memory-Access]
last_updated: 2026-07-30
tags: [hardware, memory, scheduling, placement]
---

# NUMA

> 非一致内存访问（NUMA）使 CPU、内存和 I/O 的访问成本依位置而变；线程、页面与设备的联合放置因此成为系统设计的一部分。

## 核心思想

多 socket 系统中，本地 DRAM、远端 DRAM、LLC、memory channel 与 PCIe root complex 构成分层拓扑。只绑定线程而不绑定 page/device，或只追求 locality 而忽略 load balance，都会把瓶颈转移到互连与远端 channel。

## 为什么重要

OSDI 2026 将 NUMA 从静态 affinity 扩展为动态资源控制：[[RamRyder-OSDI26]] 通过 guest-page 到 DIMM/CXL channel 的映射近似独立分配容量与带宽；[[OBASE-OSDI26]] 在 page 内按对象热度重排，说明 node-local page 仍可能有 70%–90% 冷字节；[[SBB-OSDI26]] 区分保留 cache locality 的 intra-core switch 与破坏 locality 的 inter-core migration。

## 关键观察 / 隐含假设

- **观察：locality 的单位不止 page。** [[OBASE-OSDI26]] 将对象热度纳入 page packing，[[Sepia-OSDI26]] 进一步关注 DMA page 的 LLC set 分布。
- **观察：容量与带宽需分别控制。** [[RamRyder-OSDI26]] 把 hot page 展开到多个 channel，而冷容量可放在 CXL tier。
- **假设：访问相位可被追踪。** [[DirectKV-OSDI26]]、[[LocalMoE-Hybrid-OSDI26]] 的 host/GPU placement 都依赖相对稳定的访问结构。

## 设计空间与取舍

- **Locality / balance**：严格本地化降低 latency，却可能留下空闲核和 channel。
- **Static binding / migration**：静态策略简单稳定；迁移适应 phase change，但消耗带宽并污染 cache。
- **Page / object / channel granularity**：越细越精准，metadata 与控制开销越高。

## 引用本概念的论文

- [[RamRyder-OSDI26]] — VM 级 memory-channel bandwidth isolation。
- [[OBASE-OSDI26]] — page 内对象热度重排。
- [[SBB-OSDI26]] — 多核用户态网络调度的 locality 权衡。
- [[DSA-2LM-ATC25]] — NUMA-aware tiered-memory migration。
- [[ScaleSwap-FAST26]] — 多核 swap resource placement。

## 已知局限 / 开放问题

- page migration、device DMA 和 scheduler migration 如何共享统一 topology model？
- CXL fabric 与 chiplet memory 使“本地/远端”变成连续谱，现有二分策略需重构。
