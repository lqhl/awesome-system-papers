---
type: paper
name: Strata
full_title: "Strata: Hierarchical Context Caching for Long Context Language Model Serving"
authors: [Zhiqiang Xie, Ziyi Xu, Mark Zhao, Yuwei An, Vikram Sharma Mailthody, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, hierarchical-caching, kv-cache, gpu-io, scheduling]
source_pdf: "[[osdi26-xie-zhiqiang.pdf]]"
source_md: "[[osdi26-xie-zhiqiang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Strata：面向长上下文 LLM 服务的分层上下文缓存（OSDI 2026）

> **原题**：Strata: Hierarchical Context Caching for Long Context Language Model Serving

> **一句话总结**：长上下文服务中，KV cache 从 CPU/SSD 回传 GPU 时会因小页碎片化和调度失衡变成 I/O 瓶颈；Strata 用 GPU-assisted I/O 解耦计算布局与传输布局，再用感知缓存负载的调度器处理 delay hit 和加载停顿，在 LooGLE 等负载上相对 vLLM-LMCache 最高提升 5×，同时保持短上下文性能。

## 问题与动机

长上下文请求会反复访问相同文档、对话历史或 agent 上下文。把已计算的 [[KV-Cache]] 放在 GPU HBM 可避免重复 prefill，但 HBM 容量不足，生产系统需要把缓存下沉到 CPU DRAM、SSD 或远端内存。缓存命中因此从“是否存在”变成“能否及时搬回 GPU”。

论文在 Qwen2.5-14B 的 LooGLE 测试中观察到，SGLang 将 KV cache 从 CPU 加载时，最多 74% 的 prefill 时间被传输阻塞（图 1）。现有分页布局适合 GPU 内存管理，却把一次长上下文加载拆成大量小拷贝；调度器又默认计算能够隐藏加载延迟，导致 GPU 等待 I/O，或在同一上下文尚未完成时重复计算。

## 关键观察 / 隐含假设

- **观察 1：小页有利于缓存命中，却不利于跨层级传输。** 以 32-token 页加载 8192 tokens 时，PCIe 5.0 实测带宽约只有理论值的 22%；在 GH200 上利用率最低约 5%（§3.1、图 3）。增大页会降低命中率，Mistral-24B/ShareGPT 上平均 TTFT 最多增加 2×，P90 TTFT 最多增加 2.9×（图 2）。
  - **依赖假设**：KV cache 的复用粒度仍然需要小页。
  - **可能失效场景**：前缀高度稳定、命中率对页粒度不敏感，或硬件 DMA 已能高效聚合小拷贝时，GPU-assisted I/O 的收益会下降。
- **观察 2：长上下文下，I/O 延迟会超过 prefill 计算可隐藏的范围。** 即使 I/O 达到 PCIe 理论带宽的 75%，加载仍可占 prefill 时间的 24%（§3.2、图 1）。
  - **依赖假设**：请求以长缓存上下文、少量新 token 为主；P-D 共置时 GPU 仍有可交错的 decode 或其他工作。
  - **可能失效场景**：新 token 很多、生成阶段占主导，或 decode 与加载共享的资源产生更强竞争时，论文的平衡规则不一定适用。
- **观察 3：缓存未完成时到达的相同上下文请求会造成 delay hit。** Mooncake agent trace 中，38% 的请求在一秒内与另一请求共享至少 6K token 前缀（§3.2）。
  - **证据强度**：中。trace 支持请求相关性，但论文主要通过模拟和受控实验评估 delay hit，未提供生产线上完整命中收益。

## 核心方法

Strata 集成到 SGLang，由 Cache Controller 和 Scheduler 组成（图 4）。Cache Controller 延续 [[SGLang]] 的 RadixTree 思路，扩展出 HiRadixTree，记录每个 KV cache 页在各层级的状态和位置。

Cache Controller 使用 GPU-assisted I/O kernel 替代反复调用 `cudaMemcpyAsync`。GPU 线程并行搬运细粒度数据，允许单页保持小粒度，同时提高并发度。GPU 端继续使用适合 attention 的 layer-first 布局，CPU/SSD 使用 page-first 布局；I/O kernel 在传输时完成地址变换，避免用一种布局同时服务计算和存储（§4.2.1）。H200 上用两个 1024-thread CUDA blocks 可达到 48 GB/s，prefill 性能下降少于 5%，decode 下降约 10%（图 5）。

Scheduler 分三步处理缓存负载。首先在 HiRadixTree 中插入 transient nodes，标记 in-queue 或 in-flight 的上下文；匹配到正在生成的长前缀时推迟请求，避免同一 miss 被重复计算。默认在匹配超过 100 tokens 时触发推迟（§4.3.1）。

其次，Batch Formation 估计每个请求需要加载和计算的 token 数，以 load/compute 比例 100 作为默认 loading-bound 阈值。它优先加入不会使批次 I/O 受限的请求，并优先合并共享上下文的 bundle hits。最后，如果批次仍需等待长 I/O，则插入 decode batch 填充计算空洞；decode 主要受 HBM 带宽限制，可与 PCIe 加载重叠（§4.3.2–§4.3.3）。

系统还提供 write-back、write-through 和 selective-writethrough 三种下沉策略，默认按访问次数选择性写回，并对所有层级使用 LRU 淘汰。SSD 命中时默认在排队期间预取到 host memory，也支持等待完成或超时策略。

## 设计取舍

- **GPU-assisted I/O 的吞吐与干扰**：用 SM 线程换取小拷贝效率。少量大 block 将 I/O 限制在少数 SM，降低干扰，但仍会占用寄存器和执行周期；论文报告的干扰是微基准结果，不等价于所有模型和 kernel 组合。
- **延迟命中推迟与公平性**：推迟长前缀请求可减少重复 prefill，却可能让个别请求等待。论文承认聚合吞吐优先的策略仍可能造成 SLO 不公平。
- **单实例内的优化范围**：Strata 主要管理单计算实例的 GPU、host memory 和本地存储，没有内建跨节点 KV cache 协调；它可与 Mooncake、MemServe 等分层内存池结合，但网络路径未被端到端验证。

## 实验与结果

- H200 上 LooGLE：Llama-8B 相对 SGLang-HiCache、vLLM-LMCache、TRT-LLM-HiCache 最高分别提升 3.2×、2.6×、1.9×；Llama-70B 最高分别为 5×、5×、3.75×（图 8）。
- NarrativeQA warm-cache：相对 vLLM-LMCache，Llama-8B、Qwen-14B、Llama-70B 吞吐最高提升 2.3×、2.6×、2.5×（§5.2.2、图 8）。
- 消融实验中，单独加入调度和 I/O 机制，峰值吞吐最高分别提升 1.8× 和 2.3%；高请求率下 I/O 优化成为主要收益来源（§5.3.1、图 9）。
- 不同 cache distance 下，I/O 优化对 shuffle 和 maximum-distance 负载带来 76% 和 95% 的峰值吞吐提升；平衡批次再增加 11% 和 12%，stall hiding 增加 8% 和 3%（图 11）。
- DeepSeek-V3/8×H20 的磁盘缓存实验中，page-first 布局相对较大页布局将平均 TTFT 降低 2.1×，吞吐提高 1.3%（§5.3.5、图 13）。
- GH200 上，Strata-IO 将 host-GPU 持续带宽从 40 GB/s 提高到 150 GB/s；仅提升硬件互连带宽不足以超过 H200 上的 Strata-IO，调度仍需适配（§5.4、图 14–15）。短上下文 ShareGPT 上，Strata 与 vLLM、TRT-LLM 性能相当（图 8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 分层 KV cache 对长上下文吞吐有必要 | LooGLE、图 8，非分层方案频繁重算，分层方案约 95% 命中 | H200，三种模型，主要是 CPU DRAM 层级 | 强 |
| GPU-assisted I/O 缓解小页传输瓶颈 | §3.1、图 3；§5.3.1、图 9 | H200/GH200，CUDA kernel；干扰依赖并发 kernel | 强 |
| 缓存感知调度能减少 delay hit 和加载停顿 | §5.3.3、图 11；§5.3.4、图 12 | Mooncake 部分结果为模拟；阈值需按硬件和模型配置 | 中 |
| Strata 提升端到端长上下文吞吐 | §5.2、图 8，最高相对 vLLM-LMCache 5× | 三个模型、四类数据集；到远端内存和多租户 SLO 的覆盖有限 | 强 |

## 批判性分析

### 论证链条

论文的链条基本闭合：小页造成传输碎片，布局又把单个逻辑页分散到各层；GPU-assisted I/O 同时提高并发和传输连续性；当加载仍占主导时，调度器用 delay-hit 推迟、批次配平和 bubble filling 减少等待。图 9 的组件消融支持两条机制分别贡献收益，图 14–15 说明单纯更快的互连不能替代软件调度。

但“部署在生产环境”主要作为背景陈述，公开实验集中在三种硬件、合成到达过程和有限数据集。论文没有给出生产 trace 的端到端 SLO、成本、故障恢复或多租户隔离结果，因此 5× 更适合解释为指定测试配置下的吞吐上界，而非普遍部署收益。

### 假设压力测试

调度器将 load/compute 比例压缩为单一阈值，默认值 100 依赖模型、GPU、互连和请求混合。模型结构变化、PCIe 拓扑、NUMA 绑定、并发度或 SSD 延迟变化都可能改变阈值。论文在 GH200 上展示了适配趋势，但没有系统地给出阈值迁移或在线自适应策略。

延迟命中缓解依赖短时间内的前缀相关性。cache distance 很大时，delay hit 本来就少；相反，推迟请求可能损害独立请求的 TTFT。论文通过保留队列顺序减轻饥饿，但没有报告 P95/P99 TTFT 或不同租户之间的公平性。

### 实验可信度

基线覆盖 vLLM-LMCache、TRT-LLM-HiCache 和 SGLang-HiCache，模型包含 8B、14B、70B，且同时测量 TTFT 与输出 token 吞吐。ShareGPT、LooGLE、NarrativeQA 和 ReviewMT 覆盖 RAG、对话和 agent 风格负载。局限是到达时间主要由 Poisson 过程模拟，SSD 实验只有一个受限磁盘平台，远端网络层没有进入端到端比较。

### 系统性缺陷

GPU-assisted I/O 仍会与计算 kernel 争用 SM、寄存器和调度资源；CUDA 12.8 的 `cudaMemcpyBatchAsync` 干扰更小，但传输吞吐低于 Strata kernel（38 GB/s 对 48 GB/s，§6）。写回策略、LRU 元数据和 transient nodes 增加了运维与状态管理复杂度。故障恢复、缓存一致性、跨实例失效、磁盘写放大和多租户资源隔离在论文中未充分讨论。

## 局限与后续工作

- **公平性与 SLO**：论文承认吞吐优先的批次形成仍可能造成个别请求的 SLO 违约。后续可在相同负载下报告 P95/P99 TTFT、按租户的 tail latency 和吞吐，并比较公平约束带来的代价。
- **存储层调度**：当前 SSD 预取主要借助排队时间隐藏，尚未像 host-to-GPU 加载一样纳入统一的资源配平。可验证的问题是：加入 SSD 带宽、队列深度和剩余 prefetch 时间后，是否能在混合缓存距离下稳定降低 TTFT。
- **混合注意力模型**：Strata 针对标准 dense attention 的 KV cache。对 sparse/linear attention 或 [[MoE]] 模型，需要重新定义缓存页、命中和加载资源。
- **跨节点扩展**：将 page-first 布局和 GPU-assisted I/O 接入 Mooncake 或 MemServe 的远端池，测量 RDMA/NIC 争用、故障恢复和缓存一致性，才能检验单实例结论能否扩展到 disaggregated serving。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[RadixTree]]、[[Continuous Batching]]
- **同类系统**：[[SGLang]]、[[vLLM]]、[[Mooncake]]、[[MemServe]]、[[LMCache]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[vLLM-vs-SGLang]]
