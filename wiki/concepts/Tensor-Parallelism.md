---
type: concept
aliases: [Tensor Parallelism, Tensor-Parallel, tensor-parallel, TP, Megatron-style parallelism, intra-layer parallelism]
parent: "[[LLM-Inference]]"
last_updated: 2026-08-17
tags: [distributed-training, llm-inference, parallelism]
---

# Tensor-Parallelism

> 张量并行（tensor parallelism，TP）在一层内部切分矩阵、Attention head 或其他 tensor，让多张加速卡共同完成一次算子；它用频繁通信换取更大的可用显存和聚合算力。

## 核心思想

以 Transformer MLP 为例，Megatron-style TP 常先按输出维切分第一个线性层（column parallel），每张 GPU 得到一部分中间通道；第二个线性层再按输入维切分（row parallel），各卡产生 partial result，最后用 AllReduce 合并。Attention 可以按 head 或投影维切分，KV 也按相同布局保存在各 rank。这样单卡不用保存和计算整层，但每个 block 会出现多次 collective。

TP degree 表示一份模型跨多少张卡。degree 增大时，每卡权重、KV 或中间张量通常减少；单卡 GEMM 也变小，通信参与者与同步频率增加。收益取决于矩阵形状、batch、序列长度和互连。只有在减少的计算与容量压力大于 collective、launch 和小 GEMM 损失时，更多 GPU 才更快。

训练中，TP 要和 [[Data-Parallelism]]、[[Pipeline-Parallelism]]、sequence/context parallelism、[[Expert-Parallelism]]、[[FSDP]] 或 [[ZeRO]] 组合。推理中，它还要和 prefill/decode 阶段、[[KV-Cache]] 布局、[[Continuous-Batching]]、SLO 与实例复制共同选择。TP 不是“模型并行”的同义词，也不是固定应该优先于 PP 的默认答案。

## 为什么重要

第一个作用是让单卡放不下的层可执行。第二个作用是缩短单次大矩阵计算，适合 compute-bound prefill 或训练。第三个作用是利用 NVLink/NVSwitch 等高带宽域把一组 GPU 变成一个逻辑 worker。

代价是通信在每层重复发生。[[TokenWeave-MLSys26]] 对 8×H100 的 dense LLM 测得，TP AllReduce 即使走 NVLink 仍占 9%–23% 延迟，紧随其后的 RMSNorm 另占 4%–9%。[[DCP-OSDI26]] 则在 4×A100 PCIe 上发现，低带宽互连使高频 AllReduce 足以让动态 PP 获得更高 goodput。这两个结果并不矛盾：它们共同说明 TP 的结论必须绑定拓扑、阶段和 batch。

TP 还会固定状态布局。模型权重、optimizer state、KV block、checkpoint 和通信组都按 degree 与切分轴分片；改变 TP degree 需要重新分片或重载状态。[[UCP-ATC25]]、[[TrainMover-OSDI26]]、[[AdaCheck-FAST26]] 分别从可重配 checkpoint、rank 替换和冗余检测角度说明，并行布局已经是系统状态的一部分。

## 关键观察 / 隐含假设

- **观察：互连拓扑决定 TP 的第一条边界。** [[DCP-OSDI26]] 的“PP 优于 TP”只在单机 4×A100 PCIe 4.0、Qwen2.5-14B/32B 和论文 SLO 下成立；作者明确指出 NVLink/NVSwitch 上 TP 通信更便宜，结论可能反转。跨节点 TP 通常更难，因为 collective 延迟与网络争用更高。
- **观察：prefill 与 decode 的最佳 degree 不一定相同。** prefill token 多、GEMM 大，容易摊销通信；低 batch decode 每步矩阵小，collective 和 kernel launch 占比更高。固定一套 TP 配置便于运行，却可能让一个阶段为另一个阶段买单。
- **观察：通信重叠只有超过 break-even 才有收益。** [[TokenWeave-MLSys26]] 通过 smart splitting 和 AllReduce–RMSNorm 融合，从约 1K tokens 起让 dense model prefill iteration 相对 vLLM-Multimem 加速 1.16–1.28 倍，ShareGPT 吞吐最高提高 1.19 倍；Mixtral 在 1K/2K tokens 开完整 overlap 反而有净开销，4K 起才启用。
- **观察：模型结构可以改变传统 TP 的最佳切法。** [[BOOST-MLSys26]] 为低秩 bottleneck Transformer 重做切分；30B 模型在 16×A100 的短 iteration benchmark 中为 1.27 秒，FullRank-TP 和 Vanilla-TP 为 2.43/2.58 秒。它说明 Megatron 切法不是所有架构的最优模板，但实验只到 4 节点。
- **观察：TP 会损失实例级并发。** [[Weaver-ATC25]] 在 2×A100-40GB NVLink 上测得 Llama-3-8B TP=2 相对两个独立实例有 17.5%–26.6% token throughput 损失；WEAVER 因而把 hot 模型的一部分非参数化 Attention 工作交给 cold GPU，而不是把整个 hot 模型直接做更宽 TP。
- **观察：运行时长尾可能临时改变并行方式。** [[BatchGen-OSDI26]] 在离线 batch 末尾对单条 straggler 使用 TP、对多条 straggler 使用 DP；但一次 `PARTITION` 重配置约需 5–10 秒，只在剩余任务足够长时划算。这给“弹性 TP”一个明确 break-even，而不是无成本切换。
- **观察：TP rank 的形状对称性有利于恢复。** [[TrainMover-OSDI26]] 让 standby 用无通信 shadow iteration 预热 TP/DP/EP 角色，在 1,024 GPU 实验中把计划迁移和意外故障停机分别降到 16.6 秒、21.1 秒。它保持原并行布局，没有证明动态改变 TP degree 同样便宜。
- **观察：并行布局会进入正确性与持久化语义。** [[TrainCheck-OSDI25]] 用 TP rank 间 LayerNorm 权重发散展示 silent error；[[TrainVerify-SOSP25]] 验证 parallelized data-flow graph 与逻辑图等价；[[AdaCheck-FAST26]] 则利用 TP/DP/PP/EP 产生的 tensor redundancy 压缩 checkpoint。性能 planner 不能把这些状态只当作通信字节。
- **观察：TP 需要和 PP/EP 的重叠一起规划。** [[Tessera-OSDI26]] 在 4,096–12,288 张 Hopper GPU 的异构 MoE 训练中，不改变高层并行模板，而是联合选择 PP partition 与细粒度通信重叠；MFU 相对提高 20.0%–32.8%。这里的收益来自整个 TP/PP/EP 组合和生产 Megatron baseline，不能单独归因于 TP。
- **假设：各 shard 工作量大体均匀。** 标准 head/channel 切分默认每个 rank 计算和通信相近；MoE routing、变长序列、非均匀 head、异构 layer 或硬件慢卡会破坏这个前提。[[ECHO-OSDI26]] 还说明 MLA KV 在其部署中采用 DP，不能简单用 TP 把单个 worker 的 KV cache 横向摊开。
- **假设：collective group 与软件栈稳定。** kernel、NCCL 算法、拓扑、后台流量和 GPU 频率都会移动 crossover。离线 profile 若不带版本和硬件标签，很容易把旧结论用于错误环境。

## 设计空间与取舍

- **TP degree**：小 degree 保留大 GEMM 和更多独立副本，通信少；大 degree 降低每卡容量并聚合算力，collective 与同步更多。planner 应按实际模型和 SLO 扫描，而不是默认取节点内 GPU 数。
- **切分轴**：MLP column/row、Attention head、vocab、sequence/context 和低秩维度的通信位置不同。结构化模型应重新推导，而不是机械套用 dense Transformer 模板。
- **collective 实现**：AllReduce 可以拆成 ReduceScatter + AllGather，也可融合后继 RMSNorm 或与 GEMM 重叠。[[TokenWeave-MLSys26]] 说明小 tensor 上简单拆分会变慢，必须控制 CTA wave 和通信占用的 SM。
- **TP 与 PP**：TP 每层通信、没有 pipeline bubble；PP 只在 stage 边界传 activation，却会受到 microbatch 与阶段失衡。[[DCP-OSDI26]] 的动态 chunk 和 delay scheduling是在低带宽域修复 PP，不是一般性的 TP 替代。
- **TP 与 DP/实例复制**：TP 扩大单实例能力，DP 增加独立并发。在线低 batch serving 常更偏向多副本，模型太大或 prefill 很重时才扩大 TP；[[Prism-OSDI26]] 把一个 TP GPU group 视为不可再拆的副本，并对 shard 做 anti-affinity。
- **TP 与 EP**：MoE routed expert 更适合 EP，dense Attention/MLP 仍可 TP。两类 collective 竞争相同网络和 SM，单独优化其中一个可能把瓶颈推给另一个。
- **静态与动态重配置**：静态配置简单、状态稳定；动态 degree 可适应阶段和长尾，却要重建通信组、reshard 权重/KV/checkpoint。BatchGen 的 5–10 秒重配和 TrainMover 的角色保持设计都说明该成本不能忽略。
- **权重预取换 activation 通信**：[[mTuner-ATC25]] 在 LoRA 微调中提前 gather 静态权重，缩小后续 activation collective group；相对所测基线，PCIe/NVLink 平均吞吐提高 28.3%/14.5%。这种方法利用 frozen base weight，可变全量训练未必适用。
- **执行图捕获**：TP rank 的频繁 launch 和同步让 [[CUDA-Graph]] 更有价值。[[GraCE-OSDI26]] 在 1/2/4×H100 的四个 TP workload 上，相对 PyTorch2-CG 最高加速 3.56 倍、平均提高 75%；结果来自筛选的 CG-sensitive workload，不是所有 TP 训练的平均收益。

## 引用本概念的代表性论文

- [[MoE-Lightning-ASPLOS25]] — 在单节点用 TP 增加总 HBM，2→4 T4 的超线性收益来自解除 memory-capacity bottleneck，不保证跨节点成立。

- [[vLLM-SOSP23]] — 在推理中按 Attention head 切 KV shard，并由 centralized manager 维护统一 block table。
- [[DCP-OSDI26]] — 给出 PCIe GPU 上动态 PP 与 TP 的受控 crossover 证据。
- [[TokenWeave-MLSys26]] — 在 8×H100 上融合并重叠 TP AllReduce 与 RMSNorm。
- [[BOOST-MLSys26]] — 为低秩 bottleneck Transformer 设计不同于普通 Megatron 的 TP。
- [[Weaver-ATC25]] — 量化 TP=2 相对两个独立 serving instance 的吞吐代价，并提出跨模型 Attention offload。
- [[BatchGen-OSDI26]] — 在离线 batch 的单 straggler 尾部临时切到 TP。
- [[ECHO-OSDI26]] — 说明原生稀疏 Attention 的 MLA KV 在所测部署中不能靠扩大 TP 直接解决容量问题。
- [[Prism-OSDI26]] — 将 TP GPU group 当作多模型放置的原子单位，并约束 shard anti-affinity。
- [[SuperInfer-MLSys26]] — 在 TP=2 的 GH200 上验证 KV rotation 仍有效；没有搜索 TP degree。
- [[TrainMover-OSDI26]] — 利用 TP/DP/EP rank 形状对称性预热 standby，但保持并行布局不变。
- [[Tessera-OSDI26]] — 在固定并行模板内联合规划 PP partition、TP/EP topology 和通信重叠。
- [[GraCE-OSDI26]] — 处理 TP 执行图中的 graph break、参数复制和负优化。
- [[mTuner-ATC25]] — 用 frozen weight 预取改变后续 activation communication 的 TP group。
- [[UCP-ATC25]] — 用 per-parameter 原子 checkpoint 在 TP/PP/DP/ZeRO 布局间转换；1T 模型端到端重配置少于 5 分钟。
- [[AdaCheck-FAST26]] — 自动发现不同并行组合下的 checkpoint tensor redundancy。
- [[TrainCheck-OSDI25]] — 从历史 silent error 中提取并在线检查 TP rank 不变量。
- [[TrainVerify-SOSP25]] — 从形式化角度验证 TP/PP/DP execution plan 的等价性。
- [[WLB-LLM-OSDI25]] — 在长上下文 4D 并行中说明“token 数均匀”不等于 Attention 工作量均匀。
- [[AXLearn-MLSys26]] — 通过配置将 TP、PP、FSDP 和 EP 组合进统一 layer library。
- [[veScale-FSDP-MLSys26]] — 让 FSDP ragged shard 与 TP、EP 及量化 block 语义共存。

## 已知局限 / 开放问题

- **自动选择 crossover。** planner 需要同时建模小 GEMM、collective、kernel launch、KV 容量、batch 和 SLO，并在 PCIe、NVLink、RoCE/InfiniBand 上给出可验证边界。
- **低开销弹性 TP。** 权重、KV、optimizer、checkpoint 与通信组的在线 reshard 仍昂贵；需明确重配置何时能由剩余工作摊销。
- **公平比较并行策略。** TP、PP、DP 和 EP 应使用相同模型语义、kernel backend、SLO 与内存预算；不能让一种方案用调优 chunk、另一种只用默认值。
- **处理非均匀结构。** MoE、GQA/MLA、低秩层、变长文档和异构 GPU 都会破坏均匀 shard 假设，planner 还要考虑 straggler 与 network contention。
- **验证状态正确性。** 动态布局必须证明 block table、optimizer state、randomness、collective order 和 checkpoint 可恢复，不能只验证短时吞吐。
- **报告尾延迟和能耗。** 通信重叠可能提高平均吞吐，却占用 SM、推高功耗或伤害小请求；应同时报告 P99 TTFT/TPOT、GPU-hour 与 energy/token。
