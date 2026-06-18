---
type: paper
name: NEST
full_title: "NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning"
authors: [Irene Wang, Vishnu Varma Venkata, Arvind Krishnamurthy, Divya Mahajan]
venue: MLSys
year: 2026
tags: [device-placement, distributed-training, network-topology, dynamic-programming, zero]
source_pdf: "[[37693cfc748049e45d87b8c7d8b9aacd.pdf]]"
source_md: "[[37693cfc748049e45d87b8c7d8b9aacd]]"
---

# NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning (MLSys 2026)

> **一句话总结**：NEST 用网络-计算-内存联合 DP 在真实分层/oversubscribed 拓扑上搜索 hybrid 并行策略，较 Alpa/MCMC 等基线吞吐最高 **2.43×**，并可在 1000+ GPU 上保持可扩展搜索。

## 问题

分布式训练需同时权衡 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、data/expert/sequence/context parallel 与 ZeRO，而 Alpa、TopoOpt 等要么简化网络为 2D mesh、要么 post-hoc 才检查内存，导致 over-sharding、通信膨胀与 >64 GPU 扩展失效。真实数据中心网络分层、带宽不对称，collective 成本随 placement 剧变。

## 核心方法

**正交策略分类**：SUB-GRAPH（TP/EP/SP/CP，离线 profile 后嵌入 cost）与 GRAPH-GLOBAL（PP/DP/ZeRO，DP 显式搜索）解耦，避免组合爆炸。

**Level-wise network abstraction**：DP 反向放置时，前向激活来源未知；用 3–5 个通信 locality level（intra-node/rack/remote）抽象延迟，恢复 optimal substructure。

**联合 cost model**：每层 latency = compute + collective（前向/反向）+ ZeRO/recomputation 内存决策；内存约束内嵌于 DP 转移，非事后裁剪。

## 关键结果

- Fat-tree TPUv4-like 集群平均吞吐较 manual **1.59×**、MCMC **1.71×**、Alpa-E **2.43×**、Phaze **1.19×**
- 1000+ accelerator 近线性扩展；GPT3-175B 等可在内存约束下自适应 ZeRO stage
- 内存模型与实测平均误差 **<7%**

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]
- **同类系统**：Alpa、TopoOpt、Phaze、Mist、Megatron-LM
- **同会议**：[[MLSys-2026]]