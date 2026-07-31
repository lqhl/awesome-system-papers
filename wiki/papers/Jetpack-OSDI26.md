---
type: paper
name: Jetpack
full_title: "Jetpack: Consensus Made Generally Fast"
authors: [Ze Tang, Zihao Zhang, Weihai Shen, Jicheng Shi, Shuai Mu]
venue: OSDI
year: 2026
tags: [distributed-systems, consensus, replication, fast-path, geo-distribution]
source_pdf: "[[osdi26-tang.pdf]]"
source_md: "[[osdi26-tang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 可插件化的一轮往返共识快路径（OSDI 2026）

> **原题**：Jetpack: Consensus Made Generally Fast

> **一句话总结**：Jetpack让request同时走1-RTT commutativity fast path和原consensus path，fast成功即可提交、原路径必须honor同一decision；以结构条件处理view-change hazard，在六个系统/10个AWS datacenters上commit latency最多降60%。

## 问题与动机

Raft/MultiPaxos client commit通常2 RTT；EPaxos等1 RTT fast path与协议深度耦合，成熟系统无法替换。简单gateway会破坏batching、slow-replica tolerance。难点是fast path承诺跨leader election/view change仍有效，否则新leader可能提交冲突decision。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

client并发发送到fast replicas与original leader path。无冲突/可交换command由supermajority在1 RTT确认；conflict/failure回退原路径。Jetpack总结fast layer必须满足的两项结构要求与两条设计原则，使view-change收集到足以继承fast promise的evidence，原路径随后只能决定同值。original clients可完全不走fast path且无额外串行gateway。

## 实验与结果

- **评测设置**：在论文给定的生产 trace 或代表性工作负载上，对比原系统/现有最佳基线，以吞吐、延迟、资源节省或覆盖率为主要指标（§6）。

- 集成六种consensus systems，在10 AWS regions/datacenters测试。
- fast path达1 RTT，平均commit latency最高下降60%。
- 禁用/失败fast path时保留original throughput、batching与failure properties；冲突率/leader change sweep展示fallback。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

最大价值是抽取fast-path correctness条件而非再发明一个协议。双路径会增加网络/replica work，在高冲突或高load时fast多失败却仍付成本。commutativity specification若错误会破坏安全性；跨view proof虽关键，工程集成仍需逐系统确认log/command semantics。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 形式化验证每个host protocol适配与Byzantine扩展。
- 用online conflict predictor选择是否发fast path，控制冗余流量。
- 生产数据库transaction、reconfiguration与membership churn评估。

## 相关

- **相关概念**：[[Consensus]]、[[Fast-Path]]、[[State-Machine-Replication]]、[[View-Change]]
- **相关系统**：[[Raft]]、[[MultiPaxos]]、[[EPaxos]]
- **同会议**：[[OSDI-2026]]
