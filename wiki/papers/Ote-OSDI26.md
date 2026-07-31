---
type: paper
name: Ote
full_title: "Extracting Database Access-Control Policies From Web Applications"
authors: [Wen Zhang, Dev Bali, Jamison Kerney, Aurojit Panda, Scott Shenker]
venue: OSDI
year: 2026
tags: [access-control, web-application, database, concolic-execution, policy-mining]
source_pdf: "[[osdi26-zhang-wen.pdf]]"
source_md: "[[osdi26-zhang-wen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 从 Web 应用抽取数据库访问控制策略（OSDI 2026）

> **原题**：Extracting Database Access-Control Policies From Web Applications

> **一句话总结**：Ote对Ruby on Rails做query-focused concolic execution，记录“什么条件触发什么SQL”，再合并/规范化为可审阅策略；LLM relevance judge剪掉与数据访问无关分支，将可能数天的探索降到数小时，并在三款应用发现手写policy错误。

## 问题与动机

legacy web app把access control散落在checks、ORM scopes与SQL filters，既难审计也无法交给外部DB proxy enforcement。完整symbolic execution面临branch explosion；目标不是自动猜意图，而是提取代码实际允许的data accesses供人审核。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

Ote只symbolically track影响query/condition的小类operations，执行路径产生带path predicate的SQL transcript；之后将conditioned queries转relational normal form、merge和simplify。[[LLM|LLM]] judge判断branch是否与data access相关，人工hints处理难模型的framework semantics；review后的policy可独立enforce。

## 实验与结果

- **评测设置**：在论文给定的生产 trace 或代表性工作负载上，对比原系统/现有最佳基线，以吞吐、延迟、资源节省或覆盖率为主要指标（§6）。

- 三个real Rails applications与handwritten policies比较，抽取结果发现后者多个错误。
- 大型schema（如50 tables）可处理；超过80% hints自动生成，其余人工补充。
- relevance pruning把潜在days级exploration压至hours。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

Ote提取observed/code-reachable policy，不证明它符合developer intent，也不保证concolic coverage完整。LLM pruning若误判相关branch会静默漏策略，安全工具应给coverage/uncertainty。dynamic SQL、native extension、external service与reflection会突破模型。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 用sound conservative fallback与coverage proof约束LLM pruning。
- 扩展其他framework/language、dynamic SQL与microservices。
- 将抽取policy接入runtime monitor，比较新版本行为差异。

## 相关

- **相关概念**：[[Concolic-Execution]]、[[Access-Control]]、[[Policy-Mining]]、[[Database-Security]]
- **同会议**：[[OSDI-2026]]
