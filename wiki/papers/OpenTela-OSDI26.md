---
type: paper
name: OpenTela
full_title: "OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving (Operational Systems)"
authors: [Xiaozhe Yao, Youhe Jiang, Ilia Badanin, Qinghao Hu, Robert Matthew Smith, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, hpc, orchestration, crdt, sovereign-ai]
source_pdf: "[[osdi26-yao.pdf]]"
source_md: "[[osdi26-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 统一去中心化异构资源的 [[LLM|LLM]] Serving 平台（OSDI 2026）

> **原题**：OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving (Operational Systems)

> **一句话总结**：OpenTela用无需root的user-space overlay跨Slurm/HPC机构提供CRDT gossip discovery、统一serving API与异构感知调度；22个月服务1,300万requests、150亿tokens、142 models和逾1,000 researchers。

## 问题与动机

sovereign AI资源多是batch-oriented HPC：allocation短暂、compute node不对外、无Kubernetes service discovery/load balancing，且GPU跨cluster/domain碎片化。单独划serving partition会与training争抢并造成idle。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

各allocation内agent通过CRDT-based gossip维护service/node状态，即使部分cluster不可达也能最终收敛；gateway统一vLLM/SGLang与cluster manager API并路由。scheduler基于GPU memory/model parallelism、queue与profile latency在异构GPU间做max-flow-like placement。所有组件user space运行，不要求管理员重配HPC。

## 实验与结果

- **Trace结果**：production model的prefix reuse ratio最高超过90%，reasoning request的P95 E2E latency相对non-reasoning request高5.5×（§6）。
- **生产边界**：22个月跨机构cluster trace包含13M requests和15B tokens；相对默认异构调度基线，比较mean end-to-end latency与aggregate throughput（§5）。
- **评测设置**：在论文给定的生产 trace 或代表性工作负载上，对比原系统/现有最佳基线，以吞吐、延迟、资源节省或覆盖率为主要指标（§6）。

- 22个月跨机构production：13M requests、15B tokens、142 models、1,000+ researchers。
- control-plane overhead、failure recovery与跨cluster scaling实验展示continuity；heterogeneity-aware policy降低mean E2E latency。
- 公开system与匿名production trace，增强可复现性。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

长期真实部署是最大贡献，解决组织边界而非单engine kernel。但gossip eventual consistency可能短暂路由到dead/stale replica；跨机构identity、quota、privacy与accounting比技术discovery更难。mean latency调度可能牺牲tail/fairness，WAN model transfer也昂贵。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 强化multi-tenant auth、audit、quota与data sovereignty。
- 报告P99、stale-state误路由和WAN partition恢复。
- 联合batch scheduler以可证明方式共享training/serving capacity。

## 相关

- **相关概念**：[[CRDT]]、[[Service-Discovery]]、[[Heterogeneous-Scheduling]]、[[Sovereign-AI]]
- **相关系统**：[[Slurm]]、[[vLLM]]、[[SGLang]]
- **同会议**：[[OSDI-2026]]
