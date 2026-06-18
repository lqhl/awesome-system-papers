---
type: entity
kind: system
aliases: [vLLM]
status: active
last_updated: 2026-04-24
tags: [llm-inference, serving]
---

# vLLM

> UC Berkeley 提出的高吞吐 LLM serving 框架，PagedAttention 的起源，是当前 open-source LLM inference 事实标准之一。

## 是什么

vLLM 由 UC Berkeley Sky Lab（Kwon, Stoica 等）于 2023 年 SOSP 提出。核心 contribution 是 [[PagedAttention]]——把 KV cache 当 OS 虚存分页管理，消除内外部碎片，让单 GPU 吞吐相比 FasterTransformer 提升 2-4×。

vLLM 之后快速演化为社区生态：支持 continuous batching、tensor parallelism、speculative decoding、prefix caching、FP8、LoRA、guided decoding 等几乎所有主流 LLM serving feature。它也是大量后续 system 工作的 baseline 或集成目标。

## 演进时间线

- **2023 SOSP**：原始论文（Kwon et al.），引入 [[PagedAttention]] 和 [[Continuous-Batching]] 联合调度
- **2024**：FP8 / MQA / GQA 支持；PagedAttention V2；prefix sharing
- **2025**：disaggregated inference 集成；speculative decoding；多种推理优化
- **2026**：作为 baseline 出现在大量论文里：[[fabric-lib-MLSys26|fabric-lib]] 提到 vLLM 是 P2P 通信集成对象之一；[[LayeredPrefill-MLSys26|LayeredPrefill]] 在其上实现 layer-group prefill 调度；[[Stream2LLM-MLSys26|Stream2LLM]] 扩展 streaming prompt + LCP 缓存失效；[[EventTensor-MLSys26|EventTensor]] 的 ETC megakernel 低 batch decode 快 1.48×；[[SuperInfer-MLSys26|SuperInfer]] 剖析其 GH200 offload 仅 ~10GB/s 有效带宽
- **2026 MLSys**：[[SpanQueries-MLSys26|SpanQueries]] 以 492 行扩展 span query IR 与跨请求 KV 复用；[[ContextPilot-MLSys26|ContextPilot]]、[[DriftBench-MLSys26|DriftBench]] 列为可集成推理后端；[[BEAM-MLSys26|BEAM]] 事件驱动联合 DVFS+batching 降能耗 51%；[[ScaleSearch-MLSys26|ScaleSearch]] 改进 NVFP4 rounding 路径

## 相关概念

- [[PagedAttention]]（vLLM 引入的核心机制）
- [[KV-Cache]]
- [[Continuous-Batching]]
- [[Prefix-Caching]]
- [[Speculative-Decoding]]

## 对比

- [[vLLM-vs-SGLang]]（按需创建）

## 相关论文

- *vLLM 原始论文*（SOSP 2023, Kwon et al.）— [[vLLM-SOSP23]]
- [[fabric-lib-MLSys26|fabric-lib]] — 把 P2P RDMA 集成进 vLLM 等推理框架
- [[FluxMoE-arXiv26|FluxMoE]] — 基于 vLLM v0.10.2，用 PagedTensor 把 MoE expert 转为 streaming resource（仅 20 LoC 侵入），Qwen3-Next-80B 上 3.0× 吞吐
- [[LayeredPrefill-MLSys26|LayeredPrefill]] — 在 vLLM 上实现 layered prefill（layer-group 调度轴），MoE serving 下 TTFT 降 70%、能耗/token 降 22%
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — 首次拆解 vLLM 冷启动六步（CPU-bound 为主），白盒分步预测器 MSE 2.42 s，开源 vllm-startup-profiler
- [[CRAFT-MLSys26|CRAFT]] — 可作为 EPLB 替换模块做 cost-aware MoE expert replication
- [[OPKV-MLSys26|OPKV]] — 在 vLLM v0.7.2 上以 plugin 集成 InfiniGen/OmniKV 等 recallable sparsity，解码吞吐 1.3–1.8×
- [[Stream2LLM-MLSys26|Stream2LLM]] — 扩展 vLLM v1 支持 append/update streaming prompt，RAG 场景 TTFT 最多 11×
- [[EventTensor-MLSys26|EventTensor]] — ETC 编译 megakernel 作为 vLLM 后端，低 batch 端到端 decode 快 1.48×、warmup 3.5×
- [[GhostServe-MLSys26|GhostServe]] — 声称可移植到 vLLM 的 KV erasure-coding checkpoint 模块
- [[SpanQueries-MLSys26|SpanQueries]] — 492 行 Python 支持 span query 与 CIDRA ReRoPE，非 chat 场景 TTFT 10–20×
- [[ContextPilot-MLSys26|ContextPilot]] — context block 对齐/去重提升 prefix cache 命中，模块化接入 vLLM
- [[BEAM-MLSys26|BEAM]] — scheduler hook 联合调 chunk/microbatch/DVFS，GPU 能耗 -51%
- [[ScaleSearch-MLSys26|ScaleSearch]] — 基于 vLLM nvfp4_utils 的 ScaleSearch block scale 选择
- [[DriftBench-MLSys26|DriftBench]] — 跨框架 infrastructure drift 评测对象之一
- [[MAC-Attention-MLSys26|MAC-Attention]] — 长上下文 decode 可与 PagedAttention / IO-aware kernel 组合，KV 访问最高减 99%
- [[TriInfer-MLSys26|TriInfer]] — MLLM serving goodput 对比 baseline 之一
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — 在 vLLM 上实现 MoE EP 通信重叠，Llama-4 Scout TTFT +18.5%
- [[BOA-MLSys26|BOA]] — jailbreak oracle 可插拔 vLLM/HuggingFace serving 后端
- [[SuperInfer-MLSys26|SuperInfer]] — 针对 GH200 Superchip 的 SLO-aware KV offload，非 vLLM 插件而是独立 serving 栈
- [[TeleRAG-MLSys26|TeleRAG]] — RAG 推理 baseline 之一，CPU retrieval 占 E2E 41–60% latency
- [[AgenticCache-MLSys26|AgenticCache]] — 与 [[KV-Cache]]/context cache 正交，缓存 embodied plan transition
- [[SparseSpec-MLSys26|SparseSpec]] — reasoning model inference baseline，最高 2.13× throughput
- [[FlexiCache-MLSys26|FlexiCache]] — 扩展 block table 为 per-head-layer KV 分层 offload，GPU 内存 -70%
- [[OptiKit-MLSys26|OptiKit]] — 企业自动化 quantization + serving 调参 pipeline 的 backend 之一
- [[HetRL-MLSys26|HetRL]] — 异构 RL 训练栈集成 verl + Megatron + vLLM
- [[TokenWeave-MLSys26|TokenWeave]] — 集成 vLLM-V1，TP AllReduce+RMSNorm 融合与 token-split overlap，1K tokens 仍 1.2× 延迟收益
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — CR1 VLM 推理 VRAM baseline；客户端 llama.cpp 路径与 vLLM 对照
- [[BatchLLM-MLSys26|BatchLLM]] — 大批量 offline prefix-shared 推理，显式全局前缀 + 内存中心 batching，比 vLLM 快 1.3×–10.8×
- [[FlashAgents-MLSys26|FlashAgents]] — MAS 流式 prefill 重叠，与 vLLM 式逐请求调度正交
- [[SpecDecodeBench-MLSys26|SpecDecodeBench]] — 生产 vLLM v0.10.1.1 上系统评测多种 [[Speculative-Decoding]] 变体
- [[RaidServe-MLSys26|RaidServe]] — fault-tolerant [[Tensor-Parallelism]] serving 兼容 vLLM 类栈，恢复 183× 更快
- [[DynaFlow-MLSys26|DynaFlow]] — torch.compile backend 75 LoC 集成 NanoFlow，最高 1.29×
- [[DAS-MLSys26|DAS]] — VeRL rollout distribution-aware [[Speculative-Decoding]]，−50% rollout 时间
- [[MorphServe-MLSys26|MorphServe]] — SwiftLLM（vLLM 轻量复刻）运行时 layer swap + 弹性 KV
- [[Matrix-MLSys26|Matrix]] — 合成数据 P2P 框架后端集成 vLLM
- [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] — vLLM 上量化 [[MoE]] serving tax（2–3× vs DenseFA）
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — `flashinfer_bench.apply()` 零代码动态注入 AI-generated kernel
- [[Charon-MLSys26|Charon]] — 原生接受 HuggingFace/vLLM PyTorch 模型做训练/推理仿真

## 开放问题

- vLLM 在 disaggregated inference 场景下的 KV transfer 仍是显式协调，缺乏 cross-vendor RDMA 抽象（[[fabric-lib-MLSys26|fabric-lib]] 是一个补充）
- MoE-aware 的 vLLM 调度仍在演进（[[Libra-ICLR26|Libra]] 在 [[SGLang]] 上做了，vLLM 路径尚未跟进）
