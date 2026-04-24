---
type: paper
name: FuseLink
full_title: "Enabling Efficient GPU Communication over Multiple NICs with FuseLink"
authors: [Zhenghang Ren, Yuxuan Li, Zilong Wang, Xinyang Huang, Wenxue Li, et al.]
venue: OSDI
year: 2025
tags: [gpu-communication, rdma, nccl, multi-nic, nvlink]
source_pdf: "[[osdi25-ren.pdf]]"
source_md: "[[osdi25-ren]]"
---

# Enabling Efficient GPU Communication over Multiple NICs with FuseLink (OSDI 2025)

> **一句话总结**：GPU-NIC 静态绑定在动态流量场景（LLM serving、[[MoE]]、DLRM）下只用到 13–82% NIC 带宽，FuseLink 用 NVLink 做运行时中继、把所有 NIC 聚合成一条「融合链路」，端到端两 GPU 间带宽冲到 212 GB/s，TTFT 快 2.73×。

## 问题

ML 集群通常按「GPU 数 = NIC 数」布线，每 NIC 通过 PCIe 直连一个 GPU。只有 3D 并行这种流量完全均衡的训练可以吃满；对 disaggregated LLM serving、[[MoE]] expert-parallel、DLRM embedding transmission 这类动态流量，一些 NIC 堆积（成为瓶颈）、另一些空闲，实测平均 NIC 利用率只有 13–53%（LLM serving）、29–65%（MoE）、59–82%（DLRM）。

多 NIC 同时发已有方案只能走 PCIe 非直连路径，受 PCIe root complex / NUMA 跨越拖累。NCCL 用 NVLink 也只优化「单个 NIC 走哪条 PCIe 路径」，没做多 NIC 带宽聚合与动态调度。

## 核心方法

FuseLink 的核心洞察：intra-server 的 NVLink（Tbps）和 inter-server 的 [[RDMA]] NIC（百 Gbps）在应用视角可以抽象成同一层「可调度网络资源」。

- **高效 intra-server relay**：设计空间有四种候选（GPU 写 remapped buffer / CPU 驱动的 device-to-device memcpy / 两种走 host memory 方案）。实测 D1——利用 CUDA unified virtual addressing 把 network buffer 重映射到 router GPU 上，GPU 线程 fill buffer 时自动经 NVLink 到达 router GPU——间接 NIC 吞吐最高，因为省掉了重复 copy、没有 CPU 同步开销，还能通过 intra/inter pipelining 隐藏 relay 延迟。
- **Interruption-free 调度**：只在 indirect NIC 空闲、对等 GPU 没在用本 NIC 时才借用；引入基于优先级的 memory/bandwidth budget，防止 relay buffer 撑爆 peer GPU 导致 OOM。
- **凭证式调度**：发送端根据接收端通过 RDMA credits 反馈的「本机空闲 NIC」信息 + 本机 NIC 负载，决策走哪条 NIC、是否 relay。
- **NCCL 集成**：作为独立 networking 层替换 NCCL 默认网络，ML 应用无需改代码。

通过四步消融，累计从 49.27 GBps（baseline）→ 78.39 → 76.37 → 178.59 → 212.35 GBps，relay + 去 contention + 高效调度三个组件各自贡献明显。

## 关键结果

- 两 GPU 间 inter-server 带宽 212 GBps，超过八-lane NVLink 理论值（200 GB/s），比 baseline NCCL 快 4.31×
- LLM serving 的 TTFT 缩短 1.04–2.73×
- Mixtral 8×7B MoE 训练吞吐 +1.3×
- DeepFM DLRM 训练 +1.2×

## 相关

- **相关概念**：[[RDMA]]、[[MoE]]、[[Expert-Parallelism]]
- **同类系统**：NCCL（被 FuseLink 替换的默认网络层）
- **同会议**：[[OSDI-2025]]
