---
type: paper
name: Mako
full_title: "Mako: Speculative Distributed Transactions with Geo-Replication"
authors: [Weihai Shen, Yang Cui, Siddhartha Sen, Sebastian Angel, Shuai Mu]
venue: OSDI
year: 2025
tags: [distributed-transactions, geo-replication, 2pc, speculation, key-value-store]
source_pdf: "[[osdi25-shen-weihai.pdf]]"
source_md: "[[osdi25-shen-weihai]]"
---

# Mako: Speculative Distributed Transactions with Geo-Replication (OSDI 2025)

> **一句话总结**：把 2PC 和 geo-replication **解耦**而非进一步耦合——让 2PC 在 shard leader 间推测性提交、replication 在后台跑，再用 distributed vector clock + vector watermark 把失败后的级联回滚限制在单个 epoch 内，TPC-C 上比 SOTA geo-replicated 系统吞吐高 8.6×（3.66M txn/s）。

## 问题

Spanner / FaRM 这类强一致 geo-replicated 事务系统把 2PC 决策同步复制到远端数据中心，结果 WAN 延迟支配 transaction critical path，吞吐常比单机多核数据库低千倍。Tapir / Ocean Vista / Janus 的思路是把协调和复制**更紧地**耦合进单协议，Mako 反其道而行：应当**更彻底地解耦**，让协调在数据中心内飞速跑、复制异步跟进。

但这引出一个难题：一旦 leader 在 replication 完成前挂掉，依赖它的后续 transaction 都要级联 abort。2PC 本身不是 fault-tolerant，3PC 也只能对单 transaction 生效、无法跨 transaction 防级联。Calvin 式预先排序日志又跑不过多核 Silo。已有速度或容错方案在 Mako 设定下都不适用。

## 核心方法

Mako 是一个分片、geo-replicated、serializable 的内存 K-V 事务存储。

- **Speculative 2PC**：shard leader 在同数据中心通过 [[DPDK]] 跑 4-round 2PC（Lock → GetClock → Validate → Install）完成**certification**，写 speculatively 可见；不等 replication 就返回继续处理下一个 txn。客户端在 replication 完成后才收到 ACK。
- **Distributed vector clock**：每 shard 维护一个 logical clock，每 txn 的版本是 `(c₀,...,c_{n-1})` vector。不变式：若 T₁ 依赖 T₂，T₁ 的 vector clock 各维度都 ≥ T₂。原子 `fetch_and_add` 生成 clock。shard 数量大时压成 20 个槽的 fixed-size vector（合并最大值，牺牲一些独立性以保可扩展）。
- **Per-core Paxos stream**：每 core 独立 MultiPaxos 流，避免单 Paxos 流过 ~10 线程后的同步瓶颈；batch 400 txn/entry 摊销 RPC 开销。
- **Vector watermark + 安全 replay**：每 shard 独立维护 watermark，gossip 交换后聚合成全局 vector watermark；follower 只 replay 「vector clock ≤ watermark」的 txn，用 Thomas write rule 并发无协调重放。
- **Epoch-based failure recovery**：shard 挂了就 CM 触发 epoch 自增；新 leader 重提交可恢复的 log、no-op 填不可恢复 slot，关闭 old epoch 并算 finalized vector watermark (FVW)。所有超过 FVW 的 speculation 一次性废弃——**级联 abort 被强制限制在单 epoch 内**，不会跨 epoch 传播。healthy shard 不被失败 shard 阻塞（除非事务触到它）。

## 关键结果

- TPC-C 10 shards × 24 threads：3.66M txn/s，比 SOTA geo-replicated 系统高 8.6×，且额外延迟很小
- 单数据中心无 geo-replication 情形下，Mako 比紧耦合 RDMA 系统（如 FaRM 变体）低 50%（不是 Mako 的设计目标场景）
- 可扩展到大量 shards：vector clock 压到常数 20 时仍保持良好吞吐；vector watermark 即使 10000 shards 也只有 40 KB
- Straggler tolerance：单 shard 慢不会阻塞无关 txn，因为 watermark 是 per-shard 独立的维度

## 相关

- **相关概念**：[[2PC]]、[[Paxos]]、[[Vector-Clock]]、[[Speculative-Execution]]、[[Geo-Replication]]、[[DPDK]]
- **同类系统**：Spanner、FaRM、Calvin、Ocean Vista、Janus、Rolis、Aurora
- **同会议**：[[OSDI-2025]]
