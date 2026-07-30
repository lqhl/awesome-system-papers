---
type: paper
name: Stream2LLM
full_title: "STREAM2LLM: Overlap Context Streaming and Prefill for Reduced Time-To-First-Token"
authors: [Rajveer Bachkaniwala, Chengqi Luo, Richard So, Divya Mahajan, Kexin Rong]
venue: MLSys
year: 2026
tags: [llm-inference, rag, streaming, kv-cache, scheduling]
source_pdf: "[[02522a2b2726fb0a03bb19f2d8d9524d.pdf]]"
source_md: "[[02522a2b2726fb0a03bb19f2d8d9524d]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Stream2LLM：重叠上下文流与预填充以缩短首 token 延迟（MLSys 2026）

> **原题**：STREAM2LLM: Overlap Context Streaming and Prefill for Reduced Time-To-First-Token

> **一句话总结**：观察到 RAG/ANNS 检索延迟主导 TTFT 且多租户下 [[KV-Cache]] 竞争使朴素 streaming 在内存压力下 P99 恶化 10×，STREAM2LLM 在 [[vLLM]] 上实现两阶段调度、LCP 缓存失效与硬件 cost model 抢占，在真实 crawler/ANNS trace 上把 TTFT 降到非 streaming 的 3.9–11.0×，吞吐持平（<1% 差异）。

## 问题与动机

现代 LLM 部署普遍依赖外部 context 检索（web crawler、[[RAG]]、DiskANN 等），检索耗时数百 ms 到数秒，而 inference engine 在此期间 idle。作者 claim 的核心矛盾是：**等完整 context 再 prefill → TTFT 差；不等就生成 → 质量差**。已有 PipeRAG、AquaPipe 等工作证明 **streaming**（检索与 prefill/decode 重叠）在单请求下能显著降低 TTFT，但论文认为这不足以覆盖生产部署：

1. **多租户**：并发请求争用有限 GPU memory 与 [[KV-Cache]] block，触发 swap/recompute 抢占。
2. **动态到达**：不同请求的 context chunk 异步到达，静态 FCFS 无法反映「刚收到新 chunk 的请求应优先处理」。
3. **两种 prompt 演化模式**：**append mode**（爬虫按序追加文档）与 **update mode**（ANNS 迭代替换 top-k，prompt 前缀可能失效），对调度与缓存语义要求不同。

论文目标是在 prefill-decode [[Disaggregation]] 架构的 **prefill 实例**上，把 streaming context retrieval 做成可生产的多租户 primitive，优化 TTFT 与 trace completion time，不评估 decode 侧 TPOT。

## 关键观察 / 隐含假设

- **观察 1**：检索延迟往往大于或可比 prefill 延迟，streaming overlap 能在 chunk 到达时立即开始/继续 prefill，从而把 TTFT 从 `T_retrieve + T_prefill` 压到近似 `max(T_retrieve, T_prefill)` 量级。
  - **依赖假设**：客户端能把 context 以 chunk 形式增量提交；prefill 实例能在 prompt 未完整时合法开始推理（接受 partial context 的质量 trade-off 由应用承担）。
  - **可能失效场景**：检索极快（in-memory HNSW）或 chunk 极大导致单次 prefill 仍主导；需要严格完整 context 才允许生成的 SLO。

- **观察 2**：多租户 streaming 下，**内存是主导瓶颈**——每个请求 growing prompt 占用更多 [[PagedAttention]] block；当 `B · M_KV` 超过 GPU 容量，调度与抢占策略决定 tail latency，而非 streaming 架构本身。
  - **依赖假设**：实验负载的 chunk 到达率、序列长度分布与生产 RAG 相近；80% GPU memory utilization + 20% buffer 能代表常见部署。
  - **可能失效场景**：更大模型、更长 context（32K+）、更高并发或 decode 与 prefill 未 disaggregate 时，瓶颈可能转移到 compute 或网络；论文未测 decode 路径。

- **观察 3**：update mode 下 prompt 频繁替换会使 naive 全量 cache 失效代价极高，但 **longest common prefix (LCP)** 能保留未变前缀的 [[KV-Cache]] block；append mode 下 LCP 通常很长，适合 swap 保留 cache。
  - **依赖假设**：检索系统的更新模式是「替换 suffix 或整体重排但保留部分前缀」，与 LCP 失效语义匹配（论文 Figure 1 动机）。
  - **可能失效场景**：早期 token 频繁变更（LCP≈0）时，update mode 退化为大量 recompute；MCPS 等 progress-based 调度会系统性吃亏（论文 §4.4 已承认）。

- **假设 1**：prefill 与 decode 已 disaggregate，TTFT 优化与 prefill 实例吞吐是独立优化目标。
  - **证据强度**：**中**——与 Splitwise、DistServe 等行业实践一致，但实验只跑 prefill 实例，未端到端验证 disagg 下的系统级 SLO。

- **假设 2**：离线 profile 的 piecewise-linear recompute/swap cost model 在运行时仍近似最优。
  - **证据强度**：**中**——在 H100/H200/A40 上拟合，内存压力 ablation 显示 cost-based 优于纯 swap 或纯 recompute；但实现注明为 idle-system 静态 profile，PCIe 争用时可能漂移。

## 核心方法

STREAM2LLM 基于 **vLLM v0.8.1 / v1 engine** 扩展，面向 streaming prompt 的多租户 prefill serving。

**两阶段调度（回应观察 2）**：将「选谁跑」与「如何拿 GPU block」解耦。Phase 1 用所选策略（FCFS、MCPS、LCAS 等）对未完成请求排序，并做 token budget / block 需求的**可行性分析**，不修改状态、不分配资源。Phase 2 按优先级尝试分配；失败则从低优先级候选中选抢占对象，用 §4.3 cost model 在 **recompute**（丢弃 block、恢复时重算 prefill）与 **swap**（block 迁到 CPU）间择优。这样抢占顺序跟随调度优先级，而非 monolithic loop 里的硬编码 LIFO。

**LCP-based 缓存失效（回应观察 3）**：通过 `is_streaming_prompt`、`is_prompt_update`、`is_streaming_prompt_finished` 等接口区分 append/update。prompt 更新时计算新旧 token 序列的 LCP，仅释放 LCP 之后 block，将 `num_computed_tokens` 设为 LCP 长度；对已 swap 到 CPU 的请求，在 CPU 侧同步失效，resume 时先 swap 回有效前缀再重算后缀。机制与 [[Prefix-Caching]] / [[RadixAttention]] 的静态 prefix 共享不同，针对**动态序列变更**。

**调度策略（回应观察 2 的时间优先级）**：
- **DEFAULT vLLM**：FIFO + LIFO 抢占——忽略 chunk 到达时间，streaming 下在内存压力时 tail 极差。
- **FCFS**：完整请求优先于 partial；两档内仍按到达序。
- **MCPS**：按已算 token 数优先——append 好，update 下 LCP 重置后优先级暴跌。
- **LCAS**：按**最近 chunk 到达时间**优先，append/update 均强，但低频到达请求可能 starvation。

**工作负载与部署**：自采 crawler trace（crawl4ai + SimpleQA，append）与 ANNS trace（FineWeb-edu + DiskANN + AquaPipe 式 recall-aware prefetch，update），在 H100/H200 上测 Llama-3.1-8B-Instruct（TP=2）。

## 设计取舍

- **取舍 1**：扩展 [[vLLM]] 而非自研 engine → 继承 [[PagedAttention]]、[[Continuous-Batching]] 与社区生态，但调度语义受 v1 scheduler 改造边界约束，与 PipeRAG（encoder-decoder cross-attention）不兼容。
- **取舍 2**：LCP 失效实现简单、与 block 粒度对齐，但无法像 radix tree 那样细粒度共享任意子串；频繁 early-token 更新时收益有限。
- **取舍 3**：两阶段调度增加实现复杂度（队列 waiting/running/finished + 失效与抢占顺序），换取策略可插拔；排序开销实测 15–16 µs（50 并发），相对 prefill 可忽略。
- **边界条件**：内存充足时各 streaming 调度器趋同，**智能调度主要在 memory pressure 下才有决定性差异**；QPS 极高时排队延迟主导，scheduler 差异收敛。

## 实验与结果

- **Crawler append**：streaming vs 非 streaming，低负载 median TTFT **3.9–4.3×**，QPS 4.0 时 **10.8–11.0×**；QPS 2 时 FCFS/LCAS P95 比 default streaming 快 **1.44× / 1.32×**，MCPS 降至 **0.73×**。
- **ANNS update**：QPS 1.0 时 P95 TTFT **2.49–2.63×** 于非 streaming；>10% 请求累计失效 **>10,000 tokens** 仍整体更快。
- **吞吐**：trace completion time 各方法相差 **<1%**（Figure 11）。
- **内存压力**（人为放大 chunk delay）：DEFAULT vLLM streaming P99 仅为非 streaming 的 **0.71×（crawler）/ 0.19×（ANNS）**；FCFS+LCAS+cost-based P99 仍快 **8–10×**；crawler 上 cost-based 约 **17–21% swap / 79–83% recompute**，ANNS 几乎全 recompute（**98–100%**）。
- **平台**：H200 141GB / H100 80GB，GPU util 80%，token budget 2048–8192。

## 批判性分析

### 论证链条

观察（检索主导 TTFT、多租户 memory 竞争、两种 prompt 演化）→ 设计（overlap + 两阶段调度 + LCP + cost preemption）→ 结果（TTFT 数量级改善、吞吐持平）链条在 **prefill 实例、Llama-3.1-8B、两条自采 trace** 内基本闭合。薄弱环节：作者将「streaming 必要但不够，需智能调度」主要建立在 **人为制造的 memory pressure** 实验上；默认 H200 配置下 preemption 很少发生，生产是否常处于该压力区需更多 trace 支撑。质量维度（partial context 下的 answer correctness）**完全未测**，论证停留在 latency/throughput 系统指标。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效 |
|------|-----------|----------|
| 多租户 memory 竞争是关键 | 压力实验下 tail 对调度敏感 | 超大 GPU、激进 KV offload、或请求数很少时调度无关 |
| LCP 覆盖主要 update 模式 | ANNS trace 上有效 | Vespa/ES 多阶段 rerank 若重写 system prompt 前缀则 LCP 短 |
| Disaggregated prefill 可孤立优化 TTFT | 实验设定一致 | 端到端 TTFT 还受 decode 排队、KV 传输影响，论文未覆盖 |
| 静态 cost model 足够 | Ablation 优于单一策略 | 多租户 PCIe/NVLink 争用、动态负载下 profile 过期 |

### 实验可信度

**强项**：真实 crawler + DiskANN 管线 trace、append/update 双模式、多 scheduler × eviction ablation、H100/H200 跨硬件、artifact 开源（vLLM 0.8.1 fork + trace）。**弱点**：（1）baseline 是 vanilla vLLM 有无 streaming，未与最新 [[Chunked-Prefill]]/Sarathi-Serve 等静态长 prompt 策略对比；（2）QPS 范围有限（crawler ≤4，ANNS ≤2），距超大规模 serving 有 gap；（3）仅 8B 模型，[[MoE]]/更大 hidden dim 下 KV block 与 swap 成本曲线可能改变 cost model 平衡点；（4）update mode 借鉴 AquaPipe prefetch 但 AquaPipe 无公开实现，难以 apples-to-apples 对比。

### 系统性缺陷

- **正确性与一致性**：LCP 失效保证 KV 与当前 prompt 一致，但未讨论 streaming 过程中**已生成 token** 与后续 prompt 更新的一致性（若允许边检索边 decode，可能存在语义回溯问题）——论文聚焦 prefill 实例，边界未完全澄清。
- **公平性与 starvation**：LCAS 对低频 chunk 请求不保证公平；论文未给出 starvation 量化或 SLA 保障。
- **故障恢复**：swap 到 CPU 的 block 在进程 crash 时如何恢复——**论文未讨论**。
- **可观测性**：提供 QUEUED/SCHEDULED/PREEMPTED 等 event，利于诊断，但未评估 telemetry 对 hot path 的影响（仅报 sorting µs 级）。
- **运维成本**：每 GPU 型号需 ~5 分钟离线 profile 生成 JSON，可接受；但 vLLM 版本升级时 fork 维护成本**论文未讨论**。

## 局限与后续工作

- **局限 1**：仅评估 prefill 实例，decode TPOT、跨实例 KV 传输、端到端 TTFT 未覆盖。
- **局限 2**：无 output quality / retrieval recall 对 streaming 的 trade-off 测量；partial context 下的用户体验仍属应用层假设。
- **局限 3**：LCAS 等策略在极端 update（短 LCP）与低频 append 下存在已知弱点；无自适应 scheduler 选择机制。
- **Future work 1**：在**生产级多租户 trace**（含 tenant 隔离、burst、混合 append/update）上测量 preemption 频率与 P99，验证「memory pressure 是否常态」。
- **Future work 2**：将 cost model 扩展为**在线自适应**（PCIe 争用、NVLink 拓扑），并与 [[RadixAttention]]/更细粒度 invalidation 对比 update mode 下的 recompute 上界。
- **Future work 3**：端到端 disaggregated 部署中测 TTFT + 质量，明确允许「检索未完成即开始 decode」的产品语义边界。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Disaggregation]]、[[Prefix-Caching]]、[[RadixAttention]]、[[Chunked-Prefill]]、[[RAG]]
- **同类系统**：[[vLLM]]、PipeRAG、AquaPipe、[[SGLang]]
- **同会议**：[[MLSys-2026]]
- **对比**：与 CacheBlend 等「静态多 chunk KV 复用」正交——STREAM2LLM 解决 **prompt 随时间动态变化** 的调度与失效，而非固定 chunk 集合的拼接优化
