---
type: paper
name: InfiniDefrag
full_title: "Compaction-Free Memory Defragmentation for Virtualization via Infinite Guest Physical Address Space"
authors: [Peixin Zeng, Hao Huang, Yanqi Pan, Wen Xia, Darong Yang, et al.]
venue: OSDI
year: 2026
tags: [virtualization, memory-fragmentation, huge-pages, memory-compaction, linux]
source_pdf: "[[osdi26-zeng.pdf]]"
source_md: "[[osdi26-zeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 利用近无限 GPA 实现无压缩内存去碎片（OSDI 2026）

> **原题**：Compaction-Free Memory Defragmentation for Virtualization via Infinite Guest Physical Address Space

> **一句话总结**：InfiniDefrag把GPA视作PB级近无限虚拟空间，分配新连续GPA并重映射离散HPA，而非在guest搬页压缩；YCSB-Redis相对LLFREE/Linux THP/4KB pages throughput提高21%–105%，接近无碎片性能。

## 问题与动机

guest huge page需连续GPA，但传统把GPA当固定physical space，碎片后调用compaction，导致Redis throughput最高-51%、latency +102%。实际上GPA到HPA还有EPT映射，guest不必在原GPA区间凑连续空间。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

Infinite Address Manager回收free fragments并扩展连续GPA region，以memory trade将离散旧GPA换成新区；Host Memory Guard维护GPA–HPA mapping并保证实际HPA不超VM quota。Scalability Optimizer使用lockless bitmap、in-kernel remap、delayed TLB flush与hybrid paging支撑multi-thread/VM。

依赖57-bit/PB GPA足够且guest/device不把physical address永久外泄；remap需协调DMA/pinned pages。

## 实验与结果

- YCSB-Redis throughput相对多baseline提高21%–105%，达到ideal no-fragment附近。
- Graph500/Redis/Specjbb/GUPS等验证guest huge-page价值与multi-workload扩展。
- 避免compaction latency spike，同时host quota不因GPA膨胀失控。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

把GPA重新解释为可扩展virtual namespace是简洁洞察。无限只是地址数量，page table/EPT metadata与TLB invalidation仍随稀疏GPA增长；passthrough DMA、snapshot/migration、memory hotplug会依赖稳定GPA，兼容性是主要边界。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 测长期GPA space/metadata增长与回收。
- 支持pinned/DMA/passthrough与live migration。
- 形式化验证remap、TLB与concurrent fault一致性。

## 相关

- **相关概念**：[[Memory-Fragmentation]]、[[Huge-Pages]]、[[Guest-Physical-Address]]、[[Memory-Compaction]]
- **同会议**：[[OSDI-2026]]
