---
type: paper
name: LMCache
full_title: "LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference"
authors: [Yuhan Liu, Jiayi Yao, Yihua Cheng, Yuwei An, Xiaokun Chen, Shaoting Feng, Yuyang Huang, Samuel Shen, Rui Zhang, Kuntai Du, Junchen Jiang]
venue: arXiv
year: 2025
tags: [llm-inference, kv-cache, prefix-caching, disaggregation, cache-layer, production-systems, area/ai-infra]
source_pdf: "[[arxiv25-liu-lmcache.pdf]]"
source_md: "[[arxiv25-liu-lmcache]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# LMCache：用于企业级 LLM 推理的高效 KV 缓存层（arXiv 2025）

> **原题**：LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference

> **一句话总结**：LMCache 的关键判断是 [[KV-Cache]] 已经从单请求 GPU 内存优化变成跨请求、跨引擎、跨存储层的共享数据对象；它用大 chunk 搬运、compute-I/O overlap、connector API 和 controller API 把 [[Prefix-Caching]] 与 [[Disaggregation]] 做成生产级 cache layer，在 vLLM 上报告最高 15x 吞吐提升、1.9-8.1x TTFT 降低，并从企业部署里发现 remote KV loading 有时比重新 prefill 更快、context truncation 会把 prefix hit ratio 从约 85% 打到约 45%。

## 问题与动机

传统 LLM serving 把 [[KV-Cache]] 视为一次请求内部的 GPU 内存状态：prefill 生成 KV，decode 复用 KV，query 完成后这份状态基本结束生命周期。LMCache 指出的变化是，长 context、RAG、多轮会话、agent workflow 和 [[Prefill-Decode-Disaggregation]] 让 KV cache 的生命周期跨过了单次 query，也跨过了单个 inference engine 实例。

论文把需求拆成两个生产场景。第一个是 cross-query context caching：多个 query 共享长文档、system prompt、conversation history 或 RAG context 时，保存已生成的 KV 可以避免重复 prefill。第二个是 PD disaggregation：prefill GPU 负责吞吐型大输入，decode GPU 负责延迟敏感的 token generation，中间必须把 KV 从 prefiller 传到 decoder。

已有 [[vLLM]]、[[SGLang]] 这类 engine 已经有 GPU prefix cache 或 CPU offload，但论文认为它们不是一个独立的 KV cache layer：缺少高效跨层搬运，缺少跨节点/跨后端的 storage abstraction，也缺少给 scheduler/router/operator 使用的 lookup、pin、move、compress 等管理语义。LMCache 的目标因此不是替代 inference engine，而是在 engine 和 storage/network backend 之间增加一层可复用的 KV movement 与 control substrate。

这篇论文的系统味道很重：贡献并不只是一组优化 kernel，而是把「KV cache 是 inference engine 内部副产物」改成「KV cache 是可以被调度、迁移、持久化、压缩、路由感知的 first-class data structure」。这也是它和很多只做单点 prefix caching 或 KV compression 工作的主要边界。

## 关键观察 / 隐含假设

- **观察 1：用户存储的 KV cache 总量已经远超 GPU memory，且 non-GPU 部分仍在被复用。** 论文的 real-world usage statistics 显示，5 周内 stored KV cache delta 从约 10T bytes 增长到超过 30T bytes，主要增长来自 non-GPU storage；top users 的 reused-token / stored-token 指标也在增长，超过 19% 的用户对 stored token 的平均复用超过 1.5 次。
  - **依赖假设**：自愿开启 tracker 的 LMCache 用户代表了足够典型的 enterprise serving workload；这些用户的增长趋势不是短期 adoption artifact。
  - **可能失效场景**：如果 workload 以一次性短 prompt、低重复查询或严格 per-user isolation 为主，non-GPU KV reuse 的收益会明显下降。若未来模型 prefill 成本下降速度快于 storage/network loading 成本下降，reuse 的 crossover point 也会移动。

- **观察 2：paged KV memory 的小粒度布局适合 GPU 内存管理，却不适合 I/O。** [[PagedAttention]] 让 engine 以 16-64KB 左右的小 page 管理 KV，提高 batching 与显存利用率；但 KV offload / transfer 若沿用 page-by-page 搬运，会触发大量小 I/O，难以打满 PCIe/NVMe/network 带宽。论文引用的 transfer measurement 显示，RCCL/UCCL 类链路需要 MB 级甚至 16MB 左右 message 才能接近饱和，PCIe 也需要 1-2MB 才能达到理论带宽的 75-80%。
  - **依赖假设**：KV cache 的主要瓶颈是 data movement overhead，而不是 token hashing、scheduler contention、storage metadata、controller consistency 或 compression/decompression。
  - **可能失效场景**：当 KV block 很小、cache hit token 很短、网络带宽低或 backend tail latency 高时，聚合成大 chunk 的收益可能被等待时间和额外 buffering 吃掉。

- **观察 3：inference engine 和模型生态变化太快，KV cache layer 不能硬绑某个 engine 内部 layout。** 论文提到 2025 年平均每周 15-20 个 open-weight model 发布，engine 为新模型、新 attention kernel 和新硬件持续改变 KV layout。直接依赖内部 layout 的 cache layer 会变成长期维护负担。
  - **依赖假设**：一个稳定的 connector boundary 可以覆盖 scheduler、model runner、attention hook 和 memory address metadata 的主要需求，同时不把 engine 内部复杂度泄漏给 storage layer。
  - **可能失效场景**：如果新 attention 机制改变了 KV 的语义而不只是 layout，例如 selective token dropping、state-space hybrid、跨层共享 KV 或模型特定压缩，connector API 可能需要重新抽象。

- **假设 1：生产 workload 有足够多「动态可复用 context」，不只固定 system prompt。**
  - **证据强度**：中。论文给出 Company F/G trace、50% production hit rate、context truncation 前后 85% 到 45% 的 hit ratio 变化，但企业名称和 trace 细节匿名，外部复现实验不容易。

- **假设 2：把 KV cache 作为跨节点共享对象不会引入不可接受的 correctness、privacy、isolation 和 operability 成本。**
  - **证据强度**：弱到中。论文讨论 pin、clear、move、compress 这类 API，但没有系统评估多租户隔离、cache poisoning、权限边界、故障恢复、stale metadata 或 observability。

## 核心方法

LMCache 位于 [[vLLM]] / [[SGLang]] 等 inference engine 与 heterogeneous backend 之间。底层 backend 可以是 CPU memory、local SSD、remote disk、Redis、Mooncake、InfiniStore、S3、NIXL 等；传输介质可以是 PCIe、Ethernet、RDMA、NVLink。它把 engine 内部的 KV page 抽出来，经由 KV connector、token processor、storage manager、transfer channel 和 cache controller 管理。

第一组设计回应观察 2：**把小 page I/O 改成大 chunk I/O**。LMCache 不直接按 engine 的小 page 存取 KV，而是用 streaming GPU buffer 和 CUDA kernel 把 scattered paged memory pack 成更大的 configurable chunk，默认约 256 tokens per chunk。store 时先把分散 page 聚合成连续 buffer，再用 DMA 写到 CPU/storage；load 时反向把 chunk 取回 buffer，再 split 到 engine 的 paged memory。这样牺牲了一层 pack/unpack 和 buffering，换取更高有效带宽。

第二组设计是 **compute-I/O overlap**。LMCache 用独立 CUDA stream 做 layer-wise pipelining：当前 layer 计算时预取下一层 KV，或在 layer 结束后异步 store 新生成的 KV。它还利用 scheduler admit 到真正执行之间的排队间隙，把 remote/disk KV 预取到 CPU 或 GPU。这个设计回应的不是单纯带宽问题，而是 serving 系统里 request queue 本身提供了可隐藏 I/O 的时间窗口。

第三组设计是 **minimum data copy 与 dynamic offloading**。Zero-copy 部分用 reference counter 避免同一份 KV 在多个 destination 或 concurrent transfer 间被重复复制。Dynamic offloading 则只复制 engine GPU free page 区间的一部分：duplication window 小可以省 CPU memory，但会增加 query 分配 page 时等待 offload 完成的概率；window 大则降低 stall 风险，但复制更多冷 KV。这里的核心取舍是内存浪费 vs allocation stall。

第四组设计是 **standardized KV connector**。在 scheduler 侧，`get_num_new_matched_tokens` 把 LMCache backend 命中的 token 数交给 engine，使命中 token 像普通 prefix-cached token 一样影响调度；`update_state_after_alloc` 和 `build_connector_meta` 准备外部 KV load/store metadata。在 model runner 侧，`start_load_kv`、`wait_load_kv`、`start_store_kv`、`wait_store_kv` 提供执行前后和 layer 前后的 hook。这个 boundary 把 LMCache 与快速变化的 engine layout 分开，也让 out-of-tree connector 可以跟着 vLLM 生态演进。

第五组设计是 **controller API**。LMCache 不只搬运 KV，还让 KV 变成可被上层系统查询和控制的对象。内部 API 如 `batched_admit` / `batched_evict` 维护全局 token-location metadata，`batched_p2p_lookup` 支持 peer cache sharing；外部 API 如 `lookup`、`move`、`clear`、`pin`、`compress` / `decompress` 给 router、operator 和 application 使用。它直接支持 KV-aware routing、scale-down migration、explicit document pinning、cache cleanup 等生产动作。

## 设计取舍

- **大 chunk 搬运 vs 细粒度调度**：大 chunk 能显著提升带宽利用率，但会降低按 token/page 精细选择的灵活性。短 prefix 或低 hit ratio workload 可能承担额外 pack/unpack 和等待成本。

- **CPU/remote offload vs 重新 prefill**：offload 扩大 cache capacity，并在长 context 上节省 prefill；但 remote loading 受带宽和 tail latency 限制。论文自己的 sensitivity study 显示，在 32Gbps 网络下，只有当 context length 超过约 256K tokens 时 loading 才优于 naive prefill；64/128Gbps 下结论更有利。

- **统一 connector API vs engine 深度特化**：标准 API 降低集成维护成本，也让 LMCache 可被 vLLM production stack、Dynamo、llm-d、KServe 等复用；代价是新 attention 语义或特殊模型 layout 可能不容易表达，论文也承认早期为了工业稳定性牺牲了学术用户常要的 attention modification flexibility。

- **集中 controller metadata vs 分布式 cache control**：centralized manager 简化 lookup、move、pin 和 routing，但论文没有充分讨论 controller failure、metadata staleness、split-brain、跨租户权限、热点 token metadata 扩展性。

- **Python 快速演进 vs 系统语言极致性能**：论文明确说团队继续使用 Python 以获得生态和贡献速度，并用 careful optimization 隐藏 runtime overhead。这很符合开源基础设施扩张期，但长期是否能承受更严格的 latency SLO 还需要 workload 级证据。

## 实验与结果

- **CPU offload / multi-round document QA**：在 8xH100 单机上，LMCache + vLLM 对比 basic vLLM、vLLM native CPU offloading 和两个商业 endpoint，在五个模型上报告 1.9-8.1x 更低 TTFT、2.3-14x 更高 query processing rate；Qwen3-Coder-480B 上部分 baseline 无法运行或不支持。

- **Real trace**：使用 Company F/G 的 input/output token distribution，并把数天 trace stretch 到 1 小时内运行。相对 basic vLLM GPU prefix caching，LMCache 在五个模型高 QPS 下报告至少 3.7-6.8x 更低 TTFT、19-58% 更低 ITL。

- **Centralized remote storage**：在 15Gbps central storage backend + TriviaQA / LongBench workload 下，LMCache 相比 basic vLLM 在相同 TTFT 下达到 1.3-3x throughput improvement。论文同时指出 remote loading 可能比 CPU loading 慢，在短 context 或小模型上甚至慢于重新 prefill。

- **PD disaggregation**：对比 vLLM native PD disaggregation，LMCache 在 8K input / 200 output 的 random workload 上降低 mean TTFT 1.53-1.84x、mean ITL 1.12-1.66x；tail TTFT CDF 也明显更好。原因是 vLLM native PD 按 scattered page 传输，LMCache 用 chunk buffer 提高传输效率。

- **Component analysis**：CPU loading bandwidth 上，LMCache 达到 400Gbps，而 vLLM native CPU offloading 为 88Gbps；request asynchronization 通过 overlap loading 和 inference 把端到端延迟降低 1.46x；PD breakdown 显示主要收益来自减少 transmission latency，prefill/decode compute 本身相同。

- **Sensitivity**：B200 + varying bandwidth 下，32Gbps 时 KV loading 只有在 input length 超过约 256K tokens 才优于 prefill；64/128Gbps 时 loading 在所有测量 context length 上优于 prefill。这是论文里最重要的边界结果之一，因为它否定了「cache hit 一定值得 load」的简单策略。

- **SGLang integration**：在 Qwen3-32B、2xH100 TP=2 上，LMCache + SGLang CPU offload 相比 plain SGLang 有更高 throughput、更低 mean TTFT 和 end-to-end latency；相比 SGLang native CPU offloading 性能接近，但 LMCache 提供分布式层级 backend。

- **Production lessons**：Company C remote object store loading 比 full prefill 低 22-32% TTFT；Company F context truncation 使 prefix hit ratio 从约 85% 降到约 45%；Company G 观察到约 50% production prefix hit rate；社区扩展到 8 个新 storage backend、4 类 processor、2 个 inference engine。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Chunked CPU KV transfer improves loading bandwidth | 400Gbps vs vLLM CPU offloading 88Gbps (§8.5, Table 5) | component measurement, not end-to-end throughput | high |
| CPU offload improves document-QA TTFT and throughput | TTFT 1.9–8.1× lower; query rate 2.3–14× higher (§8.2, Fig.8) | 8×H100, 10K-token documents, 500GB CPU cache | high |
| Remote backend helps in centralized-storage evaluation | same-TTFT throughput 1.3–3× higher (§8.4, Fig.11) | 15Gbps CPU-memory server, TriviaQA/LongBench | high |
| Chunk transfer improves PD-disaggregation latency | TTFT 1.53–1.84× lower; ITL 1.12–1.66× lower (§8.5, Fig.12) | native vLLM PD, 8K input/200 output, NVLink | high |
| Loading vs recomputation depends on bandwidth/context | 32Gbps wins only beyond 256K tokens; 64/128Gbps win at measured lengths (§8.7, Fig.15) | B200 sensitivity experiment | high |

## 批判性分析

### 论证链条

论文的主链条大体闭合：production telemetry 说明 KV cache 正在走出 GPU memory；paged KV layout 说明 naive offload/transfer 的 I/O 粒度不合适；chunking、overlap、connector 和 controller 共同把 KV cache 从 engine 内部状态提升成系统对象；实验再在 CPU offload、remote storage、PD disaggregation 三个场景中验证收益。

最强的部分是 observation 与 design 的对应关系非常直接。小 page 无法打满带宽，因此聚合成 chunk；engine layout 快速变化，因此 connector；router/operator 需要 cache-aware 决策，因此 controller API。这种链条比单纯展示 15x 数字更可信。

薄弱处在于「enterprise-scale」和「production-ready」的外推。论文确实有企业部署经验，但公开实验仍主要由作者控制，真实 trace 是匿名且经过 stretch 的，baseline 的商业系统是黑盒，生产故障、成本、隔离、运维复杂度没有量化。它证明了 LMCache 可以在若干重要场景中显著加速，但没有完全证明它已经覆盖 enterprise cache layer 的所有风险。

### 假设压力测试

LMCache 对 **高重复长 context** 非常友好，对短 prompt、低重复、强隐私隔离或 highly personalized context 的 workload 不一定收益大。特别是 token-level hit ratio 不是唯一变量：hit token 的连续性、load path latency、backend tail、cache admission policy 和 queueing delay 都会决定是否值得 load。

硬件方面，论文结论对 network/storage 带宽很敏感。32Gbps 下 256K tokens 的 crossover point 说明，在普通以太网或拥塞网络里 remote KV loading 可能不是默认好选择；到 64/128Gbps、NVLink、RDMA 或更快 object store 时，结论明显有利。也就是说 LMCache 更像一个需要 adaptive policy 的 substrate，而不是固定 always-load 的策略。

模型方面，论文覆盖 Llama、Qwen、Sao10K 和 Qwen3-Coder-480B 等模型，但未来如果模型使用 sliding-window attention、MLA、speculative decoding、多模态 cross-attention 或压缩 KV 表示，KV 的结构和可复用性会改变。Connector API 是正确方向，但论文没有证明它足以覆盖这些语义变化。

部署方面，KV cache 跨请求共享天然涉及 tenant isolation 和 data governance。KV 不是原文 token，但它可能携带 prompt 信息；论文没有讨论 cache encryption、per-tenant namespace、access control、secure deletion 或审计。这是从 research system 走向 enterprise substrate 时不可绕过的缺口。

### 实验可信度

实验覆盖了 CPU offload、remote central storage、PD disaggregation、real-trace replay、component breakdown 和 SGLang integration，范围比许多 KV cache 论文更完整。关键 ablation 也能支撑核心设计：400Gbps vs 88Gbps loading bandwidth 直接说明 chunk-level transfer 的价值；1.46x asynchronous compute improvement 说明 overlap 不只是实现细节；sensitivity study 明确给出 remote loading 的边界。

但 baseline 公平性仍有几个不确定点。Commercial Option #1/#2 是黑盒，作者只能假设其内部是否支持 secondary storage；vLLM native CPU offloading 使用的是 v0.11.0，而主 vLLM baseline 是 v0.10.2，版本差异可能带来 confounder；真实 trace 被 stretch 到一小时，可能改变 burstiness、cache residency 和 eviction 压力。

此外，实验主要报告 TTFT、ITL、throughput 和 component latency，较少报告 memory overhead、CPU utilization、controller overhead、backend cost、failure recovery time、cache metadata size、P99/P999 under contention、multi-tenant interference。这些指标对生产 cache layer 同样关键。

### 系统性缺陷

论文没有充分讨论 consistency 与 failure model。例如 controller metadata 说某 token chunk 在某 instance/device 上，但该 worker 已重启、backend 写入失败或 move 进行到一半时，上层 router 如何避免错误路由？`clear`、`move`、`pin`、`compress` 与正在执行的 request 并发时如何定义原子性？这些都不是性能优化可以自动解决的问题。

动态 offloading 的 stall/duplication tradeoff 被描述得很好，但缺少 policy evaluation。实际系统需要根据 arrival rate、prompt length distribution、GPU memory pressure、CPU memory pressure 和 backend latency 调整 duplication window；论文没有展示自动调参或错误配置下的退化行为。

另一个缺口是 cache admission / eviction policy。论文重点在 movement substrate，但 hit ratio、capacity、fairness 和 isolation 很大程度由 admission/eviction 决定。生产中若高频 tenant 或长 context 占满 CPU/remote cache，其他 tenant 的收益和成本如何分配？论文未讨论。

最后，LMCache 让 KV cache 成为一个更强的系统抽象，也带来更强的运维表面积：backend driver、connector version、engine version、model layout、network transport、controller state 都可能成为故障点。论文从 adoption 角度说明社区扩展很快，但没有给出 compatibility test matrix、rolling upgrade strategy 或 observability design。

## 局限与后续工作

- **局限 1：production evidence 有价值但不可完全复现。** 企业 trace、hit ratio、remote storage backend、commercial baseline 都带匿名或黑盒成分，外部读者很难判断结果对自己 workload 的迁移性。

- **局限 2：adaptive policy 仍是开放问题。** 论文已经证明低带宽/短 context 下 loading 可能慢于 prefill，但 LMCache 本身更像 substrate；何时 load、prefetch、evict、compress、move 还需要 workload-aware policy。

- **局限 3：多租户安全与 correctness 讨论不足。** 跨请求、跨节点、跨 backend 共享 KV cache 需要 namespace、权限、加密、stale metadata 处理和故障恢复语义，论文没有系统评估。

- **局限 4：controller scalability 未充分量化。** 论文展示 controller API，但没有测 metadata volume、lookup latency、controller bottleneck、worker churn、large-cluster failure 情况。

- **Future work 1：建立 cache-vs-prefill 自适应决策模型。** 输入 context length、model size、current queue delay、backend bandwidth/tail latency、expected reuse 和 GPU price，预测每个 request 是否 load/prefetch/recompute，并用真实 trace 验证 TTFT、ITL、cost 的 Pareto frontier。

- **Future work 2：定义 KV cache sharing 的安全语义。** 设计 per-tenant KV namespace、capability-based lookup、encrypted backend、secure clear，并测量这些机制对 TTFT、throughput 和 hit ratio 的影响。

- **Future work 3：评估 controller failure 与 stale metadata。** 注入 worker restart、partial move、backend timeout、controller failover，测量错误路由率、fallback prefill latency 和恢复时间。

- **Future work 4：把 connector 扩展到非标准 attention/KV 语义。** 对 MLA、sliding-window attention、KV compression、speculative decoding、多模态 prefix 等情况定义最小通用接口，并比较通用 connector 与 model-specific connector 的性能/维护成本。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Disaggregation]]、[[Prefill-Decode-Disaggregation]]、[[KV-Cache-Compression]]
- **同类系统 / 组件**：[[vLLM]]、[[SGLang]]、Mooncake、InfiniStore、NVIDIA Dynamo、llm-d、KServe、AIBrix
- **相关论文**：[[CacheGen-SIGCOMM24]]、[[CacheBlend-EuroSys25]]、[[Mooncake-FAST25]]、[[InfiniGen-OSDI24]]、PromptCache、RAGCache、CachedAttention、IMPRESS、Splitwise、DistServe
- **同主题**：[[AI-Infra]]、[[LLMServing]]、[[LongContextInference]]
