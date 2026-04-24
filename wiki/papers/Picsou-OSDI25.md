---
type: paper
name: Picsou
full_title: "Picsou: Enabling Replicated State Machines to Communicate Efficiently"
authors: [Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu, et al.]
venue: OSDI
year: 2025
tags: [consensus, replicated-state-machine, byzantine-fault-tolerance, cross-cluster, blockchain]
source_pdf: "[[osdi25-frank.pdf]]"
source_md: "[[osdi25-frank]]"
---

# Picsou: Enabling Replicated State Machines to Communicate Efficiently (OSDI 2025)

> **一句话总结**：Picsou 把 TCP 的 cumulative-ACK 思想搬到"RSM 之间"——引入 QUACK（quorum ACK）支持 CFT/BFT/PoS 混用，跨集群通信在无故障时每消息只发一次，比 all-to-all 广播快 3.2-24×。

## 问题

很多场景下两个 Replicated State Machines 需要互相通信：etcd 跨数据中心 disaster recovery、政府/企业间数据对账（两方各自跑自己的 RSM，跨信任域）、blockchain interoperability（跨链资产转移）。现有方案都不理想：

- **Apache Kafka**：最流行方案，但内部靠第三个 RSM 中转状态；只适合 CFT，BFT 场景下成为中心攻击点
- **All-to-all broadcast**（ATA）：一个集群每条消息广播给对方所有节点；WAN 带宽贵，大集群下严重瓶颈
- Ad-hoc 方案、trusted third party、blockchain bridges：要么缺形式化保证、出过大规模资金被盗事件，要么中心化

需求：需要一个同时满足 (1) 强形式化保证，(2) 故障下鲁棒（Byzantine 节点不能破坏正确性也不能无限触发重传），(3) 无故障时开销恒定（单消息 + 常数 metadata），(4) 通用（CFT ↔ BFT ↔ PoS stake-based 任意组合）的 RSM-to-RSM 通信原语。

## 核心方法

先形式化 **Cross-Cluster Consistent Broadcast (C3B)** 原语：RSM A transmit m 到 RSM B，则 B 至少有一个 correct replica deliver m。然后实现 Picsou，设计借鉴 TCP 但针对 many-to-many + UpRight failure model 改造。

核心是 **QUACK**（cumulative quorum acknowledgment）：

- 接收方每个 replica 维护已收消息有序列表，把连续序号最高值 p 放到 ACK(p)——cumulative acknowledgment 意味着"所有 ≤ p 的消息该 replica 都已收到"；ACK piggyback 在反向消息上
- 发送方当收到来自 u+1 个不同 replica 的 ACK(≥p) 时，消息 m_p 形成 QUACK——保证至少一个 correct replica 已收到，可安全 GC
- **重复 QUACK** 反过来用作丢包信号：如果多个 correct replica 反复只 ACK 到 k 而不前进，说明 m_{k+1} 丢了，触发 r+1 duplicate 确认后选举唯一的 retransmitter（sender_new = sender_original + #retransmit mod n_s，不用额外通信）

三个附加机制保证通用性和健壮性：
- 用 **UpRight failure model**（u = 全故障上限，r = 拜占庭故障上限）把 CFT（r=0，2f+1）和 BFT（r=u=f，3f+1）统一
- **Round-robin 轮换 sender-receiver pair**：无故障下每个 pair 最终都配对一次，限制恶意节点持续作恶
- **φ-list（并行 cumulative ACK）**：在 cumulative ACK 之外附加最多 φ 位的 bitmap 表示"已收到的非连续消息"，避免 adversarial drop 场景下串行恢复——多个丢失消息可并行重传
- **Stake-aware 版本**：QUACK 阈值按权重累计，sender-receiver pair 选择用 apportionment 数学避免小 stake 节点被过度轮到

Garbage collection 需处理 Byzantine receiver 伪造 ACK 导致消息过早丢弃的边界情况（让后续 duplicate QUACK 附带高水位 k 使接收端补齐）。

## 关键结果

- Microbenchmark：4 节点时相比 All-to-all 快 **3.2×**，19 节点时最高 **24×**
- etcd cross-DC disaster recovery（us-west-4 ↔ us-east-5，5 节点）：Picsou 让 etcd 跑满 Raft 磁盘 goodput 70 MB/s（有 5× sharding 带宽），Kafka 最多 3 shard 达 150 MB/s 理论值但被 WAN 延迟拖累；Picsou 比 Kafka 最多快 **2×**
- 跨链（Algorand ↔ ResilientDB BFT）：跨 RSM 通信 Picsou 带来的吞吐下降 ≤ 15%，successfully handle Algorand（120 块/秒）和 ResilientDB（6000 batch/秒）之间巨大速差

## 相关

- **相关概念**：[[Replicated-State-Machine]]、[[Byzantine-Fault-Tolerance]]、[[Consensus]]、[[Reliable-Broadcast]]、[[TCP]]、[[Blockchain-Bridge]]
- **相关系统**：Raft、PBFT、Algorand、ResilientDB、etcd、Kafka、Delos、Aegean、GeoBFT、Steward
- **同会议**：[[OSDI-2025]]
