---
type: paper
name: Nostor
full_title: "Stripeless Data Placement for Erasure-Coded In-Memory Storage"
authors: [Jian Gao, Jiwu Shu, Bin Yan, Yuhao Zhang, Keji Huang]
venue: OSDI
year: 2025
tags: [erasure-coding, in-memory-storage, rdma, kv-store, fault-tolerance]
source_pdf: "[[osdi25-gao.pdf]]"
source_md: "[[osdi25-gao]]"
---

# Stripeless Data Placement for Erasure-Coded In-Memory Storage (OSDI 2025)

> **一句话总结**：Nos 抛弃"stripe"概念、用组合数学 SBIBD 决定 primary-to-backup 拓扑，让 RDMA 内存 KV-store Nostor 以 XOR 异或编码实现多故障容忍，吞吐比条带化 EC 提升 1.61-2.60×。

## 问题

RDMA 内存 KV-store 需要容错但内存昂贵。传统 erasure coding（EC）省空间，但都以 **stripe** 为基本单位——每个 chunk 必须属于一个 stripe，这在 fast in-memory 场景暴露硬伤：

- **Intra-object**（Ceph、EC-Cache、Hydra）：对象切成 k 个 chunk 分放到 k 个节点，80% 的 KV 小对象（<1 KB）读写要联络 k 或 k+p 个节点，IO fanout 炸穿网络
- **Inter-object 静态分配**（哈希定 stripe）：stripe 内空位浪费内存；无法感知节点临时慢速
- **Inter-object 动态分配**（Cocytus、LogECMem 等）：要中心化 metadata service 查 stripe → 读写多一跳 + 瓶颈 + SPoF

stripe 的存在是历史包袱（来自多 chunk 故障恢复需要线性无关的编码矩阵），但它和 fast memory 的访问模式不合。

## 核心方法

Nos 完全抛弃 stripe。每个 primary 节点**独立**把对象 replica 发给若干 backup，后者**独立**把收到的 k 个 replica 异或（XOR）成一个 parity，不需要任何中心协调。两个参数：
- `p` 决定容错：每对象复制 (p+2) 次（1 primary + (p+1) backup），容 p 节点故障
- `k` 决定存储开销：每个 parity XOR k 个对象副本，放大因子 (p+1)/k

关键洞察：抛弃 stripe 仍能多故障恢复的前提是"primary-to-backup 拓扑要保证任两个 primary 不会把对象同时复制到同两个 backup"。作者证明这对应组合数学里的 **SBIBD（Symmetric Balanced Incomplete Block Design）**——一个 v×v 的 0/1 矩阵，每行每列恰 k 个 1，任两行恰共享 1 个 1 列。SBIBD 约束 v = k²−k+1，对常用 k（3,4,5,6,8,10,12,14）都存在可高效构造（cyclic rotation from topmost row）。

恢复逻辑分两种：
- **直接恢复**：故障对象 x 的某 parity P 只编码了一个故障对象（就是 x），读剩下 k−1 个 alive 对象 XOR 出 x
- **递归恢复**：当 (p+3)/2 以上节点故障时可能 x 的所有 parity 都同时编码其他故障对象 y；SBIBD 性质保证总存在一个 parity 能直接恢复 y，再回去恢复 x

Nostor 是基于 Nos 的 Rust RDMA KV-store。primary 节点从 k 个候选 backup 中选 (p+1) 个，可避开临时慢节点；用 version-based 方法处理常规 I/O、degraded I/O 和节点修复的一致性。

## 关键结果

- 实际 workload 吞吐提升 **1.61×-2.60×**（相比 Cocytus / PQ / Split 等条带化 EC baselines），中位/平均延迟持平或更低
- 内存比 3 副本复制节省 **18.7-57.4%**，但性能往往追平 replication
- 节点修复时间提升 16.4%
- 节点临时 slowdown 实验（2 node +1ms 延迟）：Cocytus 尾延迟飙 48.2×、吞吐掉 98.9%；Nostor 只在 primary 被拖时有 ms 级尾延迟，可切换 backup 节点
- 代价：最坏情况 degraded read 要递归恢复，比 Cocytus 慢 35%、比 Split 慢 62.4%

## 相关

- **相关概念**：[[Erasure-Coding]]、[[RDMA]]、[[Combinatorial-Design]]、[[SBIBD]]、[[Replication]]、[[KV-Store]]
- **相关系统**：Cocytus（condition stripe-based EC KV-store）、LogECMem、EC-Cache、Hydra、Carbink、HDFS、f4
- **同会议**：[[OSDI-2025]]
