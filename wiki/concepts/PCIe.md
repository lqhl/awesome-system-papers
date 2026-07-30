---
type: concept
aliases: [PCI-Express, Peripheral-Component-Interconnect-Express]
last_updated: 2026-07-18
tags: [hardware, io, accelerator, interconnect]
---

# PCIe

> PCI Express 是加速器、NVMe SSD、NIC 和 CXL 连接组件使用的主机设备互连；其带宽、拓扑、DMA 行为和争用可以决定系统性能。

## 核心思想

PCIe 在主机和设备之间承载内存映射控制和 DMA 数据流量。其有效行为取决于生成、通道宽度、交换机/根联合体拓扑、NUMA 布局、传输大小、点对点支持和同时设备流量。因此，标称链路带宽并不能保证端到端的吞吐量。

## 为什么重要

该语料库中的许多系统跨越了主机设备边界：存储堆栈将数据移动到 NVMe、训练系统交换 GPU/CPU 状态以及 CXL 相关设计共享 I/O 结构。测量的加速必须将 PCIe 传输限制与软件队列、内存副本和设备执行区分开来。

## 关键观察 / 隐含假设

- **观察**：更宽/更快的设备可以暴露主机端互连或软件瓶颈。 [[NVMe]] 和 [[CXL]] 页面收集此类存储/内存路径上下文。
- **观察**：DMA 和布局选择会改变可见成本。 [[PIMANN-ATC25]] 和 [[uCache-FAST26]] 评估具有显式设备路径边界的系统。
- **假设**：设备统一共享带宽。 NUMA/根联合体布局和并发流量可能会违反该假设。

## 设计空间与取舍

- **主机介导与点对点传输**：对等路径可以避免复制，但需要拓扑和平台支持。
- **带宽与延迟**：大传输分摊开销；小型控制/数据操作仍然对软件和 PCIe 交易成本敏感。
- **隔离与共享**：虚拟化/IOMMU和多设备争用改变了实际吞吐量。

## 引用本概念的论文

- [[CXL]] — memory and I/O fabric context.
- [[NVMe]] — host-to-SSD path.
- [[PIMANN-ATC25]] — device placement for ANN execution.
- [[uCache-FAST26]] — NVMe data-path and cache design.
