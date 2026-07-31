---
type: paper
name: Blowfish
full_title: "Blowfish: Elastic Virtual Machine Memory for Disaggregated Memory"
authors: [Yulong Zhang, Yilong Luo, Diyu Zhou, Quan Chen, Quanxi Li, et al.]
venue: OSDI
year: 2026
tags: [virtualization, disaggregated-memory, memory-overcommit, huge-pages, far-memory]
source_pdf: "[[osdi26-zhang-yulong.pdf]]"
source_md: "[[osdi26-zhang-yulong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向分离式内存的弹性虚拟机内存（OSDI 2026）

> **原题**：Blowfish: Elastic Virtual Machine Memory for Disaggregated Memory

> **一句话总结**：Blowfish让guest以THP-aware tracker识别huge page内部cold subpages，hypervisor经cross-layer path直接回收/恢复HPA且不改guest/I/O page table；reclaim/restore比HyperAlloc快2.48×/2.14×，5% slowdown内回收比高1.6×–6.1×。

## 问题与动机

far memory将page swap降至微秒，但software tracking/remapping变成瓶颈。host accessed-bit看不到guest语义且THP hot-bloat：一个hot 4KB让整个2MB被判hot；拆THP则增加5× TLB flush。传统restore还多层修改GPA/HPA/IOMMU。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

paravirtual guest tracker低成本识别THP内cold mappings，并通过shared interface告诉hypervisor；hypervisor直接解除/重分配HPA，保留guest GPA/page table与I/O mapping稳定。cold/free page用dedicated cross-layer path搬far memory，按page type赋不同hotness weight并控制5%性能budget。

## 实验与结果

- reclaim与restore速度相对HyperAlloc分别2.48×、2.14×。
- 5% degradation内reclamation ratio提高1.6×–6.1×；实际workload 33%–49% memory可换出。
- 软件overhead降低超过50%，保留THP translation benefit。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

跨guest/hypervisor语义消除重复page-table work很有效，但要求guest合作，无法透明服务unmodified VM。far-memory congestion/failure会把microsecond假设打破；稳定GPA下device DMA correctness虽简化，remote data durability与security仍需处理。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 多tenant far-memory congestion、failure与encryption评测。
- 降低paravirtual requirement或提供legacy VM fallback。
- 将5% budget扩展为per-VM tail SLO controller。

## 相关

- **相关概念**：[[Disaggregated-Memory]]、[[Memory-Overcommitment]]、[[Transparent-Huge-Pages]]、[[Far-Memory]]
- **相关系统**：[[HyperAlloc]]
- **同会议**：[[OSDI-2026]]
