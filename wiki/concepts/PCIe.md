---
type: concept
aliases: [PCI-Express, Peripheral-Component-Interconnect-Express]
last_updated: 2026-07-30
tags: [hardware, io, accelerator, interconnect]
---

# PCIe

> PCI Express（PCIe）是 CPU、GPU、NIC 与 NVMe SSD 的主机设备互连；系统性能取决于实际拓扑、DMA 粒度与共享争用，而非只看标称链路带宽。

## 核心思想

PCIe 以 transaction layer packet 承载 MMIO 与 DMA，端到端路径还包含 root complex、switch、IOMMU、NUMA node 和 device queue。generation、lane width 与 payload size 决定理论上限，拓扑距离、小传输、同步 doorbell 和双向流量决定有效带宽与尾延迟。

它也是 [[CXL]] 的物理基础，但二者抽象不同：PCIe 主要是设备 I/O，CXL 进一步提供 cache/memory coherence。系统必须显式决定数据驻留、host staging、peer-to-peer 与设备侧计算的位置。

## 为什么重要

OSDI 2026 将 PCIe 反复暴露为“软件优化后出现的下一层瓶颈”：[[CoPilotIO-OSDI26]] 用 CPU 代替 GPU polling 才能以 24 个而非 72+ SM 饱和 25 GB/s；[[Nixie-OSDI26]] 利用双向带宽做 GPU working-set 交换；[[DPA-Store-OSDI26]] 则把 ordered KV traversal 推到 NIC data path，减少 NIC–host 往返。

LLM serving 的权重、[[KV-Cache]] 与 request state 同时争用链路。[[DynamicPPServing-OSDI26]] 说明 PCIe GPU 上频繁 TP collective 代价高，[[Strata-OSDI26]] 则通过大块 I/O 与 GPU 重排缓解碎片化传输。

## 关键观察 / 隐含假设

- **观察：标称带宽不等于有效带宽。** 小 DMA、串行 H2D/D2H 和 queue polling 可主导路径，见 [[CoPilotIO-OSDI26]]、[[Strata-OSDI26]]。
- **观察：位置与控制面同样重要。** [[DPA-Store-OSDI26]] 把 traversal 放在 DPA，[[DirectKV-OSDI26]] 让 kernel 直接读取 CPU-resident KV，均在减少 staging。
- **假设：传输可被 overlap。** [[Nixie-OSDI26]] 与 [[FlowANN-OSDI26]] 依赖可预测 window；短窗口或突发争用会使隐藏失败。

## 设计空间与取舍

- **Host staging / direct access**：staging 利于连续访问但多一次搬运；direct path 省复制却可能受远端 latency 限制。
- **大块合并 / 细粒度需求**：coalescing 提升带宽，可能增加 overfetch 与等待。
- **Polling / interrupt / proxy**：polling 低延迟但消耗执行资源；CPU proxy 改善 GPU 利用率，却引入额外控制跳。

## 引用本概念的论文

- [[CoPilotIO-OSDI26]] — 重新放置 GPU I/O completion polling。
- [[Nixie-OSDI26]] — 以 PCIe 双向交换实现消费 GPU 时间复用。
- [[DPA-Store-OSDI26]] — 在 BlueField-3 data path 执行有序索引。
- [[Strata-OSDI26]] — 合并层级 KV cache 的碎片化 I/O。
- [[Oasis-SOSP25]] — 研究 PCIe device pooling。

## 已知局限 / 开放问题

- 如何在多设备、多租户和多 root-complex 下提供可预测的带宽隔离？
- peer-to-peer、IOMMU 与 confidential-computing 组合后的安全和性能边界仍不清晰。
