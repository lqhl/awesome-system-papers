---
type: paper
name: UCCL-Tran
full_title: "UCCL-Tran: An Extensible Software Transport Layer for GPU Networking"
authors: [Yang Zhou, Zhongjie Chen, Ziming Mao, ChonLam Lao, Shuo Yang, et al.]
venue: OSDI
year: 2026
tags: [gpu-networking, rdma, multipath, transport, ml-systems]
source_pdf: "[[osdi26-zhou-yang.pdf]]"
source_md: "[[osdi26-zhou-yang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向 GPU 网络的可扩展软件传输层（OSDI 2026）

> **原题**：UCCL-Tran: An Extensible Software Transport Layer for GPU Networking

> **一句话总结**：现有 RDMA NIC 把拥塞控制、可靠性和路径选择固化在硬件中，难以跟上 MoE 与大规模 collective 的流量模式；UCCL-Tran 用 UC/RC/UD 将数据路径与控制路径分离，在 CPU 上以 32KB 控制合并、256 QP 多路径和连接拆分实现可编程传输，在 ConnectX-7 上的 all-to-all 最高提升 4.54×，并使端到端训练速度提升 7.5%。

## 问题与动机

GPU 集群的通信模式已从较规则的 allreduce 扩展到 MoE 的 all-to-all、prefill-decode 分离和高并发点对点通信。RDMA NIC 的传输控制逻辑更新周期较长，单路径连接容易产生流碰撞；硬件拥塞控制在低流熵、高突发的 ML 流量上也可能反应不当。通过改造网络拓扑或关闭拥塞控制可以缓解个别问题，但会增加建设成本或引入拥塞、队头阻塞和死锁风险。

论文要解决的是传输层的可演化性，同时保持接近硬件传输的吞吐和延迟。UCCL-Tran 作为 NCCL/RCCL 的网络插件，对上层 collective API 保持兼容。

## 关键观察 / 隐含假设

- **观察 1：ML collective 的消息大、数据块接近 MTU，QP 状态切换开销可以被摊薄。** 在 CX_IB 上将 QP 数从 60 扩展到 60K，RC 带宽仅下降约 17%，UC 的下降更小（图 6）。
  - **依赖假设**：通信主要由 1MB–1GB 消息构成，而不是小消息 RPC。
  - **可能失效场景**：小消息、连接数进一步增长或 NIC 的 QP context 更小，PCIe/DRAM 交换可能重新成为瓶颈。
- **观察 2：流碰撞和路径拥塞是 collective 性能下降的主要来源。** CX_ETH 上硬件 RDMA 的吞吐在大消息下下降，而软件按路径 RTT 动态选择可维持更稳定的吞吐（图 7、图 15）。
  - **依赖假设**：底层网络使用 ECMP，QP 或 UDP 端口能够产生足够多的路径哈希。
  - **可能失效场景**：网络没有多路径、路径数不足，或交换机哈希无法利用 QP/端口熵。
- **假设 1：GPU 服务器有可预留的 CPU 核心。** 论文引用的集群 CPU 利用率为 20%–45%，自身训练场景平均为 128 核中的 14.5%；实现默认每个 NIC 增加 2 个 engine 核心。
  - **证据强度**：中；有部署数据支持，但不同云实例、租户隔离策略和 CPU 超售情况未覆盖。
- **假设 2：ML 流量可以接受按 chunk 而非按 packet 的控制。** 默认 32KB chunk 可用单核处理 400 Gbps 单向流量。
  - **证据强度**：强；图 14 和 §6.5.3 给出吞吐及控制延迟测量，但极端突发和更短 RTT 场景仍需验证。

## 核心方法

UCCL-Tran 将控制逻辑移到用户态 CPU，把 GPU 数据仍交给 NIC 直接 DMA。NIC 支持 UC 时，系统使用 RDMA write with immediate：数据 payload 写入 GPU，32-bit immediate data 作为控制头进入接收 CPU。UC 绕过硬件拥塞控制、重传和乱序处理，同时保留分段与重组卸载。没有 UC 时使用关闭 CC 的 RC；AWS EFA 等不能绕过硬件控制的设备使用 UD，并借助 scatter-gather 将控制头和 payload 分别放入 CPU 与 GPU。

系统为一对 NIC 共享最多 256 个 QP，使不同 QP 经由 ECMP 进入不同路径。CPU 维护每条路径的 RTT 和可靠性状态，使用 Power-of-Two sampling 选择低 RTT 路径，并用序号、ACK、重复 ACK 和超时重传处理乱序与丢包。UD 的乱序 packet 由融合进 collective reduction kernel 的 GPU scattered memcpy 重排。

为达到线速，engine 线程采用 run-to-completion 和 DRR 调度；连接拆分把一个连接的 QP 分给多个 CPU 核心。控制合并让拥塞控制、负载均衡和可靠性逻辑按 32KB chunk 工作；UD 则用 chained posting 一次提交最多 32 个 verb。接口暴露 `onChunkSize`、`onSelectPath`、`onRxACK` 和 `onRxCredit` 等回调，因此可以在不修改 NIC 固件的情况下实现 packet spraying、EQDS 接收端驱动拥塞控制和 selective retransmission。

## 设计取舍

- **CPU 可编程性换取 CPU 与控制延迟。** UCCL-Tran 需要每个 NIC 额外的 engine 核心，重载时 CC 决策和 ACK turnaround 延迟 P99 可达 36µs；论文认为这与 10–40µs 的数据中心 RTT 同量级。
- **chunk 级控制换取处理效率。** 大 chunk 能摊薄 MMIO、QP 和 CPU 开销，但丢一个 packet 可能导致整个 chunk 重传，拥塞快速变化时控制粒度不如 packet 级。
- **通用 NIC 支持换取实现复杂度。** 28.4K 行 C++，且 EFA/UD 需要约 170 行 NCCL 修改和 GPU 融合 kernel；论文未系统评估长期维护、故障诊断和多租户隔离成本。

## 实验与结果

- CX_ETH 上，UCCL-Tran 相对 ConnectX-7 的 allreduce 最高提升 2.32×，all-to-all 最高提升 4.54×（图 7）；主要收益来自动态路径选择，而非单纯增加 QP（图 15）。
- AMD rail-optimized testbed 上，all-to-all 相对 Thor-2 最高提升 1.78×，allreduce 性能相近（图 8）。
- AWS p4d EFA 上，all-to-all 相对官方 SRD 最高提升 3.27×（图 9）；论文将差异归因于主机 CPU 相比 EFA SmartNIC ARM 核心有更强的连接处理能力。
- DeepSeek-V2-Lite 训练端到端速度最高提升 7.5%；trace-driven 的 DeepSeek-V3-like serving 中，prefill 和 decode 延迟分别改善 1.13× 和 1.42×（图 11）。
- 15-to-1 incast 与 permutation 共存时，EQDS 将 permutation 流的 P99/P99.9 FCT 降低 4.50×/4.88×，incast 流降低 1.73×/1.72×（图 12）。
- 注入丢包时，UCCL-Tran selective retransmission 在 1/1024 丢包率下性能下降约 6%–30%；作者引用 Flor 的硬件传输结果为 59%–76%（图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 软件控制可以达到硬件级 collective 性能 | CX_IB 中 UC/RC 与 ConnectX-7 接近；图 10 | 16 个 400G NIC，1MB–1GB 消息，NVLink/SHM 关闭 | 强 |
| 多路径软件传输缓解流碰撞 | CX_ETH all-to-all 最高 4.54×；图 7、图 15 | ConnectX-7、特定 fat-tree 拓扑 | 强 |
| 软件扩展能改善真实 ML 应用 | 训练提升 7.5%，serving 延迟改善；图 11 | 16B DeepSeek-V2-Lite；serving 使用 trace-driven 仿真 | 中 |
| 接收端驱动控制和选择性重传有实际收益 | 图 12、图 13 | incast 为构造场景；丢包由软件注入，部分硬件基线来自 Flor | 中 |

## 批判性分析

### 论证链条

论文的链条在“硬件控制难演化—CPU 接管控制—大 chunk 与多核摊薄 CPU 成本—collective 恢复吞吐”这一范围内是闭合的。图 15 的消融支持动态路径选择是主要收益来源。端到端 serving 结果使用 trace-driven emulation，不能完全替代数百 GPU 的真实部署；训练实验也只覆盖一个 MoE 模型族。

### 假设压力测试

UCCL-Tran 依赖 ECMP 的路径熵、GPUDirect 的 DMA 路径和空闲 CPU。若网络采用不同哈希策略、路径数量较少，256 QP 不一定带来 256 条有效路径。若 CPU 与通信线程共享核、发生频繁抢占，软件 RTT 和 ACK 延迟可能破坏控制精度。论文提出可用 ECN 和 packet trimming 增强信号，但当前实现主要依赖 RTT 与丢包，拥塞判断的信息量低于能读取完整包头的 NIC。

### 实验可信度

实验覆盖 NVIDIA、AMD、Broadcom、EFA 和 AF_XDP，并包含 collective、训练、serving、incast、丢包和 CPU 扩展性。局限在于多项比较依赖特定拓扑与参数调优；EFA 的对照是 p4d.24xlarge，作者明确提醒新一代 EFA 结果可能不同。选择性重传的硬件对照部分引用 Flor，而非同一测试床复测。能耗、CPU 成本、生产故障恢复和多租户隔离没有量化。

### 系统性缺陷

控制路径在 CPU 上增加了软件抖动、状态管理和运维面。连接拆分需要维护多个子连接状态，故障恢复时还要保证 GPU buffer、ACK 和重传状态一致。UD 路径依靠 GPU 融合 kernel 做重排，会增加 GPU memory traffic，并要求 NCCL 接口扩展。论文未报告 NIC/CPU 故障、进程重启、滚动升级和跨版本兼容的处理。

## 局限与后续工作

- **局限 1**：GPU-initiated communication 与 CPU transport 的结合尚未实现；论文引用 CPU-assisted IBGDA 可能带来约 10% 性能损失。
- **局限 2**：当前控制信号主要是 RTT 和丢包，无法直接利用 ECN 或 packet trimming 状态；需要 NIC 在 CQE 中暴露这些信息。
- **后续工作 1**：在真实大规模 MoE serving 集群中测量路径热点、P99/P99.9 延迟、CPU 核心占用和故障恢复时间，并与新一代 SmartNIC 和可编程 NIC 比较。
- **后续工作 2**：评估自适应 chunk size 在突发 incast 和高丢包下的收益，明确控制精度、goodput 与 CPU 成本的边界。

## 相关

- **相关概念**：[[RDMA]]、[[Multipath]]、[[Congestion Control]]、[[GPU Networking]]
- **同类系统**：[[Flor]]、[[ZeroNIC]]、[[NCCL]]、[[RCCL]]
- **同会议**：[[OSDI-2026]]
