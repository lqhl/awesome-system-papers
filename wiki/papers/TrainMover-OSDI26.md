---
type: paper
name: TrainMover
full_title: "TrainMover: An Interruption-Resilient Runtime for ML Training"
authors: [ChonLam Lao, Jiaqi Gao, Jiamin Cao, Zhipeng Zhang, Pengcheng Zhang, et al.]
venue: OSDI
year: 2026
tags: [distributed-training, fault-tolerance, live-migration, collective-communication, checkpointing]
source_pdf: "[[osdi26-lao.pdf]]"
source_md: "[[osdi26-lao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向训练中断的弹性运行时（OSDI 2026）

> **原题**：TrainMover: An Interruption-Resilient Runtime for ML Training

> **一句话总结**：TrainMover 不改变已调优的训练并行布局，而把故障节点角色迁移到elastic/standby machine；通过sandbox warmup与两阶段delta通信组切换，将1,024-GPU中断downtime压到约20秒且不增加训练GPU显存，预计64K GPU节省55% wasted GPU-hours。

## 问题与动机

大型[[LLM|LLM]]训练持续数周，硬件故障、维护与抢占频繁发生。checkpoint-restart需重建framework、加载state和CCL group；弹性缩容则改变TP/PP/[[Data-Parallelism|DP]] layout，可能降速、OOM或留下idle GPU。生产集群通常已有约6% backup/elastic GPU，TrainMover要利用这些机器进行role-preserving replacement，避免重启整个job。

## 关键观察 / 隐含假设

- joiner的大部分初始化、kernel/JIT warmup和connection setup可在训练继续时提前完成；真正必须stop-the-world的只是membership/state切换。
- warmup需要走真实execution path，但通信/参数副作用可在sandbox中record/replay或拦截，避免加入现有collective。
- CCL reconfiguration只需更新leaver–joiner相关delta连接，而非重建全部group；phase 1可并行准备、phase 2短暂停机提交（§5）。
- standby必须能接替任意role，且operator已完成fault localization；论文明确假设fault detection/isolation instant。

## 核心方法

TrainMover controller先在joiner上communication-free sandboxed warmup：拦截collective、记录必要tensor/shape并触发CUDA/framework initialization。expected interruption可提前warm standby；unexpected case在故障后启动同一流程。state由存活rank/存储传给joiner，并通过shadow iteration使其达到可执行状态。

Two-phase delta-based CCL setup在训练后台建立额外TCP/[[RDMA|RDMA]]连接与topology metadata，membership switch时只激活变化部分。General standby不预绑定特定[[Pipeline-Parallelism|PP]]/[[Tensor-Parallelism|TP]] role，而保存role-agnostic preparation，接到leaver身份后补足对应state。layout与model partition不变，因此迁移后steady-state throughput不受reconfiguration影响。

## 实验与结果

- 在GPT类模型、不同TP/PP/DP profile与最高1,024 GPUs上，expected/unexpected interruption downtime稳定约20秒（§8.2）。
- 相对无standby版本，预计64K GPUs wasted GPU time降55%；相对Parcae降88%，折算每周约节省1.4M GPU-hours。
- sandbox/connection work并行进行，steady training throughput loss少于3%；迁移完成后无额外GPU memory overhead。
- 低带宽state transfer下仍约6–9秒相关overhead；checkpoint loading baseline可达320秒，显示其对model size/network更敏感（§8.4–§8.5）。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| role-preserving migration显著缩短中断 | §8.2 | 最高1,024 GPUs | 强 |
| two-phase/delta setup可扩展 | §8.3/8.5 | 多种并行配置 | 强 |
| 不增加训练GPU显存 | memory trace、§8.5 | migration期间 | 强 |
| 64K规模节省55% | projection | 基于生产中断/扩展模型 | 中 |

## 批判性分析

### 论证链条

设计精准针对restart critical path中的framework warmup与CCL setup，而不是另造容错parallel layout。breakdown与多scale数据支持机制；“约20秒”仍非零，但比分钟级restart更适合昂贵同步训练。

### 假设压力测试

instant fault localization并不现实，correlated rack/switch failure可能同时耗尽standby和connection path。joiner若硬件/driver异构，sandbox profile与state transfer会变化。备用池6%本身有capacity cost，projection应纳入reserve GPU opportunity cost。

### 实验可信度

实验覆盖主要机制与代表性负载，但平台和基线范围仍限制结论的普遍性。

### 系统性缺陷

系统处理machine replacement而非silent corruption；checkpoint仍需保障model state durability。复杂optimizer/sharded state、dynamic graph或non-[[Megatron|Megatron]] communication pattern可能无法直接record/replay。规模收益主要是projection而非64K实测。

## 局限与后续工作

- 联合fault detector测end-to-end detection→recovery，而非假设instant isolation。
- 注入multi-node/rack/switch correlated failures并优化standby placement。
- 在异构GPU、动态parallel layout和64K生产trace上验证成本模型。

## 相关

- **相关概念**：[[Distributed-Training]]、[[Checkpoint-Restart]]、[[Live-Migration]]、[[Collective-Communication]]
- **相关系统**：[[Megatron-LM]]、[[Parcae]]、[[Oobleck]]
- **同会议**：[[OSDI-2026]]
