---
type: paper
name: LogDrive
full_title: "The LogDrive: Composable Durability for Cloud-Based Shared Logs"
authors: [Gardner Vickers, Lucas Bradstreet, Mahesh Balakrishnan, Prince Mahajan, David Mao, et al.]
venue: OSDI
year: 2026
tags: [distributed-storage, shared-log, cloud-storage, durability, replication]
source_pdf: "[[osdi26-vickers.pdf]]"
source_md: "[[osdi26-vickers]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 云共享日志的可组合持久性（OSDI 2026）

> **原题**：The LogDrive: Composable Durability for Cloud-Based Shared Logs

> **一句话总结**：Conflux将durability与sequencing分离：LogDrive只提供可在S3等backend上striping/quorum组合的低层durable append，AtomicLog再提供全局shared-log order；该架构已作为Confluent K2的metadata/state replication层投入生产。

## 问题与动机

以cheap object storage做data plane的cloud service仍需小而强一致的metadata database；DynamoDB昂贵，自管DB复杂。传统shared log把ordering、availability与durability捆绑，难像RAID一样在不同cloud store之上组合成本/latency/failure domain。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

LogDrive暴露低层durable records/positions，不负责全局sequencing；可用shim包裹S3等store，再做striping提高throughput或quorum replication满足durability/availability。AtomicLog在任意LogDrive上构造ordered shared log，Conflux消费它复制arbitrary state machines。分层使storage组合不影响state-machine API。

假设underlying cloud stores的failure independence、durability和consistency semantics可建模；quorum composition若跨同一provider correlated domain会高估安全性。

## 实验与结果

- **成本结果**：代表性workload与latency SLA下，相对直接使用DynamoDB，Conflux-over-DynamoDB将metadata cost降低10×、overall cost降低3×（§6）。
- **对比边界**：在代表性cloud-storage workload与latency SLA下，相对直接使用DynamoDB保存metadata，测量吞吐、延迟与成本（§6）。
- **评测设置**：在论文给定的生产 trace 或代表性工作负载上，对比原系统/现有最佳基线，以吞吐、延迟、资源节省或覆盖率为主要指标（§6）。

- Conflux运行于多种cloud storage与RAID-like composition，展示cost/latency/durability tradeoff。
- 与直接DynamoDB保存metadata相比，代表workload/SLA下Conflux-over-object-store降低成本，同时达到K2需要的吞吐。
- production evidence：部署于Confluent cloud-native publish-subscribe service K2。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

durability/sequencing分离是干净抽象，让共享日志不再固定复制策略。成本结论高度依赖cloud pricing、request billing与object-store tail；shared log workload的小write需要buffer/batch，否则object store天然不匹配。quorum跨backend的真实correlated failure与recovery bandwidth是关键风险。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 跨region/provider故障注入，验证quorum independence与rebuild time。
- 发布完整cost model，纳入request、egress、compaction与tail SLA。
- 探索adaptive LogDrive composition随价格/health在线变化。

## 相关

- **相关概念**：[[Shared-Log]]、[[Quorum-Replication]]、[[Object-Storage]]、[[State-Machine-Replication]]
- **相关系统**：[[Conflux]]、[[Amazon-S3]]、[[DynamoDB]]
- **同会议**：[[OSDI-2026]]
