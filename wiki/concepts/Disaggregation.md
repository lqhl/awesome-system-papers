---
type: concept
aliases: [Disaggregation, disaggregated inference, prefill-decode disaggregation, P/D disaggregation]
parent: "[[LLM-Inference]]"
last_updated: 2026-06-20
tags: [llm-inference, scheduling, system-architecture]
---

# Disaggregation

> 把 LLM 推理的 **prefill**（prompt 一次性算 KV）与 **decode**（逐 token 生成）拆到不同 GPU/节点，让两类工作各自在最优硬件配置与 batch 规模上运行。代价是每个请求须在池间传 [[KV-Cache]]，高效 P2P 通信（[[RDMA]]）是 enabler。

## 核心思想

LLM 推理两阶段计算特性截然不同：

| 阶段 | 计算特性 | 硬件偏好 |
|---|---|---|
| Prefill | compute-bound，高并行度 | 高算力 GPU、大 SM 数 |
| Decode | memory-bound，每步一 token | 高 HBM 带宽、灵活小 batch |

collocate 两阶段时硬件需求互相妥协：prefill 占大 batch 拖慢 decode 长尾；decode 算力闲置而 HBM 带宽吃满。**Disaggregation** 拆成 prefill cluster + decode cluster + global scheduler，各自独立选并行策略与 batch size。

## 为什么重要

[[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] 基于近十亿 MAU 生产经验：在线严格 TTFT/TTIT SLO 下，disagg QPS 比 [[Continuous-Batching]] 高 1.5–2.2×，因 decode batch 可远大于 mixed batch（70B 上 112 vs 28）；Meta 多数在线服务已迁 disagg 省 ~30% 容量。离线吞吐 sole objective 时差距缩小甚至 continuous batching 略胜——说明 disagg 不是 universal win，而是 SLO 与流量形态依赖的架构选择。

[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] 用 datacenter-scale 模拟器扫描数百万设计点，绘制 throughput–interactivity Pareto 前沿：prefill-heavy（ISL ≫ OSL）、>10B 模型收益最大；ctx:gen GPU 比须动态 rate matching，固定 ratio 会在 Pareto 一侧极好、另一侧崩溃。这些论文把 disagg 从概念争论推进到可量化的部署指南。

## 关键观察 / 隐含假设

- **观察 1：prefill 与 decode 的 compute/memory ratio 差 1–2 个数量级，强行 collocate 等于背两套冲突负载。** [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]]：最优并行 phase-specific（70B online prefill PP4-TP2、decode TP8）。
- **观察 2：disagg 收益高度依赖流量形态——prefill-heavy 最赚，decode-heavy 且 latency 不紧时 co-located 往往更好。** [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] Figure 1/8：DeepSeek-R1 在多种 ISL/OSL 下 Pareto 曲线形态差异巨大。
- **观察 3：最优 ctx:gen GPU 比随模型、latency 目标、prefix caching、speculative decoding 显著变化。** [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]：ctx:gen=3.5 宽松 latency 优，收紧则劣化；0.5 相反；Dynamo Planner 动态匹配相对静态最高 ~8× goodput。
- **观察 4：KV 跨池传输在典型 datacenter 配置下通常不是瓶颈，但拓扑与异步实现关键。** [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] 式 3/4 推导 + [[fabric-lib-MLSys26|fabric-lib]] 层间流水 WRITEIMM + IMMCOUNTER 可在 CUDA Graph 下逐层 RDMA。
- **观察 5：co-located piggybacking（[[Chunked-Prefill]]）对 MLA 有 chunk 级重算 overhead。** [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]：每个 prefill chunk 重复 down/up projection，削弱相对 disagg 的优势；GQA 模型敏感性不同。

## 设计空间与取舍

- **KV transfer 时机**：layer-by-layer（与 prefill 后续层 overlap）vs 全部 prefill 完一次推；[[fabric-lib-MLSys26|fabric-lib]] 用 UVM watcher + paged_writes 支持前者。
- **Rate matching**：静态 ctx:gen ratio vs 动态 Planner（[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] Dynamo）；burst 到达时 scale 滞后是风险。
- **Prefill 侧并行**：紧 FTL 长上下文下 Chunked Pipeline Parallelism（CPP）优于宽 [[Tensor-Parallelism]]（[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]）；通信量 send/recv vs TP allreduce。
- **异构硬件映射**：算力型 prefill GPU + 带宽型 decode GPU 可达同质最佳 QPS，估 15–25% cost efficiency（[[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]]）。
- **二级 disagg（[[LAPS-MLSys26|LAPS]]）**：PD 分离的 prefill 池内再分 long/short prefill pool，消除 compute-memory 互扰。
- **MLLM 扩展（[[TriInfer-MLSys26|TriInfer]]）**：encode/prefill/decode 三解耦 + 自动选 E+P+D/EP+D/ED+P。
- **Streaming prefill（[[Stream2LLM-MLSys26|Stream2LLM]]）**：面向 disagg prefill 实例，streaming context 与 prefill overlap 降 TTFT。

## 引用本概念的论文

- [[fabric-lib-MLSys26|fabric-lib]] — production-deployed disaggregated KV transfer over EFA & ConnectX
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 在线 strict SLO 下 disagg QPS 1.5–2.2× vs continuous batching
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 数十万设计点 Pareto + Dynamo Planner 动态 rate matching
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 异构 KV + on-disk storage 为 shared-prefix 复用设计
- [[Libra-ICLR26|Libra]] — 评估假设 prefill-decode 已分离，专注 prefill MoE LB
- [[FluxMoE-arXiv26|FluxMoE]] — 针对 disagg decode 阶段 memory-bound 做 expert paging
- [[Stream2LLM-MLSys26|Stream2LLM]] — disagg prefill 实例 streaming context overlap
- [[LAPS-MLSys26|LAPS]] — PD disagg prefill 池内 long/short 再分池
- [[TriInfer-MLSys26|TriInfer]] — MLLM Hybrid EPD 解耦，goodput 最高 2.4×
- [[DriftBench-MLSys26|DriftBench]] — 跨 GPU/框架/精度迁移 output consistency 风险
- [[GhostServe-MLSys26|GhostServe]] — 流式 KV parity checkpoint 适配 disagg 拓扑
- [[MorphServe-MLSys26|MorphServe]] — layer swap 释内存，弹性扩 KV 容量
- [[CacheGen-SIGCOMM24|CacheGen]] — KV cache 跨节点压缩传输
- [[LMCache-arXiv25|LMCache]] — 分布式 KV cache 层与 disagg 协同

## 已知局限 / 开放问题

- KV transfer 在长 context 下单序列可 >10 GB，跨 rack 以太网可能成为瓶颈
- Decoder 端 prefix sharing 与 cross-instance disagg 语义冲突，跨池 prefix cache 难做
- 异构 GPU（H100 prefiller + A100 decoder）精度对齐与 sharding 难
- 模拟器假设 rate-matched 满载、层间 KV 即时流式搬运，生产 queueing/scheduler 开销可能偏移 Pareto（[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]）
- Mooncake / Splitwise / DistServe 等待完整 paper wiki 页补充演进时间线