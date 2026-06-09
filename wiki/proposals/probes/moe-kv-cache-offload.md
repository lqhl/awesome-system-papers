---
type: probe
topic: "MoE expert weights and KV cache offloading to CPU memory / NVMe under GPU memory shortage"
created: 2026-06-09
probed_papers: ["[[FluxMoE-arXiv26]]", "[[LMCache-arXiv25]]", "[[CacheGen-SIGCOMM24]]", "[[CacheBlend-EuroSys25]]", "[[Libra-ICLR26]]", "[[LatencyOptimal-MoELB-INET4AI25]]", "[[fabric-lib-MLSys26]]", "[[DeepSeek-V4-arXiv26]]", "[[vLLM-SOSP23]]", "[[LayeredPrefill-MLSys26]]", "[[CRAFT-MLSys26]]", "[[MoEBlaze-MLSys26]]", "[[EventTensor-MLSys26]]", "[[FlexiCache-MLSys26]]", "[[Kitty-MLSys26]]", "[[SkipKV-MLSys26]]", "[[SuperInfer-MLSys26]]", "[[MorphServe-MLSys26]]", "[[BatchLLM-MLSys26]]", "[[DistCA-MLSys26]]", "[[MOE-INFINITY-arXiv24]]", "[[OD-MoE-arXiv25]]", "[[CoX-MoE-DAC26]]", "[[MoE-nD-arXiv26]]", "[[IceCache-arXiv26]]", "[[ContextAwareMoE-CXLNDP-arXiv25]]"]
---

# Probe: MoE Expert Weights and KV Cache Offload

## Landscape

### 每个相关工作的定位

| 工作 | 做了什么 | 没做什么 | 隐含假设 |
|------|----------|----------|----------|
| [[vLLM-SOSP23]] | 用 [[PagedAttention]] 把 [[KV-Cache]] 变成 block-managed dynamic memory，并支持 CPU swap | 权重仍默认常驻 GPU；swap 是被动 OOM/preemption 机制，不是常态 tiering | 请求 KV 的生命周期和增长形态类似 OS 页；GPU HBM 应优先服务当前 active sequence |
| [[FluxMoE-arXiv26]] | 把 MoE expert 权重当 PagedTensor 流式装载，压缩 GPU backend + CPU offload 腾 HBM 给 KV cache | 没把 KV cache 同时 offload 到 CPU/SSD；没在 PD 分离或 128K-1M context 下测；没与 KTransformers / [[MOE-INFINITY-arXiv24]] 直比 | Expert 访问窗口可被两层滑动窗口覆盖；expert load 能藏在 decode compute 里；腾出的 HBM 给 KV 比保 expert 更值 |
| [[LMCache-arXiv25]] | 提供 GPU/CPU/SSD/remote 多 tier KV cache 层，支持 prefix reuse 和 PD disaggregation | 只管理 KV，不管理模型权重/expert cache；placement 主要是 KV-local policy | KV cache 是可持久化数据对象；跨请求 reuse 足够高时，慢层级读取能抵消 recompute |
| [[CacheGen-SIGCOMM24]] | 把 KV cache 编码成 bitstream，优化跨节点/慢链路传输体积 | 不决定哪些 KV 留在 HBM；不处理 expert 权重 | KV transfer 的主要瓶颈是字节量；KV 的统计分布可被 codec 利用而质量近似无损 |
| [[CacheBlend-EuroSys25]] | RAG 多 chunk 场景 selective KV recompute，只更新少量 cross-attention token | 只面向预计算 chunk KV 融合；不处理 decode-time expert/KV 资源竞争 | 非 prefix chunk 的大部分 KV 可复用；少量 recompute 可以被下一层 KV fetch 隐藏 |
| [[DeepSeek-V4-arXiv26]] | 模型侧用 CSA+HCA 把 1M context 的 KV cache 压到 V3.2 的 10%，expert 走 FP4/FP8 | 没给通用 runtime 的 CPU/NVMe expert+KV 联合 offload 策略 | 长上下文压力最好先由架构/量化削掉；异构 KV layout 是模型内生设计，不是通用 PagedAttention 兼容对象 |
| [[Libra-ICLR26]] | 用相邻层 hidden state 投机预测下一层 routing，并隐藏 MoE LB 开销 | 聚焦 prefill 和 expert replication/LB；不做 expert offload，也不管 KV tier | Routing 可提前预测；expert 热度在短窗口内稳定到足以指导复制 |
| [[LatencyOptimal-MoELB-INET4AI25]] | 把 expert rebalancing 的搬运代价纳入 ILP/heuristic，减少无效 expert 迁移 | 单独优化 expert placement；没把 KV cache pressure 纳入目标 | Expert 搬运是否值得可以用历史 demand 和移动成本判定；LB 收益必须跨多步摊销 |
| [[CRAFT-MLSys26]] | 按层估计 expert replica benefit，用 MCKP 分配 replica 显存预算 | 只在 GPU/集群内复制 expert；不考虑 CPU/NVMe；KV 只是被挤占的背景资源 | Replica 的收益按层差异巨大；uniform EPLB 浪费显存，显存节省可间接给 KV |
| [[LayeredPrefill-MLSys26]] | 把 prefill 调度轴从 token 改成 layer-group，减少 MoE expert 重载 | 不做 decode expert cache/offload；不管理 KV 慢层级 | MoE prefill 的主要浪费来自重复加载同层 expert；按 layer 聚合能提升 expert reuse |
| [[MoEBlaze-MLSys26]] | 消除 MoE 训练里的 per-expert routed buffer 物化，降低 activation/routing memory wall | 训练系统，不是推理 offload；不处理 KV cache | MoE memory wall 不只来自权重，也来自 routing/intermediate buffer；避免物化比搬运更好 |
| [[EventTensor-MLSys26]] | 用 Event Tensor 编译 data-dependent MoE megakernel，减少同步和 launch overhead | 只解决 kernel/task dependency；不做 memory tier placement | MoE runtime 的动态性可以被一等 event abstraction 表达；调度瓶颈有相当部分在 GPU 内同步 |
| [[fabric-lib-MLSys26]] | 给 KV transfer、RL weight sync、MoE dispatch 提供跨 ConnectX/EFA 的 P2P RDMA 底层 | 不提供 expert/KV 的统一 cache policy；不覆盖本地 NVMe/CPU 资源竞争 | 一旦上层知道要搬什么，可靠但无序的 P2P 原语足以支撑生产系统 |
| [[FlexiCache-MLSys26]] | 利用 KV head 时域稳定性分级处理，显著降低 GPU KV footprint | 不触碰 expert 权重；只在 KV 维度压缩/选择 | 部分 KV head 的重要性随时间稳定，可用较低成本表示 |
| [[Kitty-MLSys26]] | 2-bit KV cache + channel-wise precision boost，8x KV 内存压缩 | 不解决 KV block 放在哪；不处理 expert cache | 少数 key channel 对精度敏感，多数 channel 可低比特化 |
| [[SkipKV-MLSys26]] | reasoning 模型里按句级冗余跳过/驱逐 KV，并用 steering 缩短 CoT | 面向生成冗余，不是多 tier I/O；不处理 MoE expert | CoT 中存在句级重复和 non-execution thoughts，KV 可按语义冗余删减 |
| [[SuperInfer-MLSys26]] | GH200 上用主动 rotary scheduler + DuplexKV 把 KV 在 HBM/Grace DRAM 间高带宽轮转 | 针对 NVLink-C2C，不是 PCIe/NVMe；不管理 expert 权重 | CPU DRAM 带宽足够高时，KV offload 可从被动 OOM 变成主动调度；大块搬运和 overlap 是关键 |
| [[MorphServe-MLSys26]] | 运行时把层精度降级释放 HBM，再弹性扩大 KV cache | 权重形变是 dense layer quant swap，不是 MoE expert offload；KV 仍主要留 GPU | 流量尖峰时临时牺牲部分层精度可换 SLO；压力消退后恢复精度 |
| [[BatchLLM-MLSys26]] | offline 大批量推理中全局前缀树 + memory-centric token batching 最大化 KV reuse | 面向已知大批量 prefill；不处理在线 MoE expert cache miss | 当 workload 可提前看见时，KV 生命周期应由全局计划而非 LRU 决定 |
| [[DistCA-MLSys26]] | 长上下文训练中把 stateless core attention 拆到 attention server 池 | 训练 attention disaggregation，不是 inference KV/expert offload | 无参数 attention 与有参数层可分离调度；token 粒度任务可动态 rebatch |
| [[MOE-INFINITY-arXiv24]] | personal-machine MoE serving：activation-aware expert tracing、prefetch、expert cache，支持 SSD offload dir | 2024 系统，未处理 KV cache tier 的同预算竞争；主线是 expert cache hit/miss | MoE sparse activation 有可利用 temporal locality；expert cache 可以显著优于 naive layer offload |
| [KTransformers](https://madsys.cs.tsinghua.edu.cn/publication/ktransformers-unleashing-the-full-potential-of-cpu/gpu-hybrid-inference-for-moe-models/SOSP25-chen.pdf) | CPU/GPU heterogeneous MoE inference，GPU 放 attention/shared/hot experts，CPU 执行多数 routed experts | 专注 CPU 执行 expert，不是把 expert 与 KV 一起作为统一 tiered object 管理 | MoE expert matmul 在强 CPU/AMX/NUMA 下可接受；保持 attention/KV 在 GPU 是更好的切分 |
| [vLLM MoE offload RFC](https://github.com/vllm-project/vllm/issues/38256) | 提议 CPU pinned expert weights + fixed GPU expert cache + LFRU/cross-layer prediction | 仍把 KV profiler 和 expert cache memory accounting 分开；尚无成熟生产评估 | expert cache miss 可由跨层预测压低；CPU-pinned expert allocations 可以在 vLLM memory profiling 之外处理 |
| [NVIDIA Dynamo KVBM](https://docs.dynamo.nvidia.com/dynamo/components/kvbm) | 统一 KV block manager，支持 HBM/Host DRAM/Remote DRAM/Local SSD/对象存储等后端 | 只管理 KV blocks，不管理 MoE expert weights | KV blocks 是独立于 engine 的统一内存对象；NIXL 可以抽象不同传输/存储后端 |
| [[CoX-MoE-DAC26]] | AMX CPU-GPU co-execution，batch-level expert computation + selective attention offloading | 关注 CPU/GPU 协同执行与 selective attention offload；未覆盖 NVMe 或 unified expert/KV cache | CPU expert computation 可以通过 coalescing batch 而非 microbatch 获得吞吐；常用 expert 静态放 GPU 足够有用 |
| [[MoE-nD-arXiv26]] | 把每层路由到不同 KV compression tuple，在全局 KV budget 下做多轴压缩 | 只压 KV，不管理 expert 权重 | 不同层对 KV eviction/quantization 的敏感度差异很大；全局内存预算应按层异构分配 |
| [[IceCache-arXiv26]] | 用语义 token clustering + PagedAttention 改善 CPU-GPU KV transfer 和长序列质量 | 不涉及 MoE expert；目标是 KV token budget/transfer | 语义相关 token 连续化后，KV offload 的选择和带宽利用都会更好 |
| [[ContextAwareMoE-CXLNDP-arXiv25]] | 用 prefill activation statistics 指导 decode expert placement，冷 expert 放 CXL-NDP 原地执行 | 面向 CXL-NDP 硬件；不处理 KV cache 与 expert 共享 CPU/NVMe | 当 expert 权重搬运太贵时，移动 activation 去 near-data expert 比移动 expert 更合理 |
| [[OD-MoE-arXiv25]] | cacheless edge-distributed MoE inference，用 shadow model 做多层 ahead expert activation prediction | 主要面向多 edge nodes 并行加载 expert；不管理 KV tier，也不把 NVMe 当共享 expert/KV 层级 | 足够准确的 prediction 可把 expert cache 从必要条件变成可选优化；分布式 CPU-GPU links 可叠加 I/O 带宽 |
| [[DwarfStar]] | 本地 DeepSeek-V4 专用引擎：SSD streaming routed experts、hotlist/preload、expert timing、disk KV checkpoint | 不是通用 server；当前 expert SSD streaming 与 disk KV checkpoint 是两套 policy，没有统一资源仲裁 | DeepSeek-V4 的压缩 KV + routed expert 稀疏性让个人机器上的 CPU/RAM/NVMe 成为可用推理层级；正确性优先于泛化 |

整体画面：现有系统已经分别证明了 **expert 可以离开 HBM** 和 **KV cache 可以离开 HBM**，但几乎都把另一类对象当作背景常量；真正未被系统化的问题是：当 GPU、CPU DRAM、NVMe 三层同时承载 MoE expert weights 和 KV cache 时，二者在带宽、容量、预取窗口和正确性风险上互相抢资源。

## Tensions

### Tension 1: Expert offload 想把 HBM 留给 KV，KV offload 又想把 HBM 留给权重/throughput

[[FluxMoE-arXiv26]] 的叙事是冷 expert 挤占 KV，所以应把 expert 驱逐出 HBM；[[LMCache-arXiv25]]、NVIDIA KVBM、[[IceCache-arXiv26]] 的叙事是 KV 太大，所以应把 KV 驱逐出 HBM。两者单独都成立，但在同一台显存不足机器上会变成循环让位：KV 多留一点可以扩大 batch/context，expert 多留一点可以减少每 token miss。

涉及工作：[[FluxMoE-arXiv26]]、[[LMCache-arXiv25]]、[[SuperInfer-MLSys26]]、[[DwarfStar]]。

### Tension 2: Expert access 是 router-dependent，KV access 是 attention/query-dependent，两个预测信号未必同步

Expert prefetch 依赖 routing 热度或跨层 prediction；KV prefetch/eviction 依赖 prefix reuse、attention importance、semantic clustering 或 recency。一个请求的 hot expert 不一定对应它会反复访问的 KV 区域，尤其在 RAG、agent、thinking trace 里，expert specialization 可能按任务类型稳定，而 KV 重要性按问题跳动。

涉及工作：[[Libra-ICLR26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[SkipKV-MLSys26]]、[[FlexiCache-MLSys26]]、[[MoE-nD-arXiv26]]。

### Tension 3: Decode 的隐藏窗口同时被 expert load 和 KV fetch 消耗

许多工作声称 I/O 可以被 compute hide：[[FluxMoE-arXiv26]] 藏 expert materialization，[[CacheBlend-EuroSys25]] 藏下一层 KV fetch，[[SuperInfer-MLSys26]] 藏 HBM/DRAM rotation。但如果 expert weight miss 和 KV block miss 同时发生，它们共享 PCIe/NVMe/CPU memory bandwidth，隐藏窗口不是可叠加资源。

涉及工作：[[FluxMoE-arXiv26]]、[[CacheBlend-EuroSys25]]、[[SuperInfer-MLSys26]]、KTransformers、[[DwarfStar]]。

### Tension 4: 模型侧压缩正在改变系统 offload 的价值窗口

[[DeepSeek-V4-arXiv26]] 用 FP4 expert 和 CSA/HCA 极大压缩 KV；[[Kitty-MLSys26]]、[[MoE-nD-arXiv26]]、[[IceCache-arXiv26]] 继续从 KV 侧压缩；KTransformers 和 [[DwarfStar]] 则利用 DeepSeek-V4 的具体结构做窄实现。通用 offload 系统如果仍假设 BF16 dense attention + 未压缩 expert，很可能会优化一个正在消失的生态位。

涉及工作：[[DeepSeek-V4-arXiv26]]、[[Kitty-MLSys26]]、[[FluxMoE-arXiv26]]、KTransformers、[[DwarfStar]]。

### Tension 5: 工业系统偏向可运行，论文系统偏向可归纳

KTransformers、vLLM RFC、[[DwarfStar]]、llama.cpp/ik_llama 这类系统大量使用模型特定 tensor layout、hotlist、NUMA/SSD tuning；学术论文通常需要跨模型、跨硬件归纳。这个方向的真实 workload 在本地/边缘/低显存机器上很强，但要变成系统论文，需要把“模型特化工程”抽象成可测量的资源调度问题。

涉及工作：KTransformers、[[MOE-INFINITY-arXiv24]]、vLLM RFC、[[DwarfStar]]、[[FluxMoE-arXiv26]]。

## Industry Activity

- **NVIDIA Dynamo KVBM / KV offload**：Dynamo 文档已把 KVBM、LMCache、FlexKV 作为 vLLM KV cache offloading 后端，支持 CPU 和 disk tiers，并与 KV-aware routing/disaggregated serving 集成。KVBM 底层用 NIXL 抽象 HBM、Host DRAM、Remote DRAM、Local SSD、文件系统、对象存储等后端。来源：[KV Cache Offloading](https://docs.nvidia.com/dynamo/backends/v-llm/kv-cache-offloading)、[KVBM](https://docs.dynamo.nvidia.com/dynamo/components/kvbm)。
- **LMCache / InfiniStore / Mooncake / FlexKV**：LMCache 文档和博客显示工业界已把 KV cache 多级存储作为部署对象，后端包括 local disk、Redis、Mooncake、InfiniStore；FlexKV 公开声称 GPU/CPU/SSD 多级缓存、io_uring 和 GPUDirect Storage。来源：[LMCache architecture](https://docs.lmcache.ai/developer_guide/architecture.html)、[Local storage](https://docs.lmcache.ai/kv_cache/storage_backends/local_storage.html)。
- **KTransformers / SGLang-KT**：KTransformers 文档给出 DeepSeek-V4 Flash 1M context 的 4×RTX 5090 recipe：10 个 routed experts 留 GPU，其余在 CPU；启用 dynamic expert update，模型权重放本地 NVMe。来源：[Long Context Deployment](https://ktransformers.net/en/docs/inference/long-context-deployment)。
- **vLLM MoE offload RFC**：vLLM 社区已有 incremental MoE expert offloading RFC：expert weights 放 CPU pinned memory，固定大小 GPU cache 存 hot experts，LFRU 和 cross-layer prediction 降 miss；讨论中特别指出 CPU-pinned allocations 对 vLLM GPU memory profiler 不可见，可能影响 KV 预算。来源：[vLLM issue #38256](https://github.com/vllm-project/vllm/issues/38256)。
- **Personal-machine MoE inference**：[[MOE-INFINITY-arXiv24]]、KTransformers、ik_llama/llama.cpp、[[DwarfStar]] 都在证明一个事实：MoE 的 sparse expert 结构让“模型总大小 > GPU 显存”不再是 hard cutoff，而是 speed/capacity continuum。区别在于它们多数把 KV 视作固定占用或独立 checkpoint，而非与 expert cache 共同调度。
- **Storage vendors / system integrators**：Dell、Solidigm 等开始围绕 KV cache storage offload 做方案材料，说明 KV offload 已经从论文进入基础设施营销层；但这些材料通常默认 expert weights 仍在 memory 中，或只把 MoE 当 KV 压力来源。

## Candidate Blanks

### Blank 1: Expert cache 与 KV cache 的统一预算器

现有系统通常有两个独立 knob：GPU expert cache size 和 KV cache budget。缺少一个统一 controller，在每个 workload phase 下决定 HBM 里多放一个 expert slot 还是多放一批 KV blocks。这个 blank 不等同于 [[ImportanceGuidedKVTiering]]，后者问“哪些 KV block 重要”；这里问“expert 与 KV 两类对象谁应该占下一 GiB HBM”。

为什么现有工作没覆盖：[[FluxMoE-arXiv26]] 只把 expert 驱逐出来让 KV 受益，[[LMCache-arXiv25]] 只管 KV 多层存储；KTransformers/[[DwarfStar]] 有工程 knob，但不是可归纳的调度模型。

### Blank 2: 双 miss 场景下的带宽仲裁和隐藏窗口测量

如果同一个 decode step 同时发生 expert miss 和 KV miss，系统需要决定谁先走 PCIe/NVMe、谁可以等待、谁应该 fallback recompute/CPU execute。现有论文常把自己的 I/O 藏在 compute 里，但没有测两个 offload 子系统同时抢慢层级时的 queueing 和尾延迟。

为什么现有工作没覆盖：单论文通常隔离变量评估，expert offload 和 KV offload 分属两条文献线；硬件 profiling 需要真实 runtime 而非 trace-only 模拟。

### Blank 3: Router signal 与 attention signal 的跨对象联合预测

MoE router 产生 expert demand，attention/semantic scores 产生 KV demand。这两个模型内信号是否能组合成一个 shared prefetch plan 尚未被测量。例如 prefill 阶段 router 统计是否能预测 decode 的 expert miss；早期 decode attention 是否能预测后续 KV block miss；二者是否在任务类型上相关。

为什么现有工作没覆盖：[[Libra-ICLR26]] 只预测下一层 expert；[[ImportanceGuidedKVTiering]] 关注 KV importance；没有工作把 router 和 attention signal 放在同一 trace schema 里。

### Blank 4: NVMe as shared inference tier，而不是单一对象的 backing store

[[MOE-INFINITY-arXiv24]]、[[DwarfStar]] 把 NVMe 用作 expert backing store；LMCache/FlexKV 把 NVMe 用作 KV backing store。缺少“NVMe 同时存 expert pages、KV pages、checkpoint/session pages”时的 layout、I/O scheduling、wear、read amplification 和 mmap/pread 策略研究。

为什么现有工作没覆盖：云论文偏 RDMA/CPU DRAM，个人机器系统偏能跑即可；NVMe 的细节在系统论文里常被简化成 bandwidth number。

### Blank 5: 模型特化 offload 经验的可移植抽象

DeepSeek-V4、Kimi-K2、Qwen3MoE 的 routed expert 数、top-k、KV layout、压缩结构不同。[[DwarfStar]] 这样的窄实现能利用 DeepSeek-V4 的 exact layout 做正确性和速度优化，但学术贡献需要说明哪些部分是模型无关抽象，哪些必须留给 model adapter。

为什么现有工作没覆盖：通用系统怕模型特化，模型特化系统不追求跨模型抽象；DeepSeek-V4 这类异构 KV + FP4 expert 模型出现时间太近。

### Blank 6: Offload policy 的 correctness/silent failure boundary

Expert offload 是精确的，只要权重加载正确就不改输出；KV compression/eviction/offload 可能导致 recompute、跳过、低精度或 stale checkpoint。两者联合后，系统可能为了 SLO 选择不同 fallback 路径，产生难以归因的 silent quality drift。

为什么现有工作没覆盖：expert offload 文献通常强调 exactness，KV 文献单独评估 quality；联合系统需要同时记录 expert miss、KV miss、fallback、输出差异。

## Key Unknowns

### Unknown 1: 在真实 workload 下，下一 GiB HBM 给 expert cache 还是 KV cache 的边际收益更高？

测量方法：在同一引擎上扫 expert cache budget × KV budget 二维网格，记录 tokens/s、TTFT、TPOT、P99、context capacity、expert miss rate、KV hit rate。workload 至少包括 ShareGPT、LongBench/RAG、多轮 agent trace、DeepSeek-V4 thinking/max 模式。

### Unknown 2: Expert miss 和 KV miss 是否在时间上相关？

测量方法：为每个 decode step 记录 selected experts、expert cache hit/miss、KV block hit/miss、attention block ids、token position、layer。计算 cross-correlation：高 expert miss burst 是否伴随 KV miss burst；router entropy 和 KV working-set size 是否同步上升。

### Unknown 3: 两类 I/O 的可隐藏窗口到底有多大？

测量方法：在 PCIe GPU、GH200/C2C、Apple unified memory、NVMe SSD 四类平台上做 microbenchmark：单独 expert load、单独 KV fetch、同时 expert+KV load；对比 sequential、priority、deadline-aware、large-batch coalescing。输出 “hidden bytes per layer/token” 而不是只报 bandwidth。

### Unknown 4: Router statistics 能否提前 enough steps 预测 expert prefetch？

测量方法：复现 [[Libra-ICLR26]] 的相邻层 prediction，但把目标从 replication 改成 offload prefetch deadline；测 top-k expert prediction lead time、miss penalty、prefetch waste。特别测 decode 小 batch和 batch diversity 高的多租户场景。

### Unknown 5: KV offload policy 是否需要理解 MoE routing？

测量方法：在相同 KV budget 下比较 routing-blind KV tiering（LRU/importance/semantic）和 routing-aware tiering（按 expert group/task type 分桶维护 KV hotness）。如果 routing-aware hit rate 或 tail latency 明显更好，说明 MoE expert specialization 是 KV placement 信号。

### Unknown 6: NVMe 同时承载 expert pages 和 KV pages 时，文件布局和 I/O API 影响多大？

测量方法：对比 mmap page fault、explicit pread、io_uring、direct I/O、GPUDirect Storage（若硬件可用）；分别测 expert 大连续读、KV 小块随机读、混合读。记录 read amplification、CPU overhead、tail latency、page cache pollution。

### Unknown 7: 模型侧压缩后，offload 研究的有效窗口在哪里？

测量方法：用 DeepSeek-V4 Flash/Pro、Qwen3MoE、Kimi-K2、Mixtral 做跨模型实验，分别打开/关闭 FP4 expert、KV quantization、CSA/HCA 类压缩。绘制 “model compression level → offload benefit” 曲线，判断这个方向是面向 frontier compressed MoE，还是主要面向本地/旧模型/低显存部署。

### Unknown 8: 联合 offload 的最小可复现平台是什么？

测量方法：以 [[DwarfStar]] 为窄平台做 trace collector，再用 vLLM/SGLang-KT 做通用平台复验。最小平台应能同时记录 expert cache、KV disk checkpoint/CPU offload、NVMe I/O、token latency，并能用 official-vector/logit diff 做 correctness gate。
