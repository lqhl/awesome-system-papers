---
type: paper
name: CRAFT
full_title: "CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations"
authors: [Adrian Zhao, Zhenkun Cai, Zhenyu Song, Lingfan Yu, Haozheng Fan, Jun Wu, Yida Wang, Nandita Vijaykumar]
venue: MLSys
year: 2026
tags: [moe, expert-parallelism, load-balancing, llm-serving, expert-replication]
source_pdf: "[[17e62166fc8586dfa4d1bc0e1742c08b.pdf]]"
source_md: "[[17e62166fc8586dfa4d1bc0e1742c08b]]"
---

# CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations (MLSys 2026)

> **一句话总结**：观察到 MoE expert replication 存在 per-layer 收益差异大且整体 sublinearly 递减，用 per-layer benefit 估计 + MCKP 动态规划分配 replica 预算，在 DeepSeek-R1-671B 和 Kimi-K2-1T 上相比 EPLB 均匀复制平均 1.14×（最高 1.2×）throughput，同时显著降低显存占用。

## 问题

[[MoE]] 用 [[Expert-Parallelism]]（EP）切分专家，但 router 的 Zipfian 分布导致严重的 expert 级负载不均——少数 hot expert 成为整个 GPU 的瓶颈，all-to-all dispatch 也堵塞。主流做法 EPLB 采用「每 GPU 每层 1 个 replica」的均匀复制来缓解，但在 60-层 MoE + 千亿参数模型下显存开销巨大，挤占 [[KV-Cache]]。本文做了两个关键观察：
- **Observation 1**：各层对 replication 的收益差异大。高 skew 层（hot expert 承担 >27× 平均负载）replication 效果显著；低 skew 层 placement 已够用，replication 近乎浪费。
- **Observation 3/4**：Balancedness 随 replica count **sublinearly** 增长，>16 replicas/layer 收益可忽略；plateau 点因层而异。

EPLB 均匀复制因此严重过度复制，大量 replica 边际贡献极小。

## 核心方法

CRAFT 以 per-layer 粒度按 replication benefit 分配 replica 预算，三步走：

**Step 1 — 估计 per-layer replication benefit**：对每一层，在 base-2 几何级数的 K = log₂D + 1 个 replica count 上 replay 离线 expert load 分布，测量 balancedness gain，得到 L × K 收益矩阵 T。

**Step 2 — 确定 replication factor R**：用户手动指定，或 CRAFT 自动挑选 per-replica gain 最高的 R（避开边际递减区）。

**Step 3 — MCKP 分配**：把问题建模成 Multiple-Choice Knapsack Problem：每层选一个 replica count，总数 $\le R \times D$，最大化累计 benefit。NP-hard 但 D、K、L 规模小，动态规划在 pseudo-polynomial 时间内求解。

**Capacity-Aware Expert Assignment**：因为 per-layer replica 数不同，直接分配会导致 GPU 间 expert capacity 和 KV cache 大小不一致（影响 DP rank 内最大并发）。用贪心 + 两个目标解决：
- **Primary**：新 replica 总分给 expert 数最少的 GPU（保证 R = r/D 整除后各 GPU memory 一致）。
- **Secondary**：并列时 interleaved 分配到不同 node 以平衡节点级 capacity。

最终套用标准 greedy placement（最 hot expert → 最 cold device）。

无需训练或模型修改，可直接替换 [[SGLang]] / [[vLLM]] / TensorRT-LLM / DeepSpeed 的 EPLB 模块。

## 关键结果

- 在 8 节点 p4de.24xlarge（64× A100-80GB）集群，SGLang v0.4.8 基础上实验。
- DeepSeek-R1-671B（58 MoE 层，256 experts）和 Kimi-K2-1000B（60 MoE 层，384 experts），top-8 路由。
- 相比 EPLB 均匀复制，端到端 goodput 平均 **1.14×**，最高 **1.2×**；CRA8 比 EPLB 少分配 **7.25–7.5×** replica 仍保留大部分 balancedness gain。
- TTFT 平均降 **29%**（vs BASE），与 EPLB 相当。
- 小集群（6 节点）上 EPLB 因 KV cache 被挤掉 75% 反而慢于 BASE；CRA8 仅减 6% KV cache，仍比 BASE 快 **1.14×**。
- R = 8 是 sweet spot；>16 replica/layer 几乎无额外 balancedness gain。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[KV-Cache]]
- **相关系统**：[[SGLang]]、[[vLLM]]、EPLB
- **同会议**：[[MLSys-2026]]