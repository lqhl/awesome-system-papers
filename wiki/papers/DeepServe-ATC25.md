---
type: paper
name: DeepServe
full_title: "DeepServe: Serverless Large Language Model Serving at Scale"
authors: [Junhao Hu, Jiang Xu, Zhixia Liu, Yulong He, Yuetao Chen, et al.]
venue: ATC
year: 2025
tags: [llm-serving, serverless, npu-cluster, pd-disaggregation, autoscaling, kv-cache]
source_pdf: "[[atc2025-hu-junhao.pdf]]"
source_md: "[[atc2025-hu-junhao]]"
---

# DeepServe: Serverless Large Language Model Serving at Scale (ATC 2025)

> **一句话总结**：DeepServe 的核心判断是生产 MaaS 同时遇到异构 AI workload、stateful/disaggregated LLM serving 和突发扩缩容；它用 request-job-task 抽象 + NPU-centric 的 FlowServe/RTC/DistFlow + PD-aware 调度 + prewarm/DRAM/NPU-fork 扩缩，把华为云 Ascend 集群上的 LLM serving 做成运行一年以上的 serverless 平台，并在 34B TP=4 实验中报告 FlowServe 版本迭代带来 2x+ 吞吐提升、NPU-fork 在 HCCS 上 0.15-0.19s 级加载模型分片。

## 问题与动机

DeepServe 要解决的不是单个 inference engine 的局部优化，而是云厂商 MaaS 平台上的端到端托管问题：同一个 AI cluster 里有 fine-tuning 这类小时到天级任务，也有 chat、agent serving、batch inference 这类秒到分钟级请求。平台需要对外提供简单 API，对内又要做资源共享、SLO 控制、扩缩容和故障恢复。

论文把困难拆成三类。第一，AI workload 的持续时间和资源粒度差异很大，静态分配会浪费，过度混部又会互相干扰。第二，LLM serving 已经从单机 stateless request 变成有状态分布式系统：[[KV-Cache]]、[[Prefix-Caching]]、[[Disaggregation|prefill-decode disaggregation]] 和 context caching 都让一次请求的状态跨 engine、跨 NPU、跨存储层移动。第三，在线请求波动强，而 LLM TE 启动慢，尤其是大模型权重从 SSD/DRAM/NPU 间搬运会主导 cold-start latency。

作者的 claim 边界很清楚：DeepServe 是 Huawei Cloud 在 Ascend NPU 大集群上的 serverless AI platform，论文重点只展开 model serving；post-training 和 agent serving 被纳入 request-job-task 抽象，但具体机制基本不展开。因此这篇更像一篇生产系统经验论文：价值在于把 abstraction、engine、scheduler、autoscaling 放到同一个运行系统里，而不是证明某个单点算法在开放 benchmark 上支配所有方案。

## 关键观察 / 隐含假设

- **观察 1：生产 MaaS 的 workload 粒度差异要求平台抽象先于单点 engine 优化。** 论文用 fine-tuning、agent serving、chat/batch serving 的持续时间差异作为动机，并在 Figure 1 里把 Job Executor、Task Executor 和 Cluster Manager 作为共同控制面。
  - **依赖假设**：这些 workload 共享同一类 AI cluster，并且平台愿意用统一 runtime 进行拆解、调度和扩缩。
  - **可能失效场景**：如果训练、微调、推理由不同集群或不同团队完全隔离，request-job-task 的收益会下降，系统主要贡献会退化成 serving engine + autoscaling。

- **观察 2：LLM serving 的关键资源对象已经从 request 变成跨请求、跨实例的 tensor state。** RTC 不只做 [[PagedAttention]] 式 block allocation，还要管理 prefix-token match、explicit ID match、Populate、Copy、Free 等 API；DistFlow 则负责把 tensor 在 tiered storage 和 TE 之间点对点搬运。
  - **依赖假设**：请求之间存在可复用 prefix/context，cache placement 对性能足够重要，并且 KV transfer 比重新 prefill 更划算的情况经常出现。
  - **可能失效场景**：随机 prompt、短上下文、小模型、低复用率 workload 会削弱 locality-aware scheduling 和 RTC prefetch 的价值；过高并发下 cache transfer 也可能和 serving 通信抢链路。

- **观察 3：PD-disaggregated 与 PD-colocated 不是固定优劣，而是由 prefill/decode 长度和负载共同决定。** Figure 6 的 heatmap 显示，长 prefill + 相对短 decode 往往偏向 PD-disaggregated，而 decode/prefill 比例很高时 PD-colocated 可能更好；作者还说跨 RPS 合并后超过 80% 的格子符号稳定。
  - **依赖假设**：prefill length 可准确知道，decode length 可用轻量模型以足够精度预测；热图不会因模型、采样参数、trace 或硬件代际快速失效。
  - **可能失效场景**：Figure 7 显示高 RPS 时 PD-aware 会弱于 round-robin，因为同资源下 PD-disaggregated TE 更容易 overload；decode length predictor 只有 84.9% bucket accuracy，长尾任务误判会直接影响 TE 选择。

- **观察 4：冷启动瓶颈主要在 TE 初始化和模型加载，而不是传统 serverless 的容器启动本身。** Figure 9 显示优化后 TE-Pre-Load 仍是最大块；Figure 10 显示 DRAM-hit、RoCE/HCCS NPU-fork 能显著降低 TE-Load。
  - **依赖假设**：机器有足够 DRAM 做模型预加载，已有运行 TE 可作为 NPU-fork 源，NPU-to-NPU 链路有足够空闲带宽。
  - **可能失效场景**：scale-from-zero 无法使用 NPU-fork；多模型长尾会降低 DRAM preload hit rate；GPU/以太网集群若没有类似 HCCS/SuperPod 的链路，秒级扩缩结论需要重测。

- **隐含假设：RTC soft state 丢失是可接受的性能损失，而不是正确性问题。**
  - **证据强度**：中。论文讨论故障时说 TE/JE failure 后重启并重定向，RTC 状态 append-only 且可重算，因此不实现复杂 consistency protocol；但没有给出故障注入、cache loss 对 SLO 的影响或多租户隔离细节。

## 核心方法

DeepServe 的对外抽象是 request-job-task。request 是用户的 HTTP 触发，job 是内部处理请求类型的逻辑单元，task 是 job 内的细粒度执行单元。chat request 在 PD-colocated engine 上可能只有一个 task；在 [[Disaggregation|PD-disaggregated]] 模式下会拆成 prefill task 和 decode task。Job Executor 负责把 request 拆成 task 并选择 TE，Task Executor 执行 task，Cluster Manager 管扩缩、健康检查和资源预热。

FlowServe 是每个 model-serving TE 内的 engine，设计原则是 microkernel-inspired、NPU-centric、SPMD。tokenizer 独立扩缩；master 负责 scheduler、RTC 和 DistFlow 的控制决策；每个 NPU 上有 executor 执行模型 forward、RTC executor 和 DistFlow worker。作者刻意选择 centralized master scheduler，而不是完全 distributed scheduler，理由是实现简单、统一管理 [[Pipeline-Parallelism]] micro-batch 和 memory preemption，但代价是 IPC 更频繁。

在单 TE 内，FlowServe 用两类异步性保持 NPU 忙碌。第一是 asynchronous [[KV-Cache]] prefetch：scheduler 在 enqueue 阶段查询 RTC match，若 cost model 判断复用 cache 有利，就调用 Populate 让 RTC/DistFlow 异步把 KV 放到本地 NPU。第二是 asynchronous execution：decode 阶段下一轮需要的资源通常由 sequence 数而非生成 token 内容决定，所以 scheduler 可以和当前 batch 的 model execution 并行准备下一轮输入。这个设计和 [[vLLM]]、[[SGLang]]、[[NanoFlow-OSDI25|NanoFlow]] 的方向一致。

RTC 把内存分配和 cache relation 管到一起。它保留 [[PagedAttention]] 式 block table，同时加 hybrid indexing：prefix-token radix tree 支持 implicit prefix caching，ID-based index 支持显式 context caching endpoint。RTC 的 Populate API 是关键，因为它把“命中 cache”从本地判断扩展成“把远端或 tiered storage 上的 tensor 拉到本地 NPU”。这使 scheduler 可以把 cache locality 纳入 TE 选择，而不是只看 queue length。

DistFlow 提供跨 TE 的 tensor transfer primitive，接口比集合通信更接近 raw memory transfer：用户指定 source/destination buffer，DistFlow 负责 LinkCluster 和 transfer。scaled-out Ascend cluster 上走 HCCL peer-to-peer；SuperPod 上利用统一内存地址空间和 NPU memory copy primitive。它支撑两层 disaggregation：task-level 的 prefill/decode 分离，以及作者计划中的 operator-level attention/expert 分离，后者和 [[MoE]]、[[Expert-Parallelism]] 更相关。

分布式调度由 JE 执行，按 Algorithm 1 先 PD-aware，再根据 load balanced 与否选择 locality-aware 或 load-aware。locality-aware 用 global/local prompt tree 找 longest common prefix，类似 Preble、[[SGLang]] 和 MemServe 的方向。PD-aware 先离线构造 PD-disaggregated vs PD-colocated heatmap，再用 decode length predictor 把请求映射到热图格子。组合策略的简单性是优点：先选 TE 类型，再在类型内做 cache locality 或 load balance。

快速扩缩拆成 Scaler-Pre、TE-Pre-Load、TE-Load、TE-Post-Load、Scaler-Post 五步。DeepServe 用 pre-warmed pods 消除环境准备，用 pre-warmed TEs 把 Python/NPU/HCCL 初始化移出关键路径，用 safetensors + DRAM preload 降低 local model loading，用 NPU-fork 从已有 TE 经 DistFlow/HCCS/RoCE 复制权重，用 offline profiling、async allocation 和 dummy request 替代昂贵 warm-up，最后由 Cluster Manager 主动推送 TE list 更新。

## 设计取舍

- **集中式 scheduler 换实现简单性**：master scheduler 让 memory preemption、chunked prefill、PP micro-batch 和 cache placement 统一处理，但 IPC 与 master bottleneck 需要持续优化；论文自己的 Figure 3 也显示 v1 到 v2 的 2x+ 主要来自 asynchronous scheduling 和 IPC 优化。
- **硬件特化换扩缩速度**：NPU-fork、HCCS、HCCL P2P、SuperPod shared memory 都让 Ascend 平台受益，但也让结论难直接迁移到普通 GPU/RDMA 集群。
- **离线 heatmap 换在线低开销调度**：PD-aware 策略实现简单，在线只需 prefill length、predicted decode bucket 和热图查表；代价是热图随模型、SLO、RPS、采样参数和硬件变化可能过期。
- **soft state 换低复杂度**：RTC 不做复杂一致性协议，cache 丢了可以重算；这符合 cache 语义，但论文没有展示 cache loss、TE reboot 或 JE failover 对 tail latency 的影响。
- **prewarm 换资源冗余**：pre-warmed pods/TEs 和 DRAM model cache 降低 cold start，但占用 idle pod、DRAM 和管理复杂度；多租户长尾模型越多，preload 命中越难。

## 实验与结果

- **生产背景**：DeepServe 在 Huawei Cloud Ascend NPU cluster 上运行一年以上，支持 fine-tuning、agent serving 和 model serving API。论文展开的硬件包括 Ascend 910B scaled-out server（每台 8 张 NPU，200Gbps RoCE）和 CLOUDMATRIX384 SuperPod（48 server、384 Ascend 910C、约 200GB/s unidirectional interconnect、统一内存地址空间）。
- **FlowServe engine 演进**：34B model、TP=4、256 decode steps 的 offline test 中，v1 到 v2 通过 asynchronous scheduling 和 IPC optimization，在 TPOT SLO=50ms 时吞吐提升超过 2x；v2 到 v3 通过 data structure、sampling 等优化再提升约 20%。PP scheduler 配合 [[Chunked-Prefill]] 把 TTFT 降低至少 20%。
- **PD-disaggregated serving**：34B model、TP=4、内部 trace（约 2K input、200 output）下，PD-disaggregated 配置在某些 SLO 下能提供更高 throughput，并在相同 throughput 下取得更低 TPOT；但曲线也显示资源配比不当时会出现 decode-side TPOT 上升。
- **PD-aware scheduling**：Figure 6 的热图显示 PD-disaggregated 优势集中在较长 prefill 和中短 decode 区域，decode/prefill ratio 到 2-4 时不少格子偏向 PD-colocated。作者把多个 RPS 热图相加，并报告超过 80% 格子符号稳定；decode predictor 用 128-token bucket，accuracy 为 84.9%。内部 code-generation trace 上，10 RPS 时 PD-aware 的 JCT/TPOT 优于 round-robin，低 RPS 接近，高 RPS 会变差。
- **扩缩容路径**：Figure 9 显示优化后 E2E scaling latency 大幅下降，但 TE-Pre-Load 仍占主体：Llama3-8B TP=1、CodeLlama-34B TP=4、Qwen-72B TP=8 的 post-opt TE-Pre-Load 分别约 26.45s、29.53s、31.69s。TE pre-warming 对多数模型把 TE-Pre-Load 优化约 35%，并进一步把它移出 critical path。
- **模型加载**：Figure 10 中 DRAM-miss 对 Llama3-8B TP=1、CodeLlama-34B TP=4、Qwen-72B TP=8 分别约 3.3s、11s、24s；DRAM-hit 降到 1.1s、2.1s、3.2s；RoCE NPU-fork 为 0.71s、0.76s、0.91s；HCCS NPU-fork 为 0.15s、0.16s、0.19s。
- **NPU-fork scalability**：HCCS + Llama3-8B TP=1 下，从一个 running TE 并行扩到 31 个新 TE，scale time 只从约 0.44s 增到约 0.58s；source TE 同时 prefill/decode 时延迟上升有限。论文据此声称可数秒内并行扩到 64 instances。

## Critical Analysis

### 论证链条

论文的主链条是闭合的：生产 MaaS 的多 workload + stateful LLM serving + bursty traffic，分别对应 request-job-task、RTC/DistFlow、PD-aware scheduling 和 fast scaling。作为生产系统论文，这条链条有说服力，因为每个组件都对上了一个真实运维痛点。

薄弱处在于贡献很多，隔离实验有限。request-job-task 抽象没有和其他 serverless/AI platform abstraction 做对照；FlowServe 的主要数据是内部版本迭代，而不是和同硬件上的 [[vLLM]] / [[SGLang]] 公平比较；PD-aware 和 scaling 则是相对独立的 microbenchmark。结果更适合证明“DeepServe 是可运行的生产系统”，而不是证明每个 design 都是必要且最优的。

### 假设压力测试

最脆的是 workload stability。PD-aware 依赖热图稳定和 decode length prediction；如果业务从 code-generation 切到 long-form writing、tool use、RAG 或 multimodal，decode/prefill 分布、prefix locality 和 SLO 权重都会变。论文承认 decode length prediction 是开放问题，但没有展示 predictor drift 或 online retraining。

第二个压力来自硬件。NPU-fork 的漂亮数字很依赖 HCCS/SuperPod 这类高带宽 NPU-to-NPU link；普通 RoCE 已经慢到 0.7-0.9s，跨 rack 或被 KV transfer/MoE all-to-all 抢占时可能更差。scale-from-zero 也只能靠 DRAM/SSD 路径，不能靠 NPU-fork。

第三个压力来自故障和多租户。论文说 RTC 是 soft state、TE/JE failure 可重启并在 5 分钟内恢复，但生产 SLO 真正关心的是 failure 期间 tail latency、cache miss 风暴、请求重试、quota/fairness 和租户隔离。这里几乎没有实验。

### 实验可信度

可信的地方是系统确实来自生产环境，并且数据覆盖 engine、scheduler、scaling 三条关键路径。Figure 10 的模型加载数字尤其清楚，能直接说明 DRAM-hit 与 NPU-fork 的量级差异。

不足是可复现性和 baseline。内部 trace、Ascend NPU、FlowServe 私有实现、Huawei cluster manager 都让外部很难独立验证。FlowServe 的 2x+ 来自版本迭代，不代表相对公开 SOTA 的 2x。PD-aware scheduling 的评估规模是四台服务器、34B TP=4、内部 code-generation trace；它能说明策略有用，但不能覆盖更大集群、更强波动、更复杂多模型混部。

### 系统性缺陷

DeepServe 的工程面非常重：自研 engine、RTC、DistFlow、scheduler、autoscaler、prewarm pool 和 Cluster Manager。论文没有展开 observability、debuggability、配置管理、灰度发布和跨版本兼容，这些在生产中很可能比单个调度算法更难。

尾延迟与隔离也没有被完全展开。论文报告 JCT、TPOT、TTFT 和 scaling latency，但没有系统回答多租户 quota、batch inference 与 chat request 的相互影响、prewarm pool 被抢占、cache state 被恶意或偶然污染时的隔离策略。

最后，NPU-specific 和 NPU-agnostic 的边界有些模糊。作者说高层架构可迁移到 GPU/NVLink，但最强结果来自 Ascend HCCS、HCCL P2P、SuperPod unified memory 和大 DRAM 机器；把这些替换成 NVIDIA/AMD/Ethernet 后，哪些结论仍成立需要重新测。

## 局限与 Future Work

- **局限 1：公开可复现性弱。** 关键结果依赖内部 trace、Ascend 集群和私有 FlowServe。Future work：用 ShareGPT/BurstGPT/LMSYS/code-generation trace replay，在同一 SLO 下比较 DeepServe-style scheduler、round-robin、load-only、locality-only 和 PD-only。
- **局限 2：PD-aware 的热图可能 stale。** Future work：做 online heatmap calibration，按模型版本、采样参数、SLO 和 RPS 自动检测热图漂移，并报告错误 TE 类型选择对 JCT/TPOT 的影响。
- **局限 3：decode length predictor 只作为组件存在。** Future work：把 84.9% bucket accuracy 拆成 under-predict/over-predict 成本，并评估 predictor latency、GPU/NPU/CPU 占用与调度收益是否相抵。
- **局限 4：故障恢复缺少定量实验。** Future work：对 TE failure、JE failure、RTC cache loss、DistFlow transfer failure 做 fault injection，报告 P99 TTFT/TPOT、cache hit recovery time 和重试放大。
- **局限 5：prewarm/predictive preload 的资源成本未闭合。** Future work：在多模型 Zipf workload 下测 DRAM preload hit rate、idle TE 成本、per-request cost 和 SLO violation，和 [[BlitzScale-OSDI25|BlitzScale]]、ServerlessLLM、FaaScale 类模型加载方案比较。
- **局限 6：operator-level disaggregation 还停留在计划。** Future work：在 [[MoE]] 模型上同时测 prefill/decode disaggregation、attention/expert disaggregation、NPU-fork 和 DistFlow 共享链路时的干扰。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Disaggregation]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[MoE]]、[[Expert-Parallelism]]、[[RDMA]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[NanoFlow-OSDI25|NanoFlow]]、MemServe、Mooncake、Splitwise、DistServe、ServerlessLLM、NVIDIA Dynamo、AIBrix
- **相关论文**：[[BlitzScale-OSDI25]]、[[KVCacheInTheWild-ATC25]]、[[NVIDIA-Disagg-Study-MLSys26]]、[[LMCache-arXiv25]]
- **同会议**：[[ATC-2025]]
