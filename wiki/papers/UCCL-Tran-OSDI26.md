---
type: paper
name: UCCL-Tran
full_title: "UCCL-Tran: An Extensible Software Transport Layer for GPU Networking"
authors: [Yang Zhou, Zhongjie Chen, Ziming Mao, ChonLam Lao, Shuo Yang, et al.]
venue: OSDI
year: 2026
tags: [gpu-networking, rdma, transport]
source_pdf: "[[osdi26-zhou-yang.pdf]]"
source_md: "[[osdi26-zhou-yang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向 GPU 网络的可扩展软件传输层
> **原题**：UCCL-Tran: An Extensible Software Transport Layer for GPU Networking

## 问题与动机

RDMA NIC 把 transport control 固化在硬件中，迭代慢于 ML workload；single-path collision、[[MoE|MoE]] incast 和 loss recovery 因而难以快速适配。完全绕开 NIC 又会失去其高效 data path。

## 关键观察 / 隐含假设

- RDMA data path 可继续由 NIC 执行，transport decision 则可移到 host CPU。
- 软件 control path 足以实现 multipath 等硬件无法快速提供的机制。
- 假设 host CPU budget 可控，NIC 暴露必要队列与状态接口。

## 核心方法

[[UCCL-Tran]]（uTran）解耦 RDMA data/control path：NIC 保留高速数据搬运，host software 执行 transport control，并以 multipath 避免 flow collision。统一接口允许 collective 和 P2P workload 插入新策略。

## 实验与结果

ML collective 在 NVIDIA ConnectX-7 上吞吐最高提高 4.5×，在 Broadcom Thor-2 rail-optimized network 上最高提高 1.9×；相关 workload 的 message tail latency 可改善 4.9×（§7，图 14）。边界是 RDMA-enabled GPU cluster。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 软件 control path 可保持高性能 | ConnectX-7 collective 最高 4.5× | §7 | 强 |
| extensibility 跨 vendor 有效 | Thor-2 仍有最高 1.9× 提升 | 图 14 | 强 |

## 批判性分析

### 论证链条
保留硬件 data path、抽出易变 control path，是对 workload 演化速度与 NIC 固化周期不匹配的直接回应。

### 假设压力测试
CPU 饱和、短消息高 packet rate 或 NIC 接口受限时，软件控制可能成为新瓶颈。

### 实验可信度
跨两家 NIC 与多类 ML communication 增强泛化性；超大规模拥塞稳定性和 CPU opportunity cost 仍需生产 trace。

## 局限与后续工作

- 可扩展 congestion control、failure recovery、security isolation，并验证数千 GPU 网络中的收敛与公平性。

## 相关

- [[OSDI-2026]]
- [[RDMA]]
- [[GPU-Networking]]
