---
type: concept
aliases: [chunked prefill, Chunked Prefill, chunked-prefill, prefill chunking, split prefill, piggyback prefill]
parent: "[[Continuous-Batching]]"
introduced_by: SARATHI
last_updated: 2026-07-30
tags: [llm-inference, scheduling, batching]
---

# Chunked-Prefill

> [[Continuous-Batching]] 的调度技术：把长 prompt 的 prefill 切成固定 token 数的小 chunk（如 512 token/chunk），每 iteration 算一个 chunk，同 iteration 里 piggyback 一批 decode 请求，让 prefill 与 decode 在同一 kernel call 混跑。目标是同时控制 TTFT（首 token 延迟）与 TBT（token-to-token 延迟）——SARATHI (2023) 提出，Sarathi-Serve (OSDI '24) 落地，[[vLLM]]、[[SGLang]] 已默认开启。

## 核心思想

朴素 continuous batching 两种失败模式：

1. **纯分阶段调度**：prefill 独占 iteration → decode 完全 stall，TBT 抖动
2. **prefill + decode 混跑**：长 prompt 的 prefill kernel 可能跑几百毫秒，decode 全部 block

根因：prefill 计算量 ∝ prompt_len²（attention）+ prompt_len（FFN），decode 每步只加 1 token，单 iteration 耗时差距可达 1000×。

Chunked prefill 把 prefill 切成固定算力预算的 chunk：每 iteration 执行 ≤`chunk_size` 个 token 的 prefill + 搭载 B 个 decode 请求（各 1 步）。chunk 之间通过 [[KV-Cache]] 续算；[[FlashAttention-2-ICLR24|FA2]]/[[FlashAttention-3-NeurIPS24|FA3]] variable-length 支持天然兼容。chunk_size 控制 TTFT–TBT trade-off：小 chunk → TBT 稳但 TTFT 长；大 chunk → TTFT 好但 TBT 抖。工程上常动态调整：队列压力大时减小保 decode，队列闲时增大保 TTFT。

Sarathi-Serve 报 Llama-2 13B：TBT P99 降低 ~2×、TTFT 持平或略降、吞吐提高 ~1.3–2×。

## 为什么重要

Chunked prefill 是 co-located serving 里调和 prefill/decode 资源冲突的「软方案」——不需要物理拆两组 GPU（[[Disaggregation]] 的「硬方案」），在中等规模部署中往往够用。这些论文共同假设：**iteration 级算力预算可控是 SLO 合规的前提，chunk_size 是最直接的旋钮**。

但近年论文揭示其副作用：[[LayeredPrefill-MLSys26]] 指出 chunked prefill 在 MoE serving 上引发 sparsity erosion（hybrid batch >256 激活几乎全部 expert）；[[NVIDIA-Disagg-Study-MLSys26]] 指出对 DeepSeek-R1 MLA 有 chunk 级重算 overhead（每个 chunk 重复 down/up projection），削弱相对 disagg 的优势。因此 chunked prefill 与 disagg、layered prefill、prefix cache 的关系是当前 serving 系统设计的前沿争论点。

## 关键观察 / 隐含假设

- **观察 1：co-located piggybacking 对 DeepSeek-R1 MLA 有 chunk 级重算 overhead。** [[NVIDIA-Disagg-Study-MLSys26]] 每个 prefill chunk 重复 down/up projection；可缓存 up-projected KV 缓解但增加实现复杂度；GQA 模型（Llama）敏感性不同。
- **观察 2：SLO 合规 decode batch 很小，但 chunked prefill hybrid batch 常 >256，逆转 MoE 稀疏激活优势。** [[LayeredPrefill-MLSys26]] SLO >90% 时 decode batch ≤32 仅约 55% expert 被加载；chunked prefill hybrid batch 激活几乎全部 expert，per-expert token 不足以饱和 compute。
- **观察 3：LPU serving 中极小 chunk（1–2 token）即可饱和 self-attention，用于消除 PP bubble。** [[SHIP-MLSys26]] dynamic chunked prefill + fused context-batch；但 reasoning production traffic 下 it/s/u 显著下降，长 CL 二次成本与 decode-priority 冲突未完全解决。
- **观察 4：chunk 级 KV 是 fault tolerance 与 streaming 的自然粒度。** [[GhostServe-MLSys26]] 对齐 chunked prefill 做 chunk 级 KV parity checkpoint，8:2 parity 相对全量复制 host memory 与延迟各降约 75%/73%。
- **观察 5：最佳 chunk size 由 TTFT 与 TPOT slack 共同决定，并会随负载变化。** [[DynamicPPServing-OSDI26]] 在 PCIe pipeline parallel serving 中发现，小 chunk 减少 stage imbalance 但损害 GEMM efficiency；其 predictive controller按 SLO 和 arrival rate 选 chunk，在 4×A100 的 Conversation workload 上将 TPOT/E2E 最多降低 35%/31%。

## 设计空间与取舍

- **路线 1：固定 chunk_size piggyback（Sarathi-Serve 经典）**：实现简单、TBT P99 显著改善；牺牲是 TTFT 略增、MoE sparsity erosion（[[LayeredPrefill-MLSys26]]）。
- **路线 2：动态 chunk_size（队列压力自适应）**：队列忙时减小保 decode、闲时增大保 TTFT；牺牲是调参复杂、可预测性下降。
- **路线 3：Layered / layer-group prefill（[[LayeredPrefill-MLSys26]]）**：按 layer 组调度消除 MoE expert 冗余重载；牺牲是单机 TP 验证为主，multi-GPU/disagg 未充分测试。
- **路线 4：Disaggregation 硬拆分（[[NVIDIA-Disagg-Study-MLSys26]]、[[fabric-lib-MLSys26]]）**：prefill/decode 物理分离，无 piggyback 冲突；牺牲是 KV 跨池传输、rate matching、部署复杂度。
- **路线 5：CPP（Chunked Pipeline Parallelism）**：长 prompt 分 chunk 沿 [[Pipeline-Parallelism]] 流水（[[NVIDIA-Disagg-Study-MLSys26]]）；牺牲是 PP bubble 与 stage 数绑定，与 co-located chunked prefill 是不同维度。
- **路线 6：极小 chunk + 异构硬件（[[SHIP-MLSys26]]）**：1–2 token chunk 消除 LPU PP bubble；牺牲是 C2C 带宽失配、prefix cache 破坏确定性。
- **路线 7：SLO-aware dynamic chunk + pipeline delay scheduling**：[[DynamicPPServing-OSDI26]] 联合 TTFT/TPOT slack 调 chunk，并延后有余量的 decode 请求以缓解 D–D bubble；收益集中在 PCIe/低带宽互连，且可能损害旧请求公平性。

## 引用本概念的论文

- SARATHI — 提出 chunked prefill + piggyback decode 调度原则
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — MLA chunk 级重算 overhead；co-located piggyback vs disagg Pareto 扫描
- [[LayeredPrefill-MLSys26|LayeredPrefill]] — chunked prefill 引发 MoE sparsity erosion；layer-group 调度替代方案
- [[GhostServe-MLSys26|GhostServe]] — 对齐 chunked prefill 做 chunk 级 KV parity checkpoint
- [[SHIP-MLSys26|SHIP]] — dynamic chunked prefill（1–2 token）+ fused context-batch 消除 PP bubble
- [[TokenWeave-MLSys26|TokenWeave]] — token-split 时 suffix attention 依赖 prefix，chunked attention 保依赖
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — 高 token tier 兼作 chunked prefill chunk size
- [[BatchLLM-MLSys26|BatchLLM]]、[[MixLLM-MLSys26|MixLLM]]、[[Stream2LLM-MLSys26|Stream2LLM]]、[[SuperInfer-MLSys26|SuperInfer]]、[[LAPS-MLSys26|LAPS]] — 进阶 prefill 调度
- [[BEAM-MLSys26|BEAM]] — [[Pipeline-Parallelism]] 下 chunk size 与 microbatch 作为能耗优化旋钮
- [[CRAFT-MLSys26|CRAFT]] — MoE serving 中 chunked prefill 与 expert replication 争用显存
- [[ContextPilot-MLSys26|ContextPilot]]、[[SpanQueries-MLSys26|SpanQueries]] — 长上下文 prefill 与 KV locality 协同
- [[TriInfer-MLSys26|TriInfer]]、[[SparseSpec-MLSys26|SparseSpec]]、[[SpecDecodeBench-MLSys26|SpecDecodeBench]] — 对照 disagg / 结合 spec decoding
- [[CacheBlend-EuroSys25|CacheBlend]]、[[CacheSlide-FAST26|CacheSlide]]、[[BreakingTheIce-MLSys26|BreakingTheIce]] — KV cache 与 prefill 调度交互
- [[ReSpec-MLSys26|ReSpec]] — RL 生成阶段按 active batch 动态开关 speculation
- [[DynamicPPServing-OSDI26]] — 在 pipeline parallel serving 中按 SLO 动态选择 chunk size，并以 delay scheduling 协同处理 P–D/D–D imbalance
- [[CLONE-ATC25]]、[[DeepServe-ATC25]]、[[OD-MoE-arXiv25]]、[[Bidaw-FAST26]]、[[NanoFlow-OSDI25]]、[[Sirius-ATC25]]、[[Toppings-ATC25]] — 从训练/服务共置、MoE、缓存、流水线与端到端数据流考察 chunk 粒度

## 已知局限 / 开放问题

- MoE serving 上 sparsity erosion 使 chunked prefill 优势逆转（[[LayeredPrefill-MLSys26]]）；multi-GPU / disagg 环境未验证 layered prefill 的 cross-device KV 开销
- MLA 模型 chunk 级重算 overhead 削弱 co-located 优势（[[NVIDIA-Disagg-Study-MLSys26]]）；缓存 up-projected KV 的实现复杂度与 prefix cache 交互未展开
- [[NVIDIA-Disagg-Study-MLSys26]] 对 co-located 强基线（Sarathi-Serve、LayeredPrefill 等）对比有限，disagg 优势可能相对「旧式 piggyback」被放大
- chunked prefill 与 [[Prefix-Caching]]、speculative decoding、[[Disaggregation]] 联合评估不足
- 动态 chunk_size 的策略缺乏 workload-aware 最优性理论；`G=⌈L/512⌉` 等启发式非 workload-optimal（[[LayeredPrefill-MLSys26]] 局限 2）
- [[DynamicPPServing-OSDI26]] 仅在 4×A100 PCIe 单机和 P90 SLO 上验证；bursty arrival、P99、公平性、NVLink 与跨节点 PP 的 crossover 尚未建立
