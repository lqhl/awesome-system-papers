---
type: paper
name: FastACS
full_title: "Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale"
authors: [Sushant Kumar Gupta, Anil Raghunath Iyer, Chang Yu, Neel Bagora, Olivier Pomerleau, et al.]
venue: ATC
year: 2025
tags: [messaging, distributed-systems, rma, google, low-latency]
source_pdf: "[[atc2025-gupta.pdf]]"
source_md: "[[atc2025-gupta]]"
---

# Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale (ATC 2025)

> **一句话总结**：Google 生产部署的 file-based 有序消息系统，跨集群用 RPC、集群内用 [[RMA]] 读基于 [[CliqueMap]] 的内存 chunk cache，给数千 consumer 提供 p99 亚秒级跨洲交付，单 leaf cluster 可推到 1.8 Tbps。

## 问题

实时业务（广告、支付、欺诈检测）需要把 producer 数据低延迟有序送到全球数千 consumer。Kafka 等 pull-based 系统的 broker 受限于 SSD 与 broker 内存：实测 Google Cloud 上 9 partition Kafka 在 14 Gbps consumer throughput 后写读冲突，吞吐崩溃。Pulsar/BookKeeper 的 128MB segment 在 tail-read 时对 consumer fan-out 友好度不够。Push-based 系统又会把 latency-sensitive backend 阻塞掉。生产规模下「ordered + at-least-once + 数千 fan-out + 低延迟」的组合此前没有现成系统。

## 核心方法

Producer append 到 Colossus 文件作为 single source of truth，**多层存储**：
- **Data cache**（内存层）：建在 [[CliqueMap]]（RPC 写、RMA 读）之上；文件按 4KB chunk 分片，key = hash(file path, chunk seq)，r=3 复制，1 分钟 TTL。
- **Metadata cache**：保存文件长度 + lease 锁；24h TTL。
- **Colossus**：作为 fallback，consumer 落后或 cache miss 时读盘。

Reader-writer 沿 Prim 算法构出来的 minimum spanning copy tree（最多 4 跳）跨集群拷贝；reader 用 50ms 间隔 poll metadata cache，data cache 读用 relaxed read（任一 replica）+ consistent read（多数派）混合，30ms 后 hedge。Writer 对 complete chunk 并行写、对 partial chunk 串行（避免 prefix 错误）。Dueling writer 用 metadata cache 里 lease + poison 机制处理 Slicer 弱一致性引入的双写。Consumer 优先读 data cache，只有当 Colossus 比 cache 领先超过 1s 才 fallback（避免 Colossus 限流引发雪崩）。

## 关键结果

- 生产部署在数十个集群，跨大陆 p99 亚秒级到 数秒 交付。
- Experiment 1(a)：单 leaf cluster 7,950 consumer 稳定 70 Gbps / 4.5M QPS data cache 读，p99 message delivery delay ~500ms。
- Experiment 2(a)：horizontal scale 到 20,000 consumer 时 data cache 1.8 Tbps，replica 18 → 481（比预测多 4%），p99 < 2.5s。
- 单 cache replica 故障 quorum 保住；双 replica 同 key shard 故障 60k/s fallback、最高 2s spike，自愈后恢复。

## 相关

- **相关概念**：[[RMA]]、message-delivery、distributed-file-system、tail-latency
- **同类系统**：Kafka、Pulsar、Wormhole、Cloud PubSub、ActiveMQ
- **同会议**：[[ATC-2025]]
