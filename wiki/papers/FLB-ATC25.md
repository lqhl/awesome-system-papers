---
type: paper
name: FLB
full_title: "FLB: Fine-grained Load Balancing for Lossless Datacenter Networks"
authors: [Jinbin Hu, Wenxue Li, Xiangzhou Liu, Junfeng Wang, Bowen Liu, et al.]
venue: ATC
year: 2025
tags: [datacenter-network, load-balancing, rdma, pfc, congestion-control]
source_pdf: "[[atc2025-hu-jinbin.pdf]]"
source_md: "[[atc2025-hu-jinbin]]"
---

# FLB: Fine-grained Load Balancing for Lossless Datacenter Networks (ATC 2025)

> **一句话总结**：揭示细粒度 load balancing 在 PFC-enabled lossless DCN 里反而扩大 HoL blocking——FLB 通过 threshold-free rerouting + 拥塞流隔离把 PFC PAUSE 减 96%、相比 LetFlow+Swift / MP-RDMA / Proteus 平均 FCT 降 18–40%。

## 问题

[[RoCE]] + [[PFC]] 在 lossless DCN 里普及，但 PFC PAUSE 会传播 back-pressure 引发全网 paralysis。同时多路径 LB 是必需的。作者实验发现：**flowlet-based LB（CONGA / LetFlow）在 lossless DCN 里 flowlet gap 几乎不出现**（RDMA + rate shaper），无法灵活分流；**packet-level / flowcell-level LB 反而把 congested flow 撒到所有 path，让所有 upstream port 都被 PFC PAUSE**——31-to-1 incast 下 packet spraying 让 ~340 条 path 全 paused，而 ECMP 只 paused 70 条。congestion control（DCQCN/Swift/HPCC/PCN）也救不了，因为微突发 < 1 RTT 不可控。

## 核心方法

设计目标三条：normal 下灵活 reroute / 拥塞下消除 HoL blocking / 最小依赖 congestion control。两个核心模块：

1. **Threshold-free flexible rerouting**（Algorithm 1）：每个 packet 都尝试切换到延迟最小的 path，**约束条件**是「current path 与 target path 的延迟差 < 当前 packet 与上一 packet 间隔」——这样保证不会乱序。延迟用 source edge switch 周期采样的 one-way delay（减 base delay 处理时钟不同步）。flowlet 必出现的弱场景下也能 reroute。
2. **Congested flow isolation**：egress queue 超过 isolation threshold 时，downstream switch 生成 CNM 带上 flow ID + 拥塞流数 n 回传 source edge switch；source 把这些拥塞流 consolidate 到最少数量的 isolation path（数量 = 总收敛速率 / 单链路带宽），其余 uncongested flow 走剩余 path。queue 落回阈值后通过 non-congestion CNM 释放。

可选 minimal rate control：sender 默认 line rate 发，收到 CNM 直接 set rate `C/n`，跳过迭代收敛。基于 Wedge 100BF-32X P4 switch 实现，资源占比不到 10%。

## 关键结果

- Web Search 真实 workload，testbed 20 server + P4 switch，FLB 相比 ECMP+DCQCN/LetFlow+DCQCN/MP-RDMA 平均 FCT 降 48% / 42% / 30%；99th percentile 提升最多 88%。
- PFC PAUSE rate 比对照降最多 96%；link utilization 在 Web Search 下相比 LetFlow / LetFlow+DCQCN / MP-RDMA 高 78% / 144% / 28%。
- 大规模 NS3 模拟（16 spine × 32 leaf Clos）下 FLB+RC 比 LetFlow+DCQCN / MP-RDMA / Proteus+DCQCN 降 AFCT 70% / 36% / 29%。
- Goodput 相比 CONGA+DCQCN 提 45%。

## 相关

- **相关概念**：[[RDMA]]、[[RoCE]]、[[PFC]]、ECMP、flowlet
- **同类系统**：CONGA、LetFlow、MP-RDMA、Proteus、Swift、DCQCN、PCN、HPCC
- **同会议**：[[ATC-2025]]
