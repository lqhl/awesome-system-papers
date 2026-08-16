---
type: concept
aliases: [chunked prefill, Chunked Prefill, chunked-prefill, prefill chunking, split prefill, piggyback prefill]
parent: "[[Continuous-Batching]]"
introduced_by: SARATHI
last_updated: 2026-08-14
tags: [llm-inference, scheduling, batching]
---

# Chunked-Prefill

> 分块预填充（chunked prefill）把一个长 prompt 的 prefill 沿 token 维拆成多次执行。调度器每轮只处理其中一块，并可在同一轮加入正在生成请求的 decode token。它用更细的工作量上限保护 TPOT/TBT，但通常会增加调度状态，并在 TTFT、GPU 利用率和逐 token 尾延迟之间重新取舍。

## 核心思想

一次完成长 prompt 的 prefill，GPU 计算效率通常较高，但这次执行可能持续很久，让已有请求无法按时产生下一个 token。分块预填充给每个调度轮次设置 token budget：先处理 prompt 的第一块，保存产生的 [[KV-Cache]]，之后的块继续读取已有前缀并追加新 KV，直到整个 prompt 完成。

它常与 [[Continuous-Batching]] 一起使用：一个 iteration 中既有若干 prefill token，也有每个 active decode 请求的新 token。这里的“chunk”不是独立请求；后面的 chunk 仍要注意前面的全部上下文。它也不等于 [[Disaggregation|prefill/decode 分离]]：前者是在同一执行环境中切时间片，后者通常把两个阶段放到不同实例并传输 KV。

chunk size 是核心旋钮：

- 小 chunk 缩短单轮阻塞，更容易守住 TPOT/TBT，但矩阵变小、调度轮次增多，TTFT 可能变差。
- 大 chunk 更容易让 GPU 饱和，也能减少重复的 per-chunk 工作，但 decode 要等待更久。
- 最合适的值会随 prompt 长度、decode batch、模型结构、并行拓扑、硬件和 SLO 改变，不能只靠一个全局常数。

## 为什么重要

长上下文和 reasoning workload 让 prefill 与 decode 的时长差越来越大。分块预填充不需要额外 GPU 池或跨节点传输，因此是共置服务中很实用的第一层手段。OSDI 2026 的 [[DCP-OSDI26]] 进一步说明，即使已经分块，固定 chunk 在流水线并行中仍会因负载变化产生 stage bubble；控制器需要结合 SLO 和当前 batch 动态选择。

但“更细就更好”并不成立。MoE、MLA、KV offload、prefix reuse 和 pipeline 都会给每个 chunk 加额外成本。当前论文更像是在画适用边界，而不是证明一个统一的最佳实现。

## 关键观察 / 隐含假设

- **固定 chunk 很难同时适应负载与流水线。** [[DCP-OSDI26]] 在 4 张 PCIe A100 上观察到：小 chunk 减少 P–P/P–D bubble，却降低 GEMM 效率；大 chunk 相反。它用延迟预测按 SLO 选 chunk，再用 delay scheduling 处理 D–D 失衡。结果支持该平台上的机制，但只测 P90 和有限 arrival 形态，不能外推到 NVLink、多节点或 P99。
- **MoE 会把 token 分块转成重复的 expert 权重流量。** [[LayeredPrefill-MLSys26]] 发现，小 hybrid batch 可能覆盖很多 experts，但每个 expert 分到的 token 又不足以饱和计算；每个 chunk 还要重新穿过所有层。其 layer-group 替代方案在两种 MoE、单机双 H100 上有效，尚未覆盖 dense model 和 P/D 分离。
- **MLA 可能在每块重复投影。** [[NVIDIA-Disagg-Study-MLSys26]] 的模拟指出 DeepSeek-R1 MLA 在每个 prefill chunk 重复 down/up projection；缓存展开后的 KV 可以少算，但增加内存和实现复杂度。这个结论依赖模拟器和所用 engine，不能直接套到 GQA 模型。
- **硬件不同，合理 chunk 可以相差几个数量级。** [[SHIP-MLSys26]] 在 SRAM LPU pipeline 中报告 1–2 token 的块也能让 self-attention 饱和，并按生产 P:D 比动态放大。这个结果依赖 LPU 的片上带宽和超长 pipeline，不代表 HBM GPU 也应使用同样大小。
- **分块能成为状态管理的自然边界。** [[GhostServe-MLSys26]] 在每个 prefill chunk 后生成 KV parity checkpoint，减少全量复制；但 gather、PCIe 下刷和恢复本身会占资源，P/D 分离时 parity 应放在哪一侧仍未解决。
- **短 prompt 和长 prompt 可能应走不同路径。** [[Wang-LocalMoEInference-OSDI26]] 在双 RTX 5090 加大容量 CPU DRAM 的本地系统中，让少于约 2K token 的请求走 chunked prefill，长请求使用专门的 prefill 路径。阈值来自这套硬件和约 1 TB FP8 MoE 权重，不能当作通用规则。
- **调度需要同时看 KV 空间和 deadline。** [[Prism-OSDI26]] 用 prompt 长度、预计 chunked-prefill 速度、到达时间和 TTFT SLO 计算 slack；[[SuperInfer-MLSys26]] 则在 KV 压力下把请求状态旋转到 CPU memory。二者说明 token budget 不能脱离 admission 和 KV residency 单独优化。
- **全阶段分离是替代路线，不是必然更好。** [[EcoServe-OSDI26]] 指出共置 chunking 仍会频繁切换，但完全 P/D 分离在普通 Ethernet 上又可能被 KV 流量卡住。其 phase-based hybrid 用复制完整模型换少搬 KV，适用条件与 chunked prefill 不同。

## 设计空间与取舍

- **固定或动态 chunk**：固定值易实现和预测；动态值能利用实时 slack，但依赖准确 cost model，也可能让请求间公平性更难解释。
- **token 维或 layer 维切分**：token chunk 对 dense model 直接；[[LayeredPrefill-MLSys26]] 的 layer group 减少 MoE 重载，却要跟踪每个请求的 partial-layer 状态。两种切法也可以组合。
- **共置、阶段时间片或物理分离**：共置少传 KV；[[EcoServe-OSDI26]] 用较长 phase 减少切换；完全分离独立伸缩，但把 KV 和网络放进关键路径。
- **先到先服务或 SLO-aware 排序**：FCFS 简单；deadline/slack 调度能提高合规率，也可能推迟长请求或旧请求。
- **统一 token budget 或分阶段预算**：多模态的 [[TriInfer-MLSys26]] 分开限制 image 和 text token，因为 encode、prefill、decode 的饱和点不同。
- **只做计算切块或同时管理状态**：[[GhostServe-MLSys26]] 把 checkpoint 对齐 chunk，[[ECHO-OSDI26]] 则在 2,048-token chunk 下做稀疏 KV 预取；状态操作可能抵消更细粒度带来的调度收益。

## 引用本概念的论文

### 直接证据与主要扩展

- [[DCP-OSDI26]]、[[LayeredPrefill-MLSys26]]、[[NVIDIA-Disagg-Study-MLSys26]]、[[SHIP-MLSys26]]：分别研究动态大小、MoE 的 layer 维替代、P/D 设计空间和 SRAM pipeline。
- [[Wang-LocalMoEInference-OSDI26]]、[[Prism-OSDI26]]、[[SuperInfer-MLSys26]]：把 chunk 决策与本地 CPU–GPU 分工、deadline 或 KV offload 联合起来。
- [[GhostServe-MLSys26]]、[[ECHO-OSDI26]]：把 chunk 用作 KV checkpoint 或稀疏 KV 预取的边界。
- [[TriInfer-MLSys26]]、[[BEAM-MLSys26]]、[[CRAFT-MLSys26]]：分别把 chunk 纳入多模态阶段预算、能耗控制和 MoE expert placement。

### 与缓存、流式输入和替代调度的交互

- [[Stream2LLM-MLSys26]]、[[ContextPilot-MLSys26]]、[[SpanQueries-MLSys26]]：让输入流式到达或复用非完整前缀；它们会改变真正需要 prefill 的 suffix。
- [[CacheBlend-EuroSys25]]、[[CacheSlide-FAST26]]、[[BreakingTheIce-MLSys26]]、[[Bidaw-FAST26]]：讨论 KV 复用、缓存恢复或缓存层；与 chunk scheduler 的联合行为大多仍是未完成工作。
- [[EcoServe-OSDI26]]、[[DeepServe-ATC25]]、[[OD-MoE-arXiv25]]：以阶段分离、serverless 或 MoE 路径作为替代/组合方案。
- [[MixLLM-MLSys26]]、[[ReSpec-MLSys26]]：说明大 chunk/batch 会改变量化 kernel 的算术强度，speculative decoding 又会改变 active batch；它们没有直接提出 chunk scheduler。
- [[CLONE-ATC25]]、[[NanoFlow-OSDI25]]、[[OpenTela-OSDI26]]、[[Sirius-ATC25]]、[[Toppings-ATC25]]：主要在相关工作、兼容性或未来系统模型中引用本概念，不能作为其 chunk 策略已被实验证明的证据。

## 已知局限 / 开放问题

- 需要在线、低开销地同时预测 TTFT、TPOT、energy、KV growth 和 pipeline bubble；单一 token 数模型往往不够。
- 动态策略必须报告 P99、公平性、饥饿和 burst 恢复，而不只报告平均吞吐或固定 Poisson 到达。
- MoE、MLA、speculative decoding、prefix cache 和 KV offload 会改变每块的真实成本，组合评测仍很少。
- chunk 之间的 partial state 会扩大取消、抢占、故障恢复和版本升级的正确性面。
- 不同论文使用的 SLO、chunk size、模型和硬件差异很大。应报告完整 Pareto 和 crossover，不能只比较各自最佳点。
