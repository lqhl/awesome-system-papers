---
type: concept
aliases: [MoE, Mixture of Experts, Mixture-of-Experts, mixture of experts]
last_updated: 2026-08-18
tags: [llm-architecture, sparse-activation, scaling]
---

# MoE

> 混合专家模型（Mixture of Experts，MoE）为每个 token 只激活少数 expert，用近似不变的活跃 FLOPs 换更大的总参数容量。模型侧的稀疏计算会在系统侧变成动态路由、大权重存储、细粒度 all-to-all 和负载长尾。

## 核心思想

一个常见 MoE layer 有四步：

1. router/gate 为每个 token 打分，选 top-k experts；
2. dispatch 将 token activation 按 expert 重排，必要时经网络发到 expert 所在 GPU；
3. 各 expert 执行自己的 FFN/GEMM；
4. combine 把多个 expert 输出按 router 权重合并回原 token 顺序。

“每 token 只激活 k 个 expert”只减少本次数学计算，不会自动减少全部 expert 权重的存储、router/dispatch metadata、padding、跨 GPU 通信和热点 expert 排队。训练通常再叠加 [[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]] 和 [[Data-Parallelism]]；推理还要与 [[KV-Cache]] 共享 HBM。

## 为什么重要

MoE 把“大模型放不下”和“每次只用一小部分”同时带入系统。这使它既适合大集群的 expert parallel，也适合大主存+小 GPU 的本地 offload，但两者需要完全不同的设计。

OSDI 2026 的论文把这个范围展示得很清楚：

- [[Wang-LocalMoEInference-OSDI26]] 在单节点中用 CPU DRAM 存约 1 TB 原始 FP8 权重，长 prefill 流式上 1–2 张 RTX 5090，decode 则在 CPU 执行 expert。
- [[UEP-OSDI26]] 把 MoE 通信重写成 GPU 发起、CPU proxy 执行 GPUDirect RDMA 的 token-level 路径。
- [[UCCL-Tran-OSDI26]] 从 transport 层处理 all-to-all path collision 和 incast。
- [[Tessera-OSDI26]] 将 router 波动、MoE 通信重叠和 pipeline partition 联合调度。
- [[BatchGen-OSDI26]] 在离线推理中打破“一个 sequence 长期绑一张 GPU”，在 attention–MoE 边界合并来自多个 sequence 的 token。
- [[RollArt-OSDI26]] 把 MoE agentic RL 的 rollout、environment、reward 和 trainer 放到不同硬件域，在 3,000 多张 GPU 上运行。

所以 MoE 不是单一 kernel 概念；它同时改变模型结构、并行抽象、内存配置、网络流量和容错状态。

## 关键观察 / 隐含假设

- **稀疏 FLOPs 不等于稀疏系统成本。** [[MoE-Serving-Tax-MLSys26]] 系统化展示 dispatch/combine、padding、expert 小 batch 和负载不均可吃掉理论稀疏收益。因此不能用“活跃参数只有总参数的某个比例”直接预测 token/s。
- **prefill 和 decode 的 expert 执行路径可以相反。** [[Wang-LocalMoEInference-OSDI26]] 中，长 prefill 是高算术强度 GEMM，适合将权重流式上 GPU；低并发 decode 是带宽受限 GEMV，只读激活 expert，适合留 CPU。系统在 4K token 以下不用流式 prefill，说明 crossover 强依赖 prompt 长度、DRAM/PCIe 带宽和 GPU 能力。
- **小规模 expert parallel 不能直接照搬云端方案。** 同一论文的两张无 P2P GPU 上，标准 EP=2 的 dispatch/combine 占20K-token prefill 单层约 31% 时间；SmallEP 先复制 token，再各卡本地 routing 和局部归约，仅在 EP size 不大于每 token 激活 expert 数的小 EP 场景有明确优势。
- **MoE 通信是细粒度、动态、稀疏 all-to-all。** [[UEP-OSDI26]] 以 DeepSeek-V3 为例描述每个 FP8 token activation 约 7 KB、可发往 8 个 experts。标准大 buffer packing 会占 GPU SM，逐条小发送又难打满 NIC。UEP 用 CPU proxy 换 portability，代价是每 GPU 最多 4 个 CPU cores 与新的 host-side failure surface。
- **网络收益可能来自避免 collision，而非单链路更快。** [[UCCL-Tran-OSDI26]] 在无拥塞 InfiniBand 上与 ConnectX-7 基本相当，跨机架 all-to-all 才因多路选择最高提高 4.54 倍 bus bandwidth；真实 16B DeepSeek-V2-Lite 训练吞吐最高提高 7.5%。这两个数字不能互换。
- **最佳 pipeline stage 取决于“重叠后”成本。** [[Tessera-OSDI26]] 发现不同 MoE layer pair 能隐藏的通信比例相差约 3 倍，因此先生成并实测细粒度 schedule，再选 pipeline partition。其 20.0%–32.8% MFU 提升来自 4,096–12,288 张 Hopper 上的五个生产任务，不是通用单机结论。
- **attention 和 expert GEMM 喜欢不同 batch 大小。** [[BatchGen-OSDI26]] 观察到 attention 在较小 batch 已饱和，几百个 experts 却需要更大 global batch 才能让每个 GEMM 变大。在 module boundary yield 能重组 token，但要保存 hidden/KV state，更适合离线 batch-completion-time 而非严格在线 SLO。
- **请求路由和 expert 路由不是同一层问题。** [[LMetric-OSDI26]] 的集群 router 虽然评测了 Qwen3 MoE，但 score 只看请求的待算 prefill token 与实例 batch size；它不观察 token 会命中哪个 expert。该结果可说明 MoE 模型也需要 request placement，不能证明 expert hotspot 已被解决。
- **expert 热度预测是缓存/迁移系统的隐含前提。** [[PopFetcher-ATC25]]、[[FluxMoE-arXiv26]]、[[OD-MoE-arXiv25]] 分别用预取、paging 或预测式加载处理冷 expert。routing 随 domain、batch 和训练漂移时，当前 hotness 不一定能预测下一层/下一批。
- **稀疏结构会扩大正确性与恢复状态。** [[OpGuard-OSDI26]] 需在 MoE dispatch/combine 边界对齐 tensor；[[SDCHunter-OSDI26]] 要重写 deterministic MoE routing/scatter 才能重放 SDC；[[TrainMover-OSDI26]] 的 shadow iteration 记录数据在 GPT-5.12T MoE 设置下可少于 300 GB，但动态 routing 没覆盖到的路径仍可在切换后触发冷初始化。

## 设计空间与取舍

| 维度 | 选择 | 好处 | 主要代价 |
|---|---|---|---|
| routing | top-1/top-k、容量限制、负载均衡 loss | 控制活跃计算与专家分工 | token drop/padding、质量与系统负载耦合 |
| expert placement | 分片、复制、迁移、paging/offload | 减通信或扩大可容纳模型 | HBM 占用、miss stall、链路带宽 |
| 执行位置 | GPU、CPU、NDP | 适应容量和算术强度 | kernel 生态分裂、精度/指令依赖 |
| 通信粒度 | 大 buffer collective、token-level P2P | 高带宽或低延迟 | packing SM 成本或大量小消息 |
| 调度 | 静态 stage、在线 routing-aware | 稳定低开销或适应漂移 | 离线 profile 失效或控制面开销 |
| 批粒度 | sequence batch、expert batch | 简单 request SLO 或大 expert GEMM | 一端改善会恶化另一端 |
| 精度/近似 | 原生 FP8/FP4、量化、延后/跳过 expert | 减容量和带宽 | 需要独立 model-quality 证据 |

## 引用本概念的论文

- [[Transformer-NeurIPS17]] — Transformer 稠密 FFN 的模型上游，为后续稀疏 expert layer 提供基础。
- [[MoE-Lightning-ASPLOS25]] — 以 CGOPipe 和 Hierarchical Roofline Model 联合安排 CPU attention、GPU expert 与权重传输；长 context 时 CPU bandwidth 可能重新成为瓶颈。
- [[KTransformers-SOSP25]] — 在低并发本地场景中用 CPU 执行 expert，并以 Expert Deferral 换取 CPU/GPU 重叠。
- [[Wang-LocalMoEInference-OSDI26]] — 将长 prefill、短 prefill 和 decode 拆到 GPU stream-loading 与 CPU expert 两类路径。
- [[UEP-OSDI26]] — 为跨 GPU/NIC 的 token-level expert dispatch 提供可移植 host proxy。
- [[UCCL-Tran-OSDI26]] — 在 NCCL/RCCL 下插入可编程 transport，处理 all-to-all collision/incast。
- [[Tessera-OSDI26]] — 联合实测 MoE schedule、pipeline partition 和 bubble filling。
- [[BatchGen-OSDI26]] — 在 attention–MoE 边界跨 sequence 合并 expert batch，优化离线完成时间。
- [[RollArt-OSDI26]] — 大规模异构 MoE agentic RL 的任务域放置和异步 trajectory。
- [[MPK-OSDI26]] — 在 persistent mega-kernel 中保留静态 expert task，再按运行时 top-k metadata 动态分配 token 工作。
- [[Nixie-OSDI26]] — 将 MoE 权重作为普通 GPU 对象做 pin/migration；它降低切换成本，但不利用 expert 可预测、可复制等专门语义。
- [[LMetric-OSDI26]] — 在 dense/MoE serving 上优化请求级 prefix locality 与实例负载，不处理 token-level expert placement。
- [[MoE-Serving-Tax-MLSys26]] — 分解稀疏模型在 serving 中的真实系统税。
- [[FarSkip-Collective-MLSys26]] — 修改 forward/backward/autograd 以增加 expert-parallel communication overlap。
- [[CRAFT-MLSys26]] — 按成本和热度选 expert replication。
- [[FluxMoE-arXiv26]] — 分页管理 expert 权重，将 HBM 在 expert 和 KV 之间弹性分配。
- [[PopFetcher-ATC25]] — 在 Megatron 生态中预取 MoE expert，依赖 routing locality。
- [[TrainMover-OSDI26]] — 暴露动态 MoE 路径对 shadow warm-up 和 rank 迁移的覆盖问题。
- [[Kareus-OSDI26]] — 说明动态 MoE routing 可让按重复分区离线搜索的通信—能耗计划失效。
- [[OpGuard-OSDI26]]、[[SDCHunter-OSDI26]] — 把 router/dispatch/collective 顺序纳入正确性对齐与 SDC 重放。
- [[PithTrain-arXiv26]] — 将 PP×FSDP×CP×EP、DualPipeV overlap、FP8 与 fused routing kernel 收进约 11 KLoC 的 agent-native 训练栈；5 组 H100/B200 配置中有 4 组匹配或超过 Megatron-LM，但模型与平台覆盖显著更窄。

## 已知局限 / 开放问题

- **router quality 和 system balance 仍被分开优化。** 迁移/复制 expert 会改变优化器想要的负载分布，而 load-balancing loss 也可使模型质量变化。需要同时报吞吐、尾延迟、专家使用和模型质量。
- **缺少可组合的 expert 状态抽象。** 权重、quantization scale、router 版本、optimizer state、缓存副本和 in-flight token 在迁移/故障时应如何一致，尚没有统一契约。
- **静态 profile 易受 routing drift 影响。** domain、prompt、batch、模型更新和多租户干扰都会改变 expert hotness 和通信 pattern；在线重规划又可在关键路径引入 stall。
- **高可用证据不足。** 大部分性能论文没有覆盖 expert host/GPU 失败、路由重试、半完成 all-to-all、权重版本切换和相关机架故障。
- **跨层联合调度空间太大。** router、expert placement、EP/TP/PP、KV budget、transport、batch 和 DVFS 都会相互影响；穷举全部配置不现实，但独立调优又容易选到局部最优。
