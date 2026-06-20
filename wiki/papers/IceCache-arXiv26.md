---
type: paper
name: IceCache
full_title: "ICECACHE: Memory-Efficient KV-Cache Management for Long-Sequence LLMs"
authors: [Yuzhen Mao, Martin Ester, Qitong Wang, Ke Li]
venue: arXiv
year: 2026
tags: [llm-inference, kv-cache, long-context, offloading, sparse-attention, memory-management]
source_pdf: "[[arxiv26-icecache.pdf]]"
source_md: "[[arxiv26-icecache]]"
---

# ICECACHE: Memory-Efficient KV-Cache Management for Long-Sequence LLMs (arXiv 2026)

> **一句话总结**：IceCache 的关键假设是长上下文 decode 时真正有用的 [[KV-Cache]] token 可由 query 在 key embedding 空间中近似找回，且语义相关 token 应该被放进同一批 [[PagedAttention]] page；它用 per-head DCI-tree 重排 page layout、用 M-DCI 做 query-aware page retrieval、再用 bulk CPU-GPU loading 隐藏传输开销，在 LongBench 上 256-token budget 保留约 99% Full KV accuracy，并在 36k context 下以约 0.11s TPOT 达到 99.0% Full-KV accuracy。

## 问题与动机

长序列 LLM 推理的核心系统压力来自 [[KV-Cache]] 的线性增长：context 越长，每个 decode step 需要保留和访问的 key/value 越多，显存占用和 memory bandwidth 都会变成瓶颈。作者把目标放在 resource-constrained GPU 上的 long-context / long-generation inference，而不是训练或短 prompt serving。

已有方法大致分成两类。Eviction-based 方法如 H2O、[[StreamingLLM]]、SnapKV 速度快，因为它们尽量不做 CPU-GPU 迁移，但 token 选择更静态，长生成或 query 变化时容易丢关键上下文。Offloading-based 方法如 MagicPig、OmniKV、PQCache、ArkVale 试图把大部分 KV 放到 CPU，需要时再拉回 GPU，但如果 page selection 不准，就会在 PCIe 上搬很多无关 token。

IceCache 针对的是一个更细的系统缺口：[[PagedAttention]] 把 KV 分成 page 之后，Quest / ArkVale 等 query-aware 方法仍按原始 token 顺序构造 page。若当前 query 需要的 key 分散在很多顺序 page 中，系统为了少数有效 token 必须加载大量无关 page。IceCache 的主张是 page layout 不应该只是内存分配问题，也应该编码 token 的语义局部性。

## 关键观察 / 隐含假设

- **观察 1：长上下文 attention 对少数 token 高度稀疏，且这些 token 需要 query-aware 选择。** 论文引用 sparse attention / KV-cache 工作，并用 Passkey Retrieval、LongBench、GSM8K CoT、RULER 证明在 64-256 token budget 下仍可接近 Full KV。
  - **依赖假设**：任务的有效上下文确实集中在少数 key 上，而不是需要大范围均匀聚合；attention sparsity 能被 runtime retrieval 近似捕获。
  - **可能失效场景**：需要全局统计、长篇风格一致性、跨文档均匀综合、或 dense retrieval-like aggregation 的任务，可能不满足少数 key 足够的前提。

- **观察 2：按 token 顺序组织 page 会降低 query-aware offloading 的命中率。** Quest / ArkVale 的 page 是顺序 page；IceCache 认为相关 token 被打散后，selected page 中无关 token 比例高，导致 GPU memory 和 PCIe bandwidth 被浪费。
  - **依赖假设**：key embedding 空间中的近邻关系足以代表未来 query 的 attention relevance；把近邻 key 放到同一 page 能显著提升 page-level hit rate。
  - **可能失效场景**：如果模型层中的 key geometry 不稳定，或者不同 head / layer 的 relevant token 分布高度动态，静态或增量 DCI-tree 的 semantic locality 可能很快过期。

- **观察 3：offloading 的主要系统成本不是单纯搬运字节数，而是 page 分散导致的小粒度 PCIe transaction 和查询开销。** IceCache 用 bulk loading 把分散 selected pages 聚合成 contiguous CPU buffer，再一次性传到 GPU buffer，最后 scatter 到 KV table；prefill pipeline 则把 GPU prefill、KV offloading、CPU DCI indexing 重叠。
  - **依赖假设**：PCIe A100/H100 上 bulk transfer 和 pipeline 足以压住 CPU indexing / DCI query 的额外成本；CPU 64 threads 可用。
  - **可能失效场景**：CPU 更弱、PCIe/NVLink 拓扑不同、多租户 CPU 资源受限、或 serving batch 更复杂时，DCI query 和 page rearrangement 的 overhead 可能变成主瓶颈。

- **假设 1：保留 sink pages 和 window pages 可以覆盖 recency/sink-token 需求。**
  - **证据强度**：中。附录算法明确把 sink tokens 和最近 window tokens 常驻 GPU，主实验效果好；但论文没有系统扫描 sink/window 大小对不同 workload 的影响。

- **假设 2：benchmark 能代表真实 long-generation serving。**
  - **证据强度**：中偏弱。LongBench、GSM8K CoT、RULER、LongGenBench 覆盖了 QA、summarization、code、reasoning 和 needle retrieval，但没有 production trace、multi-tenant serving、batch scheduling 或 SLO tail-latency 实验。

## 核心方法

IceCache 把 [[PagedAttention]] 的 page abstraction 保留下来，但改变 page 的填充逻辑。传统 PagedAttention page 按 token 时间顺序存放 KV；IceCache 在 prefill 阶段为每个 attention head 构建一个 DCI-tree，把 key embedding 相近的 token 聚到同一 tree node，并将 node 映射到 physical memory page。这样 page 不再表示连续 token span，而表示一个语义近邻 cluster。

DCI-tree 来自 Multi-level Dynamic Continuous Indexing。论文先把 key/query embedding 做一个变换，使 maximum inner-product search 可以转成 Euclidean nearest-neighbor search；随后通过随机 promotion ratio 构建多层树，高层是稀疏索引，低层保存更多点。每个低层点连接到高一层最近 parent，形成 node / cluster。decode 期间新生成 token 的 key 也会按同一机制插入树中，使索引能随 long generation 更新。

Page selection 发生在每个 decode step。给定当前 query，IceCache 对每个 attention head 独立执行 M-DCI approximate nearest neighbor search，找出 top-k 关键 key，再加载这些 key 所在的 page。对于 GQA，多个 query heads 共享 key/value heads，IceCache 取同组 query 选择 page 的 union。被加载的 page 中所有 token 参与后续 [[Sparse-Attention]]，未选中的 key 被 mask 掉。

这个设计回应了上面的观察 1 和观察 2：如果 attention 真的稀疏，而且 key embedding 近邻能预测高 attention token，那么 page layout 的 semantic clustering 会把“找 token”变成“找少数高纯度 page”。相比 Quest / ArkVale 的顺序 page，IceCache 追求的是 page-level precision，而不只是 token-level criticality estimation。

系统层面，IceCache 用 bulk loading 解决 selected page 在 CPU/GPU 内存中不连续的问题。它先过滤已经在 GPU resident 的 page，把剩余 selected pages 聚合到 CPU preload buffer，通过一次高吞吐 PCIe transfer 到 GPU buffer，再 scatter 到 KV-cache table 的目标槽位。prefill 阶段则在 GPU 继续计算后续 layer 时，把已经产生的 KV offload 到 CPU 并启动 DCI indexing，从而把索引构建藏在 prefill pipeline 里。

附录中的 IceCache(reuse) 进一步在每三层的 anchor layer 执行 DCI query，中间层复用最近 anchor layer 的 page indices。这是一个明确的 accuracy-latency tradeoff：减少 DCI query 次数，让 TPOT 接近 OmniKV，但牺牲一点精确性。

## 设计取舍

- **语义 page layout vs 顺序 locality**：IceCache 获得更高 page hit rate，但放弃了 token 顺序 page 的简单性。任何需要按位置连续扫描或复用顺序窗口的优化，都要额外处理 node-page 映射。
- **per-head precision vs 索引成本**：每个 head 单独建 DCI-tree 能提升 retrieval granularity，但也增加 CPU 内存、index construction、query 和维护成本。论文用 pipeline 隐藏一部分成本，但复杂度真实存在。
- **offloading capacity vs tail latency**：把大部分 KV 放 CPU 可以显著降显存，但 decode step 变成 GPU attention、CPU ANN、PCIe transfer、scatter 的组合路径。平均 TPOT 好看不等于 tail latency 一定稳定。
- **approximate retrieval vs correctness**：IceCache 近似 Full KV，不改变模型权重，但它会 mask 掉未选 page。对于需要精确可复现输出或对少量遗漏极敏感的任务，retrieval miss 仍可能表现为 silent quality loss。
- **benchmark-friendly budget vs deployment policy**：论文主要报告固定 token budget 64/128/256 和 10% budget。真实 serving 可能需要按 prompt、tenant、SLO、batch size 动态调 budget，否则会在成本和质量之间卡住。

## 实验与结果

- **Passkey Retrieval**：Llama-3.1-8B-Instruct 在 10k-100k words、passkey 插入位置 0%-95%、budget 64/128/256 下均达到 100% retrieval accuracy，说明 IceCache 对 needle-style long-range dependency 很强。
- **LongBench / Llama-3.1-8B**：budget 64 的平均 accuracy 为 47.8，超过 PQCache budget 256 的 47.3；budget 256 达到 49.0，距离 Full KV 49.5 仅 0.5 分。
- **LongBench / Mistral-7B**：budget 256 平均 41.7，超过 MagicPig 39.1；budget 64 为 39.0，接近 MagicPig budget 256 的 39.1。
- **更大模型与不同 attention 架构**：Qwen3-32B 上 budget 64 / 256 分别达到 42.2 / 43.1，相当于 Full KV 43.4 的 97.2% / 99.3%；LongChat-7B-v1.5 上 budget 64 / 256 分别保留 96.3% / 99.4% Full KV performance。
- **36k latency**：TT2T 约 7.7s，IceCache(reuse) 约 5.9s，PQCache 约 13.3s；SnapKV 和 StreamingLLM 明显更快，但 accuracy 低。TPOT 图中 IceCache 约 0.11s 且达到 99.0% Full-KV accuracy，IceCache(reuse) 约 0.06s。
- **TPOT breakdown**：36k context 下总 TPOT 约 0.11s，其中 DCI query 约 0.05s、decoding 约 0.04s、loading 约 0.015s、其他约 0.005s。也就是说 IceCache 的最大新增系统成本已经是 query，而不是 PCIe loading。
- **GSM8K CoT**：Mistral-7B-Instruct-v0.2、10% budget 下 IceCache 为 47.4%，接近 Full KV 48.2%，高于 PQCache 46.2、SnapKV 44.7、StreamingLLM 44.4、ArkVale 30.9。
- **RULER 极长上下文**：Qwen3-4B-Instruct-2507 在 150k/200k/250k tokens、budget 256 下，Single-NIAH 都保持 100%；Multi-keys NIAH 和 QA 与 Full KV 接近。latency scaling 图显示 Full KV 从约 190ms/token 增至约 350ms/token，而 IceCache(reuse) 约 140ms/token 增至约 155ms/token。
- **LongGenBench 附录**：Llama-3.1-8B-Instruct、256-token budget 下，IceCache 明显优于 PQCache，接近 Full KV，支持作者关于 long generation 的补充 claim。

## Critical Analysis

### 论证链条

论文的主链条比较闭合：长上下文 KV-cache 造成显存和 bandwidth 压力；少数 token 对 decode 质量更重要；顺序 page 会让 query-aware page selection 的 page purity 不高；因此按 key embedding 语义聚类 page，再 query-aware 召回 page，可以在小 budget 下保持 accuracy。LongBench / GSM8K / RULER 的结果基本支撑“accuracy 在这些 benchmark 上接近 Full KV”，latency breakdown 也证明 bulk loading 后 PCIe transfer 不是最大项。

较弱的一环是“semantic clustering 等价于未来 query relevance”。论文用结果间接证明有效，但没有充分拆出 page hit rate、token recall、cluster purity、不同层/head 的分布变化等 measurement。如果 IceCache 的优势来自 DCI retrieval 本身、sink/window 保留、page reuse 策略或某些 benchmark 的 needle-like 特性，当前实验不容易完全区分。

### 假设压力测试

IceCache 最怕的 workload 是相关信息分散且必须同时聚合的任务，而不是少量关键 evidence retrieval。长文风格迁移、代码库级一致性修改、多文档证据加权、或需要保留大量中等 attention token 的任务，可能让 64/256 budget 不够。论文覆盖了 summarization、QA、code、CoT，但没有专门构造“many weak signals”压力测试。

硬件上，论文的结论绑定在 A100 40GB PCIe、H100 80GB PCIe、64 CPU threads、CUDA 12.2、PyTorch 2.4.1、FlashInfer 这类配置上。若部署环境是 NVLink GPU 池、CPU 资源受限实例、或者 batch serving 中 CPU 被多个请求共享，DCI query 与 CPU-side indexing 的成本占比可能变化。

规模上，RULER 到 250k tokens 的 accuracy 和 300k latency 趋势很有价值，但仍是单 GPU 受控实验。真实 serving 还有 batching、admission control、prefix sharing、tenant isolation、cache eviction across requests，以及 failure recovery，IceCache 没有讨论这些系统层面的外推。

### 实验可信度

基准选择比较全面：Passkey 检验 long-range retrieval，LongBench 覆盖多类长上下文任务，GSM8K CoT 检验长生成 reasoning，RULER 测极长上下文，LongGenBench 做附录补充。baseline 覆盖 eviction、offloading、quantization、query-aware page selection，也包括 Full KV 和 ground-truth Top-k。

但公平性仍有几个不确定点。MagicPig 因 AVX-512 限制被排除在 36k latency 图之外；OmniKV 保留更多 layer 在 GPU，内存占用和方法目标不完全一致；TOP-k 是 oracle 上界，不是可部署 baseline。论文报告平均 accuracy 较多，tail-latency、quality variance、retrieval miss case 和 SLO violation 没有展开。

### 系统性缺陷

实现复杂度显著高于普通 [[PagedAttention]]：per-head DCI-tree、node-page mapping、incremental insertion、bulk preload buffers、GPU scatter、sink/window residency、GQA union 和 optional reuse 都要协调。论文展示了平均 latency，但没有讨论 debugability、可观测性、索引损坏恢复、page table consistency、或请求取消/异常退出时 CPU/GPU cache 状态如何回收。

资源隔离也是空白。IceCache 把一部分瓶颈从 GPU 显存转移到 CPU 内存、CPU compute 和 PCIe 带宽；在多租户 serving 中，这些资源常常更难隔离。若多个请求同时做 DCI query 和 bulk transfer，PCIe 与 CPU thread contention 可能带来尾延迟抖动。

## 局限与 Future Work

- **局限 1：缺少 production trace 和多租户 serving 评估。** 当前结果说明 benchmark 上的 accuracy-latency tradeoff，但不能直接证明在线服务中的 p95/p99 latency、batch throughput、request interference 和 recovery 行为。
- **局限 2：缺少 page hit rate / cluster purity 分解。** 论文没有充分量化 semantic page layout 相比顺序 layout 到底提升了多少 page-level precision，以及提升来自哪些 layer/head/task。
- **局限 3：CPU/PCIe 假设较强。** 64 CPU threads、PCIe A100/H100 的结果不一定能外推到 CPU 受限云实例、NVLink 环境或 shared CPU serving。
- **局限 4：quality risk 是 silent 的。** 一旦 ANN miss 掉关键 page，模型可能仍输出流畅但错误的答案；论文没有提供 miss detection、fallback 到 Full KV、或 confidence-based budget expansion。
- **Future work 1：构造 page-purity benchmark。** 固定模型和 budget，比较顺序 page、random page、semantic DCI page 的 selected-page token recall / irrelevant-token ratio / accuracy，分 layer/head/task 报告。
- **Future work 2：做 SLO-aware adaptive budget。** 根据 query entropy、retrieval margin、task type 或 observed miss risk 动态调 page budget，并测 p95/p99 latency 与 accuracy。
- **Future work 3：评估 multi-request serving。** 在 vLLM-like scheduler 中加入 IceCache，测 batching、prefix sharing、tenant contention、CPU thread pressure 和 PCIe saturation。
- **Future work 4：设计 safe fallback。** 当 DCI query margin 低或 selected pages 分散度异常时，自动扩大 budget 或回退到 Full KV / larger window，并量化额外成本。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Sparse-Attention]]、[[Attention]]
- **同类系统 / 方法**：[[vLLM]]、Quest、ArkVale、PQCache、OmniKV、SnapKV、[[StreamingLLM]]、MagicPig、H2O
- **相关论文页**：[[vLLM-SOSP23]]、[[DecouKV-ATC25]]、[[DiffKV-SOSP25]]、[[SkipKV-MLSys26]]、[[OPKV-MLSys26]]、[[KVCacheInTheWild-ATC25]]
- **同会议**：arXiv 预印本，暂无会议页
