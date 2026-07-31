---
type: paper
name: RamRyder
full_title: "Break on Through to the Other Side: Pooling Memory Elastically with RamRyder"
authors: [Yanbo Zhou, Erci Xu, Dongjoo Seo, Adam Manzanares, Steven Swanson]
venue: OSDI
year: 2026
tags: [memory, virtualization, cxl, bandwidth-isolation, resource-pooling]
source_pdf: "[[osdi26-zhou-yanbo.pdf]]"
source_md: "[[osdi26-zhou-yanbo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 弹性池化内存容量与带宽（OSDI 2026）

> **原题**：Break on Through to the Other Side: Pooling Memory Elastically with RamRyder

> **一句话总结**：RamRyder控制guest pages到DIMM/CXL channels的映射，将memory capacity与bandwidth近似独立分配并动态迁移，隔离VM争用；cluster平均capacity utilization +28.6%、bandwidth +43.2%，性能距exclusive ideal在5%内。

## 问题与动机

cloud memory按vCPU固定容量且不出售bandwidth；tenant为峰值带宽订半socket导致capacity/bandwidth分别时空过配，二者idle pattern并不相关。仅CXL capacity pooling不能解决bandwidth QoS。

## 关键观察 / 隐含假设

- memory channel是可分配bandwidth unit，page placement决定VM可用channels。
- capacity可在CXL/remote pool，hot pages按bandwidth需求跨channels展开。
- page migration能在需求变化速度内完成且不产生大tail。

## 核心方法

hypervisor/guest协同维护page→channel mapping，按VM bandwidth/capacity allocation做channel isolation或sharing；controller监测利用率，动态attach/reclaim DIMM/CXL channel并限速migration。LLC partition配合防止cache-side interference。

## 实验与结果

- **设置**：STREAM、Redis YCSB、GAP graphs与cluster traces，对比Shared/Ideal/channel isolation，以throughput/latency/utilization为指标（§6）。
- P30平均/最大capacity +28.6%/+22.1%，P90 bandwidth +43.2%/+26.1%。
- Redis contention相对Shared latency -25.2%，距Ideal 5%内；128-thread mapping overhead平均3.6%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| capacity/bandwidth可独立弹性分配 | 图 15/20 | channel granularity | 强 |
| isolation接近exclusive | §6.2 | 所测VM workloads | 强 |

## 批判性分析

### 论证链条

trace先证明capacity与bandwidth错配，page-channel control再直接解决，cluster projection和applications一致。

### 假设压力测试

channel数少导致allocation granularity粗；burst快于migration时无法瞬时供带宽，CXL channel也比DIMM慢。

### 实验可信度

多workloads和ablation较完整，但single-server为主，cluster utilization含trace-driven projection。

## 局限与后续工作

- 多server CXL fabric、failure与[[NUMA|NUMA]] topology。
- finer-grained hardware QoS和burst prediction。

## 相关

- **相关概念**：[[CXL]]、[[Memory-Bandwidth]]、[[Memory-Pooling]]、[[Performance-Isolation]]
- **同会议**：[[OSDI-2026]]
