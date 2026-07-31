---
type: paper
name: Pompe-SRO
full_title: "Equal Opportunity: A Correctness Condition for Ordered Consensus"
authors: [Yunhao Zhang, Haobin Ni, Soumya Basu, Shir Cohen, Maofan Yin, et al.]
venue: OSDI
year: 2026
tags: [consensus, blockchain, fairness, ordering, verifiable-randomness]
source_pdf: "[[osdi26-zhang-yunhao.pdf]]"
source_md: "[[osdi26-zhang-yunhao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Ordered Consensus 的机会平等正确性条件（OSDI 2026）

> **原题**：Equal Opportunity: A Correctness Condition for Ordered Consensus

> **一句话总结**：论文指出ordering linearizability无法阻止低网络延迟参与者系统性front-running；以equal opportunity要求同等qualified requests获得相同排序机会，并用Secret Random Oracle构造Pompe-SRO，保持约1,893 cmd/s但latency增加1.12×–1.42×。

## 问题与动机

SMR只要求全序，ordered consensus限制Byzantine influence，却不约束timestamp重叠请求；网络更快的adversary可合法抢先/夹击并获利。

## 关键观察 / 隐含假设

- fairness应区分relevant qualification与irrelevant network advantage。
- 在候选近似同等时引入不可预测randomness可界定ordering bias。
- randomness须fault-tolerant且commit前对攻击者保密。

## 核心方法

equal-opportunity condition形式化候选slot selection probability；SRO提供secret-then-reveal random value，有SGX trusted hardware与threshold VRF两种实现。Pompe-SRO在原timestamp order的ambiguous window用SRO打散，保留清晰先后请求的ordering linearizability。

## 实验与结果

- **设置**：12 CloudLab geo nodes/80-node simulation、front-running/sandwich attacks，对比Pompe与HotStuff，以bias、throughput、P50/P99 latency为指标（§6）。
- attack成功偏差显著降低；Pompe-SRO 1,893 cmd/s vs Pompe 1,842。
- latency为Pompe的1.12×–1.42×；TEE random约3µs，TVRF combine 67 shares约6.3ms。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| equal opportunity缓解ordering attack | 图 10 | threat/model assumptions | 强 |
| cost moderate | 图 12 | geo setup | 强 |

## 批判性分析

### 论证链条

论文从现有correctness允许的真实经济攻击出发，新condition与random oracle直接封堵network advantage。

### 假设压力测试

“equally qualified”的criteria本身可能争议；adversary可操纵arrival window、censor或在应用层抢跑。

### 实验可信度

attack simulation与prototype支持机制，但金融outcome/model简化，TEE/TVRF trust取舍不同。

## 局限与后续工作

- dynamic membership、MEV市场与censorship fairness。
- 无trusted hardware的低latency SRO。

## 相关

- **相关概念**：[[Consensus]]、[[Blockchain-Fairness]]、[[Verifiable-Random-Function]]、[[Front-Running]]
- **相关系统**：[[Pompe]]、[[HotStuff]]
- **同会议**：[[OSDI-2026]]
