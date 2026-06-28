# CrossPool: Eficient Multi-LLM Serving for Cold MoE Models through KV-Cache and Weight Disaggregation

Zhuoren Ye, Tianyu Wo, Dinghao Xue, Mingming Zhang, Yuchen Teng, Chunming Hu, Renyu Yang<sup>†</sup>

School of Software, Beihang University

{yezr,woty,dinghaoxue,mingmingzhang,yuchenteng,hucm,renyuyang}@buaa.edu.cn

## Abstract

Emerging LLM services increasingly host many sparse MoE models, yet most models receive sparse requests and remain cold. This creates a GPU memory problem: model weights are stable and model-determined, while KV-cache is transient and demand-determined. Because cold models rarely reach peak KV-cache demand at the same time, reserving worst-case KV capacity per model wastes memory; a shared KV-cache pool can instead provision aggregate active demand. However, KV-cache sharing is not suficient when weights and KV-cache remain in a monolithic GPU mem ory pool. Static weights compete with dynamic KV-cache, and KV-head-limited attention under cold, low-concurrency trafic exposes only a fraction of replicated KV capacity, leading to low GPU memory utilization and weak long-context support. We present CrossPool, a serving engine for cold MoE models that separates FFN weights and KV-cache into two GPU memory pools: a weights pool that consolidates FFN weights across cold models, and a KV-cache pool that dynamically serves active requests while keeping attention local to KV-cache. CrossPool combines a KV-cache planner and virtualizer, a layer-wise pipeline scheduler that hides hidden-state transfers, and persistent kernels with control lowering to reduce CPU-GPU control overhead. With eficient GPU memory pooling, CrossPool underpins bursty long-context requests and outperforms the state-of-the-art kvcached-based multi-LLM serving system, reducing P99 TBT by up to 10<sup>.</sup>4×.

## 1 Introduction

Emerging large language models (LLMs) now power applications ranging from chatbots [14, 20, 29] to agentic assistants [4, 30, 31]. To serve this demand, model providers [2, 6, 11] deploy increasingly capable, fast-evolving LLMs in their datacenters. Many recent frontier and open-weight models support long context for complex tasks and use Mixture-of-Experts (MoE) architectures [9, 13, 15, 18, 22, 25, 35] to scale total parameters while keeping computation moderate.

This trend makes cold-model serving increasingly important. Recent studies [17, 19, 36] show that a few hot models serve most requests, while many cold models are underutilized. A serving cluster that keeps many such models online therefore pays the memory cost of large MoE weights even when most models have few active requests. Long-context serving adds a second pressure point: KV-cache can grow to a large fraction of GPU memory, but unlike weights, it is allocated only while requests are active and is reclaimed after decode finishes.

The key opportunity is that weights and KV-cache have diferent lifetimes. Model weights are model-determined and stable, whereas KV-cache is demand-determined and transient: its footprint varies with request rate, context length, and concurrency. Since cold models rarely peak simultaneously, reserving worst-case KV-cache for each model wastes GPU memory. Hence, a shared KV-cache pool can instead provision for aggregate active demand.

Simple memory sharing within a unified GPU memory pool is insuficient. Existing multi-LLM serving systems [17, 38] improve GPU sharing through multiplexing or elastic memory management, but they still colocate static weights and dynamic KV-cache under the same GPU pool. This couples the KV-cache capacity visible to a request with the amount of memory already occupied by weights. It also exposes an algorithm-system mismatch: KV-head-limited attention algorithms such as MLA [12] and MQA [15, 34] reduce per-token KV-cache, while serving engines often use DP attention for such models to increase aggregate throughput. Under cold, low-concurrency workloads, however, only replicas holding active requests expose usable KV-cache capacity to those requests. The result is not merely ineficient sharing: modern long-context MoE models can lose usable context capacity under the same hardware budget.

We present CrossPool, an LLM serving framework for cold MoE models that separates FFN weights and KV-cache into diferent GPU memory pools. The weights pool consolidates FFN weights from multiple cold models, while the KV-cache pool dynamically shares GPU memory for active KV-cache across model instances. CrossPool keeps attention and other non-FFN modules in the KV-cache pool for local KV access, and executes FFN modules in the weights pool because they dominate MoE parameters. The pool boundary exchanges hidden states rather than KV-cache tensors. This design increases shared KV-cache capacity without giving up competitive performance. To make this practical, CrossPool addresses three design challenges: heterogeneous KV-cache planning, communication across disaggregated pools, and graph/control overhead under layer-wise mixed scheduling. Our main technical contributions are threefold.

![](images/afcbac6d3aeff7e76e68eb272690d12047cbb2d56e34797f55100d1bb1be954b.jpg)

![](images/ee4355c93a817538441d5850be2acd97ed50dc87b8a40545d3739ea3c2932ec2.jpg)  
(a) Underutilized cold models (b) Accumulated KV-cache  
Figure 1. Cold-model underutilization and accumulated KVcache usage under low RPS. Subfigure (a) summarizes data from OpenRouter [32], and (b) stacks active KV-cache bytes for four 7B models at 0.2 RPS over one hour.

• KV-cache planner and virtualizer. CrossPool plans the shared KV-cache pool budget and parallelism ofline, then exposes the pool through virtualized paging [28].

• Layer-wise pipeline scheduler. CrossPool schedules attention and FFN at layer granularity, overlapping hidden-state transfers with computation across in-flight batches.

• Persistent kernels and control lowering. CrossPool separately captures attention and FFN subgraphs and lowers frequent scheduling and communication control to GPUresident persistent kernels.

We evaluate CrossPool on a production-grade platform against Static Partition and kvcached [38]. CrossPool improves memory pooling eficiency to support long-context requests while preserving competitive performance on balanced workloads.

## 2 Background and Motivation

## 2.1 Multi-LLM Serving and KV-cache Memory

LLM model providers (e.g., DeepInfra [11], Alibaba Model Studio [2], Volcano Engine [6]) are deploying more LLMs to meet rising demand for agentic applications. Recent work [17, 19, 36] shows that LLM popularity is highly skewed: a few hot models receive most user requests, while many cold models are underutilized. Fig. 1a plots the CDF of token consumption across models on OpenRouter [32] and shows that ∼90% of models are cold and consume few tokens.

Serving cold models is intricate because of their large GPU memory footprint. During inference, GPU memory is mainly occupied by model weights and KV-cache. Weights are fixed by the architecture and remain resident once a model is loaded, while KV-cache is generated dynamically by attention and reclaimed after requests finish. Fig. 1b shows that at low RPS (requests per second), active KV-cache usage varies widely across models but often remains low, indicating a potential to share a unified KV-cache pool across multiple cold models. It is desirable to properly size a shared pool for aggregate active KV-cache at a random time, not for each request’s peak. Under low request volume (cold trafic), many models exhibit no active requests, and KV-cache usage fluctuates as requests start and finish. This allows provisioning the pool to a high percentile of aggregate demand instead of the worst-case load for each model.

![](images/4f6e498a87ada3bc6e07d76994563a8094c743ff78803ac9f99f292918be1f79.jpg)  
(a) Aggregated memory pool

![](images/fce3e827940497d00475f6962e8f2bd2c2e5c19acb9f955db485659d9ae468c8.jpg)  
(b) Disaggregated memory pool  
Figure 2. KV-cache availability when serving a single request on 4 GPUs. Comparison of monolithic and disaggregated memory pools for weights and KV-cache. n\_heads values of MHA, GQA and MQA are 4, 2 and 1, respectively.

## 2.2 Mismatch between Algorithms and Systems

Recent LLMs use diverse attention algorithms (e.g., GQA [1], MQA [34], MLA [12]) to improve computation and memory eficiency. For KV-cache placement, the key factor is the number of KV heads. With <sup>??</sup> GPUs, these algorithms fall into: (Type I) MHA and GQA with n\_heads ≥ <sup>??</sup>; and (Type II) MQA, MLA, and GQA with n\_heads <sup>< ??</sup>. TP (a.k.a., tensor/head parallelism) naturally exposes KV-cache capacity for Type I models.

Modern serving engines (e.g., vLLM [23] and SGLang [39]) typically use data parallelism (a.k.a., DP) or DP attention (a.k.a., DPA) for KV-head-limited models. These replicas ofer high aggregate KV-cache capacity under high concurrency, but in cold-model serving only replicas with active requests provide usable capacity. Existing multi-LLM serving engines inherit these parallelism schemes from their backends and therefore sufer from low efective KV-cache utilization for Type II algorithms in low-concurrent cases.

Furthermore, current multi-LLM serving engines (e.g., MuxServe [17] and kvcached [38]) typically adopt placement strategies that colocate model weights and KV-cache within a single GPU memory pool. As a result, the cumulative footprint of model weights occupies a substantial fraction of the limited GPU memory, thereby yielding low per-GPU KV-cache capacity. This, in turn, diminishes support for longcontext workloads and can, in extreme cases, lead to out-ofmemory (OOM) failures or request rejection.

Fig. 2a illustrates how current multi-LLM serving engines allocate all model parameters and KV-cache in a monolithic GPU memory pool. Under a single-request workload, in the MHA configuration (n\_heads = 4, implying TP = 4), the KVcache is efectively distributed across all four GPUs, and the request can utilize the aggregate KV-cache capacity of the entire 4-GPU group. In contrast, with grouped-query attention (GQA) (n\_heads = 2, hence TP = 2 and DP = 2), an individual request is confined to a single two-GPU replica, and therefore can only access the KV-cache capacity of that replica. Under multi-query attention (MQA) (n\_heads = 1, hence DP = 4), each request is restricted to the KV-cache of a single GPU in this placement scheme. Consequently, the 1/2 and 1/4 factors represent the fraction of total KVcache capacity that is visible to a single request under lowconcurrency conditions. In addition, the colocation of model parameters and KV-cache within the same GPU memory further reduces the efective KV-cache capacity available on each GPU.

## 2.3 Challenges

As shown in Fig. 2b, it is desirable to decouple the monolithic GPU memory pool into two disaggregated pools – a model weights pool and a KV-cache pool. This enables flexible attention parallelism, improves KV-cache utilization by avoiding unnecessary DP replicas, and maximizes per-GPU KV-cache capacity. However, this organization must solve three challenges.

C1: Enabling diverse KV-cache strategies. Diferent attention algorithms produce diferent KV tensor layouts, numbers of KV heads, and per-token KV bytes. Therefore, a shared KV-cache pool cannot use a fixed pool budget or parallelism strategy without accounting for the colocated models. The system must estimate aggregate KV demand from prompt length, output length, service time, and arrival rate; account for model-specific KV bytes per token; and choose parallelism plans that expose usable KV-cache capacity under cold concurrency. The output of this planning must be enforceable online as a pool page budget and rank assignments, otherwise the shared pool can be over-admitted during a burst.

C2: Non-negligible communication overhead between pools. Disaggregating weights and KV-cache creates a new pool boundary in the inference path. Attention must access KV-cache locally because the KV tensors grow with context length and are read at every decode step. Moving KV-cache tensors across the boundary would therefore make attention communication-bound, especially for long-context requests. At the same time, not all weights should stay with the KVcache pool, because MoE FFN modules dominate the stored parameters. The pool boundary must instead exchange hidden states, whose size is bounded by batch tokens and hidden dimension rather than accumulated context length. However, hidden-state transfer is still on the critical path: it occurs at every pool crossing, for every layer, and for every generated token. Even though each transfer is much smaller than moving KV-cache tensors, the repeated transfers accumulate into non-negligible communication overhead.

![](images/f15f509c054f686a3b6f44214d087ce186a1e0d76e8b81cb1b7c420bb40487ff.jpg)  
Figure 3. CrossPool system architecture

C3: Increased graph capture complexity under mixed scheduling. Modern serving engines rely on CUDA graph capture to reduce launch overhead, but disaggregated execution introduces layer-level breakpoints between attention and FFN. Serving multiple cold models across separate pools further creates mixed scheduling: diferent models can have diferent layer counts, batch sizes, and active request timing. If each layer transition and communication step is driven from the host, cold batches sufer frequent CPU-GPU control transitions and the benefit of graph capture is reduced. The system must retain graph execution for attention and FFN subgraphs while lowering frequent scheduling and communication control of the host-side path.

## 3 CrossPool Design

We propose CrossPool, a multi-LLM serving system that colocates cold MoE models by separately pooling GPU memory for model weights and KV-cache (Fig. 3). The weights pool aggregates weights from multiple cold models, and the KV-cache pool provides on-demand KV-cache space for active requests. During decode, a request batch first executes attention and other non-FFN modules in the KV-cache pool, transfers the resulting hidden states to the weights pool for FFN execution, and transfers the FFN output back to the KV-cache pool for the next layer.

CrossPool keeps attention close to KV-cache to avoid transferring KV-cache between two pools. It places non-FFN modules in the KV-cache pool for local KV access and executes FFN modules in the weights pool. This partition matches MoE parameter structure, where FFN modules hold most weights (Table 1). It also defines a communication boundary whose trafic does not grow with context length.

Table 1. Weight breakdown for five 10 – 30B models.  
![](images/0d22a50e77813b4238193831277a4f0d6c5505ca1c530ed02fd52c1f4c67a306.jpg)

The two pools communicate over low-latency links; our prototype uses NVLink with NVSHMEM [27] for hiddenstate transfer. The following subsections describe how KVcache planner and virtualizer work in response to C1, the layer-wise pipeline scheduler for C2 and persistent kernels with control lowering for C3.

## 3.1 KV-cache Planner and Virtualizer

CrossPool includes an ofline KV-cache planner and an online KV-cache virtualizer for heterogeneous KV-cache management. The planner computes the shared KV-cache pool budget and the parallelism plan for each model. The virtualizer then presents the pool through a uniform paged KV-cache interface, so attention kernels can use a logical KV address space while the virtualizer controls physical page allocation.

The planner uses per-model prompt, output, and servicetime samples, arrival rate <sup>??</sup>?? , page size, per-token KV bytes <sup>??</sup> (<sup>??</sup>), and a target provisioning quantile. It emits two outputs: the total KV-cache pool page budget and a parallelism plan that determines how each model uses the KV-cache pool. For model <sup>??</sup>, request <sup>??</sup> arrives at <sup>??</sup>?? and has prompt tokens <sup>??</sup>??,??, output tokens <sup>??</sup>??,??, and decode residence time <sup>??</sup>?? in the KV pool. The planner provisions for aggregate active KV at a random observation time, rather than the final KV footprint of every request. At request age <sup>??</sup>, active KV tokens grow as

![](images/22c144b03d721cd96735e68ed4ffd924194441f4357c76c55033ab1097501422.jpg)

(1)

The aggregate pool demand is:

![](images/bfda614f0acd4d8d33805ba9d8691955ebab6779b18115d857de26f5c26af38c.jpg)

(2)

CrossPool uses the P95/P99 trace-driven Monte Carlo quantile [16] as a conservative provisioning target. This sampling keeps empirical correlations among prompt length, output length, and service time, which are lost if the planner independently sizes each dimension by a worst-case percentile. After the pool demand is estimated, the planner rounds mem ory to pages and sets the shared KV-cache pool page budget.

During online serving, CrossPool schedules each request batch to the DP rank that has the largest free KV-cache space among ranks eligible for the model. The virtualizer employs

![](images/f95f6f2ae04f1cf802e7f2dc2f99a3c32baee0fc9a7c66cfd0afa9ef1061bb57.jpg)  
Figure 4. Layer-wise pipeline scheduler. It interleaves attention and FFN layers of two batches, allowing attention and FFN to be executed simultaneously on diferent batches from diferent models. Early exit is supported when one batch finishes all its layers.

CUDA VMM APIs [28] to reserve a virtual KV address range for each model and map physical KV pages on demand. Attention operators see a normal paged KV-cache interface, while physical page mapping and unmapping remain slow paths outside the per-token critical path. Active KV pages are kept until their decode requests finish; if the pool page budget is exhausted, admission control queues or rejects new requests instead of interrupting active decode requests.

## 3.2 Layer-wise Pipeline Scheduler

To address [C2], CrossPool uses a layer-wise pipeline scheduler to reduce exposed ping-pong overhead between attention in the KV-cache pool and FFN in the weights pool by overlapping their execution across batches. Fig. 4 shows the design. The scheduler maintains two in-flight batches, each with its own model id, layer cursor, and completion state. When batch <sup>??</sup><sub>1</sub> executes attention for a layer in the KV-cache pool, the hidden states of batch <sup>??</sup><sub>2</sub> from a previous layer can be processed by FFN kernels in the weights pool. After an attention stage finishes, the scheduler launches hidden-state transfer to the weights pool; after an FFN stage finishes, it transfers the output back to the KV-cache pool and advances that batch’s layer cursor.

This layer-granular state machine keeps both pools busy without requiring the two batches to have the same model or the same number of layers. If one batch finishes all its layers, the scheduler publishes its tokens, releases the completed batch state, and fetches a new batch from the corresponding request queue. The other batch can continue from its current layer cursor. This avoids a global layer barrier across models and makes the pipeline naturally compatible with heterogeneous cold-model colocation.

## 3.3 Persistent Kernels and Control Lowering

To tackle [C3], CrossPool captures graphs for attention and FFN separately and triggers JIT compilation during warmup. Separating the two graph types preserves graph execution within each pool while still allowing layer-wise scheduling across the pool boundary. CrossPool then uses persistent kernels and control lowering to keep frequent scheduling and communication control on GPUs, reducing host intervention and CPU-GPU control transitions. Fig. 5b illustrates the design.

![](images/addd146202806ffba6c5e77104f03a6cd83887691a3ebc89e42c5f6d9a6d4d02.jpg)  
(a) CPU-launched kernels and communication

![](images/af6d225a5678c3ef9f92c0f017fc13960b7104328f5e890ddd9c6f5fe27fb65b.jpg)  
(b) Persistent kernels with control lowering  
Figure 5. Persistent kernels for eficient graph execution.

CrossPool captures supported attention and FFN subgraphs during warmup and passes their graph handles to GPU-resident persistent kernels. These kernels are launched at the beginning of serving and keep running persistently. Each persistent kernel repeatedly polls per-model request queues on GPUs, selects the next ready batch for its pool, dispatches the corresponding captured graph, launches interpool hidden-state communication when the graph reaches a pool boundary, waits for computation and communication completion, and updates the batch state for the next layer. This design keeps the high-frequency control loop on GPUs, while the host remains responsible for coarse-grained admission, KV-cache page mapping, and failure handling.

## 4 Implementation

We implement CrossPool based on SGLang v0.5.10. The implementation extends the runtime with disaggregated memory pools, a transport layer for hidden state exchange, virtualized KV-cache paging in the KV-cache pool, and persistent GPU-side dispatch for layer-wise execution.

Runtime integration. CrossPool keeps the SGLang request scheduler, tokenizer path, sampling path, and attention kernels in the KV-cache pool. The main runtime change is at the transformer layer boundary. In the KV-cache pool, FFN layers are replaced with proxy layers. A proxy layer receives the hidden states produced by the local attention and non FFN modules, sends them to the weights pool, waits for the remote FFN output, and then resumes the next layer in the KV-cache pool. The weights pool hosts the corresponding

FFN modules and executes them using SGLang FusedMoE kernels. This structure keeps most existing SGLang operator implementations intact and model adaptation reusable while moving the dominant MoE weights out of the KV-cache pool. Inter-pool transport. We add a transport library based on NVSHMEM [27] for low-latency hidden-state transfer between pools. The transport interface is placed exactly at the proxy-FFN boundary: the KV-cache pool sends hidden states to the weights pool, and the weights pool sends FFN outputs back. Communication is issued asynchronously so that the layer-wise scheduler can overlap attention and FFN computation from diferent batches.

KV-cache virtualization. The KV-cache pool uses CUDA VMM APIs [28] to expose virtualized KV-cache space to attention operators. The runtime reserves virtual address ranges according to the planner output and maps physical pages as the allocator slow path. Existing SGLang attention kernels (backed by FlashAttention [10], FlashInfer [37], etc.) continue to operate over a paged KV-cache abstraction, while CrossPool tracks physical page allocation against the shared pool page budget. Active decode pages are kept until their requests finish; when the planned pool budget cannot admit a new request, admission control queues or rejects it.

Graph capture and persistent dispatch. CrossPool captures attention and FFN subgraphs separately during warmup and passes their graph handles to persistent kernels. Our current implementation captures batch sizes 1–4, which are typical for cold-model decode serving and cover the optimized path used in our experiments. The persistent kernels poll GPU-resident queues, dispatch captured graphs, launch inter-pool communication, and update batch state without returning to the host for every layer transition.

End-to-end integration. CrossPool focuses on decodeside memory colocation. Following Aegaeon [36], prefill phase runs on separate temporal-multiplexing engines. Decode phase uses the disaggregated KV-cache and weights pools, so our evaluation reports decode-side scalability, TBT, and output throughput.

## 5 Experiments

## 5.1 Experimental Setup

Workloads and models. We use Vicuna ShareGPT [3, 8] conversations as a balanced input/output workload for the decode-side TBT experiment and LongAlign [5, 40] as a long-context workload for the scalability experiment. Request arrivals follow a Poisson process with low RPS and token counts are calculated with each model’s tokenizer. We evaluate baselines and CrossPool on three MoE models colocation: Qwen3-30B-A3B, GLM-4.7-Flash, and DeepSeek V2-Lite. Accommodating weights of these 3 models requires ∼154 GB HBM.

Baselines. We compare CrossPool against (1) Static Partition: SGLang native static placement, which assigns each model a fixed GPU placement and uses static MIG partitioning when feasible; and (2) Chimera [38] (i.e., kvcached): elastic GPU memory pooling with kvcached which dynamically manages KV memory across models, but does not disaggregate KV-cache and FFN weights into separate pools. We run both of the baselines and CrossPool in prefill-decode disaggregation mode, and focus the comparison on the decode phase.

![](images/7c3a81d03e05331f7aafd768ae25b1d303e030a0b65f2785de5a176b7548ec7c.jpg)  
Figure 6. Maximum aggregate request rate estimated from sampled LongAlign context-length bins within each model’s nominal context window; vertical drops mark per-system capacity limits. Prompts are truncated to maximum context length of the two models.

Table 2. GPU placement on the five-A100 testbed.  
![](images/20f27487fba0c6a78ed7ce6d225c1e23d1d3b5802f2b05f3dfd96e5edde11c77.jpg)  
Q = Qwen3-30B-A3B, G = GLM-4.7-Flash, D = DeepSeek-V2-Lite  
KV = KV-cache, and W = FFN weights of Q + G + D.

Testbeds and placement. Our experiments use a five-A100 server (40 GB HBM per GPU with NVLINK) for decode-phase evaluation. Table 2 summarizes the GPU placement used by each system. These placements use the minimum GPU count needed to serve the three models and keep the same total GPU memory budget for model weights and KV-cache across systems. For Static Partition and kvcached, we enable DP attention for GLM-4.7-Flash and DeepSeek-V2-Lite, which adopt MLA, to avoid KV-cache replication.

Metrics. Because CrossPool primarily optimizes decodeside memory colocation, we report two metrics. First, we report the maximum aggregate request rate that a system can sustain as context length increases. For the scalability experiment, we estimate max RPS by sampling LongAlign context lengths and applying each system’s GPU placement and KV-cache budget; the estimate corresponds to the ofered rate before out-of-memory errors or fatal serving failures. Second, we report TBT (Time-Between-Tokens) as the primary decode latency metric. We finally report aggregate output throughput in an ablation study to isolate the impact of two mechanisms that reduce disaggregation overhead.

Static Partition CrossPool kvcached  
![](images/b09404425baf4898a595f7770116d6aadec3a6be53df87eb4738601b6a485434.jpg)  
Figure 7. Decode-side TBT on ShareGPT traces from 0.2 to 1.0 RPS per model.

## 5.2 Context-length Scalability

Fig. 6 evaluates whether CrossPool can serve bursty longcontext requests under the same five-GPU decode environment. As context length grows, each active request consumes more KV-cache, so a fixed per-model memory partition eventually reaches a capacity clif. We sample LongAlign requests within each non-empty long-context bin and estimate max RPS according to the GPU placement and KV-cache budget used by Static Partition, kvcached, and CrossPool. For DPattention configurations, the figure reports aggregate RPS summed across replicas; DP does not increase the maximum context length that any single replica can admit.

The vertical drops in Fig. 6 show where each placement no longer has enough KV-cache to admit the sampled context lengths. Static Partition and kvcached lose the ability to serve longer LongAlign bins once the per-model or perreplica KV capacity is exhausted. In contrast, CrossPool keeps a positive max RPS throughout the plotted supported range by exposing a larger shared KV-cache pool under the same hardware budget. This result demonstrates the capability CrossPool targets for cold serving: handling bursty long-context trafic without giving each model a large dedicated KV-cache partition.

## 5.3 Overall Performance

According to the context-length scalability analysis in §5.2, and our LongAlign serving runs, Static Partition and kvcached can encounter OOM or fatal serving failures on long-context requests even at low request rates. We therefore use Vicuna ShareGPT as a balanced input/output workload for the TBT comparison, where all systems can complete the same request-rate sweep. Fig. 7 compares the ShareGPT TBT performance of Static Partition, kvcached, and CrossPool. We sweep the request rate from 0.2 to 1.0 RPS and report P95 and P99 TBT for the three evaluated models. This experiment evaluates whether CrossPool preserves decode latency while colocating the three cold MoE models through shared KV-cache and weight pools.

Table 3. Ablation study of CrossPool techniques on ShareGPT, reporting aggregate decode-phase output throughput when serving three cold MoE models at 0.5 RPS per model.  
![](images/a6c1d5f61d7c48a8bee3ce0e8be57b955bafe6a54f6c9e6ff77de5ac4fde6999.jpg)

Across the ShareGPT sweep, CrossPool remains competitive with kvcached while providing the pooling capacity shown in Fig. 6. At 0.8 RPS, CrossPool reduces P99 TBT over kvcached by 7<sup>.</sup>6× for Qwen3-30B-A3B, 10<sup>.</sup>4× for DeepSeek-V2-Lite, and 7<sup>.</sup>3× for GLM-4.7-Flash. At 1.0 RPS, the corresponding P99 reductions are 2<sup>.</sup>1×, 5<sup>.</sup>0×, and 2<sup>.</sup>2×.

Kvcached shows higher tail TBT mainly because elastic colocation allows uncoordinated multi-model concurrency, which leads to SM, memory-bandwidth, and KV-cache contention during decode. Its shared weight/KV memory pool and limited per-replica KV capacity under DP attention further increase memory pressure under bursty traffic. CrossPool separates the KV-cache pool from the FFNweight pool and uses a planned shared KV-cache budget, making resource usage more predictable. Static Partition has the lowest latency because it keeps each model in a fixed isolated placement, but this placement does not provide the long-context pooling ability evaluated in Fig. 6. CrossPool instead targets the middle ground: under the same hardware budget, it supports larger shared KV-cache capacity while maintaining competitive token-generation latency.

## 5.4 Ablation Study

Table 3 isolates the throughput impact of the two mechanisms (§3.2 and §3.3) that reduce disaggregation overhead. The first row disables both mechanisms and serves as the unoptimized disaggregated baseline, where attention and FFN execution are serialized across the pool boundary and layer-level control remains on the host-side path. Enabling persistent kernels and control lowering alone improves aggregate decode output throughput from 55.42 to 77.86 token/s, a 1<sup>.</sup>41× gain, by reducing frequent host-side dispatch and inter-pool communication control. Enabling the layer wise pipeline scheduler alone improves throughput to 60.83 token/s, a 1<sup>.</sup>10× gain, by overlapping attention and FFN execution across in-flight batches.

Combining both mechanisms raises throughput to 111.40 token/s, a 2<sup>.</sup>01× gain over the unoptimized disaggregated baseline. This shows that the two mechanisms are complementary: persistent kernels reduce the control overhead on the layer-wise path, while the scheduler keeps the attention and FFN pools busy once that path can be driven eficiently.

## 6 Discussion

CrossPool is designed for serving multiple cold MoE models, rather than generic GPU sharing. Its main design choice is to separate two memory objects with diferent lifetimes: FFN weights are stable and tied to the model, whereas KVcache is transient and tied to demand. CrossPool therefore consolidates the dominant MoE FFN weights in the weights pool and keeps attention and other non-FFN modules in the KV-cache pool, where attention can access KV-cache locally. The pool boundary exchanges hidden states rather than KV-cache tensors, limiting cross-pool trafic to data whose size is bounded by batch tokens and hidden dimension. The layer-wise scheduler and persistent kernels then reduce the exposed cost of this boundary by overlapping attention and FFN execution across in-flight batches and keeping frequent dispatch and communication control on GPUs.

Limitations and future directions. First, communication overhead is reduced but not fully hidden. The current scheduler overlaps attention and FFN computation across batches, but A-to-F (attention to FFN) hidden-state transfer from the KV-cache pool to the weights pool, and F-to-A (FFN to attention) result transfer back to the KV-cache pool, remain on the critical path. A future implementation could use a finer pipeline that explicitly stages attention computation, A-to-F communication, FFN computation, and F-to-A communication, so that communication stages can be overlapped with adjacent compute stages more aggressively.

Second, heterogeneous model compute times can create pipeline imbalance. Diferent MoE models can have diferent attention and FFN execution times per layer. When a short-running model is pipelined with a long-running model, the shorter stage can wait for the longer stage, aligning its observed decode time with the slower model and reducing the benefit of colocation. This limitation can be mitigated at cluster placement time by grouping cold models with similar attention/FFN compute profiles before assigning them to the same disaggregated pools.

## 7 Related Work

Multi-LLM serving. MuxServe [17] and Weaver [19] improve GPU sharing via spatial multiplexing. Chimera [38] provides elastic memory management with kvcached. Aegaeon [36] uses GPU pooling and temporal multiplexing for skewed model popularity. These systems motivate coldmodel colocation, but they do not separate stable model weights from transient KV-cache as two GPU memory pools. As a result, the KV-cache capacity available to an active cold model is still constrained by the placement and footprint of colocated weights. CrossPool instead disaggregates weights and KV-cache to address the algorithm-system mismatch of KV-head-limited attention under cold, low-concurrency workloads and thus improve shared KV-cache capacity for requests.

KV-cache management. vLLM [23] uses PagedAttention, and SGLang [39] uses RadixAttention, providing eficient KV-cache management in a serving engine. Other systems expand, compress, stream, or reuse KV-cache through external storage, host memory, or selective prefetching, including Mooncake [33], LMCache [7], CacheGen [26], and InfiniGen [24]. These techniques reduce KV-cache pressure for long-context serving, but they do not make GPU KVcache a shared resource across multiple cold MoE models. CrossPool keeps the primary inference path on GPUs and uses virtualized paging to enforce a planned page budget for the shared KV-cache pool.

Attention-MoE disaggregation. MegaScale-Infer [41] and Step-3 [21] disaggregate attention and FFN computation to scale MoE inference, improve throughput, and support heterogeneous multi-node deployment. CrossPool uses a similar disaggregation strategy, but aiming to enlarge shared KV-cache pool for multiple cold MoE models via minimizing number of attention replicas. CrossPool typically deploys KV-cache pool and weights pool in one or two nodes, utilizing low-latency interconnection for cold-model serving.

## 8 Conclusion

Aggregate cold MoE serving exposes an algorithm-system mismatch. Model weights are large and stable, while KV cache is transient and unevenly used across cold models. Existing multi-LLM systems improve GPU sharing but still store static weights and dynamic KV-cache in one monolithic pool, which reduces both KV-cache usable space and per-GPU capacity when serving recent KV-head-limited models, leading to ineficient KV-cache GPU memory pooling and weak long-context support.

This paper presents CrossPool, a multi-LLM serving engine that splits FFN weights and KV-cache into disaggregated GPU memory pools while keeping attention local to KV-cache. CrossPool uses a trace-driven KV-cache planner and virtualized paging to handle heterogeneous KV-cache demand, a layer-wise pipeline scheduler to overlap attention and FFN across pools, and persistent kernels with control lowering to cut host dispatch overhead. Our evaluation demonstrates context scalability and competitive performance of CrossPool, comparing with current state-ofthe-art systems.

## References

[1] Joshua Ainslie, James Lee-Thorp, Michiel de Jong, Yury Zemlyanskiy, Federico Lebrón, and Sumit Sanghai. 2023. GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints. In Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing, EMNLP 2023, Singapore, December 6-10, 2023, Houda Bouamor, Juan Pino, and Kalika Bali (Eds.). Association for Computational Linguistics, 4895–4901. doi:10.18653/V1/2023.EMNLP-MAIN.298

[2] Alibaba Cloud. 2026. Alibaba Cloud Model Studio. htps://modelstudio. alibabacloud.com. Accessed: 2026-05-08.

[3] anon8231489123. 2023. ShareGPT Vicuna unfiltered. htps://huggingface.co/datasets/anon8231489123/ShareGPT\_ Vicuna\_unfiltered. Accessed: 2026-05-08.

[4] Anthropic. 2026. Claude Code. htps://claude.com/product/claudecode. Accessed: 2026-05-08.

[5] Yushi Bai, Xin Lv, Jiajie Zhang, Yuze He, Ji Qi, Lei Hou, Jie Tang, Yuxiao Dong, and Juanzi Li. 2024. LongAlign: A Recipe for Long Context Alignment of Large Language Models. In EMNLP (Findings) (Findings of ACL). Association for Computational Linguistics, 1376–1395.

[6] ByteDance. 2026. Volcano Engine. htps://www.volcengine.com. Accessed: 2026-05-08.

[7] Yihua Cheng, Yuhan Liu, Jiayi Yao, Yuwei An, Xiaokun Chen, Shaoting Feng, Yuyang Huang, Samuel Shen, Kuntai Du, and Junchen Jiang. 2025. LMCache: An Eficient KV Cache Layer for Enterprise-Scale LLM Inference. CoRR abs/2510.09665 (2025).

[8] Wei-Lin Chiang, Lianmin Zheng, Ying Sheng, Tianle Li, et al. 2023. Vicuna: An Open-Source Chatbot Impressing GPT-4 with 90%\* Chat-GPT Quality. htps://lmsys.org/blog/2023-03-30-vicuna/. Accessed: 2026-05-08.

[9] Damai Dai, Chengqi Deng, Chenggang Zhao, R. X. Xu, Huazuo Gao, Deli Chen, Jiashi Li, Wangding Zeng, Xingkai Yu, Y. Wu, Zhenda Xie, Y. K. Li, Panpan Huang, Fuli Luo, Chong Ruan, Zhifang Sui, and Wenfeng Liang. 2024. DeepSeekMoE: Towards Ultimate Expert Specialization in Mixture-of-Experts Language Models. In ACL (1). Association for Computational Linguistics, 1280–1297.

[10] Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, and Christopher Ré. 2022. FlashAttention: Fast and Memory-Eficient Exact Attention with IO-Awareness. In NeurIPS.

[11] DeepInfra. 2026. DeepInfra. htps://deepinfra.com. Accessed: 2026- 05-08.

[12] DeepSeek-AI. 2024. DeepSeek-V2: A Strong, Economical, and Eficient Mixture-of-Experts Language Model. CoRR abs/2405.04434 (2024). arXiv:2405.04434 doi:10.48550/ARXIV.2405.04434

[13] DeepSeek-AI. 2024. DeepSeek-V3 Technical Report. CoRR abs/2412.19437 (2024).

[14] DeepSeek-AI. 2026. DeepSeek. htps://chat.deepseek.com. Accessed: 2026-05-08.

[15] DeepSeek-AI. 2026. DeepSeek-V4: Towards Highly Eficient Million-Token Context Intelligence. htps://huggingface.co/deepseek-ai/ DeepSeek-V4-Pro/blob/main/DeepSeek\_V4.pdf. Technical Report.

[16] Hui Dong and Marvin K Nakayama. 2018. A tutorial on quantile estimation via Monte Carlo. In International Conference on Monte Carlo and Quasi-Monte Carlo Methods in Scientific Computing. Springer, 3– 30.

[17] Jiangfei Duan, Runyu Lu, Haojie Duanmu, Xiuhong Li, Xingcheng Zhang, Dahua Lin, Ion Stoica, and Hao Zhang. 2024. MuxServe: Flexible Spatial-Temporal Multiplexing for Multiple LLM Serving. In ICML (Proceedings of Machine Learning Research). PMLR / OpenReview.net, 11905–11917.

[18] William Fedus, Barret Zoph, and Noam Shazeer. 2022. Switch Transformers: Scaling to Trillion Parameter Models with Simple and Eficient Sparsity. J. Mach. Learn. Res. 23 (2022), 120:1–120:39. htps: //jmlr.org/papers/v23/21-0998.html

[19] Shiwei Gao, Qing Wang, Shaoxun Zeng, Youyou Lu, and Jiwu Shu. 2025. Weaver: Eficient Multi-LLM Serving with Attention Ofloading. In USENIX ATC. USENIX Association, 587–595.

[20] Google. 2026. Gemini. htps://gemini.google.com. Accessed: 2026-05- 08.

[21] StepFun Inc. 2025. Step-3 is Large yet Afordable: Model-system Co design for Cost-efective Decoding. CoRR abs/2507.19427 (2025).

[22] Albert Q. Jiang, Alexandre Sablayrolles, Antoine Roux, Arthur Mensch, Blanche Savary, Chris Bamford, Devendra Singh Chaplot, Diego de Las Casas, Emma Bou Hanna, Florian Bressand, Gianna Lengyel, Guil laume Bour, Guillaume Lample, Lélio Renard Lavaud, Lucile Saulnier, Marie-Anne Lachaux, Pierre Stock, Sandeep Subramanian, Sophia Yang, Szymon Antoniak, Teven Le Scao, Théophile Gervet, Thibaut Lavril, Thomas Wang, Timothée Lacroix, and William El Sayed. 2024. Mixtral of Experts. CoRR abs/2401.04088 (2024). arXiv:2401.04088 doi:10.48550/ARXIV.2401.04088

[23] Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica. 2023. Eficient Memory Management for Large Language Model Serving with PagedAttention. In SOSP. ACM, 611–626.

[24] Wonbeom Lee, Jungi Lee, Junghwan Seo, and Jaewoong Sim. 2024. InfiniGen: Eficient Generative Inference of Large Language Models with Dynamic KV Cache Management. In OSDI. USENIX Association, 155–172.

[25] Dmitry Lepikhin, HyoukJoong Lee, Yuanzhong Xu, Dehao Chen, Orhan Firat, Yanping Huang, Maxim Krikun, Noam Shazeer, and Zhifeng Chen. 2021. GShard: Scaling Giant Models with Conditional Computation and Automatic Sharding. In 9th International Conference on Learning Representations, ICLR 2021, Virtual Event, Austria, May 3-7, 2021. OpenReview.net. htps://openreview.net/forum?id= qrwe7XHTmYb

[26] Yuhan Liu, Hanchen Li, Yihua Cheng, Siddhant Ray, Yuyang Huang, Qizheng Zhang, Kuntai Du, Jiayi Yao, Shan Lu, Ganesh Ananthanarayanan, Michael Maire, Henry Hofmann, Ari Holtzman, and Junchen Jiang. 2024. CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving. In SIGCOMM. ACM, 38–56.

[27] NVIDIA. 2025. NVSHMEM: GPU Programming Interface for Scalable Communication. htps://docs.nvidia.com/nvshmem. Accessed: 2026- 05-08.

[28] NVIDIA. 2026. CUDA Virtual Memory Management (VMM). htps:// docs.nvidia.com/cuda/cuda-driver-api/group\_\_CUDA\_\_VA.html. Ac cessed: 2026-05-08.

[29] OpenAI. 2026. ChatGPT. htps://chatgpt.com. Accessed: 2026-05-08.

[30] OpenAI. 2026. Codex. htps://openai.com/codex. Accessed: 2026-05-08.

[31] OpenClaw Contributors. 2026. OpenClaw. htps://openclaw.ai. Accessed: 2026-05-08.

[32] OpenRouter. 2026. OpenRouter. htps://openrouter.ai. Accessed: 2026-05-08.

[33] Ruoyu Qin, Zheming Li, Weiran He, Jialei Cui, Feng Ren, Mingxing Zhang, Yongwei Wu, Weimin Zheng, and Xinran Xu. 2025. Mooncake: Trading More Storage for Less Computation - A KVCache-centric Architecture for Serving LLM Chatbot. In FAST. USENIX Association, 155–170.

[34] Noam Shazeer. 2019. Fast Transformer Decoding: One Write-Head is All You Need. CoRR abs/1911.02150 (2019).

[35] Qwen Team. 2025. Qwen3 Technical Report. CoRR abs/2505.09388 (2025).

[36] Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, Ennan Zhai, Xuanzhe Liu, Xin Jin, and Jingren Zhou. 2025. Aegaeon: Efective GPU Pooling for Concurrent LLM Serving on the Market. In SOSP. ACM, 1030–1045.

[37] Zihao Ye, Lequn Chen, Ruihang Lai, Wuwei Lin, Yineng Zhang, Stephanie Wang, Tianqi Chen, Baris Kasikci, Vinod Grover, Arvind

Krishnamurthy, and Luis Ceze. 2025. FlashInfer: Eficient and Customizable Attention Engine for LLM Inference Serving. In MLSys. OpenReview.net/mlsys.org.

[38] Shan Yu, Yifan Qiao, Mingyuan Ma, Yangmin Li, Shuo Yang, Xinyuan Tong, Yang Wang, Zhiqiang Xie, Yuwei An, Shiyi Cao, Ke Bao, Deepak Vij, Xiaoning Ding, Yichen Wang, Qingda Lu, Zhong Wang, Gao Gao, Harry Xu, Junyi Shu, Jiarong Xing, and Ying Sheng. 2026. Chimera: Cost-Eficient Multi-LLM Serving via GPU Memory Ballooning. In USENIX OSDI. USENIX Association.

[39] Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jef Huang, Cody Hao Yu, Shiyi Cao, Christos Kozyrakis, Ion Stoica, Joseph E. Gonzalez, Clark W. Barrett, and Ying Sheng. 2024. SGLang: Efficient Execution of Structured Language Model Programs. In NeurIPS.

[40] Zhipu AI and Tsinghua University. 2024. LongAlign-10k. htps:// huggingface.co/datasets/zai-org/LongAlign-10k.

[41] Ruidong Zhu, Ziheng Jiang, Chao Jin, Peng Wu, Cesar A. Stuardo, Dongyang Wang, Xinlei Zhang, Huaping Zhou, Haoran Wei, Yang Cheng, Jianzhe Xiao, Xinyi Zhang, Lingjun Liu, Haibin Lin, Li-Wen Chang, Jianxi Ye, Xiao Yu, Xuanzhe Liu, Xin Jin, and Xin Liu. 2025. MegaScale-Infer: Eficient Mixture-of-Experts Model Serving with Disaggregated Expert Parallelism. In SIGCOMM. ACM, 592–608.