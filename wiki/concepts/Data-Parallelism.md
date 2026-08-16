---
type: concept
aliases: [Data-Parallel, data parallel, Data Parallelism, data parallelism, DDP]
last_updated: 2026-08-14
tags: [distributed-training, parallelism, gradient-sync, llm-training]
---

# Data-Parallelism

> 数据并行（data parallelism）让多个 workers 处理不同样本，再同步梯度或参数，使它们共同完成一次逻辑上的模型更新；它容易扩展 batch，却把最慢 rank、collective 和训练状态一致性放进每一步关键路径。

## 核心思想

经典 Distributed Data Parallel（DDP）在每个 rank 保存完整模型。各 rank 独立完成 forward/backward，再通过 AllReduce 聚合梯度。全局 batch 等于各 rank local batch 的组合；为了保持同步语义，下一步通常要等所有 rank 完成本步。

模型太大时，可以在 data-parallel group 内分片 optimizer state、gradient 和 parameter。[[ZeRO]] 与 [[FSDP]] 用 ReduceScatter、AllGather 和按需 materialization 降低单卡显存，但也让通信更频繁、故障恢复更依赖分片映射。DP 还常和 TP、PP、EP 组成多维并行拓扑。

## 为什么重要

DP 是增加训练吞吐最直接的维度，也是许多系统用来比较结果、保存副本和恢复故障的基础。但同步 barrier 会放大任何局部慢点：GPU 退化、网络拥塞、输入长短不均和 runtime 抖动都会让其他 rank 空等。[[Greyhound-ATC25]]、[[AEGIS-OSDI26]] 和 [[SDCHunter-OSDI26]] 分别从 fail-slow、在线 SDC 检测和故障后诊断展示了这种“多个本应等价的 rank”既是脆弱点，也是检测信号来源。

分片和弹性又让“训练继续运行”不等于“训练语义没有改变”。更换成员、修改 DP degree 或重分 microbatch 会改变 reduction order、gradient accumulation、RNG 和 data cursor。[[FlexTrain-MLSys26]] 因此优先调整 PP 来保持 bitwise consistency；[[TrainVerify-SOSP25]] 则把逻辑训练图和具体并行执行计划做形式等价检查。

## 关键观察 / 隐含假设

- **同步一步由最慢 rank 决定。** [[Greyhound-ATC25]] 在 NCCL 层检测变慢的 GPU/链路并重分 microbatch；这种缓解假设剩余 rank 有足够余量，且 workload 可以安全重分。
- **DP 副本既是冗余，也是显存成本。** [[Hetu-v2-OSDI26]] 在故障后利用 DP redundancy 恢复参数，但要保留更多状态并放弃部分 ZeRO 节省；最大分片与快速本地恢复存在直接张力。
- **rank 间差异可以检测 silent error。** [[AEGIS-OSDI26]] 比较 DP rank 的紧凑校验信号，[[SDCHunter-OSDI26]] 用确定性 replay 和 DP group 内多数关系定位坏卡；两者都假设至少有健康、语义等价的对照执行。
- **成员替换的大部分准备可以与训练重叠。** [[TrainMover-OSDI26]] 预热 standby、增量建立 communicator，只在最新状态和连接切换时暂停；它不包含故障发现与定位时间。
- **checkpoint 格式会绑定 DP/ZeRO 布局。** [[UCP-ATC25]] 把分布式 checkpoint 还原为 per-parameter atomic form，再转到新拓扑；方案适合低频重配，不是每步保存的替代品。
- **弹性会影响数值顺序。** [[FlexTrain-MLSys26]] 明确区分严格 bitwise 模式和放宽 DP+PP 模式；只报告 JCT 改善无法说明收敛完全等价。
- **外部训练状态不会自动被 DP runtime 管理。** optimizer、RNG、dataloader、隐私噪声历史和 RL rollout 都可能有独立生命周期；统一恢复仍是开放问题。

## 设计空间与取舍

- **完整复制 DDP**：实现和恢复简单，显存开销高，大模型可能单卡放不下。
- **ZeRO/FSDP 分片**：显存接近随 rank 数下降；AllGather/ReduceScatter、prefetch 和 checkpoint 转换更复杂。
- **同步、local SGD 与异步更新**：同步语义清楚但受 straggler 影响；减少同步会改变 optimization 和 convergence。
- **静态与弹性 DP**：静态容易复现；弹性利用潮汐资源，却需重建 communicator、迁移状态并解释数值差异。
- **microbatch 重分与成员替换**：前者能快速缓解 fail-slow，后者隔离坏机更彻底；两者都要保持样本计数和更新语义。
- **跨 DC DP 与 PP**：DP 传 gradient/parameter，慢链路代价常随模型大小增长；[[CrossPipe-ATC25]] 展示了某些大模型更适合把 PP 跨 DC。

## 引用本概念的论文

- [[Greyhound-ATC25]] — 检测 DP group 内 fail-slow，并按成本逐级缓解。
- [[AEGIS-OSDI26]] — 利用 rank 间冗余做低开销在线 SDC 感知。
- [[SDCHunter-OSDI26]] — 用确定性 replay 和 DP group 多数关系定位 defective GPU。
- [[TrainMover-OSDI26]] — 在训练继续时预热替补并增量切换 DP/TP/EP communicator。
- [[Hetu-v2-OSDI26]] — 用非对称分片处理异构 GPU 与成员故障，并揭示 ZeRO 冗余张力。
- [[FlexTrain-MLSys26]] — 区分严格一致和放宽语义的弹性并行策略。
- [[UCP-ATC25]] — 解耦 checkpoint 与 DP/TP/PP/ZeRO 布局。
- [[TrainVerify-SOSP25]] — 验证逻辑训练图与并行执行计划的等价性。
- [[AdaCheck-FAST26]] — 识别不同并行组合中的 tensor redundancy，缩小 checkpoint。
- [[DynaRL-OSDI26]] — 在 RL 的 rollout、inference 与 trainer 间动态重配 GPU 和状态。
- [[Optimus-ATC25]] — 利用大模型 DP/TP/PP 通信留下的空隙调度多模态 encoder。
- [[Sailor-SOSP25]] — 联合搜索资源与 DP/PP/TP 计划，强调异构集群中的显存和 straggler 约束。

## 已知局限 / 开放问题

- 需要为弹性 DP 定义可接受的 bitwise、统计和收敛一致性，而不是统一称为“无损”。
- checkpoint、optimizer、RNG、data cursor、privacy state 与外部 rollout 仍缺统一 shard/recovery 抽象。
- 相关机架、交换机和固件故障会同时破坏多个 rank，简单多数或单副本假设可能失效。
- 评估应同时报告吞吐、ETTR、收敛、sample efficiency、网络与能源，而不只看单步时间。
