---
type: paper
name: Oasis
full_title: "Oasis: Pooling PCIe Devices Over CXL to Boost Utilization"
authors: [Yuhong Zhong, Daniel S. Berger, Pantea Zardoshti, Enrique Saurez, Jacob Nelson, Dan R. K. Ports, et al.]
venue: SOSP
year: 2025
tags: [cxl, pcie, nic-pooling, resource-pooling, cloud]
source_pdf: "[[3731569.3764812.pdf]]"
source_md: "[[3731569.3764812]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Oasis: Pooling PCIe Devices Over CXL to Boost Utilization (SOSP 2025)

> **一句话总结**：Azure 机架 NIC P99.99 利用率仅 **~20%**、33% SSD 容量与 27% NIC 带宽 stranded；PCIe switch 池化太贵（~$80K/rack），Oasis 在已有 [[CXL]] memory pool 上用软件控制面+数据面池化 PCIe，NIC 利用率 **2×**、failover **38ms**、数据路径仅个位数 μs 开销。

## 问题与动机

[[PCIe]] 设备（NIC/SSD/加速器）占服务器 **20–40%** CapEx、~**13%** OpEx 功耗，但 peak 保守分配 + 资源搁浅 + 冗余 NIC 导致低利用（P99.99 带宽利用 **20%**）。PCIe switch 池化贵且设备类型受限；RDMA  disaggregation 不适配 NIC/多数加速器。论文论点：**CXL memory pool 已为内存经济 justify，同投资可近零边际成本做 PCIe pooling**。

## 关键观察 / 隐含假设

- **观察 1**：CXL 共享内存可被 CPU load/store 与 PCIe DMA 访问，带宽/延迟可支撑设备池化（§2.3）。
  - **依赖假设**：现有 CXL 2.0 设备非跨 host cache coherent；DMA 为主路径可少 fence。
  - **可能失效场景**：CPU 频繁 cacheable 访问共享控制面时非 coherent 风险需小心（论文针对性优化 message channel）。
- **观察 2**：VirtIO 式引擎可分离通用 datapath 与 per-class engine（先实现 NIC engine）。
  - **依赖假设**：容器化环境可替换 virtio 后端；Mellanox 驱动可适配。
  - **可能失效场景**：GPU/自定义 accelerator P2P 语义更复杂，引擎需逐个验证。
- **假设 1**：非 coherent CXL 上 message channel 可做到比 prior art **29×** 吞吐（新设计）。
  - **证据强度**：强；真实 CXL pool 微基准。

## 核心方法

**Oasis**：CXL pod 内多 host 通过共享内存与远端 PCIe 设备通信。

- 利用 DMA 为主减少 cache line invalidate/fence
- **非 coherent 优化 message channel**（修复 prior bug/假设）
- 类 VirtIO 架构 + **network engine**（容器 NIC pooling）

开源：https://bitbucket.org/yuhong_zhong/oasis 。

## 设计取舍

- **取舍 1**：软件池化 vs PCIe switch——低成本灵活但 CPU 参与控制路径。
- **取舍 2**：先 NIC pooling——SSD/accelerator 引擎留 future。
- **边界条件**：datapath 开销个位数 μs，相对云网络 RTT 50–110μs 可忽略。

## 实验与结果

- 生产 packet trace：聚合 NIC 带宽利用率 **2×**
- NIC failover 中断 **38ms**
- Datapath 开销：**single-digit μs**
- Message channel：**29×** vs 既有非 coherent 设计

## Critical Analysis

### 论证链条

stranded/underutil 数据 → CXL 复用 → 2× util + 快 failover，Azure 作者+真 CXL 硬件，链条可信。全 rack TCO ROI 模型相对 $80K PCIe switch 论文定性为主，缺长期账单 A/B。

### 假设压力测试

- **安全**：跨 host 共享 NIC 的租户隔离、SR-IOV VF 映射策略。
- **CXL 3.0**：optional coherence 来临后 message channel 设计是否需重写。
- **延迟敏感**：μs 级 overhead 对 tail-sensitive RPC 累积效应。

### 实验可信度

Microsoft 生产 trace + CXL 2.0 原型强；仅 network engine 限制结论外推到 GPU pool。

### 系统性缺陷

驱动/hypervisor 集成复杂度、故障注入覆盖面、多租户公平 queue 论文未充分展开。

## 局限与 Future Work

- **局限 1**：当前主要 NIC engine；GPU/SSD 未端到端。
- **局限 2**：非 coherent CXL 编程负担仍高。
- **Future work 1**：CXL pod 全栈 TCO 模型（内存池 + Oasis）vs PCIe switch 5 年 ROI。
- **Future work 2**：与 [[RDMA-LiveMigration]]/NIC hot-standby 联动测 38ms failover 下应用 SLO。

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]、[[Resource-Pooling]]、[[NIC]]、[[VirtIO]]
- **同类系统**：PCIe switch (GigaIO/Liquid)、RDMA SSD disaggregation、Titan
- **同会议**：[[SOSP-2025]]
