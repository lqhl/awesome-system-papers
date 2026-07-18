---
type: paper
name: FaaScale
full_title: "FaaScale: Unlocking Fast LLM Scaling for Serverless Inference"
authors: [Minchen Yu, Rui Yang, Chaobo Jia, Zhaoyuan Su, Sheng Yao, "et al."]
venue: MLSys
year: 2026
tags: [serverless, llm-inference, model-scaling, rdma, cold-start]
source_pdf: "[[1ff1de774005f8da13f42943881c655f.pdf]]"
source_md: "[[1ff1de774005f8da13f42943881c655f]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# FaaScale: Unlocking Fast LLM Scaling for Serverless Inference (MLSys 2026)

> **一句话总结**：观察到 serverless LLM 在 burst 下 host cache 命中率低（trace 上 36%–64% 仍走 SSD）、而 400Gbps [[RDMA]] 集群已能秒级 multicast 大模型，FaaScale 用 PipeCast 把 binomial multicast 与动态 [[Pipeline-Parallelism|pipeline-parallel]] 推理重叠——部分 block 到达即开工；BurstGPT trace 上 P90 TTFT 比 SOTA 低 **2.4–5×**，GPU 成本降 **17.8%–31.3%**。

## 问题与动机

Serverless LLM inference 面临三重矛盾，作者称之为 trilemma：

1. **请求突发**：生产 trace（BurstGPT、XYZ、Azure OpenAI GPT）显示请求率在数十秒到数分钟内可涨 **10×+**，要求 tens–hundreds 节点 **sub-second scale-out** 才能守住 TTFT SLO。
2. **单模型显存巨大**：Llama-70B ~140GB，冷启动（加载+初始化）可达分钟级，远超典型 inference 的 sub-second 期望。
3. **模型爆炸**：Hugging Face 50 万+ 微调变体，aggregate memory demand 远超 GPU 集群容量，频繁 eviction/reload 恶化 cold start。

现有三类缓解策略均不够：

- **Remote loading**（Hugging Face endpoints 从 S3/registry 拉模型）：大模型 + 并发加载带宽争用/registry throttling，不适合实时 serving。
- **GPU over-provisioning**（SageMaker provisioned concurrency、XYZ 预绑 GPU）：低负载时大量 idle，违背 pay-per-use。
- **Host memory / SSD cache**（ServerlessLLM 等）：多租户 + 大模型下 cache hit rate 差；作者测得 Llama-70B 从 SSD→GPU **>30s**，比 host memory 慢一个数量级。

论文 claim：不应在 startup latency 与 over-provisioning 之间二选一，而应利用 **高速互联 multicast** + **部分权重到达即可推理** 两条 insight，实现不额外常驻 GPU 的 fast scale-out。

## 关键观察 / 隐含假设

- **观察 1**：生产 serverless LLM 的 host memory cache 命中率不足以支撑 burst scale-out。作者 replay BurstGPT/XYZ trace，keep-alive 15s（对应 Fig.2 分布尾部）时，两 trace 上 SSD load 分别占 **64%** 和 **36%**；单节点最多缓存 3 模型、12 模型在 SSD 的配置下，>95% 模型在内存中存活 **<15s** 即被 LRU 驱逐。
  - **依赖假设**：多租户、模型多样性高、per-node host memory 有限（~100s GB）是常态；burst 时需要 **同一模型在多台机器上并发实例化**。
  - **可能失效场景**：租户少、模型集小、或平台愿意大量 over-provision host cache；单租户专用集群 cache hit 接近 100% 时 PipeCast 收益缩小。

- **观察 2**：现代 AI serving 集群的 **RDMA/GPUDirect** 带宽足以在秒级 multicast 数十–百 GB 模型；且 inference 可在 **部分 block 到达** 时通过跨节点 [[Pipeline-Parallelism|pipeline parallelism]] 立即开工，不必等全员收完整模型。
  - **依赖假设**：集群有稳定 **400Gb/s InfiniBand + GPUDirect RDMA**；网络拓扑适合 binomial pipeline（hypercube 邻接传输）；block 粒度可离线 profile 后在不同负载下仍有效。
  - **可能失效场景**：低带宽/高 jitter/非 RDMA 网络（论文承认绝对收益会下降）；GPU–NIC NUMA 错位、NCCL 拓扑优化可能部分抵消 multicast 优势（12-node 实验已观察到）。

- **观察 3**：通用 multicast（binomial pipeline、NCCL broadcast、FaaSNet binary tree）**不感知 inference 语义**——无法把「哪些 block 先到齐」与「哪些节点可拼成 execution pipeline」协同优化。
  - **依赖假设**：pipeline-parallel 中间结果通信开销可控；k-way transmission 的 circular shift 能让互补 block 在 **b/k** 步内凑齐第一份完整模型。
  - **可能失效场景**：模型极大、block 数 b 过小导致传输步数爆炸，或 b 过大导致 pipeline 中间数据开销主导；k≥2 时分布式 pipeline 同步开销会形成 throughput「阶梯平台」（论文 §7.3 已报告）。

- **假设 1**：评测 workload 以 **bursty、不可预测** 的 serverless 多租户为主，而非可预测 prefetch（对比 DynamoLLM）或 P/D [[Disaggregation]] 专用调度（对比 [[BlitzScale-OSDI25|BlitzScale]]）。
  - **证据强度**：**强**——BurstGPT 30 分钟片段 + 高压 50-request stress test 直接支撑；但缺少更长 trace、多租户干扰、跨模型混部。

- **假设 2**：scale-out 时集群中至少有一份 RDMA-accessible 完整 replica（GPU 或 host memory），cold start 从该源 multicast；[[KV-Cache]] 复用由外部系统（如 Mooncake）互补而非本文范围。
  - **证据强度**：**中**——locality-driven startup 三档（GPU hot / host warm / remote cold）在实现中明确，但 trace 实验对三种路径的分解不够细。

## 核心方法

FaaScale 的核心原则是 **pipelined multicast inference**：模型分发与 [[Pipeline-Parallelism|pipeline-parallel]] 推理执行协同，部分权重到达即可开工。实现载体是 **PipeCast**，配合 cluster manager + per-node model manager（~10K Python + 1K C++）。

### PipeCast 三件套

1. **Inference-aware multicast**
   - 模型切成细粒度 block，基于 **binomial pipeline**（hypercube 拓扑邻接传输）做 multicast。
   - **k-way transmission**（Algorithm 1）：N 个节点分成 k 个子组，各子组 circular shift block 传输顺序，使互补 block 并行到达，第一份完整模型可在 **b/k** 步后可用。
   - Block size **b** 离线 profiling 选「肘点」：过小则传输步数多，过大则 PP 中间结果通信开销增；针对稳定 RDMA 网络一次选定，volatile 网络自适应留给 future work。

2. **Pipelined inference execution**
   - **Dynamic execution pipeline**：跨节点动态拼 PP 链（Algorithm 2），优先从各子组等量取节点；互补 block 到齐即启动 pipeline，不必等所有 destination 收全。
   - **2D pipelining**：沿 multicast 路径同时 batch 维 + 层维流水，burst 时快速消化排队请求。
   - **Mode switching**：节点收全模型后切 **local mode**，去掉跨节点通信。
   - **Multi-GPU 扩展**：单 GPU 模型默认跨节点 PP；multi-GPU 模型可跨节点 PP 或 opportunistic intra-node NVLink 复制再跨节点扩展。

3. **Locality-driven startup + memory management**
   - 三档启动：GPU hot / host warm（加载同时可组 PP）/ remote cold（PipeCast multicast）。
   - **Tensor packing**：每 block 连续内存布局，bulk RDMA 传输。
   - **GPU memory pre-allocation**：block 与 pipeline 中间结果大小固定，预分配降低运行时开销；动态 [[KV-Cache]] 仍由推理引擎（如 [[vLLM]]）管理。

传输基于 Derecho/RDMC + GPUDirect [[RDMA]]；推理扩展 Meta Llama 框架支持 local/distributed inference。

## 设计取舍

- **取舍 1：传输–计算重叠 vs 控制面复杂度**——动态 pipeline 需要跟踪 block 可用性、增量组建/退役 pipeline，但作者称开销限于 transient metadata，不改变 data path；换取 TTFT 从「等全模型」变为「等首个可执行 pipeline」。
- **取舍 2：离线 block size vs 在线自适应**——简化部署、避免 runtime 调参，但高波动网络或新硬件代际可能需要重 profile；论文明确列为 orthogonal future work。
- 取舍 3：Binomial multicast 专用性 vs NCCL 通用性——针对 LLM block + PP 语义优化，multicast microbenchmark 上 70B/多节点场景最高快 FaaSNet 1.82×、NCCL 1.53×；12-node 时 NCCL 拓扑优化部分掩盖差距。
- 取舍 4：不做 KV 复用 vs 与 Mooncake 等互补——本文聚焦 model parameter fast scaling；[[KV-Cache]] 状态管理外置，降低系统边界但意味着端到端 cold-to-serving 仍依赖其他层。
- **边界条件**：RDMA 稳定集群、Llama-2 7B/13B/70B、最多 24 GPU/12 节点测试bed 上最强；纯 SSD 路径（ServerlessLLM-SSD）作为弱 baseline 凸显 GDR 价值，但可能低估「强本地 cache + 预取」组合。

## 实验与结果

- **Testbed**：H800 集群，400Gb/s IB，Testbed1（单 GPU 装下 7B/13B）与 Testbed2（70B 需 multi-GPU per node）；对比 ServerlessLLM、FaaSNet（binary tree + GDR）、NCCL broadcast。
- **Multicast 延迟**（Fig.7，k=1）：端到端比 FaaSNet/NCCL 最高快 **1.82× / 1.53×**；模型越大、节点越多优势越大；12-node 13B 增益受 NUMA/NCCL 优化部分限制。
- **高压 ramp-up**（Fig.8–9，50 requests）：FaaScale **1.1s** 内全部开始 serving，vs FaaSNet **2×**、NCCL **1.4×**、ServerlessLLM **8×** 慢；Llama-2 7B 上 k=1 ramp ~0.6s，k=4 可降至 ~**0.15s**。
- **BurstGPT 30 分钟 trace**（Fig.10–11）：P90 TTFT **2.4–5×** 优于 baselines；累计 GPU 时间比 FaaSNet/NCCL/ServerlessLLM 少 **17.8% / 18.1% / 31.3%**；距 ideal scaling（零加载开销）gap **4.3%–18.6%**。
- **Ablation 线索**：k≥2 时出现 throughput 阶梯平台，主因分布式 PP 中间结果同步（§7.3）；技术报告（Yu et al. 2025b）含更多 microbenchmark 与 sensitivity。

## Critical Analysis

### 论证链条

Observation（cache miss 高 + RDMA 够快 + 部分权重可推理）→ Design（PipeCast：k-way multicast + dynamic PP + mode switch）→ Microbenchmark（multicast 1.5–1.8×）→ Stress test（1.1s serve 50 reqs）→ Production trace（TTFT 2.4–5×、GPU 17–31% 节省）链条整体闭合。

薄弱跳步：

1. **「host cache 失效」→「必须用 network multicast」**：测量有力，但未系统对比「更大 host cache + 智能预取 + BlitzScale 式层粒度 live scaling」的组合上限。
2. **离线 b 的鲁棒性**：多种模型/拓扑下共用同一 profile 策略，volatile 网络场景未验证。
3. **Ideal scaling gap 4.3%–18.6%** 的来源分解（控制面、PP 同步、pipeline 退役）在正文较简略，依赖 technical report。

### 假设压力测试

- **论文已证明**：RDMA 集群上 multicast + 部分 PP 重叠显著优于 FaaSNet/NCCL/ServerlessLLM；7B/13B/70B 一致趋势；burst trace 下 scale-out/in 更敏捷、GPU 时间更省。
- **可能失效**（推断）：
  - **低多样性 / 高 cache 预算**：若 host cache hit >90%，ServerlessLLM 路径可能接近 FaaScale，PipeCast 优势集中在 miss 路径。
  - **Predictable traffic**：DynamoLLM 类 prefetch 可能消除多数 cold scale-out，本文优势集中在不可预测 burst。
  - **P/D disaggregated serving**：[[BlitzScale-OSDI25|BlitzScale]] 针对 Prefill/Decode 分离 + 层粒度 live scaling，尚未 head-to-head；FaaScale 不做 P/D 调度，mixed workload 下谁更优未明。
  - **更大集群 / 多 rack**：binomial pipeline 跨 rack 带宽不对称、故障域未讨论。
  - **Security / 多租户隔离**：RDMA 直接 GPU 访问、跨租户 model multicast 的隔离与配额论文未讨论。

### 实验可信度

- **Workload**：BurstGPT（Azure OpenAI GPT 区域服务）有 production 代表性；30 分钟片段偏短；XYZ trace 用于 cache 分析但未作为端到端主结果。
- **Baseline 公平性**：ServerlessLLM 实现去掉 Ray Serve 开销，但 scaling 走 SSD（无 GDR multicast），可能放大差距；NCCL/FaaSNet 在 trace 中「优先 remote GPU GDR、否则 SSD」的假设对两者有利，但仍输 FaaScale。
- **Ablation**：k 变化、block size、PP 同步开销有定性讨论；缺少「无 PP 重叠」「纯 multicast 无 k-way」「固定 b vs 最优 b」的定量分解。
- **Metric**：主报 TTFT、throughput ramp、累计 GPU time；**TBT、SLO violation rate、scale-in 延迟、多模型混部** 覆盖有限。

### 系统性缺陷

- **尾延迟**：高压测试报 TTFT，k≥2 阶梯平台暗示 sustained throughput 可能波动；论文未系统报告 **P99 TBT** 或 long-running stability。
- **故障恢复**：节点中途失败、multicast 重传、pipeline 成员变更论文未讨论。
- **可观测性 / 运维**：动态 pipeline 状态、block 传输进度、mode switch 的 debug 接口论文未描述。
- **资源隔离**：burst cloning 式跨租户干扰未评测；RDMA 带宽与 serving traffic 共存时的隔离策略仅隐含于「网络空闲」假设。
- **兼容性**：基于 Meta Llama 框架扩展；其他推理引擎（[[vLLM]]、SGLang）接入成本论文未量化。

## 局限与 Future Work

- **局限 1**：Block size **b** 依赖离线 profiling，对高度波动网络需 online adaptive tuning——论文明确标为 future work。
- **局限 2**：Dynamic PP 在 k≥2 时引入中间结果同步开销，形成 throughput 阶梯平台；更轻量跨节点 PP 或更粗 block 可能是折中，但未给出自动选择机制。
- **局限 3**：实验规模上限 24 GPU / 12 节点；12-node multicast 增益已受 NCCL 拓扑优化部分掩盖，超大规模行为外推需谨慎。
- **Future work 1**：在 volatile 网络条件下 **在线调整 b 与 k**，并用 microbenchmark 量化 elbow point 漂移——可客观验证鲁棒性 claim。
- **Future work 2**：与 [[KV-Cache]] 复用系统（Mooncake 等）和 P/D [[Disaggregation]] 框架（[[BlitzScale-OSDI25|BlitzScale]]、DistServe）做端到端集成，测量「model scale-out + KV 命中 + PD 调度」的联合 TTFT/TBT。
- **Future work 3**：多 rack、故障注入、多租户 RDMA 隔离下的 scale-out 正确性与 tail latency——填补 production 部署空白。

## 相关

- **相关概念**：[[RDMA]]、[[Pipeline-Parallelism]]、[[KV-Cache]]、[[Disaggregation]]、[[Tensor-Parallelism]]
- **同类系统**：ServerlessLLM、FaaSNet、NCCL、[[BlitzScale-OSDI25|BlitzScale]]、DynamoLLM、Medusa
- **同会议**：[[MLSys-2026]]
- **互补**：Mooncake（cluster-level [[KV-Cache]] pool）、[[vLLM]]（推理引擎与 KV 管理）
