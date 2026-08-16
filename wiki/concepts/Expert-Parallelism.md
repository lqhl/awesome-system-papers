---
type: concept
aliases: [Expert Parallelism, Expert-Parallel, expert-parallel, EP, MoE Expert Parallelism]
parent: "[[MoE]]"
last_updated: 2026-08-14
tags: [moe, distributed-training, llm-inference, parallelism]
---

# Expert-Parallelism

> 专家并行（expert parallelism，EP）把 MoE experts 分到不同 devices；router 为 token 选择 expert 后，系统通过 dispatch AllToAll 发送 token，执行 expert，再通过 combine 把结果送回原 rank。

## 核心思想

MoE 每个 token 只激活少量 expert。EP 因而可以让每张 GPU 只保存部分 expert weights，在不让每个设备承担全部参数的前提下扩大模型。代价是每个 MoE layer 通常要做两次不规则 token permutation 和跨设备通信，消息目的地由运行时 routing 决定。

EP 的“并行度”不是唯一变量。expert placement、replication、token capacity、precision、node 内外拓扑、CPU proxy、communication overlap 和 pipeline partition 都会改变端到端性能。平均每张卡 expert 数相同，也不表示每张卡 token 或通信相同。

## 为什么重要

MoE 用较低 active FLOPs 扩大参数，却把 dense model 的规则 collective 变成动态 AllToAll。prefill 的 token 多、单 expert batch 大；decode 的 token 少、weight traffic 占主导；训练还要处理 gradient 和 optimizer state。因此，同一个 EP plan 很难同时适合训练、prefill 和 decode。

OSDI 2026 的论文进一步显示，通信“可隐藏多少”比裸通信时间更重要。[[Tessera-OSDI26]] 发现不同相邻 layer 能隐藏的通信比例相差约三倍，必须把细粒度 overlap schedule 和 PP partition 一起选。[[UEP-OSDI26]] 则说明 portability 也需要进入设计：GPU 只发小 routing command，CPU proxy 为不同 NIC 补齐顺序和可靠性语义。

## 关键观察 / 隐含假设

- **routing skew 会形成 hot expert 和 straggler。** [[CRAFT-MLSys26]] 说明每层复制收益差异大，统一复制会挤占 [[KV-Cache]]；动态或 layerwise replication 依赖负载 profile 能代表后续流量。
- **通信和计算必须按 post-overlap cost 规划。** [[Tessera-OSDI26]] 先生成并实测 layer-pair schedule，再切 PP stage；只按 FLOPs 或裸 AllToAll 时间会重新制造不平衡。
- **portable transport 可以把 NIC 细节移到 CPU。** [[UEP-OSDI26]] 在多 GPU/NIC 组合上运行，但每 GPU 最多占四个 CPU cores，并扩大 host crash、乱序和调试面。
- **本地 MoE 也有“小规模 EP”。** [[Wang-LocalMoEInference-OSDI26]] 的 SmallEP 针对 1–2 张消费 GPU，避免照搬大集群 collective；系统瓶颈转向 DDR、PCIe 和 CPU GEMV。
- **prefill 与 decode 的 EP 税不同。** [[MoE-Serving-Tax-MLSys26]] 把 prefill 的 padding/straggler 与 decode 的 weight amplification 分开；routing skew 在 decode 中有时反而减少活跃 expert，不能一概视为坏事。
- **精度和 layout 会改变通信路径。** [[FP8FlowMoE-MLSys26]] 避免 transpose 后重复量化，[[MoEBlaze-MLSys26]] 避免物化 routing buffer；kernel、precision 与 EP 不应独立优化。
- **故障恢复依赖 rank 对称和冗余。** [[TrainMover-OSDI26]] 利用 EP/TP/DP rank 的结构相似性预热 standby；[[SDCHunter-OSDI26]] 为 deterministic replay 固定 MoE dispatch 与 collective 顺序。

## 设计空间与取舍

- **Flat AllToAll**：接口简单；跨节点、异构 NIC 和大 EP degree 时容易拥塞。
- **Hierarchical EP**：先节点内、再跨节点，减少慢链路 traffic；增加 staging、同步和 topology 绑定。
- **Expert replication**：缓解热点和长尾；消耗 HBM，并需决定副本路由和更新一致性。
- **Token padding/drop 与无 padding 路线**：固定 shape 易优化；padding 浪费计算，drop 可能影响模型质量。
- **GPU-direct 与 CPU-proxy transport**：前者延迟低但绑定硬件；后者可移植、易升级，但占 CPU 并引入新故障面。
- **CPU/GPU 或 CXL-NDP offload**：扩展容量；预测错误和总线带宽会落入每 token 关键路径。
- **联合 EP/PP/DP 规划**：更接近全局最优；搜索、profiling 和 runtime switching 更复杂。

## 引用本概念的论文

- [[Tessera-OSDI26]] — 联合 EP overlap、pipeline partition 和运行时 bubble filling。
- [[UEP-OSDI26]] — 用 CPU proxy 提供跨 NIC/GPU 的 portable EP communication。
- [[Wang-LocalMoEInference-OSDI26]] — 在本地 CPU–GPU 平台实现小规模 expert parallelism。
- [[CRAFT-MLSys26]] — 在显存预算内按层分配 expert replicas。
- [[MoE-Serving-Tax-MLSys26]] — 分解 prefill 与 decode 中不同来源的 MoE/EP 开销。
- [[MoEBlaze-MLSys26]] — 减少 routing buffer 和 SwiGLU activation memory。
- [[FP8FlowMoE-MLSys26]] — 让 FP8 scale、transpose 和 EP data flow 保持一致。
- [[FarSkip-Collective-MLSys26]] — 用近似的 partial/outdated activation 打破 EP communication 的硬依赖。
- [[TrainMover-OSDI26]] — 利用 EP rank 对称性预热可替换任意角色的 standby。
- [[SDCHunter-OSDI26]] — 固定 MoE routing 与 collective 顺序以支持 bitwise replay。
- [[veScale-FSDP-MLSys26]] — 用结构感知 shard 支持 EP、量化和矩阵 optimizer 组合。
- [[LayeredPrefill-MLSys26]] — 说明 chunked prefill 会侵蚀 MoE sparsity，并改为 layer-group 调度。

## 已知局限 / 开放问题

- 需要在 routing drift 和多租户流量下低成本重放置/复制 expert，同时控制迁移尖峰。
- GPU、NIC 与 CPU queue 的 ordering、retry 和 partial failure correctness 仍缺少统一语义。
- 应联合搜索 precision、layout、replication、EP/PP/DP topology 和 KV 预算，而不是分别调优。
- 评估需报告 P99 token latency、CPU cores、网络能源、drop/padding 和模型质量，不能只报 AllToAll bandwidth。
