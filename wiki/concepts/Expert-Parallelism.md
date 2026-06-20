---
type: concept
aliases: [Expert Parallelism, Expert-Parallel, expert-parallel, EP, MoE Expert Parallelism]
parent: "[[MoE]]"
last_updated: 2026-06-20
tags: [moe, distributed-training, llm-inference, parallelism]
---

# Expert-Parallelism

> [[MoE]] 专用并行切法：把每层 N 个 expert 分到 N/g 张 GPU，每张负责 g 个 expert。token 经 router 选 top-k expert 后，按目标 GPU 重排（[[AllToAll]] dispatch）→ 本地 expert FFN → 再 [[AllToAll]] combine。通信模式从 AllReduce 变为 AllToAll，对网络拓扑和负载均衡极度敏感。DeepSeek-V3 把 EP 推到 256 卡，[[DeepEP]] 针对 H800 NVLink/RDMA 异构带宽设计 hierarchical 协议。

## 核心思想

MoE 模型（671B DeepSeek、400B+ Qwen3）参数 70% 以上在 expert FFN。走 [[Tensor-Parallelism|TP]] 每层需搬整张巨大 FFN 到所有卡，不划算；把 expert 切到不同 GPU 更自然：

- 每卡存 `N_expert / N_gpu` 个 expert 权重
- token 稀疏激活：每 token 只经过 top-k（通常 2–8）个 expert
- 通信量 ∝ token 数 × hidden_dim × k，而非权重大小

前向流程：attention → router → AllToAll dispatch（按 expert 位置重排 token）→ 本地 FFN → AllToAll combine → continue。两次 AllToAll 是核心 overhead。[[DeepEP]] 观察到 H800 节点内 NVLink 160 GB/s、跨节点 RDMA 50 GB/s，异构带宽使 naive AllToAll 严重倾斜，于是分阶段 hierarchical 协议。

EP 常与其他维度组合：TP+EP（expert 内部再 TP）、DP+EP（attention DP、FFN EP）、PP+EP（跨 layer PP、stage 内 EP）、ZeRO+EP（optimizer/grad shard）。

## 为什么重要

EP 是 MoE 从「架构创新」落地到「可训练可部署系统」的关键切分维度。没有 EP，trillion-parameter MoE 的 expert 权重无法分布到集群；有了 EP，AllToAll 通信与 token imbalance 又成为 serving 延迟的主因。这些论文共同假设：**EP 的性能由最慢 GPU（straggler）决定，AllToAll 是同步 collective，热 expert 倾斜直接转化为 tail latency**。

2025–2026 年 MoE 系统研究主线几乎围绕 EP：训练侧 [[NEST-MLSys26]] 把 EP 纳入 device placement 搜索、[[FP8FlowMoE-MLSys26]] 消除 cast-free FP8 下的 Q/DQ 碎片开销；推理侧 [[CRAFT-MLSys26]] 做 per-layer replication benefit 估计、[[Libra-ICLR26]] 做 speculative gating prediction；[[Disaggregation]] 场景下 prefill 与 decode 的 expert 访问模式不同，需配不同 EP 度数（[[NVIDIA-Disagg-Study-MLSys26]]）。

## 关键观察 / 隐含假设

- **观察 1：各 MoE 层对 expert replication 的收益差异极大，均匀 EPLB 会严重过度复制、挤占 [[KV-Cache]]。** [[CRAFT-MLSys26]] 以 Kimi-K2 为例，layer 20 peak-to-mean 仅 2.5×（replication-ineffective），layer 51 最热 expert >27× 平均（replication-effective）；Fig. 6 显示 layer 20 几乎不受益，layer 51 plateau 在 16 replicas。
- **观察 2：chunked prefill 的 hybrid batch 会逆转 MoE decode 侧的稀疏激活优势。** [[LayeredPrefill-MLSys26]] 指出 SLO 合规 decode batch ≤32 时仅约 55% expert 被加载，但 chunked prefill hybrid batch 常 >256 激活几乎全部 expert，同时 per-expert token 不足以饱和 compute——即 sparsity erosion。
- **观察 3：FP8 MoE 中 Q/DQ 与轻量 data movement kernel 碎片开销可与 GEMM/通信同量级。** [[FP8FlowMoE-MLSys26]] 尤其在较小 batch 或高 EP 时；cast-free scaling-aware transpose 可消除 double quantization error。
- **观察 4：oversubscribed 集群上通信可占训练时间显著比例，最优 EP 策略强依赖模型 × 拓扑。** [[NEST-MLSys26]] 在 1024 GPU 模拟中 EP+ZeRO 联合搜索；静态网络成本不建模 dynamic congestion 是已知局限。

## 设计空间与取舍

- **路线 1：标准 EP + AllToAll（Megatron/DeepSpeed 默认）**：实现简单、与 router 语义直接对应；牺牲是对 token imbalance 和异构带宽敏感，tail latency 由 straggler 决定。
- **路线 2：Hierarchical AllToAll（[[DeepEP]]、[[fabric-lib-MLSys26]]）**：节点内 NVLink + 跨节点 RDMA 分阶段；牺牲是 custom 协议维护成本，vendor 绑定。
- **路线 3：Expert replication / placement（[[CRAFT-MLSys26]]、[[Libra-ICLR26]]、EPLB）**：热 expert 复制或 speculative routing 缓解倾斜；牺牲是显存（replica 挤占 KV cache）与模型质量（auxiliary loss）。
- **路线 4：Expert paging / caching（[[FluxMoE-arXiv26]]）**：decode 阶段冷 expert 驱逐出 HBM；牺牲是 page fault 延迟与 disagg 场景复杂性。
- **路线 5：算子融合与通信 overlap（[[FarSkip-Collective-MLSys26]]、[[MoEBlaze-MLSys26]]）**：残差连接重叠 dispatch/combine、index 列表替代 routing buffer；牺牲是框架侵入性。
- **路线 6：Disagg 下 phase-specific EP 度数**：prefill dense batch vs decode sparse token 配不同 EP（[[NVIDIA-Disagg-Study-MLSys26]]）；牺牲是 rate matching 与 KV 跨池传输复杂度。

## 引用本概念的论文

- [[CRAFT-MLSys26|CRAFT]] — per-layer replication benefit 估计 + MCKP 分配 replica 预算，vs EPLB 平均 1.14× goodput、replica 少 7.25–7.5×
- [[LayeredPrefill-MLSys26|LayeredPrefill]] — chunked prefill 引发 MoE sparsity erosion；按 layer-group 调度消除冗余 HBM traffic
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — casting-free FP8 MoE 训练流，高 EP 下消除 Q/DQ 碎片开销，671B 吞吐 +21%
- [[NEST-MLSys26|NEST]] — device placement 原生支持 EP 与 ZeRO 联合搜索，1024 GPU 模拟
- [[Libra-ICLR26|Libra]]、[[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — MoE LB 专项：speculative gating / ILP heuristic
- [[MoEBlaze-MLSys26|MoEBlaze]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]] — EP 训练通信 / kernel 优化
- [[ParallelKittens-MLSys26|ParallelKittens]]、[[AXLearn-MLSys26|AXLearn]]、[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 框架 / 训练 / Disagg 里的 EP
- [[HetRL-MLSys26|HetRL]] — 异构 RL 调度含 intra-model TP/PP 与 tasklet placement
- [[FCP-MLSys26|FCP]] — 与 FSDP/TP/EP/SP 透明组合的 flexible context parallelism
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 5D 并行中 EP 对 MoE 推理部署的系统级 trade-off
- [[FluxMoE-arXiv26|FluxMoE]] — disaggregated serving decode 阶段 expert paging 腾 HBM 给 KV cache
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]]、[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]]、[[OD-MoE-arXiv25|OD-MoE]] — edge/offload/CXL 场景 EP 变体
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — MegaMoE 融合 EP kernel 1.5–1.96× 加速
- [[SHIP-MLSys26|SHIP]] — MoE 小 batch 下 per-token expert 执行保 pipeline 平衡
- [[TokenWeave-MLSys26|TokenWeave]]、[[MixLLM-MLSys26|MixLLM]] — serving 调度与 EP 交互
- [[Charon-MLSys26|Charon]]、[[FlexTrain-MLSys26|FlexTrain]] — EP 仿真 / 弹性训练（EP 度固定）

## 已知局限 / 开放问题

- decode 阶段 + 多节点 EP 的在线 LB 仍是开放问题（[[Libra-ICLR26]]、[[LatencyOptimal-MoELB-INET4AI25]] 聚焦 prefill + 单节点）
- [[CRAFT-MLSys26]] 优化目标是 offline balancedness gain 而非直接端到端 latency；production trace 上 routing 漂移的闭环行为未验证
- expert placement 在异构硬件混布下尚无成熟方案；[[NEST-MLSys26]] 静态网络成本不建模 dynamic congestion
- chunked prefill 与 EP 的 sparsity erosion（[[LayeredPrefill-MLSys26]]）在 multi-GPU / disagg 环境未充分验证
- FP8 EP 在开启 overlap 的 production 1F1B schedule 上的净收益待重测（[[FP8FlowMoE-MLSys26]] future work）
