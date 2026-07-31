---
type: concept
aliases: [DP, Data-Parallel, data parallel, Data Parallelism, data parallelism, DDP]
last_updated: 2026-07-30
tags: [distributed-training, parallelism, gradient-sync, llm-training]
---

# Data-Parallelism

> 数据并行（data parallelism, DP）让多个 workers 处理不同 data shards，并通过 gradient/parameter collective 保持模型副本一致；它最易扩展，也最直接暴露同步、容错与数值顺序问题。

## 核心思想

经典 DDP 每个 rank 持完整参数并计算 local gradient，再 AllReduce 得到全局更新。ZeRO/FSDP 将 optimizer、gradient 或 parameter 分片，用 ReduceScatter/AllGather 换取更低单卡 memory。DP 可与 Pipeline、Tensor、Expert Parallelism 组成多维 topology。

同步 DP 的一步由最慢 rank 决定；elastic resize、recovery 或 microbatch 重分配会改变 gradient accumulation order、RNG 与 optimizer state。系统必须区分“训练继续”与“数值/统计语义等价”。

## 为什么重要

DP 是增加训练吞吐的首选维度，也是 failure redundancy 的来源，但通信量随模型/gradient 增长。跨慢网络、MoE expert 参数和 fully-sharded collectives 会让 overlap、bucket layout 与 topology 成为主导因素。

## 关键观察 / 隐含假设

- **DP barrier 放大 fail-slow**：[[Greyhound-ATC25]] 通过 microbatch reassignment 缓解 straggler；[[RobustRL-OSDI26]] 按 RL role 区分合法 idle 与故障，避免错误重启。
- **容错依赖保留 redundancy**：[[Hetu-v2-OSDI26]] 的 elastic/fault strategy 假设仍有 DP redundancy，并为恢复禁用部分 ZeRO 优化，明确交换 memory 与 availability。
- **扩缩容会改变数值顺序**：[[FlexTrain-MLSys26]] 指出改变 DP degree 难以保持 bitwise consistency，不能只用 throughput 衡量 elastic training。
- **隐私训练引入额外 DP state**：[[Cocoon-OSDI26]] 的 correlated-noise history 可超过 GPU/CPU memory，需要 precompute/coalescing 与 CXL/NMP 扩展。
- **成员切换应与训练重叠**：[[TrainMover-OSDI26]] 在原 workers 继续训练时预热 joiner 和 communicator，只在 commit 阶段暂停。

## 设计空间与取舍

- **replicated DDP**：恢复简单、memory 高；大模型单卡可能不可容纳。
- **ZeRO/FSDP**：降低 memory，增加频繁 collectives，并减少故障时可直接利用的完整副本。
- **Local SGD/async DP**：减少同步等待，改变 optimization semantics 与 convergence。
- **elastic DP**：回收动态资源，需重新映射 optimizer/RNG/data cursor 并解释数值差异。
- **cross-DC DP**：实现直接但传 gradient 大；[[CrossPipe-ATC25]] 展示某些模型下 PP 更适合慢链路。

## 引用本概念的论文

- [[RobustRL-OSDI26]] — 针对 trainer/rollout 不同健康模式做 role-aware recovery。
- [[Hetu-v2-OSDI26]] — 在异构、弹性和故障场景重配 DP/并行 topology。
- [[TrainMover-OSDI26]] — 不中断大部分训练地替换 DP member。
- [[Cocoon-OSDI26]] — 为 differential-private DP training 管理 correlated-noise state。
- [[FlexTrain-MLSys26]] — 分析 elastic DP/PP 的性能和一致性。
- [[Greyhound-ATC25]] — 处理 DP group 内 fail-slow 与 workload imbalance。

## 已知局限 / 开放问题

- 为 elastic DP 定义可接受的数值/统计一致性，而非笼统“无损恢复”。
- 联合 communicator rebuild、optimizer sharding、data cursor 与 RNG checkpoint。
- 在 correlated rack/network failures 下选择 redundancy 与 standby placement。
- 将 convergence、sample efficiency、energy 与 throughput 放进同一评估。
