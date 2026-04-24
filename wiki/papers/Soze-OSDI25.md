---
type: paper
name: Soze
full_title: "Söze: One Network Telemetry Is All You Need for Per-flow Weighted Bandwidth Allocation at Scale"
authors: [Weitao Wang, T. S. Eugene Ng]
venue: OSDI
year: 2025
tags: [networking, bandwidth-allocation, telemetry, datacenter, congestion-control]
source_pdf: "[[osdi25-wang-weitao.pdf]]"
source_md: "[[osdi25-wang-weitao]]"
---

# Söze: One Network Telemetry Is All You Need for Per-flow Weighted Bandwidth Allocation at Scale (OSDI 2025)

> **一句话总结**：只用商品以太网交换机的 queueing delay 一项 INT 信号作为协调通道，去中心化地收敛到 per-flow weighted max-min fair 分配，把 TPC-H 作业平均 JCT 压到 0.79×。

## 问题

数据中心 weighted bandwidth allocation 能满足 ML 训练、Spark/Hadoop、RPC 等多样化 SLO 需求（给 critical path、straggler 或重要 job 倾斜带宽），但现有方案都有硬伤：交换机 packet scheduling 受限于 per-flow 队列数和权重粒度；logical centralized 带宽分配器（如 BwE）有高通信延迟和计算开销，agility 差。

要在大规模云上做到细粒度、高敏捷、去中心化的加权分配，难点有四：（1）bottleneck 动态变化且不可预测；（2）需要海量信息；（3）权重粒度必须细；（4）需要快速响应流量和权重变化。

## 核心方法

核心洞察：每条 flow 路径上只需要**一个** telemetry 信号就够，不管跳数是多少。Söze 巧妙地把 queueing delay 从传统的「拥塞度计量」重新诠释为「bottleneck 上 weighted fair share 的编码」。

算法推导：把加权公平公式拆成两个充分必要条件——总到达率等于带宽 B，所有 flow 的 `r/w` 相等。Söze 用交换机上的 queueing delay 同时表达这两个等式：（1）delay 稳定在非零值意味着 arrival rate = B；（2）把目标 delay 设计成 `r/w` 的单调递减函数 `T(r/w)`，每个 sender 观察到的 delay 值就告诉它自己的 `r/w` 应该和大家统一到什么值。每个 sender 根据本地观察独立调整速率 `r_k ← r_k · (T⁻¹(D) / (r_k/w_k))^m`，证明了在 `0<m<2` 时收敛到 weighted max-min fair。

交换机侧只要 9 行 Tofino P4 代码输出平滑后的 queueing delay，ACK 把信号带回 sender，无需编程交换机或 per-flow 状态。任意拓扑下取路径上最大 queueing delay 即可正确识别 bottleneck。

## 关键结果

- TPC-H 22 个 job 在 NS-3 模拟 1024 服务器 fat-tree 上：平均 JCT 降低 0.79×，最大降低 0.59×
- eRPC testbed（4 servers + Tofino-1）上展示了 critical path 优先、coflow straggler mitigation 等多种应用场景
- 收敛到 weighted fair share 仅需几个 RTT
- 相比 DCQCN、HPCC，Söze 既能做 congestion control 又能做 weighted allocation

## 相关

- **相关概念**：[[Queueing-Delay]]、[[INT]]
- **同会议**：[[OSDI-2025]]
