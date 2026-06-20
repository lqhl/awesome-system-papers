---
type: entity
kind: system
aliases: [vLLM]
status: active
last_updated: 2026-06-20
tags: [llm-inference, serving]
---

# vLLM

> UC Berkeley Sky Lab 提出的高吞吐 LLM serving 框架，[[PagedAttention]] 与 [[Continuous-Batching]] 的开源落点，是当前论文中最常被当作 baseline、集成目标与对照栈的 open-source inference engine 之一。

## 是什么

vLLM 由 Kwon、Stoica 等人在 SOSP 2023 提出（[[vLLM-SOSP23]]）。核心贡献是把 [[KV-Cache]] 从「按 max_seq_len 连续预分配」改成 OS 虚存式分页：固定 token 数的 KV block + block table 间接寻址 + on-demand 分配 + copy-on-write 共享。论文测量 FasterTransformer / 自实现 Orca 只有 **20.4%–38.2%** KV 显存真正存 token state；分页后有效利用率接近 100%，在相似 normalized latency 下吞吐比 FasterTransformer / Orca 高 **2–4×**。

vLLM 的定位是**通用 GPU serving runtime**，而非单模型本地引擎。它与 [[Orca-OSDI22|Orca]] 的 iteration-level batching 互补：Orca 解决时间维交错，PagedAttention 解决空间维 memory utilization。此后 vLLM 快速演化为社区生态，集成 tensor parallelism、speculative decoding、prefix caching、FP8、LoRA、guided decoding、disaggregated inference 等主流 feature，也成为大量 MLSys/OSDI/SOSP 后续工作的默认集成面。

这些论文共同把 vLLM 视为「block 级 KV 抽象 + continuous batching + 可插拔 kernel/调度 hook」的事实标准。它的边界也很清楚：论文反复指出 vLLM 假设 decoder-only、单卡/多卡 HBM 内竞争 batch size；overload 下 swapping 会暂停接新请求；centralized block manager 在超大规模下的控制面扩展性未被原始论文充分讨论。

## 关键观察 / 隐含假设

- **观察 1：KV cache 仍是 serving 的主导内存瓶颈，分页管理的价值与 memory-bound 程度强相关。** [[vLLM-SOSP23]] 在 OPT-13B 上量化 KV 占 serving 内存大头，PagedAttention kernel 虽慢 20–26%，但更大 batch 抵消后端到端仍显著更快；[[FlexiCache-MLSys26]]、[[SparseSpec-MLSys26]] 等 2026 工作仍把 vLLM 的 [[PagedAttention]] 当作长 context decode 的默认 KV 布局前提。
- **观察 2：prefix-based caching 对非 chat workload 会系统性 miss。** [[SpanQueries-MLSys26]] 指出 RAG、judge-generator 等场景的复用差异本质是输入块是否可交换，而非 workload 类型；vLLM 线性 prefix 假设下 hit rate 可趋近 0%，需 span query IR 等扩展（492 行 Python 即可非 chat TTFT **10–20×**）。
- **观察 3：vLLM 是论文里的「可改造 serving 壳」，但深度集成往往意味着非 trivial fork。** [[LayeredPrefill-MLSys26]]、[[OPKV-MLSys26]]、[[BEAM-MLSys26]] 等通过 scheduler hook / plugin 接入；[[SuperInfer-MLSys26]] 则剖析 GH200 上 vLLM offload 仅 **~10GB/s** 有效带宽、swap 串行化等软件栈瓶颈，说明 PagedAttention 抽象在新型 superchip 上还需配套 memory movement 重设计。
- **观察 4：作为 baseline 时，vLLM 版本与配置漂移会显著影响结论可比性。** [[DriftBench-MLSys26]] 以 H100/FP16/vLLM 0.11.0 为固定 baseline 测 105 配置；[[BreakingTheIce-MLSys26]] 显示近 1.5 年 9 个 major release 冷启动方差 **>4×**。这些论文共同假设：引用 vLLM 数字时必须写明版本与 runtime flag。
- **观察 5：MoE serving 中 expert 常驻与 KV 容量存在直接竞争。** [[FluxMoE-arXiv26]] 在 vLLM v0.10.2 上仅 **20 LoC** 侵入，用 PagedTensor 把 expert 流式化，Qwen3-Next-80B 高 batch 场景最高 **3.0×** 吞吐；[[MoE-Serving-Tax-MLSys26]] 则量化 vLLM 上 MoE serving tax 可达 dense 的 **2–3×**。

## 演进时间线

- **2023 SOSP**：[[vLLM-SOSP23]] 提出 [[PagedAttention]] + [[Continuous-Batching]]，确立 block 级 KV 管理范式。
- **2024**：社区快速补齐 FP8、MQA/GQA、prefix sharing、PagedAttention V2；[[SGLang-NeurIPS24]] 以 vLLM v0.2.5 为对照，推动 prefix-cache 与 structured program 讨论。
- **2025**：[[DiffKV-SOSP25]]、[[LMCache-arXiv25]]、[[CacheBlend-EuroSys25]] 等把 KV 管理扩展到多层存储与近似复用；[[NanoFlow-OSDI25]] 探索 dataflow serving 与 vLLM 栈关系。
- **2026 MLSys / 周边**：vLLM 从「被对比的 baseline」转为「被扩展的 platform」——[[SpanQueries-MLSys26]]（span query IR）、[[LayeredPrefill-MLSys26]]（layer-group prefill）、[[Stream2LLM-MLSys26]]（streaming prompt）、[[ContextPilot-MLSys26]]（context block 对齐）、[[fabric-lib-MLSys26]]（P2P RDMA 集成）、[[BreakingTheIce-MLSys26]]（冷启动六步分解）、[[DriftBench-MLSys26]]（跨框架 drift 评测维度之一）。

## 相关概念

- [[PagedAttention]]（vLLM 引入的核心机制）
- [[KV-Cache]]
- [[Continuous-Batching]]
- [[Prefix-Caching]]
- [[Speculative-Decoding]]
- [[Disaggregation]]

## 相关论文

- [[vLLM-SOSP23]] — 原始系统：PagedAttention、block manager、COW 共享与 Orca 式 batching
- [[SpanQueries-MLSys26]] — 492 行扩展 span query IR，突破 chat-centric prefix caching
- [[LayeredPrefill-MLSys26]] — layer-group 调度轴，MoE serving 下 TTFT −70%、能耗/token −22%
- [[FlexiCache-MLSys26]] — per-head-layer KV 分层 offload，GPU 内存 −70%
- [[FluxMoE-arXiv26]] — PagedTensor expert paging，基于 vLLM v0.10.2 最高 3.0× 吞吐
- [[OPKV-MLSys26]] — recallable sparsity plugin，解码吞吐 1.3–1.8×
- [[BatchLLM-MLSys26]] — 离线全局 prefix 树，相对 vLLM 1.3–10.8×
- [[BreakingTheIce-MLSys26]] — 冷启动六步分解，CPU-bound 为主，预测器 MSE 2.42 s
- [[SuperInfer-MLSys26]] — 剖析 vLLM GH200 offload 带宽与 swap 串行化瓶颈
- [[DriftBench-MLSys26]] — 跨 GPU/精度/框架 infrastructure drift 的固定 baseline
- [[fabric-lib-MLSys26]] — 跨厂商 P2P RDMA，可集成 vLLM 等栈做 KV/MoE/RL 权重传输
- [[EventTensor-MLSys26]] — ETC megakernel 后端，低 batch decode 1.48×
- [[FarSkip-Collective-MLSys26]] — MoE EP 通信重叠，Llama-4 Scout TTFT +18.5%
- [[CRAFT-MLSys26]] — cost-aware MoE expert replication，可替换 EPLB 模块
- [[SparseSpec-MLSys26]] — reasoning model baseline，最高 2.13× 吞吐
- [[ContextPilot-MLSys26]] — context index 与 prefix cache 协同，模块化接入 vLLM/SGLang
- [[GhostServe-MLSys26]] — 可移植 KV erasure-coding checkpoint 模块
- [[ScaleSearch-MLSys26]] — 基于 vLLM nvfp4_utils 的 NVFP4 rounding 路径
- [[MoE-Serving-Tax-MLSys26]] — 量化 vLLM 上 MoE vs dense serving tax