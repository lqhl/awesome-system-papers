---
type: paper
name: DRack
full_title: "DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication"
authors: [Xu Zhang, Ke Liu, Yuan Hui, Xiaolong Zheng, Yisong Chang, et al.]
venue: ATC
year: 2025
tags: [cxl, disaggregation, rack-architecture, networking, datacenter]
source_pdf: "[[atc2025-zhang-xu.pdf]]"
source_md: "[[atc2025-zhang-xu]]"
---

# DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication (ATC 2025)

> **一句话总结**：用 CXL 3.0 fabric 把 rack 内所有 NIC 与 memory 池化共享，让任何 host 都能借用闲置 NIC 加速跨 rack 通信，相比 ToR-centric 架构通信阶段平均减少 37.3%，p99 尾延迟降 62.2%。

## 问题

数据中心 ToR-centric rack 架构中，跨 rack 流量占 87.1%（Facebook 数据），但单 host 的 NIC 是瓶颈，且 ToR 上行 oversubscribe。与此同时，rack 内 NIC 利用率长期偏低（90% 以上 NIC 在 1s 内不发不收，整体 < 20%），原因：(1) BSP / MapReduce 计算-通信交替时 NIC 空闲；(2) 数据倾斜 / 负载不均；(3) 资源碎片化的非分布式作业。已有方案（增加带宽硬件、可重配置网络、调度优化）成本高或受限于流量预测难度。

## 核心方法

三大 disaggregation 设计：

- **NIC pool**：通过 [[CXL]] 3.0 fabric + SR-IOV 把 rack 内每张 NIC 虚拟成多个 vNIC，任何 host 可以同时驱动所有 NIC 发送/接收，把 ToR 的角色"上推一层"消除 oversubscribe。MPTCP 拆 subflow 平均使用 vNIC。
- **Memory pool**：把每 host 的 12GB 本地 memory 加入 256B 粒度的 interleave set IS0，剩余 4GB 放 latency-critical 数据结构（virt_queue）。NIC pool DMA 跨多 memory 设备读写，绕开单 host PCIe 链路与 memory 带宽瓶颈。
- **Memory semantics 直读**：CPU 用 CXL.mem load/store 直接访问 memory pool，不需要先 DMA 到本地 DRAM。
- **DRAM cache + Pass-by-reference**：在每 host 的 CXL port 加 DRAM cache（128B / 4KB 多粒度）缓解 CXL.mem 远端访问 ~13µs 高延迟（本地 2.2µs）。Intra-rack 通信用引用传递（CXL.mem store 到对方 ref_queue）+ TCP/IP 透明翻译，避免数据拷贝。

实现：8 颗 MPSoC FPGA + 服务器组成 quad-rack 原型，用 DoCE 协议栈把 AXI 信号封进 Ethernet 帧模拟 CXL transactions。

详见 [[atc2025-zhang-xu]]。

## 关键结果

- PageRank / KV store / ResNet 训练 / LLM 训练 / DLRM 推理：通信阶段平均减少 37.3%。
- Redis 等 latency-sensitive workload：p99 尾延迟降 62.2%。
- 在 BSP-based scheduler（Crux）和 MapReduce scheduler（ShuffleWatcher）上正交叠加性能收益。

## 相关

- **相关概念**：[[CXL]]、[[Disaggregation]]、[[RDMA]]
- **同会议**：[[ATC-2025]]
