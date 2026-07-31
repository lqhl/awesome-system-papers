---
type: paper
name: Espresso
full_title: "Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing"
authors: [Shushu Yi, Yuda An, Li Peng, Xiurui Pan, Qiao Li, et al.]
venue: OSDI
year: 2026
tags: [storage, cxl, ssd, computational-storage, resource-sharing]
source_pdf: "[[osdi26-yi.pdf]]"
source_md: "[[osdi26-yi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 通过跨 SSD 计算资源共享构建低成本 CXL JBOF（OSDI 2026）

> **原题**：Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing

> **一句话总结**：Espresso把SSD内部FTL compute/memory解耦，在CXL coherent fabric上让idle SSD的ARM/DRAM协助busy SSD处理burst，从而每盘只配置moderate resources，同时维持enterprise JBOF性能并降低硬件成本。

## 问题与动机

enterprise SSD为sporadic worst-case I/O各自配置大量ARM/DRAM，JBOF中大多数时间闲置；[[PCIe|PCIe]] black-box SSD无法跨盘利用这些资源，host virtualization又需copy/backhaul。

## 关键观察 / 隐含假设

- 不同SSD burst不同步，aggregate compute headroom足以statistical multiplexing。
- CXL cache coherence允许remote SSD直接访问metadata/data结构，避免host copy。
- FTL功能可拆为明确ownership的components。

## 核心方法

SSD architecture分解data-end/compute-end和metadata services；decentralized controller发现idle compute，重定向busy SSD request并load balance。CXL共享address/coherence支持remote ARM读取所需state，protocol维持flash/FTL ordering与failure isolation。

## 实验与结果

- **设置**：CXL JBOF prototype、mixed/bursty SSD workloads，对比conventional fully provisioned SSD与harvesting designs，以IOPS/latency/cost为指标（§6）。
- 在减少一半per-SSD compute/DRAM provision下接近full-resource performance，相对Shrunk/VH throughput高19.2%/20.0%。
- compute utilization提高50.4%，BOM cost降低19.0%，lender性能平均只下降1.3%（§6、图 13–14）。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| inter-SSD sharing降低overprovision | §6 | burst不完全相关 | 中 |
| CXL避免host copy bottleneck | component breakdown | prototype | 中 |

## 批判性分析

### 论证链条

从per-device peak provision转为JBOF pool合理，CXL提供此前缺失的低开销共享substrate。

### 假设压力测试

correlated write bursts、hotspot或一盘failure会耗尽pool；跨SSD FTL state扩大fault domain和firmware复杂度。

### 实验可信度

prototype证明可行，但真实CXL SSD生态、wear/failure和vendor cost模型仍不成熟。

## 局限与后续工作

- correlated workload、device failure与tail SLO。
- 量化BOM、power与wear amplification。

## 相关

- **相关概念**：[[CXL]]、[[JBOF]]、[[Computational-Storage]]、[[FTL]]
- **同会议**：[[OSDI-2026]]
