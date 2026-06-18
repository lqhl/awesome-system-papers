---
type: concept
aliases: [Disaggregation, disaggregated inference, prefill-decode disaggregation, P/D disaggregation]
parent: "[[LLM-Inference]]"
last_updated: 2026-04-24
tags: [llm-inference, scheduling, system-architecture]
---

# Disaggregation

> 把 LLM 推理的 **prefill**（prompt 全部一次性算 KV）与 **decode**（一次一个 token）拆到**不同**的 GPU/节点上，让两类工作各自在适合的硬件配置上跑。代价：每个请求要在两组 GPU 之间传 [[KV-Cache]]，所以高效的 P2P 通信（[[RDMA]]）是 enabler。

## 核心思想

LLM 推理两个阶段计算特性截然不同：

| 阶段 | 计算特性 | 硬件偏好 |
|---|---|---|
| Prefill | compute-bound（一次算完整个 prompt 的 K/V/O，并行度高）| 高算力 GPU、大 SM 数 |
| Decode | memory-bound（每步算一个 token，HBM 带宽是瓶颈）| 高 HBM 带宽、小 batch 灵活调度 |

如果在同一组 GPU 上 collocate 两个阶段（vanilla 实现），各自的硬件需求互相妥协：
- Prefill 占用大 batch 时，decode 长尾被拖慢
- Decode 阶段算力闲置，HBM 带宽吃满

**Disaggregation**：
- Prefill cluster：高算力 GPU，主要跑 prefill；算完把 KV cache 推给 decoder
- Decode cluster：高带宽 GPU，主要跑 decode；接收 KV 后开始 token-by-token 生成
- Global scheduler：决定每个请求走哪个 prefill / decode 节点对

## 为什么这样做

观察：prefill 和 decode 的 compute/memory ratio 差 1-2 个数量级。强行 collocate 等于让 GPU 同时背两套互相冲突的负载。Disaggregation 让两类工作各自在最优 batch / hardware 配置上跑，整体 SLO 和 throughput 都改善。

代价：每个请求多了一次跨节点的 KV 传输（潜在大几 GB），需要高带宽 RDMA。但 KV transfer 与 prefill 后续 layer 计算可以 overlap。

## 实现要点

- **KV transfer 时机**：layer-by-layer（prefiller 算完每层就推一层）vs 全部 prefill 完再一次推
- **路由策略**：根据 input length 把请求分到 prefiller、根据 KV cache 利用率分到 decoder
- **错误处理**：prefiller / decoder 失联时的 cancellation 与 KV reuse 安全（[[fabric-lib-MLSys26|fabric-lib]] 用 heartbeat + per-request cancellation token）
- **网络层**：[[RDMA]] one-sided WRITE + 异步 completion（[[fabric-lib-MLSys26]] 提供跨厂商 RDMA 抽象）
- **Sharding 不一致**：prefiller 与 decoder 的 KV cache sharding 可能不同（GQA / MLA），需要 page-wise offset/stride

## 相关概念

- 上游：[[LLM-Inference]]、[[Continuous-Batching]]
- 关联：[[KV-Cache]]（被传输的对象）、[[RDMA]]（传输底层）、[[Prefix-Caching]]（disaggregation 跨实例的 prefix 共享）
- 同代际系统设计：[[MoE]] 的 expert parallelism（也是横向把模型/计算切到多 GPU）

## 提出 / 关键论文

- **Splitwise** (ISCA 2024, Patel et al.) — 早期 disaggregation 提案，phase splitting
- **DistServe** (Zhong et al. 2024) — goodput-oriented disaggregation
- **Mooncake** ([[fast2025-qin|FAST 2025, Qin et al.]]) — KVCache-centric architecture，更激进的 KV 优先

## 引用本概念的论文

- [[fabric-lib-MLSys26|fabric-lib]] — production-deployed disaggregated KV transfer over EFA & ConnectX
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 异构 KV cache 结构 + on-disk storage 为 shared-prefix 复用设计,是 disaggregation 场景的上层支持
- [[Libra-ICLR26|Libra]] — 评估假设 prefill-decode 已分离，专注 prefill 阶段 MoE LB
- [[FluxMoE-arXiv26|FluxMoE]] — 明确针对 disaggregated serving 的 **decode 阶段**（memory-bound）做优化，用 expert paging 把 MoE 专家腾出来留给 KV cache
- [[Stream2LLM-MLSys26|Stream2LLM]] — 面向 prefill-decode disaggregation 的 prefill 实例，streaming context 与 prefill overlap 降 TTFT
- [[LAPS-MLSys26|LAPS]] — 在 PD disagg 的 prefill 实例内再分 long/short prefill pool，消除 compute-memory 互扰
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 数十万设计点模拟 + Dynamo Planner 验证：prefill-heavy 最赚、ctx:gen 须动态 rate matching
- [[TriInfer-MLSys26|TriInfer]] — MLLM Hybrid EPD（encode/prefill/decode）解耦 + 自动选 E+P+D/EP+D/ED+P，goodput 最高 2.4×
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — Meta 生产经验：在线严格 SLO 下 disagg 比 continuous batching QPS 高 1.5–2.2×，离线吞吐场景两者趋同
- [[DriftBench-MLSys26|DriftBench]] — 跨 GPU/框架/精度迁移时的 output consistency 风险评测
- *Mooncake*（待生成 paper wiki 页）
- *Splitwise / DistServe*（待生成）

## 已知局限 / 开放问题

- KV transfer 在长 context 场景下仍是带宽 bound（单序列就可能 > 10 GB）
- Decoder 端的 prefix sharing 与 disaggregation 的语义有冲突（cross-instance prefix cache 难做）
- 异构 GPU（H100 prefiller + A100 decoder）的精度对齐和 sharding 难
