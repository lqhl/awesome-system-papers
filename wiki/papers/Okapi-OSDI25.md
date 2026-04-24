---
type: paper
name: Okapi
full_title: "Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems"
authors: [Sanjith Athlur, Timothy Kim, Saurabh Kadekodi, Francisco Maturana, Xavier Ramos, et al.]
venue: OSDI
year: 2025
tags: [distributed-storage, erasure-coding, cluster-filesystem, hdfs, striping]
source_pdf: "[[osdi25-athlur.pdf]]"
source_md: "[[osdi25-athlur]]"
---

# Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems (OSDI 2025)

> **一句话总结**：Okapi 把集群文件系统里的 data striping 宽度和 erasure code group 宽度解耦，允许独立调优，读吞吐最高提升 80%、seek 减少 70%、EC 转换 IO 开销降 70%。

## 问题

现有集群文件系统（Colossus、Lustre、Ceph、HDFS 等）把 k-of-n 纠删码的数据条带宽度和编码分组宽度强制耦合在一起：文件的 k 个 data block 既用于 striping（跨 k 个盘并行 IO）又用于 grouping（共同计算 parity）。这造成两个根本问题：

1. **性能与空间效率相互制约**：宽 stripe 对超大顺序读有利但对中等读（≤50 MB）tail latency 高、per-byte seek 开销大；宽 group 则更省空间但重建 IO 代价更高。两个维度被迫选同一个 k 值，无法同时满足视频流式服务（要窄 stripe + 宽 group）和大数据批处理（要宽 stripe + 窄 group）等典型场景。
2. **EC 转换 IO 爆炸**：当磁盘老化/数据变冷需要改 EC 方案时，耦合架构必须 re-stripe——把文件所有数据重写一遍。Google 每天 100K+ 次文件级 EC 转换，带来多 PB 的日常 IO。一次 2020 年的磁盘批量故障触发了紧急降 k 操作，瞬间打爆存储集群。

## 问题（续）

HDD 密度继续变大但 bandwidth 不涨，IO-per-TB 已是硬瓶颈，继续耦合越来越贵。

## 核心方法

Okapi 把 stripe width 和 group width 解成两个独立配置。挑战在于如何避免 metadata 翻倍、写路径内存爆炸、降级读放大。三个核心设计：

1. **从 stripe 映射推断 group**：只要约定「group 由连续 data block 组成」，block 编号 x 落在 stripe `⌈x/stripe_width⌉` 和 group `⌈x/group_width⌉`，几个模运算就能推。不用额外维护 group 映射表，metadata 几乎零增长。
2. **Partial parity 写路径**：解耦后 k 个 data block 可能跨多个 stripe，朴素做法要缓存多达几十个 cell 才能算 parity。Okapi 利用 `G×[D1,...,Dk]` 线性可分性，来一个 data block 就算一个 partial parity（G×[0,Di,0,..]）攒在客户端内存里，最后再求和，显著压缩客户端内存。
3. **降级读缓存**：reads 跨多 stripe 时，reconstruct 所需的数据大概率会被后续 stripe read 读到，Okapi 预判并缓存，消除读放大。
4. **Re-grouping 代替 re-striping**：EC 转换时只要读数据重算 parity，不移动数据 block，即可把文件从 k1-of-n1 换成 k2-of-n2。选 `C = LCM(k1,k2)/k2` 个新 group，必要时做少量 block relocation 以满足 failure domain 要求。

作者在 HDFS 上实现了 Okapi 以做 apples-to-apples 对比，同样思路可套到 Ceph、Colossus、PanFS。

## 关键结果

- 对 12-of-15 EC 文件读 8 MB：读吞吐提升最高 **115%**（6-of-9 EC 下最高 80%）；seek 减少最高 **70%**。
- Google 派生的只读工作负载端到端客户端延迟降 **36%**。
- EC 转换 IO：相对 read–re-encode–write 降最多 **50%**；结合 smart EC-transition 技术降最多 **70%**。
- metadata 和文件管理器内存只增加 < 1%。
- 用 Google 紧急降 k 场景和 Backblaze 磁盘失败日志分析，长期 disk-adaptive redundancy 场景省 38–45% IO。
- mid-sized 降级读的读放大最多增加 2×，但作者认为在实际 workload 下可接受。

## 相关

- **相关概念**：Erasure-Coding、Reed-Solomon、Disk-Adaptive-Redundancy、Data-Striping
- **同会议**：[[OSDI-2025]]
