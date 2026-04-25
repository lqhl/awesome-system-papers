---
type: paper
name: SwitchGNN
full_title: Accelerating Distributed Graph Learning by Using Collaborative In-Network Multicast and Aggregation
authors: [Zhaoyi Li, Jiawei Huang, Yijun Li, Jingling Liu, Junxue Zhang, et al.]
venue: ATC
year: 2025
tags: [gnn, in-network-aggregation, programmable-switch, distributed-training, p4]
source_pdf: "[[atc2025-li-zhaoyi.pdf]]"
source_md: "[[atc2025-li-zhaoyi]]"
---

# Accelerating Distributed Graph Learning by Using Collaborative In-Network Multicast and Aggregation (ATC 2025)

> **一句话总结**：用 P4 可编程交换机做 graph-aware 的 in-network multicast + 聚合，把 GNN 全图训练 epoch 时间最多缩短 74%（128-worker Reddit）。

## 问题

分布式 GNN 全图训练每轮 graph propagation 需在 worker 间做大量 one-to-many multicast 与 many-to-one aggregation，通信占 epoch 时间 80%。理想情况下把这两步 offload 到可编程交换机能把流量从 $O(EM^2)$ 降到 $O(EM)$，但直接套用 ATP/SwitchML 那一套 graph-agnostic 方案有两大问题：(1) 顶点依赖复杂，发送顺序随机会让 aggregator 长时间空等／output 队列堆积（10 GB 级 queue backlog）；(2) Reddit 32-worker 需要约 500 MB aggregator，但 Tofino 只有 10–100 MB，~99% 边界顶点存在依赖，溢出后大量流量被旁路回 host，浪费 in-network aggregation 机会。

## 核心方法

SwitchGNN 引入两项 graph-aware 设计：

- **Graph-Aware Multicast Reordering (GAMR)**：以优先级 BFS 决定顶点上送顺序，高度数顶点优先发送、邻居顶点尽量贴近时间窗口，减少 aggregator 等待与队列突发。理论分析星形图 PB 完成时间 $n$，随机顺序平均 $(3n-1)/2$。
- **Multi-level Graph Partitioning**：用 METIS 把连通的边界顶点切成多个 block，确保单 block 顶点数不超 aggregator 容量；切边形成新 block 递归切分，按 block 顺序发送。每个 block 同步完成后 switch 通知 host 发下一个 block。

实现：DPDK host stack + P4 ASIC，自定 32-bit Src/Dst id、16-bit Block_id、Count、ECN、Resend 等头字段；类 ATP 风格的 128 B aggregator；用 packet recirculation 实现一个 packet 多次访问同一 register。深度细节见 [[atc2025-li-zhaoyi]]。

## 关键结果

- 8-worker testbed 上比 BNS-GCN 训练吞吐高 54%、比 G3 高 24%（Ogbn-products / Reddit / Yelp）。
- 128-worker NS3 仿真 Reddit：epoch time 比 BNS-GCN/G3/strawman 分别降 74%/65%/83%。
- Port RocksDB 的 GET+SCAN 实验中切换到 leaf-spine 拓扑后跨 rack 流量降低显著。
- 100 MB switch memory 时流量下降 81%，10 MB 时仅 23%（小内存导致更多 cut-edge 块）。

## 相关

- **相关概念**：[[GNN]]、[[In-Network-Aggregation]]、[[Programmable-Switch]]、[[Graph-Partitioning]]、[[METIS]]
- **同类系统**：ATP、SwitchML、BNS-GCN、G3
- **同会议**：[[ATC-2025]]
