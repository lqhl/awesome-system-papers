---
type: concept
aliases: [continuous batching, Continuous Batching, iteration-level scheduling, in-flight batching, dynamic batching, Orca-style batching]
parent: "[[LLM-Inference]]"
introduced_by: Orca (OSDI 2022)
last_updated: 2026-08-17
tags: [llm-inference, scheduling, batching]
---

# Continuous-Batching

> 连续批处理（continuous batching）在每次模型迭代前重新组织正在运行的请求：已经结束的请求退出，新请求可以加入，未结束请求继续生成。它避免静态 batch 被最长输出拖住，但也把请求调度、KV 内存、动态 shape 和尾延迟紧密绑在一起。

## 核心思想

自回归生成每轮通常为每个请求产生一个 token，但不同请求的输出长度差很多。静态 request-level batching 要等整个 batch 的所有请求结束，短请求完成后仍占着位置。连续批处理把执行单位改成 iteration：调度器维护 active set，每轮为仍活跃的序列准备输入、block table 和采样状态，再执行一次 forward。

它并不保证每轮只做 decode。新请求的 prefill 可以单独运行，也可以通过 [[Chunked-Prefill]] 分块后与 decode 混合。一次 iteration 的成本由 active request 数、每个请求读多少 KV、prefill token 数、speculative draft/verify 长度、模型并行和 kernel 选择共同决定。

因此目标不应只是“把 batch 填满”。更实用的目标是在 TTFT、TPOT/TBT、KV 容量和公平性约束下，最大化满足 SLO 的 goodput。

## 为什么重要

连续批处理是现代 LLM serving runtime 的基础时间抽象。[[vLLM-SOSP23]] 说明，它和 paged KV 管理是互补关系：调度器让请求随时加入退出，分页式 KV 才能按需增长并控制碎片。[[SGLang-NeurIPS24]] 又把跨请求 prefix reuse 放进同一个动态内存池。

几乎所有更上层机制都会改变 iteration：量化决定用哪种 GEMM，稀疏 attention 决定召回哪些 page，speculative decoding 一次可能验证多个 token，P/D 分离改变 active set 所在的实例，LoRA 会增加 adapter 装载，故障恢复还会恢复 partial KV。连续批处理不是一个固定算法，而是这些机制的共同调度面。

## 关键观察 / 隐含假设

- **时间利用率和空间利用率必须一起解决。** [[vLLM-SOSP23]] 把 iteration-level scheduling 与 [[PagedAttention]] 结合；若 KV 仍按最大长度连续预留，动态加入更多请求很快会耗尽 HBM。
- **更大 batch 并不总是更好。** batch 增大通常提高 GEMM 利用率，却也增加排队、TPOT 和 KV 占用。[[DCP-OSDI26]] 还发现 decode cost 有硬件效率台阶，129 个 token 可能接近 256 个的成本；简单线性模型会选错。
- **prefill 会阻塞正在生成的请求。** [[EcoServe-OSDI26]] 说明即使 separate/hybrid batching 或 chunking 已经存在，频繁 prefill/decode 切换仍会损害 TTFT、TPOT 和 decode batch 积累；它的 phase-based 方案用更粗时间窗口换少干扰。
- **MoE 会让“混成大 batch”产生反效果。** [[LayeredPrefill-MLSys26]] 发现 prefill 与 decode 的 hybrid batch 可能激活几乎全部 experts，却没有足够的 per-expert token 进入 compute-bound 区。结果只覆盖两种 MoE 和单机 TP，不能外推到所有模型。
- **动态 shape 会传到 kernel 和编译层。** [[ADAngel-OSDI26]] 的不同精度 GEMM 最优实现随 prefill/decode 和矩阵形状改变；[[EventTensor-MLSys26]] 则把 continuous batching 的 shape 变化作为静态 CUDA Graph/megakernel 难点。两者都没有给出通用在线 cost model。
- **算子边界可能比请求边界更粗。** [[MPK-OSDI26]] 在 persistent mega-kernel 内按 tensor fragment 调度，让不同算子的 SM tasks 提前重叠。不过主评测是固定 offline arrival、prompt 和输出，尚不能证明线上 P99 与多租户公平性。
- **KV residency 会决定谁能进入 active set。** [[Strata-OSDI26]] 在分层缓存 load 较慢时先运行 ready decode，[[OPKV-MLSys26]] 又指出稀疏召回需要 layer-level metadata 更新，比中心化 iteration-level RPC 更细。调度器不能只看计算队列。
- **speculation 让请求进度不再同步。** [[ReSpec-MLSys26]] 的 RL generation 中，active batch 随长尾输出下降，系统需要按 batch 动态开关 speculation。结果来自训练 rollout，不等同于一般在线聊天流量。
- **多租户附加状态会打断 iteration。** [[Toppings-ATC25]] 发现 LoRA adapter 按需装载会累计阻塞 inflight decode；CPU-assisted prefill 缩短了中断，但没有消除 prefill/decode 的结构冲突。

## 设计空间与取舍

- **何时 admission**：一有空位就加入能减少等待，可能让当前 iteration shape 抖动；按窗口或 bucket 等待更容易形成高效 batch，却增加低负载延迟。
- **prefill 策略**：整段 prefill 的 GPU 效率高、阻塞长；chunked prefill 控制 TPOT，但增加轮次和 partial state；P/D 分离进一步隔离阶段，同时需要传 KV。
- **调度目标**：FCFS 简单；deadline、priority 或 slack-aware 策略提高 SLO 合规率，可能牺牲长请求和低优先级租户。
- **KV admission 与 eviction**：只根据剩余 block 数最直接；结合 prefix reuse、slow-tier load、未来增长和取消概率更准确，也更依赖预测。
- **host scheduler 或 device scheduler**：CPU 易实现复杂策略，但有 launch/RPC 开销；[[MPK-OSDI26]] 和 [[EventTensor-MLSys26]] 把部分调度下沉 GPU，换来更强架构绑定和调试成本。
- **每轮一个 token或可变进度**：普通 decode 容易对齐；speculative、diffusion 或 multi-token 方法提高吞吐，却使验收数、KV rollback 和 batch 重组更复杂。
- **在线服务或离线批推理**：[[BatchGen-OSDI26]] 认为大规模离线任务不应让一个 sequence 长期绑定一张 GPU，而应在 attention–MoE 边界迁移和重组 coroutine。这个结论不直接适用于严格交互 SLO。

## 引用本概念的论文

### 基础与直接扩展

- [[vLLM-SOSP23]]、[[SGLang-NeurIPS24]]：分别把动态请求集合与 paged KV、prefix reuse 结合。
- [[NEO-MLSys25]]：在每个 iteration 联合决定 CPU/GPU request 与 prefill/decode batch，CPU contention 是新增边界。
- [[BlendServe-ASPLOS26]]：离线场景可预先重排完整 request set，不应把其吞吐直接外推在线 continuous batching。
- [[SkyWalker-EuroSys26]]：用 pending admission signal 在跨 region replica 间做 selective pushing。
- [[Agentix-NSDI26]]：在 continuous batch 之上加入 program identity 与进度优先级，改变公平性目标。
- [[DCP-OSDI26]]、[[EcoServe-OSDI26]]、[[LayeredPrefill-MLSys26]]：研究 prefill/decode 混合的流水线、阶段和 MoE 代价。
- [[MPK-OSDI26]]、[[EventTensor-MLSys26]]、[[NanoFlow-OSDI25]]：把调度粒度从 request/operation 继续下沉到 fragment、event 或 nano-op；在线证据强度不同。
- [[ADAngel-OSDI26]]、[[MixLLM-MLSys26]]、[[QFactory-ATC25]]：说明 batch shape 会改变低精度 kernel 的最优实现；其中 QFactory 的连续批处理仍是后续评测项。

### KV、缓存和状态

- [[Strata-OSDI26]]、[[DirectKV-OSDI26]]、[[OPKV-MLSys26]]、[[SuperInfer-MLSys26]]：处理 slow-tier KV、zero-copy、稀疏召回和 KV 旋转；DirectKV 尚未完成 production continuous-batching 集成。
- [[KVCacheInTheWild-ATC25]]、[[CacheSlide-FAST26]]、[[ContextPilot-MLSys26]]：真实复用、跨位置复用和 context reuse 会改变 admission 与 prefill 工作量。
- [[GhostServe-MLSys26]]：让在线 active requests 的 KV checkpoint 与恢复进入调度面。

### 工作负载和架构变化

- [[ReSpec-MLSys26]]、[[TiDAR-MLSys26]]：speculative 或 hybrid generation 使每轮前进 token 数变化；TiDAR 尚未完成 production continuous-batching 评测。
- [[Toppings-ATC25]]、[[Sirius-ATC25]]：adapter 装载和训练共置会抢占服务资源。
- [[BatchGen-OSDI26]]、[[PrefillOnly-SOSP25]]：分别说明离线 heavy-tail batch 与只做 prefill 的 workload 不应照搬普通交互式执行模型。
- [[TriInfer-MLSys26]]、[[NVIDIA-Disagg-Study-MLSys26]]：把多模态 encode 或 P/D 独立资源池纳入动态 batch 和 rate matching。
- [[FlashAttention-4-MLSys26]]、[[SolidAttention-FAST26]]、[[CDLM-MLSys26]]、[[BOA-MLSys26]]、[[DataflowIsAllYouNeed-MLSys26]]：这些论文主要把 continuous batching 当作未覆盖的生产环境、硬件边界或相关概念，不能据此声称其结果已在线上动态 batch 下验证。

## 已知局限 / 开放问题

- 需要同时建模 token 数、序列长度、KV residency、cache hit、expert skew、speculative acceptance 和硬件效率台阶；单变量 latency model 很容易漂移。
- burst、取消、优先级和长短请求混合时，应报告 P99、饥饿和租户公平性，而不只是平均吞吐。
- GPU 下沉调度、CUDA Graph 和 dynamic shape 的组合会扩大预热、binary cache 与调试成本。
- KV offload、prefix reuse 和故障恢复改变请求状态的 ownership；扩缩容或重试时需要明确何时能安全迁移 active request。
- 许多论文只在固定 Poisson 到达或 offline batch 上评测。生产 trace、低负载能耗和 scheduler CPU 开销仍缺统一报告方法。
