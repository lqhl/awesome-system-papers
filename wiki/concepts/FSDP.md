---
type: concept
aliases: [Fully-Sharded-Data-Parallel, Fully-Sharded Data Parallel]
last_updated: 2026-08-18
tags: [distributed-training, sharding, memory-management]
---

# FSDP

> Fully Sharded Data Parallel（FSDP）把参数、梯度和 optimizer state 分布到 data-parallel ranks，在计算前按需 AllGather、反向后 ReduceScatter，以更多通信和调度换取更低的单卡训练状态显存。

## 核心思想

普通 DDP 的每个 rank 都保留完整模型和 optimizer state。FSDP 只让 rank 常驻自己的 shard；进入一个模块前临时聚合参数，完成计算后释放或重新分片。它和 [[ZeRO]] Stage 3 目标接近，但 API、模块边界、DTensor placement、prefetch 和 checkpoint 集成不同。

真正的峰值显存不只由静态参数大小决定。临时完整参数、通信 buffer、prefetch、activation、optimizer update 和 allocator 生命周期会叠加。分片太细会制造大量小 collective；分片太粗又让完整参数驻留过久。FSDP 的核心问题因此是“何时、以什么布局 materialize 哪些状态”。

## 为什么重要

FSDP 让单卡放不下的模型仍能用接近 data-parallel 的编程方式训练，也是 PyTorch 生态的重要大模型原语。但今天的训练状态已不再是规则 FP16/FP32 tensor：8-bit optimizer、Muon 矩阵、MoE expert、隐私训练的 per-sample state 和不规则参数都要求更灵活的 shard boundary。

[[veScale-FSDP-MLSys26]] 正面展示了这一变化。它用 RaggedShard 让不可分片的量化块或矩阵完整落在单设备，并优化 collective buffer 布局；在所测 1024-GPU 配置中，相对多种 FSDP/DeepSpeed 实现提高吞吐并降低显存，但 planner 仍依赖结构规则和 profile。

## 关键观察 / 隐含假设

- **shard boundary 必须服从算子语义。** [[veScale-FSDP-MLSys26]] 说明 element/row-wise 均匀切分可能破坏量化块和矩阵 optimizer；任意 ragged shard 更灵活，却让布局规划变成组合优化。
- **buffer copy 可能和 collective 本身一样贵。** FSDP2 的交错布局会产生额外 copy；零拷贝 distributed buffer 要求目标 layout、对齐和 tensor 顺序提前规划。
- **prefetch 以显存换 overlap。** 提前 AllGather 可以隐藏网络，但抬高峰值并可能预取错误分支；dynamic graph、MoE routing 和长度变化会让静态计划失准。
- **训练状态不止参数、梯度和 optimizer。** [[Cocoon-OSDI26]] 的相关噪声历史可远大于模型，提示 privacy state 也要与 FSDP/ZeRO 联合分层；论文目前只提出后续方向，没有多节点联合验证。
- **FSDP 可以承载新的训练语义，但必须验证混合精度细节。** [[DP-ZeRO-MLSys26]] 把 differential privacy clipping/noise 接入 ZeRO/FSDP 路径，专门处理 loss scaling 和 FP32 master weight；“一行接入”不代表任意 operator 都已覆盖。
- **模拟器需要看到真实 liveness。** [[Charon-MLSys26]] 用图级 liveness 估计 FSDP peak memory；layer-level 常数模型容易漏掉 transient buffer。
- **FSDP 只解决训练状态的一部分。** [[Chen-LLMDataPipelines-OSDI26]] 表明 checkpoint 加载、跨 DC evaluation 和多模态转换仍可让 GPU 等待；显存可容纳不等于训练 pipeline 高效。

## 设计空间与取舍

- **模块级、参数级与结构感知 shard**：模块级简单；细粒度更省显存；结构感知能支持量化/矩阵语义但 planner 更复杂。
- **reshard-after-forward**：立即释放显存，backward 前需再次 AllGather；保留参数则相反。
- **prefetch 深度**：更深可隐藏通信，也增加峰值和错误预取风险。
- **flat FSDP 与 hierarchical sharding**：跨全组分片最省显存；节点内复制可减少跨节点 collective，并保留部分故障冗余。
- **CPU/NVMe offload**：扩展容量，PCIe、host memory 和 activation swap 会相互争用（[[ProTrain-MLSys26]]）。
- **静态与动态计划**：静态稳定、易验证；动态适应拓扑和 workload，却需 state migration 和 graph switching。

## 引用本概念的论文

- [[veScale-FSDP-MLSys26]] — 用 RaggedShard、layout planner 和零拷贝 buffer 支持结构感知训练。
- [[DP-ZeRO-MLSys26]] — 将 differential privacy clipping/noise 与 ZeRO/FSDP、mixed precision 组合。
- [[ProTrain-MLSys26]] — 联合搜索 parameter persistence、checkpointing 和 offload，并与 FSDP 比较。
- [[Charon-MLSys26]] — 在原生模型图上注入 FSDP 并模拟 peak memory 与执行时间。
- [[Cocoon-OSDI26]] — 暴露超大隐私噪声历史无法由普通 FSDP 状态模型自动管理的问题。
- [[FCP-MLSys26]] — 让长序列 attention block 调度与 FSDP/TP/EP 组合。
- [[Obscura-ATC25]] — 讨论 FSDP/ZeRO 改变 activation bottleneck 后，pipeline recomputation 计划需重做。
- [[DynaRL-OSDI26]] — 在 agentic RL 对比中使用较慢 FSDP backend，说明 runtime 集成也影响系统结论。
- [[Chen-LLMDataPipelines-OSDI26]] — 从训练数据和 checkpoint 路径补充 FSDP 之外的 I/O 瓶颈。
- [[BOOST-MLSys26]] — 将低秩训练与 FSDP 的全栈组合列为后续问题。
- [[PithTrain-arXiv26]] — 在紧凑 MoE 训练栈中以 FSDP 承担 data parallelism，并与 PP/CP/EP 组合；论文验证了有限 H100/B200 配置的吞吐与短 loss curve，未覆盖长期 checkpoint/restart 或弹性 reshard。

## 已知局限 / 开放问题

- dynamic graph、MoE skew、变长序列和条件执行会破坏静态 prefetch/reshard plan。
- checkpoint、optimizer、RNG、dataloader、privacy history 和外部 service state 尚无统一 shard/recovery 抽象。
- 多租户网络拥塞下 AllGather/ReduceScatter 的 P99、公平性和 collective cancellation 证据不足。
- 异构 GPU 上仍需自动生成可验证的容量、算力与网络联合计划，并解释切换后的数值语义。
