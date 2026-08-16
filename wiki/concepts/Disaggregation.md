---
type: concept
aliases: [Disaggregation, disaggregated inference, prefill-decode disaggregation, P/D disaggregation]
parent: "[[LLM-Inference]]"
last_updated: 2026-08-14
tags: [llm-inference, scheduling, system-architecture]
---

# Disaggregation

> 分离式推理（disaggregated inference）把原本在同一模型实例上执行的阶段或状态放到不同资源池。在 LLM 服务里通常特指 prefill–decode 分离（P/D disaggregation）：prefill 实例生成 KV cache，再把它传给 decode 实例继续逐 token 生成。

## 核心思想

prefill 一次处理很多输入 token，通常更偏计算密集；decode 每轮处理少量新 token，却反复读取模型权重和历史 KV，通常更偏内存带宽与延迟。把两阶段放在不同 GPU 池后，可以为它们选择不同 batch、并行方式、GPU 数和扩缩容策略，避免长 prefill 直接阻塞 decode。

代价是状态跨边界移动。调度器必须选择 prefiller 和 decoder、给两池做 rate matching，并把每层或整请求的 KV 通过 RDMA/NVLink/PCIe 或缓存层传过去。网络拥塞、队列、失败和模型版本从此都在关键路径上。

这里要区分三类相邻设计：

- **物理 P/D 分离**：不同实例长期承担不同阶段，KV 跨实例传输。
- **时间或混合分离**：完整模型实例在较长窗口内切换 prefill/decode，减少短周期干扰，但 KV 留在本地。
- **存储、内存、专家或角色分离**：也属于广义 disaggregation，却不能直接证明 P/D serving 的收益。

## 为什么重要

分离让阶段独立伸缩，也能为 prefill 选择吞吐型配置、为 decode 选择低延迟配置。但它不是默认更优。KV 大小取决于 context、层数、head 结构和精度；网络需求还取决于到达率和传输是否能与计算重叠。短 context、低并发、慢网络或高 cache hit 都可能改变 crossover。

OSDI 2026 的 [[EcoServe-OSDI26]] 是重要反例：在普通 PCIe GPU 和 Ethernet 集群上，完全分离会被 KV 流量和固定池配比限制；复制完整模型并让多个实例错峰切换较长 phase，反而能减少数据搬运。这说明分离的真正问题不是“拆不拆”，而是在哪个边界拆、拆到什么程度。

## 关键观察 / 隐含假设

- **阶段异构是真实的，但强弱随模型改变。** MHA 的 KV 较大，GQA/MLA 的 KV 和投影成本不同。[[EcoServe-OSDI26]] 发现 A800 的计算能力比 L20 增长更快、网络只增加 2.5 倍时，完全分离反而更容易被网络卡住。
- **KV transfer 与资源配比必须联合优化。** [[NVIDIA-Disagg-Study-MLSys26]] 扫描大量模拟设计点，发现 prefill-heavy、较大模型的收益更明显，prefill:decode GPU 比需要动态 rate matching。约 8 倍 goodput 的 headline 来自特定 H200 原型相对静态配比，不能理解为 P/D 对共置系统普遍提升 8 倍。
- **远端 KV 不一定比重新 prefill 划算。** [[LMCache-arXiv25]] 把 KV 作为跨引擎、跨存储层对象，并在企业部署中观察到两种情况都存在；[[CacheGen-SIGCOMM24]] 又说明低带宽下，直接传 10 GB 级 KV 可能更慢，所以需要压缩和流式传输。
- **小块、动态成员需要不同通信抽象。** [[fabric-lib-MLSys26]] 用可靠无序 RDMA write 和计数完成来传分页 KV，避免静态 collective 的限制。它证明的是通信 substrate 和三个特定用例，不是完整 P/D scheduler 的端到端最优性。
- **prefix reuse 会改变传输经济性。** [[KVCacheInTheWild-ATC25]] 的生产 trace 显示 ideal hit 约 54%–62%，而非合成 workload 常见的近满复用；global routing 若高估 hit，可能付出远端查找和传输却没有节省 prefill。
- **分离扩大故障恢复边界。** [[GhostServe-MLSys26]] 的 chunk-level KV parity 在共置 TP 中有效，但论文明确没有解决 P/D 后 parity 归属；prefiller、decoder 或 KV store 失败时，系统要决定重算、重传还是恢复。
- **可观测性必须跨实例。** [[StriaTrace-OSDI26]] 已在含 monolithic 和 P/D 部署的生产服务中追踪请求。慢 token 的根因可能在 prefiller queue、传输、decoder、collective 或 host runtime，单实例 profiler 不够。
- **更多阶段不一定只分成 P 和 D。** [[TriInfer-MLSys26]] 把多模态 encode 也变成 first-class stage，在 E+P+D、EP+D、ED+P 等组合之间按 SLO 选择；结果来自所测 MLLM 和历史 trace，拓扑切换的生产成本仍需验证。

## 设计空间与取舍

- **共置、完全分离或 hybrid**：共置不搬 KV但有阶段干扰；完全分离独立伸缩但网络最重；[[EcoServe-OSDI26]] 的 phase hybrid 复制模型、保留本地 KV，以显存换网络。
- **请求级或 layer/chunk 级传输**：整请求协议简单，decoder 等待更久；逐层或逐块可 overlap，产生更多小消息、metadata 和错误状态。
- **固定或动态池比例**：固定配置稳定且易运维；动态 rate matching 能跟随 P:D 变化，却有冷启动、迁移和控制滞后。
- **直接传输、压缩或重新计算**：直接传最简单；压缩省带宽、增加计算与质量风险；重新 prefill 在短上下文或慢网络下可能更便宜。
- **专用 KV 服务或点对点**：共享 cache layer 能复用和统一管理，形成新的故障域与拥塞点；点对点路径短，跨请求复用较弱。
- **同构或异构硬件**：两池同构容易调配备用容量；异构能贴合阶段，但故障替代、模型 kernel 和容量规划更复杂。
- **单纯 P/D 或更多角色**：多模态 encode、MoE expert pool、RL rollout/reward/trainer 都可拆开；每多一条边，就多一组状态版本、backpressure 和重试语义。

## 引用本概念的论文

### P/D serving 与 KV 数据面

- [[EcoServe-OSDI26]]：给出普通 Ethernet 上完全分离的反例，并提出较长 phase 的跨实例错峰方案。
- [[NVIDIA-Disagg-Study-MLSys26]]：系统扫描 P/D parallelism、池比例和 SLO 的设计空间，强调动态 rate matching。
- [[LMCache-arXiv25]]、[[CacheGen-SIGCOMM24]]、[[fabric-lib-MLSys26]]：分别提供 KV cache layer、压缩流式传输和多 fabric RDMA 点对点机制。
- [[DeepServe-ATC25]]：在长期运行的 Ascend serverless 平台中，把 P/D-aware 调度、tensor cache 和扩缩容放到同一控制面。
- [[TriInfer-MLSys26]]：把多模态 encode 加入 P/D，并按 workload 选择混合拓扑。
- [[GhostServe-MLSys26]]：揭示分离环境下 KV checkpoint 的 ownership 和跨节点容错仍未解决。

### 缓存、执行与调度边界

- [[KVCacheInTheWild-ATC25]]、[[Strata-OSDI26]]、[[ContextPilot-MLSys26]]、[[CacheSlide-FAST26]]：分别从真实复用、分层加载、输入重用和跨位置复用改变“传 KV 还是重算”的选择；后两者没有完成 P/D 联合实验。
- [[PrefillOnly-SOSP25]]：说明独立 prefill 节点可能需要不同于通用 serving 的内存与调度设计。
- [[TokenWeave-MLSys26]]、[[DirectKV-OSDI26]]：优化共置/分离下的通信 overlap 或本地 CPU-resident KV；DirectKV 尚未接入完整 P/D runtime。
- [[Wang-LocalMoEInference-OSDI26]]：在单节点双 GPU 与共享 CPU 权重上做本地 P/D 分工，避免复制约 TB 级模型；适用边界和数据中心 GPU 池不同。

### 广义分离，不是 P/D 证据

- [[DGC-OSDI26]] 把 GC marking 放到共享服务；[[RollArt-OSDI26]] 拆开 rollout、environment、reward 和 trainer；[[Weave-OSDI26]] 处理可组合 AI pipeline。它们能提供 backpressure 和版本协调经验，但不能证明 LLM KV transfer 的性能。
- [[FineMem-OSDI25]]、[[Tigon-OSDI25]]、[[Nostor-OSDI25]]、[[Umap-OSDI26]] 分别研究远端内存、CXL 数据库、内存存储和分布式文件映射，是广义资源分离的邻接工作。
- [[Charon-MLSys26]]、[[BOUTE-MLSys26]]、[[MorphServe-MLSys26]] 把 disaggregation 放进模拟、成本优化或未来组合中，相关页并未给出完整 P/D 实验。

## 已知局限 / 开放问题

- 应公开共置、hybrid、完全分离随 context、arrival、KV format 和 network bandwidth 变化的 crossover，而不是只给一个最优配置。
- 扩缩容、取消、重试和节点故障时，KV、输出 token 和模型版本需要明确唯一 owner；exactly-once 很难只靠 transport 保证。
- 池比例控制要考虑冷启动和 burst。控制器反应慢时，一侧会排队、另一侧会空闲。
- 网络成本不只有带宽：小消息率、NIC CPU、collective 竞争、拥塞和 tail 都会放大 TPOT。
- 多租户 KV cache 涉及权限、清除和侧信道；跨实例复用不能只按性能设计。
- TCO 评估应包含复制模型的 HBM、KV store、NIC、host DRAM、能耗、备用容量和故障恢复，而不只算 GPU goodput。
