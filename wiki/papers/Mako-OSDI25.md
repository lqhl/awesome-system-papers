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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Mako：具有地理复制的推测分布式事务（OSDI 2025）

> **原题**：Mako: Speculative Distributed Transactions with Geo-Replication

> **一句话总结**：把 2PC 与 geo-replication **解耦**——shard leader 间推测性 2PC、复制后台跑，用 distributed vector clock + vector watermark 把失败回滚限在 epoch 内，TPC-C 10 shard×24 thread 达 3.66M txn/s，比 SOTA geo-replicated 系统高 8.6×。

## 问题与动机

Spanner/FaRM 把 2PC 每步同步 geo-replicate，WAN 延迟主宰 critical path，吞吐比单机多核 DB 低千倍。Tapir/Janus 等反而更紧耦合协调与复制。Mako 论点：WAN 下应**进一步解耦**——leader 内快速 speculative execute+certify，Paxos 复制异步跟进，客户端仍等复制完成才 ACK（强一致）。

## 关键观察 / 隐含假设

- **观察 1**：geo-replication 下提高并发反而因争用降吞吐——transactional workload 与 ML 不同，不能靠 inflight 堆满掩盖 WAN RTT。
  - **依赖假设**：shard leader 常同 datacenter 共址（Uber/Lyft 类地理分片）；跨 DC leader 时用 DPDK 仍不够抵消 WAN。
  - **可能失效场景**：跨 DC 2PC 主导、leader 故意分散；极高冲突 TPC-C 变体。
- **观察 2**：speculative 2PC 在 participant 复制前失败会导致级联 abort——细粒度依赖追踪太贵；vector clock 粗粒度 pairwise 可比即可界定回滚范围。
  - **依赖假设**：epoch 边界集体决策可接受部分 healthy shard 回滚；CM  replicated 始终存活。
  - **可能失效场景**：百万 shard 时 vector clock 宽度与 gossip 开销——论文 §6.1 讨论压缩但未 production 验证。
- **假设 1**：per-core Paxos stream + batch（400 txn）可匹配 leader 多核吞吐，无需全局串行 log。
  - **证据强度**：强；与 Rolis/Silo 路线一致且有 batch watermark 扩展。

## 核心方法

**阶段**：Execute（分布式 OCC）→ Certify（Lock/GetClock/Validate/Install 四轮 RPC，实质 2PC）→ Replication（per-core MultiPaxos stream）→ Replay（vector watermark 安全推进）→ client ACK 当 txn version ≤ watermark。

**Vector clock**：n 维，certify 时取 involved shard max 组合；保依赖单调。

**Failure**：epoch 递增；follower progress-check；粗粒度 rollback 受影响 txn；healthy shard 写 INF 结束 entry 缩小回滚。

## 设计取舍

- **取舍 1**：单 DC 无 geo 时比紧耦合 [[RDMA]] 系统慢 ~50%——设计目标本就是 WAN。
- **取舍 2**：向量时钟粗粒度→可能多 abort 一些无关节点，换 O(1) 依赖元数据。
- **边界条件**：Azure 评测；TPC-C + 多 baseline（Calvin、FaRM、Spanner 类等）。

## 实验与结果

- 10 shards×24 threads：3.66M TPC-C txn/s；8.6× vs SOTA geo-replicated。
- 单 DC：比 RDMA 紧耦合方案低 50%（预期 trade-off）。
- Calvin 等 log-order 方案：吞吐受 replay 限制（§7 实证）。
- Latency：与同步复制方案相近（复制仍 dominate client 等待）。

## 批判性分析

### 论证链条

「解耦→推测→2PC 失败级联」问题识别准确；epoch+vector watermark 是针对「2PC 非 fault-tolerant」的专门发明，文献调研（§5.1）说明非 trivial。与 Aurora/Rolis 流水线相似但多 shard watermark 扩展是贡献。

### 假设压力测试

- **已证明**：Azure geo 设置下吞吐碾压；争用实验支持「高并发无益」论点。
- **可能失效**：极端冲突下推测 abort 风暴；CM 故障恢复复杂度；跨 shard 全失败 3PC 同样级联——Mako 不 magic。
- **论文未覆盖**：交互式长事务；与 Spanner TrueTime 语义对比的 client 延迟 tail。

### 实验可信度

Baseline 选取代表性强；8.6× 醒目但依赖特定 shard/thread 配置。单 DC -50% 诚实披露。

### 系统性缺陷

实现复杂（OCC+2PC+Paxos+watermark+epoch）；运维 CM；vector clock 扩展性待观察；client 仍等 WAN 复制→延迟非 Spanner 级「感觉」。

## 局限与后续工作

- **局限 1**：非 geo 场景不占优；推测失败时 epoch 回滚仍影响吞吐。
- **局限 2**：百万 shard vector clock/watermark gossip 成本。
- **Future work 1**：压缩 vector clock 与 cross-epoch 增量 watermark 的生产测量。
- **Future work 2**：与 disaggregated storage / 持久内存 shard 结合时的 2PC 恢复。

## 相关

- **相关概念**：[[RDMA]]、2PC、OCC、Paxos
- **同类系统**：Spanner、Calvin、FaRM、Tapir、Rolis、Aurora
- **同会议**：[[OSDI-2025]]
