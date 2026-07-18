---
type: paper
name: LayeredPrefill
full_title: "From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill"
authors: [Gunjun Lee, Jiwon Kim, Jaiyoung Park, Younjoo Lee, Jung Ho Ahn]
venue: MLSys
year: 2026
tags: [llm-inference, moe, scheduling, chunked-prefill, energy-efficiency]
source_pdf: "[[02e74f10e0327ad868d138f2b4fdd6f0.pdf]]"
source_md: "[[02e74f10e0327ad868d138f2b4fdd6f0]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill (MLSys 2026)

> **一句话总结**：在 [[MoE]] + 长 prompt 的 co-located serving 里，[[Chunked-Prefill]] 的小 chunk 会触发 sparsity erosion（hybrid batch 激活大量 expert 却达不到 ridge point），论文把调度轴从 token 换成 layer group——每 iteration 仅一个 group 同时做 prefill+decode——消除跨 chunk 的 expert 权重重载（traffic 最多 **-39%**），TTFT 最多降 **70%**、端到端延迟降 **41%**、每 token 能耗降 **22%**，SLO attainment 可持续 request rate 比 chunked prefill 高 **14–45%**。

## 问题与动机

生产 LLM serving 要同时满足 TTFT 与 TBT 两类 SLO，并在固定算力/内存/互联预算下最大化吞吐。[[Continuous-Batching]]（[[Orca-OSDI22]]、[[vLLM]]）把调度粒度降到 iteration 级，让新请求的 prefill 与进行中请求的 decode 交错，显著改善吞吐与 TTFT。但长 prompt 时代，单次大 prefill 仍会在一个 iteration 内独占算力，decode batch 被 stall，触发 TBT SLO 违规。

[[Chunked-Prefill]]（[[SARATHI-arXiv23]] / Sarathi-Serve）把 prompt 沿 token 维切成小 chunk（常见 256/512），每 iteration 处理一个 chunk 并与 decode 混跑，恢复 stall-free decoding。这对 dense 模型很有效，却在 [[MoE]] 上暴露结构性代价：每个 chunk 都要穿过**全部** transformer 层，每层重复加载 expert 权重。为守 TBT SLO 必须把 chunk 压得很小，导致 routed-to-expert 的 token 数远低于现代 accelerator 的 ridge point（约 100–300 Op/B），MoE 层彻底 memory-bound——论文称之为 **sparsity erosion**：chunking 扩大了 expert coverage、压制了 reuse，反而吃掉 MoE 的稀疏收益。

作者在 Qwen3-30B-A3B 上量化这一两难：chunk 512→2048 时 prefill 能耗/token 从 60→32 mJ（**-46%**）、可持续 request rate 1.3→2.6 req/s，但 p99 TBT 从 48→129 ms 超 SLO。也就是说，chunked prefill 在 MoE 上把「stall-free TBT」与「高效 expert 加载」绑死在互斥 trade-off 上。Layered Prefill 的核心 claim 是：不必在 token 维切 prefill，改在 **layer 维**分布 prefill 工作量，即可同时保住 stall-free decode 并消除冗余 expert traffic。

## 关键观察 / 隐含假设

- **观察 1：SLO 合规的 decode batch 很小，纯 decode 时 MoE 的稀疏激活是优势；chunked prefill 的 hybrid batch 会逆转这一点。** 在 SLO attainment >90% 时，arXiv workload 平均 decode batch ≤32、ShareGPT ≤128（Fig. 3）。Table 1 显示 batch 32 时仅约 55% expert 被加载，batch 128 约 86%——decode 侧 limited activation 降低 memory traffic。但 chunked prefill 的 hybrid batch 常 >256，激活几乎全部 expert，同时 per-expert token 数仍不足以饱和 compute。
  - **依赖假设**：评测 trace（ShareGPT、arXiv Summarization）与 Poisson 到达能代表 co-located MoE serving 的 operating point；TBT SLO 按 prior work 惯例设为「32 decode batch @4096 tokens 处理时间的约 5×」。
  - **可能失效场景**：[[Disaggregation]] 把 prefill/decode 分到不同 GPU 后，hybrid batch 形态改变，sparsity erosion 机制可能弱化；dense 模型或 expert 数很少的 MoE 上 expert reload 不是主导瓶颈；极高并发下 decode batch 本身已足够大，chunk 与 layered 差距会缩小。

- **观察 2：MoE prefill 的 kernel 时间对 chunk size 高度敏感，小 chunk 让 MoE weight load 占 prefill runtime 过半。** 固定 8192 token 输入的微基准（Fig. 2）显示 chunk 512 时 MoE runtime >50% prefill、总 prefill >500 ms；chunk 增至 4096–8192 后 MoE load <100 GB、prefill ~200 ms。权重加载开销近似与 chunk 数成反比。
  - **依赖假设**：prefill 路径上 attention/FFN 开销相对 MoE reload 次要；H100 + bfloat16 + [[Flash-Attention]]-3 的实现与生产栈可比。
  - **可能失效场景**：量化/压缩 MoE、expert 常驻 SRAM、或 [[Expert-Parallelism]] 改变 load 模式时，「每层每 chunk 重载 expert」的代价模型需重测；极短 prompt（G=1）时 layered 与 chunked 几乎等价。

- **观察 3：长 prompt、高 prefill-to-decode 比的 workload 上，chunk 数增多会放大 chunked prefill 的退化，layered prefill 收益更大。** arXiv（输入约为输出的 40×）相对 ShareGPT（约 6×）在 SLO gap、expert-load reduction（39% vs 12%）、TTFT 改善上均更显著。
  - **依赖假设**：输出长度分布稳定，瓶颈主要在 prefill 侧 memory traffic 而非 decode 排队或 [[KV-Cache]] 容量。
  - **可能失效场景**：agent 式长 generation、speculative decoding、或多轮对话让 decode 阶段主导时，论文观察的 prefill-heavy 假设变弱。

- **假设 1：decoder-only Transformer 各层同质、顺序执行，可把「连续 layer group」当作合法调度单元，且 partial prefill 的 [[KV-Cache]]/activation 状态可正确跨 iteration 衔接。**
  - **证据强度**：中。论文在 [[vLLM]] 上实现并报告 end-to-end SLO/能耗，但未展开跨 group 的 KV 生命周期、pipeline bubble、或与 [[PagedAttention]] 交互的细节。

- **假设 2：co-located 单机（2×H100 + [[Tensor-Parallelism]]）结论可外推到「同一类」多 GPU 工厂，暂不需 disaggregation。**
  - **证据强度**：弱。论文明确把 multi-GPU 复杂环境与 adaptive grouping 留给 future work，未测跨节点或 PD 分离。

## 核心方法

**Layered Prefill** 把调度轴从 token 换成 layer：将 decoder stack 纵向切成 G 个连续 **layer group**，遵循 **one-group-per-iteration** 规则——每 iteration 恰好一个 designated group 对新到达请求执行 prefill 并与全部进行中请求 decode，其余 group 只做 decode。prefill 按 group 逐步推进，G 次 iteration 后完成整条 prompt 的 prefill，全程 decode 不 stall。

相对 [[Chunked-Prefill]]「每层过 ⌈L/chunk_size⌉ 遍」，layered 保证**每层只遍历 prompt 一次**，从机制上消除跨 chunk 的 redundant MoE weight reload。decode 永不阻塞，因为每个 iteration 所有 group 都参与 decode，TBT 维持 stall-free。

**与 chunked prefill 正交**：token 维 chunk 与 layer 维 group 可同时使用。组合后可用更大 chunk（减少 chunk 数、让 per-expert batch 越过 ridge point 进入 compute-bound），同时 layered 仍分布 iteration 工作量以守 TBT。作者引用 Chunked Pipeline Parallelism（Mitra et al., 2025）说明长输入场景下 chunk+layer 的互补性。

**Group 数选择**：`G(L) = max(1, ⌈L/512⌉)`，使每 iteration 的 prefill 工作量近似对齐 chunked prefill（chunk size=512）的 per-iteration 预算，便于公平对比。例如 L=8192→G=16，L=512→G=1。多个短请求可合并 batch。实现基于 [[vLLM]]，attention 用 [[Flash-Attention]]-3，大量 custom CUDA kernel + `torch.compile`，并用 CUDA Graph 加速 prefill/decode。

## 设计取舍

- **layer 调度 vs token 调度**：赢得 MoE memory traffic 与能耗，代价是实现与调度状态机复杂度上升——需跟踪每个请求处于哪个 layer group 的 partial prefill，并与 [[Continuous-Batching]] 的动态 batch 合并交互。论文未量化软件开销或调度器 CPU 成本。

- **固定 G∝L/512 对齐 vs 自适应分组**：对齐 chunked 512 利于实验隔离，但 512 是任意常数；不同 TBT SLO、模型深度、或 attention/FFN 与 MoE 耗时比变化时，最优 G 可能非线性。论文承认 layer count 不能被 G 整除时需额外策略，未给出生产 policy。

- **stall-free TBT 优先 vs 最大 prefill 吞吐**：one-group-per-iteration 限制每步最多一个 group 做 prefill，长 prompt 的 TTFT 被摊到 G 步；相比「偶尔允许大 chunk 独占 iteration」更稳 TBT，但单请求 prefill 并行度低于一次性全层 prefill。

- **边界条件**：在 **MoE + 长 context + co-located + 紧 TBT SLO** 下最优雅；dense 模型收益主要来自与 chunked 等价的 iteration 切分，无 expert reload 红利。极短 prompt（G=1）退化为近似传统混跑。极高 request rate 下（GPT+ShareGPT）两者都可能 TBT 违规，但 layered 的 TTFT 崩溃点更晚。

## 实验与结果

**设置**：2× NVIDIA H100 80GB（NVLink）、[[Tensor-Parallelism]]；Qwen3-30B-A3B（128 experts, top-8）与 GPT-OSS-20B（32 experts, top-4）；ShareGPT 与 arXiv Summarization；Poisson 到达；GPU 能耗经 NVML 差分测量。Baseline 为 chunk size=512 的 chunked prefill。

- **SLO attainment**（90% 阈值，Fig. 3）：layered 可持续 request rate 比 chunked 高约 **14–45%**。Qwen+arXiv：chunked 在 1.5 req/s 崩溃，layered 维持到 1.7+；Qwen+ShareGPT：4.4 vs 4.8 req/s；GPT+arXiv：2.3 vs 2.7 req/s；GPT+ShareGPT：6.2 vs 6.4+ req/s。
- **SLO 分解**（Fig. 4）：两者 TBT attainment 均近 100%；layered 主要在 **TTFT** 上更宽 operating region。chunk 512→1024 降低 TTFT 但拉长 iteration、恶化 TBT，总 SLO 反而下降。
- **延迟**（Table 6, Fig. 5）：Qwen+arXiv @1.3 req/s，单请求端到端 9.4→5.5 s（**-41%**）；同等 rate 下 mean TTFT 最多降 **>70%**（GPT）。
- **Expert-load traffic**（Table 7，100 请求）：ShareGPT **-12%**，arXiv **-39%**。
- **能耗与容量**（Table 8，各 scheduler 在 SLO 内最高 req/s）：Qwen 1.3→1.6 req/s（+23%），能耗/token 56.6→44.2 mJ（**-22%**）；GPT 2.1→2.7 req/s（+29%），37.4→29.8 mJ（**-20%**）。同 rate 下能耗仍降 8–9%。
- **微基准**（Fig. 2）：8192 token 输入上 MoE load 与 chunk size 近似反比，解释端到端收益机制。

## Critical Analysis

### 论证链条

论文链条清晰：**测量** chunked prefill 在 MoE 上造成 sparsity erosion 与 memory-bound prefill → **机制** 每层每 chunk 重复 traverse 导致 expert reload 放大 → **设计** layer group 保证每层只 prefill 一次且 one-group-per-iteration 保 stall-free → **结果** expert traffic、TTFT、能耗、SLO attainment 同步改善，且长 prefill workload 上效应更强。

最强证据是 microbenchmark（Fig. 2）与 expert-load counter（Table 7）对机制的直接支持，而非仅报端到端数字。将 G 对齐 512-token chunk 也尽量隔离了「每 iteration 工作量」混淆，使对比指向调度轴本身。

薄弱环节在于：论文把「chunked prefill 对 MoE 低效」外推为「应用 layered prefill 即可显著改善 MoE serving」，但实验仅覆盖两种 MoE、两种数据集、单机 TP、co-located 路径——未证明对 dense 模型、disaggregated serving、或不同 expert 规模/路由策略普适。

### 假设压力测试

**Workload**：收益随 prefill-to-decode 比升高而放大；若生产流量以短 prompt、长 generation 或多模态为主，TTFT/预填充 expert traffic 可能不是第一瓶颈。Poisson 到达未建模 burst、优先级租户或 prefix cache 命中，可能改变 batch 分布与 SLO 交互。

**硬件**：H100 ridge point 与 memory bandwidth 是分析核心；迁移到 TPU、AMD、或更新一代 GPU 时，memory-bound vs compute-bound 分界移动，小 chunk 的惩罚可能减轻。论文能耗只计 GPU device（NVML），未单独核算 NVLink 或 host 侧开销。

**部署**：全文假设 prefill 与 decode 共享同一组 accelerator。若采用 [[Disaggregation]]、独立 prefill cluster 或 expert 跨卡 [[Expert-Parallelism]]，layer-group 调度需跨设备协调，论文 future work 已承认但未验证。与 [[Prefix-Caching]]、speculative decoding、multi-LoRA 等特性的组合也未测试。

**模型**：仅 top-k routed MoE；若 routing 极不均匀、shared expert、或 Mamba/SSM 混合架构，「层同质、顺序 prefill」假设可能不成立。

### 实验可信度

优点：baseline 是业界广泛采用的 chunked prefill@512；指标覆盖 SLO attainment 分解、tail latency、能耗、microbenchmark；两种 MoE + 两种长度特性数据集形成一定泛化。

限制：**无 disaggregated / 多机 baseline**（如 DistServe、Splitwise、Pod-attention 等），难以判断 layered 相对「架构级」方案的位置。SLO 阈值沿用文献惯例，对具体产品 SLO 的敏感性未做 sweep。GPT+ShareGPT 极高负载下两者都出现 TBT 违规，说明瓶颈会转向 decode batch 膨胀，而非仅 prefill scheduling。

实现基于修改版 [[vLLM]]，但缺少调度器开销、CUDA Graph 捕获失败场景、或极端并发下内存碎片等工程指标。Expert-load counter 是自定义字节累计，与真实 HBM 流量可能存在 cache residency 差异。

### 系统性缺陷

- **Partial prefill 正确性与隔离**：跨 iteration 的 per-layer KV 与中间 activation 一致性、与 [[PagedAttention]] block 分配/释放的交互，论文几乎未讨论；多租户场景下 partial state 是否增加隔离与调试难度，论文未覆盖。
- **尾延迟与公平性**：报告 mean/p99 TTFT/TBT，但未深入分析 layered 是否引入新的排队不公平（例如新请求需等 G 步才完成 prefill，是否影响短请求或 head-of-line）。
- **可观测性与运维**：layer-group 状态使 iteration 内 workload 异构（不同 group 混 prefill/decode），profiling、日志归因、故障定位可能更复杂；论文未讨论。
- **故障恢复**：worker 重启时 partial prefill 请求如何恢复，论文未讨论。
- **与 chunk 组合时的最优策略**：正交性提出了设计空间，但未给出自动选择 G、chunk size、或二者组合的 policy。

## 局限与 Future Work

- **局限 1**：评估限于 2×H100 单机 TP、两种 MoE、co-located serving；multi-GPU、跨节点、PD 分离场景未验证。
- **局限 2**：`G=⌈L/512⌉` 为实验对齐手段，非 workload-aware 最优策略；层数不能被 G 整除时的处理仅一笔带过。
- **局限 3**：未与 disaggregation、speculative decoding、prefix cache 等生产特性联合评估；dense 模型与非 MoE 稀疏结构收益不明。
- **局限 4**：能耗与 tail latency 之外的运维成本（实现复杂度、可观测性、故障恢复）论文未量化。

- **Future work 1**：在 multi-GPU / disaggregated 环境测量 layered prefill 的 cross-device KV 与 expert 放置开销，并与 PD 分离 baseline 做 TTFT–TBT–能耗三维 Pareto 对比。
- **Future work 2**：基于实时 queue depth、prompt 长度分布、TBT slack 与 MoE arithmetic intensity **自适应**选择 G 与 chunk size，用 production trace 验证是否优于固定 `L/512`。
- **Future work 3**：量化 partial prefill 下的 KV 内存峰值、调度器 CPU 开销与 CUDA Graph 兼容性，明确相对 chunked prefill 的工程 tax。
- **Future work 4**：扩展到层数非均匀、非同质 block（如 early exit、MoE 仅部分层）时的 grouping 策略与正确性边界。

## 相关

- **相关概念**：[[Chunked-Prefill]]、[[MoE]]、[[Continuous-Batching]]、[[KV-Cache]]、[[Flash-Attention]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、[[SARATHI-arXiv23]]、[[Orca-OSDI22]]、Sarathi-Serve、Chunked Pipeline Parallelism
- **同会议**：[[MLSys-2026]]
- **对比**：layered prefill 直接挑战 [[Chunked-Prefill]] 在 [[MoE]] 上的默认有效性；与 [[LAPS-MLSys26]]、[[TriInfer-MLSys26]] 等同会工作同属「重构 prefill 调度轴」脉络，但 layered 聚焦 co-located MoE memory traffic，而非 length disaggregation 或多模态 PD
