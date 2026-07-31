---
type: paper
name: Alibaba-ASI
full_title: "Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba (Operational Systems)"
authors: [Suyi Li, Lingyun Yang, Haoxuan Yu, Sheng Yao, Tianyuan Wu, et al.]
venue: OSDI
year: 2026
tags: [gpu-cluster, workload-characterization, scheduling, fragmentation, production-system]
source_pdf: "[[osdi26-li-suyi.pdf]]"
source_md: "[[osdi26-li-suyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Alibaba ASI：超大规模异构生产 AI 集群的刻画与调度（OSDI 2026）

> **原题**：Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba (Operational Systems)

这篇 operational paper 以 Alibaba [[Serverless|Serverless]] Infrastructure 的六个月生产 trace 说明：现代 AI 集群的主要浪费已不是 fractional GPU，而是跨节点、CPU 配比、网络拓扑和预留 headroom 共同造成的不可分配容量。

## 问题与动机

GenAI 与传统 DNN、训练与在线/离线推理共享多代、多厂商 GPU fleet。即使需求持续饱和，空闲 GPU 也可能因资源 shape 不匹配、拓扑约束或高优先级保留而无法分配。论文试图以 hyperscale 生产数据识别主导瓶颈，并报告已部署的 IPC defragmentation 与 SpotGPU harvesting 机制。

## 关键观察 / 隐含假设

### 关键观察

- 99% 以上作业显式指定 GPU 型号，少于 1% 使用异构 GPU；因此型号可替代性远低于理论硬件兼容性。
- fractional-GPU sharing 很少使用，碎片主要来自 8-GPU 节点上的 stranded GPU、CPU 不足和跨 access switch locality。
- 在线推理保留峰值和 failover headroom，午夜空闲 standby 容量可达 10,000 GPU-hours；低优先级任务可在不降低保障的条件下收割它。
- 硬件规格不等于开箱性能：XPU-A 理论能力强于 H20，但未优化 GenAI 性能仅为 H20 的 80%。

### 隐含假设

- 六个月、81 个部门的 ASI 行为可代表其他 hyperscale AI 集群，而 Alibaba 的业务和配额政策不会根本改变结论。
- HP 用户准确声明 standby，LP 任务可接受随时抢占，checkpoint 成本可用于近似被驱逐损失。
- “GPU allocation ratio” 是有效利用的有意义代理，尽管 allocated GPU 的 SM 利用率可能仍然很低。

## 核心方法

### 六个月 ASI trace

数据覆盖 155,410 GPUs、37,707 GPU nodes、约 14M jobs 和 81 个部门，包含 development、training、online inference 与 offline inference，并保留优先级、GPU 型号、CPU/内存和拓扑等信息。论文公开脱敏 trace 供后续研究。

### IPC 去碎片化

Iterative Partitioned Consolidation 以分区搜索和 ejection chain 生成迁移计划，同时尊重 affinity 与约 40% locked tasks。entropy-based topology metric 倾向将分配集中在更少 access switches，降低未来大作业被 topology fragmentation 阻塞的概率。

### SpotGPU

HP 作业拥有保证容量，可通过 Standby 显式释放暂时闲置的 GPU；LP spot 作业以折扣运行并可被抢占。调度器基于 LP 任务自上次 checkpoint 后的 GPU-time 估算 eviction cost，优先选择浪费最小的 reclaim 方案。

### 异构硬件适配

论文进一步刻画 XPU-A kernel 与通信问题，并通过 [[Attention|attention]]、prefill 等 drop-in API 优化展示软件适配能改变 GPU 型号需求，但把跨模型通用支持列为开放问题。

## 设计取舍

- IPC 用分钟级实用搜索替代全局最优，适合 155K GPU fleet，但迁移本身有网络与服务扰动成本。
- SpotGPU 保持 HP 保障，以 LP 被杀死和重算换取利用率；其收益依赖充足的可抢占 workload。
- allocation ratio 易于运营计量，却不能反映 SM、HBM 和网络是否真正忙碌。
- 多厂商降低供应链风险，但增加 kernel、通信栈和模型适配的持续工程负担。

## 实验与结果

- 六个月 trace 覆盖 155,410 GPUs、14M jobs 和 81 个部门；在线推理占作业数一半以上，且超过 99% 的 job 指定 GPU 型号，说明资源并非可自由互换（§3，表 1）。
- IPC replay 在分钟内生成迁移决策，并将存在 slack resources 的 occupied nodes 减少 20.2%；约 40% locked tasks 已纳入约束，但论文未给出生产迁移导致的尾延迟。
- SpotGPU 将全 cluster GPU allocation ratio 从只运行 HP 时的 68% 提升到 HP+LP 的 93%；平均 90% 的 Standby GPU-hours 被收割，少于 5% 的 LP eviction 需要 SIGKILL。
- preemption-cost-aware placement 相比不考虑成本的策略将 LP task completion time 改善 24%，同时未影响 HP task performance；评估边界是 ASI 的 checkpoint/priority 语义。
- 同一 access switch 内 placement 相比跨 switch allreduce bandwidth 高 27%，显示网络 locality 会限制异构阶段拆分。
- XPU-A 优化使 prefill computation speedup 达 1.58 倍；端到端 request latency 在 RPS 1 和 2 时分别降低 33% 和 43%，并相对 H20 改善 2% 和 21%。
- 在线推理的 median GPU SM utilization 仅 6%；CPU-only job co-location 虽提高 CPU 使用，却使训练 GPU 的 median 与 P90 SM utilization 分别下降 10% 和 18%，暴露隔离不足。

## 论断—证据表

| 论断 | 机制/分析 | 证据 | 边界 |
|---|---|---|---|
| 现代 GPU 碎片不以 fractional GPU 为主 | 分解 node、CPU 与 topology fragmentation | 99% 以上 job 锁定型号，sharing 很少使用 | 单一 Alibaba fleet 与政策环境 |
| 实用 defragmentation 可回收容量 | IPC 分区搜索与 ejection chain | slack occupied nodes 减少 20.2% | replay 结果，未报告迁移用户影响 |
| 可抢占 LP 工作可收割生产 headroom | Standby 与成本感知 reclaim | allocation ratio 从 68% 升到 93% | allocation 不等于计算利用率 |
| 多厂商采用需要软件栈共同优化 | XPU-A kernel 与 drop-in API | request latency 降低 33%/43% | 少数模型与硬件组合 |

## 批判性分析

### 论证链条

论文先用 trace 诊断“高需求但低有效利用”，再分别用 IPC 和 SpotGPU 对应结构性碎片与时间性 headroom，最后把未解决问题归结为厂商、网络和 interference 异构。观察与机制映射清楚，且 operational data 比合成集群更有价值。

### 假设压力测试

如果 LP 工作缺少频繁 checkpoint，93% allocation 可能伴随巨大重算；如果 HP 用户不主动释放 Standby，容量仍会锁死。若模型能跨 GPU 型号自动编译与调优，当前 99% 型号 pinning 可能快速变化，trace 结论具有时代性。

### 实验可信度

规模和字段丰富度突出，公开 trace 提升可复现性。IPC 主要使用 replay，SpotGPU 指标偏 allocation，缺少能耗、SM utilization、p99 HP latency 和失败恢复；部分硬件优化只是 preliminary case study，不能代表所有 XPU。

### 系统性缺陷

ASI 仍依赖人工型号 pinning、两级优先级和静态 quota，未形成统一的性能可移植抽象。把 idle GPU 填满并不自动提高有效工作：在线推理 median SM 仅 6%，co-location 又造成最高 18% 的 P90 干扰，核心 isolation 问题尚未解决。

## 局限与后续工作

- 用 useful FLOPs、tokens/s、能耗和 SLO 达成率补充 allocation ratio。
- 将真实 migration cost、network locality 与 HP p99 latency 纳入 IPC/SpotGPU 联合优化。
- 建立跨厂商模型性能预测和自动 kernel adaptation，减少显式型号 pinning。
- 设计对 HBM、SM、CPU 和网络均有严格隔离的在线推理 co-location。

## 相关

- [[GPU-Cluster-Scheduling]]
- [[GPU-Fragmentation]]
- [[Spot-Instances]]
- [[Alibaba-Cluster-Trace]]
