---
type: paper
name: Barre
full_title: "Barre: Empowering Simplified and Versatile Programmable Congestion Control in High-Speed AI Clusters"
authors: [Yajuan Peng, Haoran Wei, Xiaolong Zhong, Junkai Huang, Haohan Xu, et al.]
venue: ATC
year: 2025
tags: [congestion-control, rdma, rocev2, ai-cluster, programmable-nic]
source_pdf: "[[atc2025-peng-yajuan.pdf]]"
source_md: "[[atc2025-peng-yajuan]]"
---

# Barre: Empowering Simplified and Versatile Programmable Congestion Control in High-Speed AI Clusters (ATC 2025)

> **一句话总结**：ByteDance 在 BlueField-3 SuperNIC PCC 上实现的简化 rate-based AIMD CC，用 Fast Increase / Dual-lock / Inflight Monitor 三件套补齐 RDMA per-flow 控制不足，部署 10K GPU 一年以上、AI 训练吞吐平均 +9.6%。

## 问题

400Gbps RoCEv2 AI 集群仍主要用 2015 年的 DCQCN，调参困难、congestion 响应慢、易触发 PFC。先进 CC 算法（HPCC 需 INT、Swift 需复杂 sqrt 计算、Poseidon 也存在 inflight byte 控制问题）部署门槛高，与现代商用 NIC/switch 不兼容。同时 AI 训练里 AlltoAll 占 60% 流量、SendRecv/AllReduce 各有不同 latency/bandwidth 需求，需要 broad applicability + simple logic + implementation practical 的统一框架。

## 核心方法

Barre 在 BlueField-3 PCC（Programmable Congestion Control）上实现 event-driven CC：

- **Adaptive Adjustment Interval**：以 CNP 作为 congestion signal（避开 RTT baseline 难定问题），real-time RTT 决定增长间隔；Per-CNP-based 微小衰减（β 取 0.95–0.99）实现自然 fairness。
- **Fast Increase**：连续 K 次 RTT 未收 CNP 则切到大步长 A（≈ NIC 带宽 1/1000），平衡 mice flow 快收敛和 elephant flow 稳定性。
- **Dual-lock**：把 DCQCN 的 ByteCounter "OR" Timer 改为 "AND"，缓解高低速流间的不公平、严重拥塞下的过冲。
- **Inflight Monitor**：用 PCC TX event 累计 RTT 内发送字节，超过 R×RTT 时立即降到 1/4，弥补 RDMA 缺乏 inflight byte 控制。
- **RTT-based Enhancement**：给 RTT probe 加序列头/双时间戳防丢包错配，用 RTT 比例缩放每流 α 做 path-length-aware fairness。

详细 algorithm 1 和 fluid model 分析见 [[atc2025-peng-yajuan]]。

## 关键结果

- 256-GPU NCCL AlltoAll：交换机队列长度平均 -16.45%（最高 -21.79%）
- 大规模测试 vs DCQCN：延迟平均 -55.89%，带宽利用 +15%；与 InfiniBand 性能基本持平
- 实际训练任务吞吐平均 +9.6%
- 已部署 10K+ GPU 跨 4 层交换机一年以上，0 次 PFC 触发
- 4 颗 RISC-V core 可处理 10M congestion events/s

## 相关

- **相关概念**：[[Congestion-Control]]、[[RoCEv2]]、[[DCQCN]]、[[PFC]]、[[Programmable-NIC]]、[[CNP]]
- **同类系统**：HPCC、Swift、Poseidon、InfiniBand
- **同会议**：[[ATC-2025]]
