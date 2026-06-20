---
type: concept
aliases: [DP, Data-Parallel, data parallel, Data Parallelism, data parallelism, DDP]
last_updated: 2026-06-20
tags: [distributed-training, parallelism, gradient-sync, llm-training]
---

# Data-Parallelism

> **Data Parallelism（DP）** 在多个设备上各持 **完整模型副本**，每步处理不同 data shard，通过 **gradient 或 parameter 同步**（AllReduce、ReduceScatter+AllGather、[[ZeRO]] 分片）保持一致。它是大模型训练最直观的扩展维度，也是与 [[Pipeline-Parallelism]]、[[Tensor-Parallelism]] 正交组合的「第三维」——但在 LLM 尺度下，DP 通信量随参数量增长、与 bubble/overlap 强耦合，且 **扩缩容会破坏累加顺序与数值一致性**。

## 核心思想

经典 DDP：每 GPU 算 local gradient $g_i$，AllReduce 得平均梯度 $\bar g = \frac{1}{N}\sum_i g_i$，各副本同步更新。显存瓶颈催生 **ZeRO**（optimizer state / gradient / parameter 分片 + 按需 AllGather），以及 **FSDP** 等 fully-sharded 变体——通信从「每步一次大 AllReduce」变为「多次分片 collective」，与 [[Tensor-Parallelism]] 的 per-layer AllReduce 叠加。

在 **3D 并行**（TP × PP × DP）中，DP 通常在最外层：每个 PP stage 组内多副本处理不同 micro-batch shard。跨 **数据中心** 时，DP 要同步整模型梯度/optimizer state，通信体积大、对带宽敏感；论文因此常把跨 DC 维度优先给 [[Pipeline-Parallelism]]（[[CrossPipe-ATC25|CrossPipe]]：405B 上 cross-DC PP 可比 cross-DC DP 快 3.05×）。

**弹性训练** 暴露 DP 特有语义：增减 DP 度改变 **gradient 累加顺序** 与随机数对齐，无法像 PP 扩缩那样保 bitwise 一致（[[FlexTrain-MLSys26|FlexTrain]]）。**Fail-slow** 下 DP 组内 straggler 直接拖慢全局 barrier（[[Greyhound-ATC25|Greyhound]]），可通过 micro-batch 重分配缓解。

适用边界：DP 假设各副本模型同构、同步 barrier（或显式接受的 Local SGD 变体）。极大模型需与 TP/PP 组合否则单卡放不下；MoE 下 expert 参数使 DP 通信量放大，常与 [[Expert-Parallelism]] 交叉。

## 为什么重要

本 wiki 当前 **28** 篇 inbound 将 DP 作为显式优化对象，说明它不仅是「默认训练模式」，而是：

1. **通信主导瓶颈**：跨 DC、geo-distributed、低带宽下 DP gradient/parameter sync 占 step time 大头（[[DreamDDP-MLSys26|DreamDDP]]、[[CrossPipe-ATC25|CrossPipe]]）。
2. **调度与 bubble 的耦合变量**：PP schedule 需建模可 overlap 的 DP collective（[[CrossPipe-ATC25|CrossPipe]]）；MLLM 中 DP all-gather/reduce-scatter 占 ~12% step 且构成 bubble 来源（[[Optimus-ATC25|Optimus]]）。
3. **弹性与正确性 trade-off**：生产集群潮汐 idle GPU 下，DP 扩缩破坏确定性，PP 成为弹性主轴（[[FlexTrain-MLSys26|FlexTrain]]）。
4. **运维与验证**：straggler 缓解、并行 plan 验证、execution trace 标准化均把 DP 当一等公民（[[Greyhound-ATC25|Greyhound]]、[[TrainVerify-SOSP25|TrainVerify]]、[[Chakra-MLSys26|Chakra]]）。

这些论文共同假设：**DP 通信可与计算 overlap 的程度、以及 DP 度与 PP/TP 的配比，决定端到端 step time 的下界**——且不存在 universal 最优 DP 度，需 profile/plan/search。

## 关键观察 / 隐含假设

- **观察 1：跨 DC / 低带宽场景下，全量 DP sync 难以隐藏，partial sync 或换并行维度更可行。** [[CrossPipe-ATC25|CrossPipe]] 在 4 GB/s 跨 DC 带宽下 PP 最多比 DP 快 3.05×；[[DreamDDP-MLSys26|DreamDDP]] 用 layer-wise partial parameter sync 在 geo-DDP 上 1.49–3.91× 迭代加速，但需论证收敛率。
  - **依赖假设**：profile 稳定；partial sync 调度不与 BP 语义冲突（in-place 平均必须在层 BP 之后）。
  - **可能失效场景**：高带宽同 DC、极小模型通信非瓶颈时，DP 仍是最简方案。

- **观察 2：静态 PP schedule 在跨 DC delay 下会把 DP/PP collective 沿关键路径放大，需 delay-aware 联合调度。** [[CrossPipe-ATC25|CrossPipe]] 将 DP overlap 纳入 solver/greedy schedule，相对静态 schedule 最多 -33.6% runtime；receiver 未及时 post recv 会触发 NCCL rendezvous 阻塞。
  - **依赖假设**：alpha-beta 通信模型足够；profiling 在 schedule 生命周期内稳定。
  - **可能失效场景**：WAN jitter、丢包、多租户拥塞使模型偏离。

- **观察 3：DP 扩缩引入非确定性，与 PP 弹性不可互换。** [[FlexTrain-MLSys26|FlexTrain]] 明确 PP 扩缩保 bitwise 一致、DP 扩缩破坏 gradient 累加顺序；严格一致模式只动 PP，放宽才联合 DP+PP（2.27× vs 1.73× JCT）。
  - **依赖假设**：开发者需要可复现训练用于 debug/ablation。
  - **可能失效场景**：算法接受 Local SGD/异步时，DP 弹性成为首选（[[DreamDDP-MLSys26|DreamDDP]]）。

- **观察 4：fail-slow 时 DP 组是 micro-batch 重分配的天然粒度。** [[Greyhound-ATC25|Greyhound]] 对计算 straggler 解 QP 重分配各 DP 组 micro-batch 数，weighted gradient aggregation 保语义；通信 straggler 则调整 topology 把拥塞链路从 heavy-traffic DP 组换到轻流量 PP 组。
  - **依赖假设**：同步 hybrid parallelism；straggler 表现为 iteration time ≥10% 跃升。
  - **可能失效场景**：仅在某些 compute+comm 交织模式出现的 fail-slow 检测不到。

- **观察 5：变长训练下 freed GPU 常转给 DP 以提高吞吐。** [[FlexPipe-ATC25|FlexPipe]] 在短序列 iteration shrink PP 后把冗余 GPU 启动新 DP worker，平均 1.25× 吞吐；依赖 dataloader prefetch 下一 iteration 的 max sequence length。
  - **依赖假设**：总 GPU 池固定；PP+DP hybrid 已启用。
  - **可能失效场景**：定长 bucketing 使跨 iteration 波动消失，动态 reconfiguration 收益下降。

## 设计空间与取舍

- **路线 1：经典 DDP + AllReduce**——实现简单，适合同 DC 高带宽；牺牲：大模型 optimizer state 显存、跨 DC 不可扩展。
- **路线 2：ZeRO / FSDP 分片 DP**——降显存，增 AllGather/ReduceScatter 次数；与 TP 通信叠加需 overlap 调度（[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[Charon-MLSys26|Charon]]）。
- **路线 3：跨 DC 优先 PP、DP 局部或压缩**——降跨域通信体积；牺牲：pipeline bubble、fault domain 扩大（[[CrossPipe-ATC25|CrossPipe]]）。
- **路线 4：Local / partial sync（geo-DDP）**——降 sync 频率或分层 sync；牺牲：收敛分析、调度复杂度（[[DreamDDP-MLSys26|DreamDDP]]）。
- **路线 5：弹性 DP 扩缩**——吃碎片 GPU；牺牲：bitwise 精度、checkpoint 开销（[[FlexTrain-MLSys26|FlexTrain]]）。
- **路线 6：动态 PP↔DP 资源重配**——变长 workload 在线调节；牺牲：TwinLayer/host 副本与 reconfiguration 工程（[[FlexPipe-ATC25|FlexPipe]]）。
- **路线 7：straggler 缓解**——DP micro-batch 重分配、topology swap；牺牲：Megatron 绑定、挂起训练验证（[[Greyhound-ATC25|Greyhound]]）。

## 引用本概念的论文

- [[CrossPipe-ATC25|CrossPipe]] — 跨 DC 训练统一建模 PP send/recv 与可 overlap 的 DP 通信，dynamic schedule 最多 -33.6% runtime
- [[Greyhound-ATC25|Greyhound]] — 10K+ GPU fail-slow 表征；S2 DP micro-batch QP 重分配 + S3 topology 调整，256 GPU 上 1.58× 吞吐
- [[FlexPipe-ATC25|FlexPipe]] — 变长训练动态 shrink PP、冗余 GPU 转 [[Data-Parallelism]]，平均 1.25× 吞吐
- [[FlexTrain-MLSys26|FlexTrain]] — 弹性训练：PP 保精度 vs DP+PP 扩缩牺牲一致性，JCT 最多 1.73× / 2.27×
- [[DreamDDP-MLSys26|DreamDDP]] — geo-DDP layer-wise partial parameter sync + DFS 调度，1.49–3.91× 迭代加速
- [[Optimus-ATC25|Optimus]] — MLLM 训练中 DP all-gather/reduce-scatter bubble 与 encoder bubble filling
- [[TrainVerify-SOSP25|TrainVerify]] — 验证含 DP 的 Llama3/DeepSeek-V3 parallelization equivalence
- [[Chakra-MLSys26|Chakra]] — execution trace 编码 DP collective 供 ASTRA-sim co-design
- [[Sailor-SOSP25|Sailor]] — 异构/geo 集群联合优化资源分配与 DP/PP/TP
- [[Hermes-ATC25|Hermes]] — 工业训练 profiling；adaptive gradient fusion 优化 DP AllReduce 小包
- [[ByteRobust-SOSP25|ByteRobust]] — 大规模训练容错语境下的 DP 角色
- [[HypeReca-ATC25|HypeReca]] — DP 通信与 checkpoint/recomputation 交互
- [[Mycroft-SOSP25|Mycroft]]、[[Seneca-FAST26|Seneca]] — 训练 trace 与 DP 调度
- [[GMI-DRL-ATC25|GMI-DRL]]、[[UCP-ATC25|UCP]]、[[AdaCheck-FAST26|AdaCheck]] — DP 训练系统的检查点/控制面

## 已知局限 / 开放问题

- **跨 DC DP 的真实 WAN 验证不足**：delay injection 为主（[[CrossPipe-ATC25|CrossPipe]]），jitter/拥塞下 schedule 稳定性未证明
- **弹性 DP 与收敛**：增大 GBS、改变 DP 度对 tokens-to-quality 的影响常被忽略（[[FlexTrain-MLSys26|FlexTrain]]、[[CrossPipe-ATC25|CrossPipe]]）
- **与 MoE EP 的交叉**：expert 参数放大 DP 通信、EP AllToAll 与 DP 顺序依赖，联合 planner 仍开放（[[CrossPipe-ATC25|CrossPipe]] discussion）
- **Fail-slow 检测盲区**：交织型退化、Gradual <10% 漂移（[[Greyhound-ATC25|Greyhound]]）
- **ZeRO stage 与 PP overlap 的形式化验证**：[[TrainVerify-SOSP25|TrainVerify]] 覆盖 plan 但不覆盖 runtime NCCL 算法选择与动态拥塞
