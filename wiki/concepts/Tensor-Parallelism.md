---
type: concept
aliases: [Tensor Parallelism, Tensor-Parallel, tensor-parallel, TP, Megatron-style parallelism, intra-layer parallelism]
parent: "[[LLM-Inference]]"
introduced_by: "[[Megatron-LM-arXiv19]]"
last_updated: 2026-06-20
tags: [distributed-training, llm-inference, parallelism]
---

# Tensor-Parallelism

> 在 **单层内部** 把权重矩阵按列/行切到多个 GPU，局部 matmul 后在层边界 AllReduce 合并 partial sum。Megatron-LM 的经典切法让每层只需两次 AllReduce，但每层都要通信——因此 TP 通常局限在 NVLink 高带宽域（单机 8 卡），跨节点交给 [[Pipeline-Parallelism]] 或 [[Data-Parallelism|Data-Parallel]]。

## 核心思想

考虑 FFN 的两个 matmul：`Y = GeLU(X W₁) W₂`。设 4 卡 TP：

- **W₁ 按列切**：每卡算 `Y_i = GeLU(X W₁⁽ⁱ⁾)`，得到 hidden 的不同列，无通信
- **W₂ 按行切**：每卡算 `Z_i = Y_i W₂⁽ⁱ⁾`，然后 `Z = ΣZ_i`（AllReduce）

Attention 类似：QKV projection 按 head 分组列切（天然适配 multi-head），O projection 行切。每个 Transformer block 需要两次 AllReduce（Attention 出口 + FFN 出口）。

forward + backward 每步约 4 次 AllReduce × 每层 × hidden × batch × seq_len 的数据量。70B Llama、4K seq、batch 4 时单步通信可达 GB 级——NVLink 900 GB/s 尚可，InfiniBand 100–400 Gbps 往往成为瓶颈。典型 3D 并行切法：**TP 机内、PP 跨机器、DP 跨 PP stage**。

演进上，Sequence Parallelism（2022）补充 LayerNorm/Dropout activation 未切问题；Context Parallelism（2024）把 Q/K/V 按 seq 切，FA 需 ring-style 通信；MoE 架构下 expert 权重与 [[Expert-Parallelism]] 交叉切分。

## 为什么重要

TP 是「把单卡放不下的模型塞进集群」的第一道切分维度，也是推理 serving 里 prefill/decode 并行策略的核心旋钮之一。这些论文共同假设：**层内切分的通信频率与 AllReduce 带宽直接决定 TP 的可扩展上限**——因此 TP 度数不是越大越好，而是与 phase（prefill vs decode）、batch 大小、互联拓扑绑在一起。

在训练侧，TP 与 ZeRO/FSDP、PP、EP 组合构成现代大模型训练栈的默认配置；在推理侧，[[Meta-LLM-Deploy-MLSys26]] 和 [[NVIDIA-Disagg-Study-MLSys26]] 均指出 prefill 与 decode 的最优 TP 策略显著不同——宽 TP 利于 prefill 算力聚合，但 decode 阶段 memory-bound 特性使通信开销相对更重。TP 还渗透到 fault tolerance（[[GhostServe-MLSys26]] intra-node TP parity）、异构集群规划（[[Zorse-MLSys26]]、[[BOUTE-MLSys26]]）和 MoE serving tax（[[MoE-Serving-Tax-MLSys26]] padding/straggler）等系统问题。

## 关键观察 / 隐含假设

- **观察 1：prefill 与 decode 的最优 TP 度数 phase-specific，disaggregated runtime 可为两阶段选不同并行配置。** [[Meta-LLM-Deploy-MLSys26]] 报告 70B online 场景下 prefill 用 PP4-TP2、decode 用 TP8 更优；这些论文共同假设 operator 级 microbench 插值足以预测端到端，通信与 runtime overhead 可叠加在关键路径上。
- **观察 2：紧 FTL 长上下文下，prefill 侧宽 TP 的 allreduce 通信量大于 CPP（chunked pipeline parallel）。** [[NVIDIA-Disagg-Study-MLSys26]] 在 DeepSeek-R1 ISL=256K 上显示增大 PP 可同时压 FTL 又保吞吐，相对宽 TP allreduce 通信量小得多（式 1 vs 式 2）。
- **观察 3：小 batch TP 推理中 AllReduce 与 RMSNorm 的 wave 数与带宽拆分税是首次可实用化 overlap 的瓶颈。** [[TokenWeave-MLSys26]] 观察到小 tensor 上 RS+AG 拆分 AllReduce 带宽差显著，smart-split 控制 wave 数可降拆分税；强依赖 NVSHARP/Multimem 硬件代际，跨节点 TP 未验证。
- **观察 4：异构集群上 TP 与 PP/DP 组合搜索需考虑 compute block 规模——越大 TP 收益越高。** [[Quirk-Sparing-MLSys26]] 在训练集群 sparing 建模中发现 compute block 越大 TP 收益越高，影响 goodput 最优 spare 配置；[[Zorse-MLSys26]] 则指出当前 planner **不支持 TP**，层无法放入单卡时 PP+DP 仍会 OOM。

## 设计空间与取舍

- **路线 1：机内宽 TP（Megatron 经典）**：NVLink 域内 4–8 卡 AllReduce，通信延迟低、实现成熟；牺牲是跨节点不可扩展，每层固定通信税。
- **路线 2：TP + PP 3D 并行**：TP 限机内、PP 跨节点 send/recv activation，通信频率从每层降到每 L/S 层；牺牲是 pipeline bubble 与 activation 内存（1F1B / interleaved 1F1B 缓解）。
- **路线 3：完全 DP + ZeRO/FSDP（不切权重）**：通信量 per step 小但需 AllGather 参数；适合 small model 或高带宽互联，与 TP 正交组合（[[veScale-FSDP-MLSys26]]、[[FSDP]]）。
- **路线 4：MoE 下 TP + EP 交叉切分**：expert 内部再 TP 处理单 expert 仍大的情况；牺牲是 AllToAll + AllReduce 双重通信负载（[[FP8FlowMoE-MLSys26]]、[[NVIDIA-Disagg-Study-MLSys26]]）。
- **路线 5：通信 kernel 融合与 overlap**：fused AllReduce–RMSNorm（[[TokenWeave-MLSys26]]）、FarSkip 残差连接重叠 EP dispatch（[[FarSkip-Collective-MLSys26]]）、EventTensor 事件驱动通信；牺牲是硬件/拓扑依赖强，通用性受限。
- **路线 6：irregular GPU 数 hybrid TP**：[[RaidServe-MLSys26]] 用 cyclic [[KV-Cache]] placement 支持 TP7 等不规则切分；牺牲是实现复杂度与 NCCL 拓扑约束。

## 引用本概念的论文

- [[Megatron-LM-arXiv19|Megatron-LM]] — 原始 intra-layer TP 切法：QKV 列切、O/FFN 行切，每层两次 AllReduce
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 生产级模拟器：prefill/decode 最优 TP 策略显著不同，disagg 下可为两阶段选不同并行度
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 紧 FTL 长上下文下 prefill 侧 CPP 优于宽 TP；扫描数百万 disagg 设计点
- [[TokenWeave-MLSys26|TokenWeave]] — fused AllReduce–RMSNorm + wave-aware token split，小 batch TP 推理 overlap 首次实用化
- [[GhostServe-MLSys26|GhostServe]] — intra-node TP 下 chunk gather + parity 生成，对齐 [[Chunked-Prefill]] 做 KV fault tolerance
- [[Zorse-MLSys26|Zorse]] — 异构集群 PP+ZeRO 组合搜索；当前不支持 TP，未来 work 指向 DP+TP
- [[RaidServe-MLSys26|RaidServe]] — irregular GPU 数 hybrid attention + cyclic KV，TP7 decode +78%
- [[SHIP-MLSys26|SHIP]] — 72-LPU 分区 TP+PP 异构分区，QuadFour 拓扑直径 3 hop
- [[Charon-MLSys26|Charon]] — pass 注入 TP/PP/DP/FSDP/ZeRO/EP/SP 通信算子做端到端仿真
- [[AXLearn-MLSys26|AXLearn]]、[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[HexiScale-MLSys26|HexiScale]] — 训练框架并行 runtime
- [[Chakra-MLSys26|Chakra]]、[[ProTrain-MLSys26|ProTrain]]、[[BOUTE-MLSys26|BOUTE]]、[[BOOST-MLSys26|BOOST]]、[[HetRL-MLSys26|HetRL]]、[[NEST-MLSys26|NEST]] — 训练调度 / 异构训练 / 并行策略搜索
- [[OptiKit-MLSys26|OptiKit]]、[[MixLLM-MLSys26|MixLLM]]、[[LayeredPrefill-MLSys26|LayeredPrefill]]、[[DistCA-MLSys26|DistCA]] — 推理阶段 TP 切分
- [[ParallelKittens-MLSys26|ParallelKittens]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]]、[[EventTensor-MLSys26|EventTensor]] — TP 通信 kernel 优化
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]]、[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] — MoE 下 TP/EP padding 与 straggler tax
- [[PROMPTS-MLSys26|PROMPTS]] — 多 agent RAG 自动推荐 TPU ICI-mesh 分片，一次调用命中生产配置 87.5%
- [[Hawkeye-MLSys26|Hawkeye]] — Tensor Core 非确定性 bit-exact 复现，支撑可验证 ML oracle
- [[Quirk-Sparing-MLSys26|Quirk-Sparing]] — 训练集群 sparing 建模中 compute block 越大 TP 收益越高
- [[DreamDDP-MLSys26|DreamDDP]] — geo-distributed Local SGD layer-wise partial sync，与 TP 正交的 DP 优化
- [[FaaScale-MLSys26|FaaScale]]、[[FlexTrain-MLSys26|FlexTrain]]、[[ByteRobust-SOSP25|ByteRobust]]、[[Optimus-ATC25|Optimus]] — 弹性训练 / fault tolerance / MLLM 调度中的 TP 角色
- [[Soze-OSDI25|Soze]] — ML training TP 通信模式与 analytics shuffle 不同，需另测

## 已知局限 / 开放问题

- 跨节点宽 TP 在 IB 上带宽/延迟仍常是瓶颈；[[TokenWeave-MLSys26]] 跨节点 TP 未验证，[[Zorse-MLSys26]] 明确不支持 TP
- prefill/decode 最优 TP 的自动选择缺乏开源标准化工具（[[Meta-LLM-Deploy-MLSys26]] 模拟器未开源）
- irregular GPU 数 TP（[[RaidServe-MLSys26]]）与 NCCL 静态拓扑的兼容性仍是工程难点
- MoE 下 TP+EP 双重通信的 overlap 与 cast-free 量化（[[FP8FlowMoE-MLSys26]]）在 production 1F1B schedule 上的净收益待重测
- Tensor Core 非确定性（[[Hawkeye-MLSys26]]）使 TP 下 bit-exact 复现成为可验证 serving 的开放问题
