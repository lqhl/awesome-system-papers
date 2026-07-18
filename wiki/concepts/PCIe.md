---
type: concept
aliases: [PCI-Express, Peripheral-Component-Interconnect-Express]
last_updated: 2026-07-18
tags: [hardware, io, accelerator, interconnect]
---

# PCIe

> PCI Express is the host-device interconnect used by accelerators, NVMe SSDs, NICs, and CXL-attached components; its bandwidth, topology, DMA behavior, and contention can determine system performance.

## 核心思想

PCIe carries memory-mapped control and DMA data traffic between hosts and devices. Its effective behavior depends on generation, lane width, switch/root-complex topology, NUMA placement, transfer size, peer-to-peer support, and simultaneous device traffic. Nominal link bandwidth is therefore not an end-to-end throughput guarantee.

## 为什么重要

Many systems in this corpus cross the host-device boundary: storage stacks move data to NVMe, training systems exchange GPU/CPU state, and CXL-related designs share an I/O fabric. A measured speedup must distinguish PCIe transfer limits from software queues, memory copies, and device execution.

## 关键观察 / 隐含假设

- **观察**：a wider/faster device can expose host-side interconnect or software bottlenecks. [[NVMe]] and [[CXL]] pages collect such storage/memory-path contexts.
- **观察**：DMA and placement choices change the visible cost. [[PIMANN-ATC25]] and [[uCache-FAST26]] evaluate systems with explicit device-path boundaries.
- **假设**：devices share bandwidth uniformly. NUMA/root-complex placement and concurrent traffic can violate that assumption.

## 设计空间与取舍

- **Host-mediated vs peer-to-peer transfers**：peer paths can avoid copies but require topology and platform support.
- **Bandwidth vs latency**：large transfers amortize overhead; small control/data operations remain sensitive to software and PCIe transaction costs.
- **Isolation vs sharing**：virtualization/IOMMU and multi-device contention change practical throughput.

## 引用本概念的论文

- [[CXL]] — memory and I/O fabric context.
- [[NVMe]] — host-to-SSD path.
- [[PIMANN-ATC25]] — device placement for ANN execution.
- [[uCache-FAST26]] — NVMe data-path and cache design.
