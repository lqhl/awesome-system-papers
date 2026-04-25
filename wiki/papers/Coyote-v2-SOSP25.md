---
type: paper
name: Coyote-v2
full_title: "Coyote v2: Raising the Level of Abstraction for Data Center FPGAs"
authors: [Benjamin Ramhorst, Dario Korolija, Maximilian Jakob Heer, Jonas Dann, Luhao Liu, Gustavo Alonso]
venue: SOSP
year: 2025
tags: [fpga, datacenter, shell, reconfiguration, rdma]
source_pdf: "[[3731569.3764845.pdf]]"
source_md: "[[3731569.3764845]]"
---

# Coyote v2: Raising the Level of Abstraction for Data Center FPGAs (SOSP 2025)

> **一句话总结**:开源 FPGA shell 用三层分层设计让 services 和 user apps 独立动态可重配置,合成时间减 15-20%,运行时重配置快 10×,内置 RoCEv2 RDMA 栈、共享虚拟内存、FPGA-GPU DMA,10 行 Python 就能从 hls4ml 部署 NN 推理。

## 问题

FPGA 在数据中心越来越多(Microsoft AzureBoost、AWS AQUA、阿里 PolarDB、百度 Kunlun),但约 75% 的开发精力花在基础设施(网络栈、host 通信、内存控制器)而非应用本身。现有 FPGA shells 要么是商业闭源(Xilinx SDAccel、Intel OneAPI),要么是不再维护的学术项目;它们的 services 层(如 networking、MMU)做死在 static layer,一旦切换 TCP/IP ↔ [[RDMA]] 就得整卡 reboot,影响生产可用性;接口也不够通用,大部分 shell 只给单个 host data stream,难以表达多输入应用或深流水应用。

## 核心方法

**三层硬件架构**:(1) static layer 只做 CPU-FPGA link(PCIe XDMA + 控制/迁移/utility channels),不处理数据;(2) dynamic layer(services)承载 MMU、networking、ICAP 等可重配置 service;(3) application layer 放多个 vFPGA。services 从 static layer 剥出后可以运行时重配置——加载失败就丢弃、保留原配置,不 reboot 整卡。ICAP 优化控制器从 ~145 MB/s 提升到 ~800 MB/s。

**统一 vFPGA 接口**:AXI4 stream 接口同时支持 host/card/network 多数据流,vFPGA 可从硬件主动发 DMA(不经 host),支持通用 interrupt(page fault、reconfig done、TLB invalidation、user-issued)。Credit-based 共享机制 + 4 KB packetization + round-robin 交错,保证多租户公平性。

**共享虚拟内存 + RDMA**:MMU 实现在 SRAM TLB + host-side driver hybrid 模式,支持可配置 page size(到 1 GB hugepage)、可配关联度、可选 NRU eviction。社区贡献把 MMU 扩展到 GPU memory 做 FPGA-GPU 直接 DMA。内嵌 BALBOA(100G RoCEv2-compliant)stack,能和 Mellanox/BlueField 互操作。

## 关键结果

- 合成时间比现有方案减 15-20%
- Dynamic 重配置比 full reconfig 快 100×(后者还可能 destabilize 整个系统)
- Coyote v2 + hls4ml 让 NN 部署从 10 行 Python 起步,推理吞吐比 hls4ml baseline 高一个数量级
- AES CBC pipelining 减少 idle time 7×
- 可跑 AMD U250/U55C/U280 多卡,GitHub 开源(fpgasystems/Coyote)

## 相关

- **相关概念**:[[FPGA]]、[[RDMA]]、[[Partial-Reconfiguration]]、[[DPU]]、Shared-Virtual-Memory
- **同类系统**:Coyote v1、Harmonia、FOS、AmorphOS、OPTIMUS、TaPaSCo
- **同会议**:[[SOSP-2025]]
