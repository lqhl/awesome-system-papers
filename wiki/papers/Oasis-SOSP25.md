---
type: paper
name: Oasis
full_title: "Oasis: Pooling PCIe Devices Over CXL to Boost Utilization"
authors: [Yuhong Zhong, Daniel S. Berger, Pantea Zardoshti, Enrique Saurez, Jacob Nelson, et al.]
venue: SOSP
year: 2025
tags: [cxl, pcie, resource-pooling, datacenter, networking]
source_pdf: "[[3731569.3764812.pdf]]"
source_md: "[[3731569.3764812]]"
---

# Oasis: Pooling PCIe Devices Over CXL to Boost Utilization (SOSP 2025)

> **一句话总结**：Oasis 首次在软件层用 [[CXL]] 内存池做跨主机 PCIe 设备共享（NIC、SSD 等），NIC 聚合利用率提升 2×、38 ms 故障切换，几乎零增量硬件成本。

## 问题

数据中心里 NIC 和 SSD 单机成本各 ~$2000，占服务器总成本 20-40%，但实测利用率极低：Azure 生产集群里 NIC 带宽 P99.99 聚合只有 20%，27% NIC 带宽和 33% SSD 容量处于 stranded（CPU/内存先耗尽，NIC/SSD 分不出去）状态。还有些数据中心为容错配冗余 NIC，进一步摊低利用率。

现有 PCIe pooling 方案只有两条路：(1) 专用 PCIe 交换机（如 GigaIO FabreX、Liquid SmartStack），单机架成本上至 $80k，且每种 switch 只支持特定设备类；(2) RDMA 分解（如 SSD over RDMA），但 NIC 与众多加速器缺 P2P DMA 无法走这条路，且 RDMA 延迟高。

## 核心方法

Oasis 的核心观察：CXL 内存池已经为"缓解 stranded memory"经济上合理地部署了（见 Azure Pond 等），同样的硬件投入可以顺带解锁 PCIe 设备池化。一个 [[CXL]] pod（用 multi-ported memory device 连多主机，无需昂贵 CXL switch，约 $600/host）提供单向 256 GB/s 带宽，足以承载 NIC + 6 SSD 的 56 GB/s 需求；load-to-use 延迟仅 2× 本地 DDR5（亚微秒级）远低于 I/O 延迟。

Oasis 用共享 CXL 内存作为主机与远端 PCIe 设备的数据路径：CPU load/store、PCIe DMA 都能直接访问。两大挑战与解法：(1) 今日 CXL 2.0 设备**非跨主机 cache-coherent**（CXL 3.0 要求昂贵硬件改动），Oasis 观察 PCIe 设备通常走 DMA 绕开 CPU cache，因此安全地省掉大部分 invalidation/fence 避免性能损失；(2) 跨主机 signaling 请求/完成需要高效消息通道，现有 CXL 消息通道或假设 coherent 或有正确性 bug，Oasis 设计了针对 non-coherent CXL 优化的新消息通道，吞吐提升 29×。

类似 [[VirtIO]]，Oasis 提供通用 datapath，每类设备实现独立 engine；论文落地网络 engine 做 NIC pooling（容器化环境）。

## 关键结果

- datapath 仅单位数 μs 开销（对比云网络 50-110 μs 端到端延迟）
- production packet trace 回放：NIC 聚合带宽利用率 2×，无明显性能损失
- NIC 故障切换对应用透明，38 ms 中断
- 消息通道吞吐相比现有 non-coherent CXL 方案 29×
- 开源：https://bitbucket.org/yuhong_zhong/oasis

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]、[[RDMA]]、[[DMA]]、[[Resource-Disaggregation]]
- **同类系统**：[[VirtIO]]、Pond（CXL memory pooling）、GigaIO FabreX、Liquid SmartStack
- **同会议**：[[SOSP-2025]]
