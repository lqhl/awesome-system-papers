---
type: concept
aliases: [Zero-Redundancy-Optimizer, ZeRO-1, ZeRO-2, ZeRO-3]
last_updated: 2026-07-30
tags: [distributed-training, sharding, memory-management]
---

# ZeRO

> ZeRO（Zero Redundancy Optimizer）按阶段分片优化器状态、梯度和参数，消除 data-parallel ranks 上的训练状态副本，以更多 collective、临时 materialization 和恢复复杂度换取模型容量。

## 核心思想

ZeRO-1 只分片 optimizer state，ZeRO-2 再分片 gradient，ZeRO-3 进一步分片 parameter。阶段越高，常驻显存越小，但 forward/backward 需要更频繁地 all-gather 参数并 reduce-scatter 梯度。ZeRO 因而不是单一算法，而是一组在 memory redundancy、通信量、执行粒度与故障恢复间移动的设计点。

## 为什么重要

ZeRO 让传统 data parallel 扩展到超大模型，并成为 [[DeepSpeed]] 的核心抽象。OSDI 2026 的新证据进一步表明，极限去冗余不是所有场景的最优答案：[[Hetu-v2-OSDI26]] 为故障后从剩余 DP redundancy 恢复而禁用 ZeRO-1，付出约 15% step-time 代价；[[Cocoon-OSDI26]] 则显示 parameter 之外的 privacy history 也需要类似分层管理。

## 关键观察 / 隐含假设

- **显存节省会转化为通信与临时峰值。** ZeRO-3 需要按执行顺序 materialize 参数，bucket、prefetch 与释放时机决定是否真正降低 peak memory。
- **冗余既是浪费，也可能是恢复资源。** [[Hetu-v2-OSDI26]] 的无 checkpoint fault reconfiguration 依赖 DP redundancy，说明容量最大化与快速恢复存在结构性冲突。
- **状态种类持续扩张。** [[DP-ZeRO-MLSys26]] 与 [[Cocoon-OSDI26]] 把差分隐私噪声/历史纳入系统，传统三类状态已不足以描述总内存。
- **隐含假设**：设备对称、collective 稳定且执行图可预测；异构 GPU、弹性成员变化或频繁 dynamic graph 会削弱静态分片。

## 设计空间与取舍

- **Stage 1/2/3**：阶段越高容量越好，通信、调度和恢复越复杂。
- **offload 到 CPU/NVMe**：扩大可训练规模，却引入 PCIe/存储带宽和尾延迟。
- **bucket 大小与 prefetch**：大 bucket 提高 collective 效率但占显存；小 bucket 更灵活但 latency-bound。
- **与 pipeline/tensor parallel 组合**：[[FlexPipe-ATC25]]、[[CrossPipe-ATC25]] 等说明混合并行下 topology 与 bubble 会影响最优 ZeRO 级别。
- **静态冗余与弹性恢复**：保留部分副本提高故障切换速度，代价是牺牲可训练模型上限。

## 引用本概念的论文

- [[Hetu-v2-OSDI26]] — 异构/故障 HSPMD；明确量化禁用 ZeRO-1 以保留恢复冗余的约 15% 性能代价
- [[Cocoon-OSDI26]] — correlated-noise history 的异构分层，并提出与 ZeRO/FSDP 联合分片
- [[DP-ZeRO-MLSys26]] — 差分隐私训练中的 ZeRO 扩展
- [[ProTrain-MLSys26]] — 训练执行与状态管理
- [[Obscura-ATC25]] — 大模型训练内存优化
- [[FlexPipe-ATC25]]、[[CrossPipe-ATC25]] — ZeRO 与 pipeline parallelism 的组合
- [[AdaCheck-FAST26]] — 分布式 checkpoint 与恢复
- [[AITurbo-FAST26]] — 训练 I/O 加速

## 已知局限 / 开放问题

- 在真实故障率下，保留多少 redundancy 才能平衡容量与恢复时间，缺少统一模型。
- 动态 membership 下 parameter、optimizer、RNG、dataloader 和外部 history 的原子 reshard 尚未统一。
- 网络拥塞与 straggler 会使高阶段 ZeRO 的小粒度 collective 放大尾延迟。
- ZeRO 与 MoE、低精度 optimizer、CXL/NVMe offload 的联合优化空间仍高度依赖具体硬件。
