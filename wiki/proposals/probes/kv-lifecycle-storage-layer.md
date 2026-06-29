---
type: probe
topic: "KV-lifecycle storage layer"
created: 2026-06-23
tags: [kv-cache, storage, llm-serving, ai-infra, fast26, mlsys26]
probed_papers:
  - "[[vLLM-SOSP23]]"
  - "[[SGLang-NeurIPS24]]"
  - "[[PRISM-MLSys26]]"
  - "[[KVCacheInTheWild-ATC25]]"
  - "[[CacheGen-SIGCOMM24]]"
  - "[[CacheBlend-EuroSys25]]"
  - "[[LMCache-arXiv25]]"
  - "[[Bidaw-FAST26]]"
  - "[[CacheSlide-FAST26]]"
  - "[[SolidAttention-FAST26]]"
  - "[[AITurbo-FAST26]]"
  - "[[MAIO-FAST26]]"
  - "[[GhostServe-MLSys26]]"
  - "[[RaidServe-MLSys26]]"
  - "[[SuperInfer-MLSys26]]"
  - "[[OPKV-MLSys26]]"
  - "[[FlexiCache-MLSys26]]"
  - "[[SkipKV-MLSys26]]"
  - "[[Kitty-MLSys26]]"
  - "[[IceCache-arXiv26]]"
  - "[[NVIDIA-Disagg-Study-MLSys26]]"
  - "[[Meta-LLM-Deploy-MLSys26]]"
  - "[[fabric-lib-MLSys26]]"
  - "[[ContextPilot-MLSys26]]"
  - "[[Stream2LLM-MLSys26]]"
  - "[[TeleRAG-MLSys26]]"
  - "[[Terminus-MLSys26]]"
  - "[[OdinANN-FAST26]]"
  - "[[WARP-FAST26]]"
  - "[[CetoFS-FAST26]]"
  - "[[Cylon-FAST26]]"
  - "[[Xerxes-FAST26]]"
  - "[[WSBuffer-FAST26]]"
external_sources:
  - "[NVIDIA Dynamo KVBM](https://docs.nvidia.com/dynamo/design-docs/component-design/kvbm-design)"
  - "[NVIDIA NIXL](https://github.com/ai-dynamo/nixl)"
  - "[LMCache architecture](https://docs.lmcache.ai/developer_guide/architecture.html)"
  - "[Mooncake](https://github.com/kvcache-ai/Mooncake)"
  - "[TraCT arXiv](https://arxiv.org/abs/2512.18194)"
---

# Probe: KV-lifecycle Storage Layer

> 核心判断：FAST26 / MLSys26 已经把 [[KV-Cache]] 从 GPU 内存管理问题推到 storage 系统问题，但现有工作大多仍只覆盖生命周期的一段：生成、搬运、压缩、offload、reuse、fault recovery 或 device backend。真正空白是一个能描述 **KV block 从 create 到 transform、place、reuse、evict、persist、invalidate、recover** 的 storage-layer abstraction，并把 GPU scheduler、attention semantics、SSD/CXL/RDMA backend 和 correctness boundary 连起来。

## Scope Note

本 probe 聚焦 **KV-lifecycle storage layer**，不是重复已有的 [[ImportanceGuidedKVTiering]]（importance score 驱动 placement）、`thinking-model-kv-cache`（CoT trace access pattern）、或 `moe-kv-cache-offload`（expert 与 KV 共同抢 HBM/CPU/NVMe）。这里问的是更偏 FAST 的问题：

- KV block 是否需要像文件系统页、对象存储对象、或数据库 record 一样有生命周期状态机？
- 当 KV 进入 CPU DRAM、SSD、CXL shared memory、RDMA pool、object store 后，设备层的 locality、lifetime、tail、WAF、failure 和 isolation 怎么暴露给 serving layer？
- exact / compressed / sparse / recomputed / semantically clustered / parity-backed KV 是否应该共享同一个 storage contract？

补缺说明：外部检索发现 [TraCT](https://arxiv.org/abs/2512.18194) 与本题高度相关，已下载到 `papers/ai-infra/arxiv25-yoon-tract.pdf`。仓库 wrapper 的 CPU 路径在 layout 后挂住；后续用 MinerU 默认设备路径成功生成 `markdowns/ai-infra/arxiv25-yoon-tract/arxiv25-yoon-tract.md`。本 probe 仍只把 TraCT 作为外部信号引用，尚未生成 wiki paper 页。

## Landscape

| 工作 | 做了什么 | 没做什么 | 关键观察 | 隐含假设 | 可攻击点 / 脆弱点 |
|------|----------|----------|----------|----------|-------------------|
| [[vLLM-SOSP23]] | [[PagedAttention]] 把 KV 变成 block-managed GPU memory，支持 prefix sharing / COW / swap | 不处理长期持久化、多 tier 策略、跨节点生命周期 | 连续预分配 KV 只有 20.4-38.2% 实际使用，block 化能换 batch size | block/page 是自然 KV 管理粒度；GPU 内 block manager 是主战场 | page 粒度和后续 token/head/layer 稀疏不匹配；swap 是被动机制，不是 storage layer |
| [[SGLang-NeurIPS24]] | RadixAttention 用 radix tree 管 prefix KV，跨 LM program call 复用 | 多 tier DRAM/SSD/remote 只是 future；缺少隔离和一致性模型 | LM program 有 50-99% prefix cache hit；frontend structure 是 cache hint | prefix tree locality 稳定，cache-aware scheduling 近似最优 | long-output chat、agent prompt drift 和 multi-worker affinity 会降低结构性复用 |
| [[PRISM-MLSys26]] | speculative drafter 按 draft step 切换 processing module；draft KV 在 module 间传递，并在 [[SGLang]] 中系统集成 | 不讨论 draft KV lifecycle、tiering、fault 或 rejected branch cleanup 的存储契约；主实验 batch=1 | draft acceptance 随 step 下降；step-specialized 参数集可在 per-step active params 不变下提高 acceptance / TPS | module switching、draft KV 传递、reject rollback 与 CUDA graph 可以由 engine 内部透明处理 | draft KV 不是 target KV，也不是普通 prefix cache；module id、draft step、accepted/rejected 状态都需要进入 KV identity / invalidation contract |
| [[KVCacheInTheWild-ATC25]] | Alibaba 生产 trace 刻画 KV reuse、lifespan、category-aware eviction | 未做 global/distributed tiered KV；未覆盖 reasoning/agent 新 trace | 10% blocks 贡献 77% reuse，Trace B P99 lifespan 97s；inter-user reuse 接近 0 | 单实例 block lifespan 足以指导 policy；类别标签可用 | 一云一周；policy 只比最好 baseline 提升 1.5-3.9%；多实例/PD/disagg 下可能稀释 |
| [[LMCache-arXiv25]] | 提供 engine-independent KV cache layer，连接 GPU/CPU/SSD/remote；支持 vLLM/SGLang、PD disagg、controller | 明确不解决强自适应 policy、multi-tenant correctness、controller failure | 5 周 stored KV 从 10T 到 30T bytes；engine 内 page 太小不适合 I/O | KV 是可持久化 MemoryObj；chunk / connector API 能跨 engine 稳定 | load-vs-prefill 决策、backend tail、stale metadata、secret prompt leakage 仍是系统核心风险 |
| [[CacheGen-SIGCOMM24]] | 把 remote KV 编码成 compressed bitstream，减少跨链路传输体积 | 不决定 KV 的存放、生命周期、admission、失效 | adjacent KV delta 低方差，layer/channel 熵可利用；网络可主导 TTFT | 压缩 profile 可随模型/版本稳定；质量损失可控 | codec metadata/versioning、adapter/model drift、real network/storage tail 未解决 |
| [[CacheBlend-EuroSys25]] | RAG 非 prefix chunks 的 selective recompute，修正 cross-attention | 无 distributed/multi-tier KV store；quality 边界弱 | RAG 多 chunk KV 复用有价值，但 full reuse 会错过 cross-attention | 少量 recompute 可被下一层 fetch 隐藏；chunk hit 足够高 | dense cross-chunk reasoning、低 chunk hit、P99 与 correctness 未充分证明 |
| [[Bidaw-FAST26]] | 低成本 host memory + SSD 两级 interactive KV storage；dual queue、disk-HRRN、answer-length eviction、tensor caching | 单机单卡本地 SSD；不处理 RDMA/CXL pool、multi-GPU、disagg、inclusive double storage | 中国电信 trace 平均 22.4 turns/user；history KV 占 93.1% compute；80% weighted reuse distance >200GB；I/O CV >90% | 用户阅读间隔给 SSD prefetch 留窗口；interactive history KV 可精确无损复用 | burst/batch workload、短会话、agent continuous loop 会破坏阅读间隔假设；SSD endurance/tenant 隔离未展开 |
| [[CacheSlide-FAST26]] | Agent prompt 的 sliding KV reuse：CCPE + Weighted Correction Attention + SLIDE dirty page eviction | 单节点；依赖模板稳定和 CoPE LoRA；不处理 distributed tier/fault/privacy | Agent prompt 的 relative chunk order 稳定但 absolute position drift；约 26% tokens recompute | prompt template 可预测；位置校正比 full recompute 更便宜 | 模板漂移、tool output 注入、版本失配、cache poisoning 边界不清 |
| [[SolidAttention-FAST26]] | AIPC 场景 SSD-based KV offload + dynamic sparse attention；K/V interleave、bulk transfer | batch=1 / single user；非 exact；无 concurrent serving、prefix cache、endurance | SSD 带宽需要粗粒度传输；相邻 decode block selection 81% similarity | AIPC 可用 sparse approximate KV；fixed 1K context budget 足够 | background I/O 使 throughput 降 58%；质量 silent drift 和多租户 SSD tail 未覆盖 |
| [[AITurbo-FAST26]] | 云存储层为 AI bulk I/O 做 grouped read/write、dedup、fabric-aware scheduling；Mooncake KV read TTFT -23% | Inference group API 难同步；KV path 只小改 Mooncake 44 LoC；未系统做 online SLO | AI storage I/O bulk/asynchronous/grouped；frontend S-NIC 与 backend bandwidth cost 曲线是瓶颈 | 存储层可推断/利用 AI job group semantics | 在线 KV request 很难事先 group；controller/fabric QoS、failure semantics 不清 |
| [[MAIO-FAST26]] | 可编程 page cache 优化 model loading：template prefetch、XPU affinity、burn-after-reading | 只读模型加载；不处理 KV write/read/update 生命周期 | kernel prefetch 只用到 17% SSD bandwidth；NUMA/XPU affinity 影响约 20% | AI I/O template 可重复，storage layer 可被告知生命周期 | KV 是读写/重用/失效对象，不是 burn-after-reading model weights；但 MAIO 提供了 programmable cache 的 FAST 线索 |
| [[GhostServe-MLSys26]] | 用 parity shadow 为 intra-node KV checkpoint/fault recovery 降 host memory，占用少 75% | 只 TP intra-node；无 PD/disagg/durable storage；不检测 SDC | checkpoint cost 主要是 PCIe/host memory，不是 parity compute | GPU failure 是 soft intra-node；FP16 KV layout 标准 | 和已有 CPU/SSD/remote KV tier 如何协同未解决；failure model 太窄 |
| [[RaidServe-MLSys26]] | proactive KV backup、cyclic KV placement、hybrid attention 处理 irregular GPU availability | TP-centric；未讨论 backup consistency、multi-tenant KV risk | GPU 故障恢复会造成 online serving 延迟尖峰；KV/compute 失衡可被重布局缓解 | router 可见实时健康和 KV layout；hybrid attention 质量可接受 | backup 频率、带宽、脑裂、一致性与安全边界是 storage 问题但论文轻写 |
| [[SuperInfer-MLSys26]] | GH200 上主动 KV rotation + DuplexKV，解决 Grace DRAM/HBM offload bandwidth 利用 | GH200-specific；无 PD/multinode；manual params | vLLM GH200 offload <5% C2C bandwidth，因小 layer-first segments + serial transfer | 大块搬运/overlap 能把 offload 从 OOM fallback 变成常态调度 | synced-block invariant 遇 speculative rollback、prefix shared block、LoRA 可能破裂 |
| [[OPKV-MLSys26]] | 插件式 recallable sparsity，token 级 criticality 与 PagedAttention page recall 结合 | 单卡小 batch；accuracy 评价弱；无 multi-tier/disagg/prefix interaction | critical tokens 稀疏但散落 page 内；page recall 会放大 I/O | page 是可 recall 单元，token 重要性可映射到 page decision | token/page mismatch 造成约 4x I/O amplification；正击 KV storage layer 粒度问题 |
| [[FlexiCache-MLSys26]] | head temporal stability：stable head top-K 在 GPU，其余 host offload；unstable head 全 GPU | 仅 GPU-CPU 两级；单卡；无 PD/disagg/SSD | stable head promoted 页只占 top-K 的 23-35%；GPU KV footprint 可降 >70% | head stability 是 model-intrinsic，可离线 profile | 180GB host KV、PCIe/CPU contention、profile drift 和 P99 reload stall 未解决 |
| [[SkipKV-MLSys26]] | reasoning 模型句子级永久 eviction + steering + batch grouping | 不做 recall/offload；未集成 serving framework | token eviction 碎片会诱发 overthinking；句子冗余是 CoT 可压缩对象 | 被删句子不会在未来成为关键 evidence | 永久删除和 storage-layer reversible transform 是两条路线；正确性边界难归因 |
| [[Kitty-MLSys26]] | 2-bit KV quantization + key channel INT4 boost；系统布局避免 scattered read | 不管 KV 放置/生命周期；调参 per model | 少量 key channel 主导 attention score 误差；INT2 uniform 会伤 reasoning | channel sensitivity 可稳定复用；Triton layout 可部署 | ρ 自动选择、版本漂移、和 offload/PD/speculative 的组合未测 |
| [[IceCache-arXiv26]] | 语义 page layout + per-head DCI tree，使 CPU-GPU offload page 更高纯度 | production trace/multi-tenant/batching/failure 缺失 | 顺序 page 会降低 query-aware offload 命中率；DCI query 比 PCIe loading更大 | key embedding neighbor 可预测未来 query relevance | page purity / hit-rate 分解不足；CPU/PCIe 假设强；silent miss 无 fallback |
| [[NVIDIA-Disagg-Study-MLSys26]] | datacenter-scale disagg Pareto + Dynamo Planner，给出 rate matching / CPP / KV transfer 指南 | 默认无 prefix cache主 sweep；tail/failure/tenant弱；不比较开源强 baseline | 典型 datacenter KV transfer 通常不是瓶颈，但 topology/async critical | KV layer-wise transfer 可被 overlap；资源可动态 rate match | 跨 rack、prefix 碎片、remote storage hop、queueing/failure 会让 transfer 重新主导 |
| [[Meta-LLM-Deploy-MLSys26]] | Meta production deployment config explorer；在线 strict SLO 下 disagg 1.5-2.2x，省约 30% 容量 | KV tiering、multi-tenant tail、failure 未联合建模 | prefill compute-bound / decode bandwidth-bound，phase-specific parallelism 值得分离 | simulator median/mean 足够做 capacity planning；KV transfer/ops 可接受 | P99 网络抖动、elastic pool、KV storage tiers 会改变最优配置 |
| [[fabric-lib-MLSys26]] | reliable-unordered P2P RDMA abstraction，WRITEIMM + IMMCOUNTER；支持 KV migration / RL weight / MoE dispatch | 只提供 transfer primitive；无 storage policy/failure abstraction | 动态成员、非均匀 buffer、单向突发写不适合 collective | 上层知道搬什么；host-proxy 和 IMMCOUNTER 可移植 | READ/atomic 排除；MR lifecycle、cancel、heartbeat、KV storage 协同仍是上层问题 |
| [[ContextPilot-MLSys26]] | RAG context alignment/dedup/annotation，把 overlap 转成 prefix hit | 未结合 LMCache/tiered/disagg；安全/annotation injection 未解 | RAG overlap 常存在但顺序变化杀死 prefix cache | 可通过 context index 重写请求以适配 prefix-cache abstraction | index/cache consistency、tenant security、approx alignment 与 storage lifecycle 交叉 |
| [[Stream2LLM-MLSys26]] | streaming context prefill，LCP invalidation + two-stage scheduling | 只 prefill side；无 decode/KV transfer end-to-end | 用户流式上下文可提前 prefill，TTFT 3.9-11x | prompt update/invalidation 可被局部追踪 | 动态编辑让 KV 需要 version/invalidation contract，不只是 hit/miss |
| [[TeleRAG-MLSys26]] / [[Terminus-MLSys26]] / [[OdinANN-FAST26]] | RAG/vector search 侧减少 retrieval latency / disk I/O / update stalls | 不管理 generator KV | RAG pipeline 的存储/ANN latency 与 prefill/KV 命中耦合 | retrieval 与 generation 可分层优化 | 如果 retrieval 排序/结果顺序改变 prefix hit，KV storage policy 会被上游扰动 |
| [[WARP-FAST26]] | FDP SSD workload/hint emulator，显示 lifetime/RUH alignment 可把 WAF 拉近 1，误分类可让 WAF 3.5x+ | 未用 KV trace；无 LLM serving layer | SSD placement/lifetime hint 的准确性决定 WAF 与 tail | 上层能提供有用对象 lifetime/hotness class | KV block 的 lifespan/hotness 是否足以映射到 FDP/ZNS hint 完全未测 |
| [[CetoFS-FAST26]] | RDMA/NVMe-oF remote storage userspace FS，offload permission/concurrency/redo to target | 非 KV；单 initiator-target；无 multi-tenant/failure eval | 远程存储中 FS 软件栈与 inode lock 会放大网络 RTT | storage target 可可信执行权限/排序/redo | KV remote store 不能只暴露 block device；concurrency、permission、atomicity 可能要进 target |
| [[Cylon-FAST26]] | CXL-SSD full-system emulator，保留 hit ns / miss tens us 双峰；可研究 policy | 非 KV；capacity 受 host DRAM；cooperative cache API 少量评估 | CXL-SSD 的 hit/miss 双峰决定端到端 stall；QEMU 全 MMIO 不可用 | CXL-SSD 可作为 memory/storage boundary device | KV tier on CXL-SSD 需要区分 hit policy、dirty eviction、persistence、tail；不能只用平均 bandwidth |
| [[Xerxes-FAST26]] | CXL fabric/coherence simulator，探索 PBR/DMC/PCIe full-duplex | 非 KV；CXL 3.1 无硬件验证 | tree/chain root bottleneck、DMC snoop filter policy、full-duplex mix 都影响 rack-scale memory | component model 可外推到新 topology | CXL KV cache 需要 fabric topology/QoS/coherence-aware placement，而不是“共享内存无限池” |
| [[WSBuffer-FAST26]] | 重构 buffered write path，用 scrap buffer + large aligned direct write + OTflush | 非 KV；本地 NVMe/XFS；crash semantics 未单测 | 高带宽 NVMe 下 page cache 管理开销压过 DRAM buffer 价值；partial write read-before-write 极贵 | 写路径生命周期可被拆成 scrap / direct / async fill | KV write/read/delete mix 若经通用 page cache，可能遇到同类软件瓶颈；但 KV 需要自己的 crash/isolation contract |

## Tensions

### T1: KV transfer “通常不是瓶颈” vs KV storage “经常就是瓶颈”

[[NVIDIA-Disagg-Study-MLSys26]] 和 [[Meta-LLM-Deploy-MLSys26]] 在 datacenter PD disagg 语境下强调 KV transfer 常可被 layer-wise overlap 和高速互联隐藏。[[Bidaw-FAST26]]、[[SolidAttention-FAST26]]、[[LMCache-arXiv25]]、[[AITurbo-FAST26]] 则显示，一旦 KV 被放进 host DRAM、SSD、remote store 或 object/blob tier，瓶颈从“链路带宽”转成 **I/O 粒度、tail latency、reuse distance、prefetch window、storage software path**。

可攻击点：统一 benchmark 需要同时报告 transfer bytes、storage backend tail、scheduler wait、load-vs-prefill crossover，而不是只报 RDMA bandwidth 或 TTFT 平均值。

### T2: PagedAttention block vs token/head/layer/query 重要性

[[vLLM-SOSP23]] 的 page/block abstraction 是现有工程栈的根。[[OPKV-MLSys26]]、[[FlexiCache-MLSys26]]、[[IceCache-arXiv26]]、[[Kitty-MLSys26]] 都在从不同方向削弱 uniform block 假设：token criticality 散落页内，head stability 不同，semantic locality 不等于时间顺序，channel sensitivity 不同。storage layer 若只认识 fixed page，就会在 recall、load、writeback、compression 上产生放大。

可攻击点：测 page-level purity、token-level recall、layer/head sparsity 与 actual I/O amplification，尤其在 SSD/CXL/RDMA backend 上。

### T3: Exact persistence vs approximate / transformed KV

[[LMCache-arXiv25]]、[[Bidaw-FAST26]] 主要追求 exact KV reuse；[[CacheGen-SIGCOMM24]] 压缩传输；[[CacheBlend-EuroSys25]] selective recompute；[[SolidAttention-FAST26]]、[[OPKV-MLSys26]]、[[FlexiCache-MLSys26]]、[[IceCache-arXiv26]] 引入 sparse / approximate / recallable state；[[SkipKV-MLSys26]] 做 permanent semantic deletion；[[PRISM-MLSys26]] 则引入 step/module-scoped draft KV。它们都叫 KV cache，但 correctness contract 完全不同。

可攻击点：storage layer 需要 type/tag/version 表达 exact、lossy、recomputable、partial、parity-backed、invalidated，而不是只用 present/absent。

### T4: Serving SLO vs storage device lifetime / WAF / GC

FAST 论文反复提醒 storage backend 不是无副作用资源。[[WARP-FAST26]] 表明 FDP hint 错误会让 WAF 失控；[[WSBuffer-FAST26]] 表明 page cache 写路径会压不满 NVMe；[[Cylon-FAST26]] 表明 CXL-SSD hit/miss 双峰是 policy 核心。KV work 往往把 SSD 当 GB/s 数字或 cold tier，却少有 endurance、write amplification、GC tail、dirty eviction 与 object lifetime 的测量。

可攻击点：把 KV create/delete/reuse trace 投到 FDP/ZNS/CXL-SSD emulator，看 lifecycle hint 是否能改善 WAF/tail，或证明 KV trace 不适合这些设备 hint。

### T5: Cache hit is not free

[[Prefix-Caching]] 和 [[LMCache-arXiv25]] 的目标是避免 recompute，但 [[CacheBlend-EuroSys25]] 和 [[LMCache-arXiv25]] 都暗示某些场景 load 可能不如 recompute；[[SuperInfer-MLSys26]] 则显示小碎片 offload 会严重浪费高速链路。cache hit 的价值取决于 backend、chunk size、queue depth、engine layout、batch state、model size、attention variant、SLO slack。

可攻击点：需要一个 load-vs-prefill-vs-recompute-vs-decompress 的在线决策边界，而不是固定“hit 就 load”。

### T6: KV storage layer wants global metadata, but privacy/security wants narrow visibility

[[KVCacheInTheWild-ATC25]] 发现 inter-user reuse 接近 0；[[LMCache-arXiv25]]、Mooncake、llm-d、Dynamo 都在走 global/shared KV index 或 routing。global visibility 越强，命中越好，但 prompt leakage、tenant namespace、cache poisoning、stale KV、annotation injection（[[ContextPilot-MLSys26]]）的风险越大。

可攻击点：用 tenant namespace 策略 replay production-like traces，量化从 per-user 到 org-level 到 global sharing 的 hit-rate / leakage-risk Pareto。

### T7: Fault-tolerant KV vs storage-layer durable KV

[[GhostServe-MLSys26]] 和 [[RaidServe-MLSys26]] 说明 KV 已经是 fault recovery 的关键状态，但它们处理的是 GPU failure / TP serving 里的 fast recovery。[[LMCache-arXiv25]]、Dynamo KVBM、Mooncake Store 则把 KV 放进持久/远端 tier。[[PRISM-MLSys26]] 把 speculative rollback 具体化为 step-specialized drafter 的 module KV 传递与 reject invalidation。两条线还没有一个共同 failure model：worker crash、partial offload、stale block metadata、SSD failure、network partition、object store inconsistency、speculative rollback 都可能制造不同的 KV state。

可攻击点：KV lifecycle storage layer 的 fault injection benchmark 现在缺失。

## Fragile Assumptions

1. **“KV block 是 immutable value，sequence hash 足够表达身份。”**  
   对 exact prefix cache 成立；对 LoRA/adapters、quantized KV、compressed KV、partial recompute、position-corrected agent prompt、[[PRISM-MLSys26]] 式 module-specific draft KV、speculative rollback 不一定成立。需要 version/domain/schema hash，而非 token hash 单独决定 identity。

2. **“GPU page size 可以直接继承为 storage object size。”**  
   [[LMCache-arXiv25]] 已指出 engine 内 page 太小不适合 I/O；[[OPKV-MLSys26]] 暴露 token/page mismatch；[[SolidAttention-FAST26]] 需要 coarse transfer 才用满 SSD。storage object size 可能要按 layer/head/chunk/backend 动态改变。

3. **“cache hit 总是比 recompute 划算。”**  
   对小模型、短 prefix、高带宽 HBM、慢 backend、high queue depth、compressed/decompress path、cross-attention 需修正的 chunks，都可能不成立。

4. **“LRU / lifespan / category policy 足够描述 KV reuse。”**  
   [[KVCacheInTheWild-ATC25]] 支持 LRU 常常强，但 [[ContextPilot-MLSys26]]、[[CacheSlide-FAST26]]、thinking/agent/RAG workload 显示 reuse 由 prompt construction、tool loop、retrieval order、template drift 共同决定。

5. **“storage backend 是透明 byte store。”**  
   [[WARP-FAST26]]、[[Cylon-FAST26]]、[[CetoFS-FAST26]]、[[WSBuffer-FAST26]] 共同反驳这个假设。backend 的 hint、hit/miss mode、software path、concurrency control、writeback policy 直接进入 SLO。

6. **“global cache index 只影响 performance，不影响 correctness/security。”**  
   tenant isolation、prompt leakage、annotation injection、adapter/model version mismatch、stale KV reuse 都可以把 cache 命中变成错误或安全问题。

7. **“单机单卡 offload 结果可以外推到 disaggregated serving。”**  
   [[Bidaw-FAST26]]、[[SolidAttention-FAST26]]、[[FlexiCache-MLSys26]] 的关键机制依赖本地 SSD/PCIe/host DRAM/单用户或阅读间隔；跨节点后 topology、queueing、routing 和 shared backend 会改变瓶颈。

## Industry Activity

- **NVIDIA Dynamo KVBM**：公开设计文档已经把 KV block manager 定义为横跨 G1 GPU、G2 CPU pinned memory、G3 local SSD、G4 remote/blob storage 的 orchestration layer，并显式包含 block state machine、data flows、event plane、storage advisor 概念；但 G4 被视作 opaque blob store，不理解内部 layout optimization。[KVBM design](https://docs.nvidia.com/dynamo/design-docs/component-design/kvbm-design)
- **NVIDIA NIXL**：NIXL 提供面向 AI inference 的 P2P transfer library，并把 CPU/GPU memory 与 file/block/object storage 放进 modular plugin abstraction；这说明工业栈已经在做“memory + storage 一体传输层”，但 policy 和 KV semantics 不在 NIXL 里。[NIXL](https://github.com/ai-dynamo/nixl)
- **LMCache**：文档将 LMCache 定义为 GPU / CPU DRAM / local disk / remote backend 的 multi-tier KV storage system，分成 Storage Mode 和 Transport Mode；controller 支持 lookup、clear、compress/decompress、move、pin/unpin。默认 policy 仍以 LRU 等缓存策略为核心。[LMCache architecture](https://docs.lmcache.ai/developer_guide/architecture.html)
- **Mooncake / Mooncake Store**：Mooncake 已成为 vLLM/SGLang/LMDeploy/LMCache 的 KV transfer / distributed KV store backend；GitHub timeline 显示 2025 年起进入多框架集成。Mooncake Store 被描述为 distributed KV cache pool backend 和 cross-instance sharing layer。[Mooncake](https://github.com/kvcache-ai/Mooncake)
- **Dynamo KVBM + Mooncake Store RFC**：RFC 提出把 Mooncake Store 接入 KVBM G4 tier，强调 RDMA/TCP、string-key block semantics、distributed metadata server，并设定 round-trip checksum、RDMA put throughput、TTFT reduction 等 verification metrics。这是工业界把 KV store 当真正 storage backend 评估的明确信号。[RFC #1979](https://github.com/kvcache-ai/Mooncake/issues/1979)
- **vLLM NixlConnector**：vLLM 文档把 NixlConnector 定义成 disaggregated prefilling 的 fully asynchronous send/receive KV transfer connector，说明 KV transfer 已是主流 inference engine 的 connector-level feature。[vLLM NixlConnector](https://docs.vllm.ai/en/stable/features/nixl_connector_usage/)
- **llm-d**：llm-d 宣称维护 cluster-wide KV cache view，并用 prefix-cache scorer 做 cache-aware routing；global index 的 metadata 比例被说成很低，但这也把 freshness、tenant boundary、routing correctness 变成系统问题。[llm-d KV cache routing](https://llm-d.ai/blog/kvcache-wins-you-can-see)
- **TraCT**：2025-12 arXiv 提出用 CXL shared memory 同时作为 KV transfer substrate 和 rack-wide prefix-aware KV cache，声称相对 RDMA/DRAM cache baseline 平均 TTFT 最高 9.8x、P99 最高 6.2x、peak throughput 最高 1.6x。它直接暴露出 CXL KV storage 的同步、一致性、非 coherent memory data management 问题。[TraCT](https://arxiv.org/abs/2512.18194)

## Candidate Blanks

### Blank 1: KV lifecycle state machine and trace format

现有系统有 block manager，但没有跨论文/跨 engine 的 lifecycle trace schema。需要描述 block 的状态转换：

`created -> mutable/provisional -> committed/accepted/immutable -> indexed -> offloaded -> transformed(compressed/sparse/semantic/parity/draft) -> onboarded -> reused -> invalidated/rejected -> evicted -> deleted/recovered`

为什么没覆盖：[[vLLM-SOSP23]] 管 GPU pages，[[LMCache-arXiv25]] 管 connector/storage，Dynamo KVBM 管 tiers，但学术论文通常不把生命周期本身当 measurement object。FAST 领域可以把它类比成 page-cache / file-system / object-store trace。

### Blank 2: Storage-device-aware KV placement

KV block 有 lifespan、reuse distance、hotness、tenant、exactness、size、write/read pattern。[[WARP-FAST26]] 说明 lifetime hint 对 SSD WAF 极敏感；[[Cylon-FAST26]] / [[Xerxes-FAST26]] 说明 CXL backend 的 topology/hit-mode 影响 policy。缺少工作把 KV lifecycle trace 映射到 FDP/ZNS/CXL-SSD/CXL fabric hint，并测 WAF、tail、GC、throughput。

为什么没覆盖：AI-infra 论文常把 SSD/CXL/RDMA 当 bandwidth tier；FAST 论文缺真实 KV trace 和 serving SLO。

### Blank 3: Typed KV objects beyond present/absent

Exact KV、quantized KV、CacheGen bitstream、CacheBlend partially recomputed chunks、FlexiCache host-offloaded stable-head pages、OPKV recallable sparse pages、GhostServe parity-backed KV、[[PRISM-MLSys26]] module-specific draft KV 都需要不同 correctness contract。缺少一个 KV object type system 或 metadata schema，让 scheduler 知道 “load exact / decompress / recompute / expand budget / fallback full KV / discard rejected draft KV” 的代价和质量风险。

为什么没覆盖：每篇论文定义自己的 transform，互相不组合；现有 connector API 多是 bytes/chunks/blocks。

### Blank 4: Load-vs-prefill-vs-recompute-vs-decompress decision boundary

KV cache layer 需要在线决定：命中后是从 CPU/SSD/remote/CXL load，还是重新 prefill，还是 decompress，还是 partial recompute。[[LMCache-arXiv25]] 给出工程 substrate，[[CacheBlend-EuroSys25]] 给出 selective recompute，[[Bidaw-FAST26]] / [[SolidAttention-FAST26]] 给出 SSD reuse，但缺少统一 cost model 和可证伪 crossover 曲线。

为什么没覆盖：现有工作倾向证明自己的 path 有收益，而不是在统一系统中让不同 path 竞争。

### Blank 5: KV storage layer fault and consistency model

如果 KV 已经进入 storage layer，必须回答：worker crash 后哪些 block 可复用？partial offload 的 block 如何标记？[[PRISM-MLSys26]] 式 speculative draft KV 在 reject、branch 切换或 module 切换后如何 invalidation？streaming prompt edit 如何 invalidation？remote store checksum / version / lease 怎么做？[[GhostServe-MLSys26]] 和 [[RaidServe-MLSys26]] 从 GPU fault tolerance 进入这个问题，但还没有覆盖 durable/tiered/disaggregated KV store。

为什么没覆盖：LLM serving 系统通常将 failure 交给 orchestration，KV cache 被视为可丢弃优化；但 long-context/agent/persistent sessions 已经让 KV 变成昂贵状态。

### Blank 6: Tenant-aware global KV index

Mooncake、llm-d、Dynamo、LMCache 都走向 shared/global KV metadata。缺少研究量化 namespace 策略：

- per-request
- per-user
- per-org
- public corpus
- model/adaptor/version scoped
- encrypted / confidential KV

对 hit rate、leakage risk、routing skew、metadata freshness、cache poisoning 的影响。

为什么没覆盖：生产系统需要，但公开论文很少有多租户 prompt / user trace；[[KVCacheInTheWild-ATC25]] 只显示 inter-user reuse 低，没有进入安全设计。

### Blank 7: KV-aware storage scheduler for agent/RAG pipelines

RAG/agent 里 retrieval result order、prompt annotation、tool output、streaming edit 会改变 prefix cache 和 KV invalidation。[[ContextPilot-MLSys26]]、[[Stream2LLM-MLSys26]]、[[CacheSlide-FAST26]] 分别处理一段，但没有一个 storage scheduler 能联合 retrieval index state、prompt builder、KV tier state 与 generator SLO。

为什么没覆盖：RAG 系统与 LLM serving 系统仍分层开发，KV cache 只看到最终 prompt，不知道上游为什么改变。

### Blank 8: KV storage benchmark with FAST metrics

需要一个不是“又一个 serving throughput benchmark”的 FAST-style suite：输入 KV lifecycle trace + backend model，输出 TTFT/TPOT/P99、read amplification、write amplification、GC/tail、device utilization、checksum/fault outcome、tenant isolation outcome。

为什么没覆盖：FAST 论文缺 LLM KV workload，MLSys 论文缺 storage-internal metrics。

## Key Unknowns

### Unknown 1: KV block lifecycle distribution 到底是什么样？

测量：在 vLLM/SGLang/LMCache 上 instrument block events，覆盖 ShareGPT、多轮客服、RAGBench/LongBench、agent traces、reasoning traces。记录 create/commit/offload/load/reuse/evict/delete/invalidate、block size、layer/head/chunk、tenant、model/adaptor/version、SLO slack。

判断标准：能否分出稳定的 lifecycle classes，例如 ephemeral decode KV、short-lived prompt KV、long-lived system prompt KV、RAG document KV、agent template KV、fault-recovery checkpoint KV。

### Unknown 2: KV lifespan/hotness 能否生成有效 SSD/CXL hints？

测量：把 Unknown 1 的 trace replay 到 [[WARP-FAST26]] / FEMU / ZNS emulator / CXL-SSD emulator，比较 no hint、LRU hint、oracle lifetime、online predicted lifetime。指标包括 WAF、P99 read/write、GC stalls、TTFT/TPOT。

关键问题：KV trace 是否有足够可预测 lifetime；误分类是否像 WARP 的 Noisy RUH 一样把收益反转。

### Unknown 3: storage object size 应该是多少？

测量：以 engine page、LMCache chunk、layer-contiguous block、head-specific block、semantic page、256KB SSD-aligned segment 等粒度 replay。记录 load amplification、token recall、backend throughput、scheduler stall、metadata overhead。

关键问题：是否存在一个跨 backend 的对象粒度；还是必须 tier-specific layout。

### Unknown 4: cache hit vs recompute 的真实 crossover 在哪里？

测量：扫模型大小、context length、batch state、backend（HBM/DRAM/SSD/RDMA/CXL/object）、queue depth、compression type。对同一 prefix/chunk 比较 load exact、load compressed+decompress、partial recompute、full prefill。输出 cost model，而不是单点速度。

关键问题：LMCache / Bidaw / CacheBlend / CacheGen 的收益区域是否互相覆盖或互相排斥。

### Unknown 5: approximate/transformed KV 的质量边界如何进入 storage policy？

测量：对 [[Kitty-MLSys26]]、[[FlexiCache-MLSys26]]、[[OPKV-MLSys26]]、[[IceCache-arXiv26]]、[[SkipKV-MLSys26]] 类 transform 做统一 differential test：同 prompt、同 seed，对比 full KV logits / answer / pass@k / calibration。把 transform metadata 加入 block state，测 fallback 策略。

关键问题：storage layer 能否根据 risk 选择 exact vs approximate，还是 quality drift 必须由模型/attention layer 内部处理。

### Unknown 6: global KV index 的安全边界和性能 Pareto 是什么？

测量：对真实或合成多租户 trace，分别启用 per-user / per-org / global / public-corpus namespace。记录 cache hit、routing skew、metadata volume、stale hit、potential leakage surface。注入 prompt poisoning、annotation injection、adapter mismatch。

关键问题：是否存在值得发表的 counterintuitive finding，例如 “global sharing 提升很小但风险很大” 或 “public corpus KV dominates useful reuse”。

### Unknown 7: failure 注入下 KV storage layer 如何退化？

测量：注入 prefill worker crash、decoder crash、partial offload interruption、SSD read error、remote store stale metadata、RDMA partition、CXL memory stale ownership、[[PRISM-MLSys26]] 式 speculative rollback / module switch。记录是否 fallback recompute、是否 silent wrong output、恢复 TTFT/P99。

关键问题：KV cache 是否仍可被当作 disposable optimization，还是 long-context/agent serving 已经需要 KV recovery contract。

### Unknown 8: CXL shared memory KV cache 的真实边界在哪里？

测量：基于 [[Cylon-FAST26]] / [[Xerxes-FAST26]] 或真实 CXL 平台，replay PD KV transfer + prefix reuse trace，比较 RDMA pool、CPU DRAM pool、CXL shared memory、local SSD。纳入 topology、coherence/synchronization、tenant QoS、hit/miss mode。

关键问题：[TraCT](https://arxiv.org/abs/2512.18194) 的 CXL KV path 是通用转折点，还是只在特定 rack/topology/traffic 下成立。

## Probe Takeaways

1. **最像 FAST 的切入点不是“更好的 KV eviction”，而是 KV lifecycle + storage backend co-design。** 这能自然连接 FAST26 的 WARP/CXL/CetoFS/WSBuffer/MAIO/AITurbo 与 MLSys26 的 LMCache/disagg/fabric/KV compression。
2. **PagedAttention 之后的下一个抽象可能不是另一个 page policy，而是 typed KV object lifecycle。** 它要表达 exactness、transform、version、tenant、placement、failure 和 backend hint。
3. **现有工业系统已经足够接近，但仍有研究空白。** Dynamo KVBM / LMCache / Mooncake / llm-d 提供了工程 substrate；它们缺的是可公开验证的 lifecycle measurement、storage-device-aware policy、security/failure boundary。
4. **有 FAST-style measurement 空间。** 如果能拿到或生成 KV lifecycle trace，并把它 replay 到 SSD/CXL/RDMA/object storage backend，论文贡献可以不是“又快 20%”，而是定义社区如何衡量 KV storage layer。
5. **与已有 proposal 的边界清楚。** 这不是 importance-guided tiering，也不是 thinking model access pattern，也不是 expert+KV budget；它们都可以消费这个 lifecycle layer，但本 probe 的核心是底层 storage contract。
