---
type: paper
name: CoX-MoE
full_title: "CoX-MoE: Coalesced Expert Execution for High-Throughput MoE Inference with AMX-Enabled CPU-GPU Co-Execution"
authors: [Muyoung Son, Yi Chen, Soongyu Choi, Seungjae Yoo, Joo-Young Kim]
venue: DAC
year: 2026
tags: [llm-inference, moe, cpu-gpu, amx, expert-offloading, throughput]
source_pdf: "[[arxiv26-cox-moe.pdf]]"
source_md: "[[arxiv26-cox-moe]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CoX-MoE：通过启用 AMX 的 CPU-GPU 协同执行进行高吞吐量 MoE 推理的合并专家执行（DAC 2026）

> **原题**：CoX-MoE: Coalesced Expert Execution for High-Throughput MoE Inference with AMX-Enabled CPU-GPU Co-Execution

> **一句话总结**：CoX-MoE 的核心观察是 throughput-oriented [[MoE]] inference 里 micro-batching 虽然省显存，却会把 expert GEMM 打碎成 memory-bound 小任务；它用 AMX-enabled CPU-GPU co-execution、coalesced expert execution 和 expert-aware stratification 重新分配 attention / expert 的显存与计算，最终在 Mixtral、DeepSeek、Qwen3 上相对 MoE-Lightning 提升 1.7-2.4x throughput，相对 FlexGen 提升 3.4-7.1x。

## 问题与动机

CoX-MoE 解决的不是交互式低延迟 serving，而是 offline benchmarking、大规模数据处理、synthetic data generation 这类大 batch、高吞吐 [[MoE]] inference。这个场景的难点是显存同时被三类对象挤压：MoE expert 权重、attention / FFN 中间激活、以及 decode 过程增长的 [[KV-Cache]]。论文用 Mixtral-8x22B 举例：BF16 权重约 282 GB，batch 64、prompt 4096 又会产生约 72 GB intermediate data，总 footprint 约 350 GB，远超单张 80 GB GPU。

传统 offloading 系统通常把大 batch 切成 micro-batches，降低瞬时 activation 占用，并让同一份 expert 权重在多个 micro-batch 间复用。这对 dense model 或普通 layer offload 是合理的，但 MoE expert 本来就只收到稀疏 token；再切 micro-batch 会让每个 expert 的输入更小，operational intensity 下降，expert computation 从 compute-bound 掉到 memory-bound。

另一条路线是 CPU-assist：把部分计算放到 CPU，少搬 expert 权重。但既有方案多依赖 AVX，主要关注 decode-stage attention 的 GEMV，难以承担 prefill / batch inference 中的 expert GEMM。CoX-MoE 的判断是 Intel AMX 已经把 CPU BF16 matrix throughput 推到足够高的量级，CPU 可以成为真正的 MoE co-execution device，而不是 host memory 的附属搬运路径。

## 关键观察 / 隐含假设

- **观察 1：micro-batching 会把 expert execution 推进 memory-bound 区域。** 论文在 Qwen3-30B-A3B、RTX 6000 Ada、Xeon Platinum 8452Y 上 profile batch 128/256/512、prompt length 512，发现 expert computation 占总 latency 超过 97.5%；当 micro-batch size 从 256 降到 128、64、32 时，expert latency 近似按 2.06x、1.68x、2.09x 继续放大，而 non-MoE latency 基本稳定。
  - **依赖假设**：workload 是大 batch throughput inference，full batch 下每个 expert 能拿到足够 token，使 coalescing 真的提高 arithmetic intensity。
  - **可能失效场景**：interactive serving、batch 很小、router 分布极端稀疏、或 expert 本身已经足够大时，coalescing 的收益会下降，甚至会增加排队和 buffering 成本。
- **观察 2：attention intermediate data 是专家驻留显存的主要敌人。** 在论文的 GPU attention baseline 中，prefill attention 相关 intermediate data 占 VRAM partition 的 84.6%，expert weights 只能拿到 11.5%；把 attention offload 到 AMX CPU 后，expert weights 可用 partition 扩到 58.5%，虽然 attention latency 上升，但总 inference latency 下降约 40%。
  - **依赖假设**：AMX CPU 的 attention / projection GEMM 足够快，并且多放 expert 到 VRAM 带来的收益大于 CPU 执行和 PCIe activation movement 的额外开销。
  - **可能失效场景**：GPU HBM 很充足、CPU 没有 AMX、CPU 被其他 workload 争用、或 CPU-GPU 互连从 PCIe 变成 NVLink-C2C / unified memory 后，attention offloading 的最优点会改变。
- **观察 3：expert offload 同时受 PCIe 带宽和 CPU/GPU 算力不对称约束。** 论文的 roofline 图把 PCIe expert transfer 标成约 32 GB/s，而 CPU DDR5 memory bandwidth 约 300 GB/s；AMX BF16 峰值约 144 TFLOPs/socket，虽然远强于 AVX-512，但仍低于 RTX 6000 Ada 约 364 TFLOPs。简单把 expert 丢给 CPU 会把瓶颈从 GPU 转到 CPU。
  - **依赖假设**：roofline 模型能近似反映真实 kernel、PCIe transfer、activation/KV movement 的相对成本。
  - **可能失效场景**：NUMA 访问、AMX kernel 达不到理想利用率、PCIe 与 GPU kernel overlap 不稳定、或多租户 CPU 争用都会让静态搜索结果偏离运行时最优。
- **假设 1：expert activation skew 可以用小样本 probing 预测。** Fig. 3(c) 显示 BIG-Bench Hard 上某层 expert workload 高度不均，单个 expert 的 token allocation 可比另一些 expert 高 4515x；Fig. 8 进一步显示 EAS 在 VRAM 只能容纳有限 expert 时，比 random selection 高约 40% expert hit ratio。
  - **证据强度**：中。论文在 CoQA、MBPP、DeepSeek、Qwen3 上展示了趋势，但还没有证明跨 domain、长时间运行、混合 workload 下 activation map 的稳定性。
- **假设 2：整批 workload 事先可见，EAS 的预分析成本可以摊销。** EAS 需要 input embedding、clustering、prototype selection 和 prefill-only probing，这天然适合 offline batch inference。
  - **证据强度**：中。论文把目标场景限定在 throughput-oriented batch inference，这个假设合理；但没有充分量化 EAS preprocessing/probing 的 wall-clock 成本与 amortization threshold。

## 核心方法

CoX-MoE 的第一层抽象是 coalescing-aware orchestration。它把一个 decoder layer 拆成四个 operation units：QKV projection、attention、output projection、以及 expert FFN。前三个 non-MoE operation 可以继续按 micro-batch 调度，但 expert FFN 必须对整个 batch 做 coalesced execution，再在 CPU 和 GPU 之间并行切分。这直接回应观察 1：不要为了省显存把最主要的 expert GEMM 切碎。

第二层是 unified allocation strategy。系统联合搜索两类决策：一类是 QKV projection / attention / output projection 放 CPU 还是 GPU；另一类是 expert placement，把 expert 分成 GPU-resident experts、host-resident 但可 paged 到 GPU 的 migrant experts、以及 CPU-bound experts。搜索目标是最小化 per-layer latency，成本模型包含 operand load、compute roofline、[[KV-Cache]] store、VRAM budget 和 PCIe transfer。这里的关键不是某个单点 offload policy，而是把 compute allocation 和 expert allocation 绑在一起求解。

attention offloading 是这个 unified strategy 里最反直觉的一步。传统直觉是 attention 留 GPU、expert 权重 offload；CoX-MoE 反过来指出，在大 batch prefill 中 attention intermediate data 会挤掉大量 expert residency。把 attention 或 projection 移到 AMX CPU 上，可能让更多 hot expert 常驻 VRAM，从而减少 expert transfer 和 CPU overload。这个设计回应观察 2，但也把系统收益绑定到 AMX CPU、PCIe 拓扑和 batch shape。

第三层是 strategy-aware micro-batch determination。CoX-MoE 不再问“全模型应该用多大的 micro-batch”，而是只为 non-MoE operations 选择 micro-batch size；expert operation 的 micro-batch size 被固定为 full batch。这是一个很重要的接口简化：micro-batch 从全局执行粒度变成局部资源管理工具，避免它伤害 expert arithmetic intensity。

Expert-Aware Stratification（EAS）负责在 inference 前决定哪些 expert 值得预放进 GPU。流程是：为全部输入生成 embedding，聚类得到 strata，按比例选 prototype，只对 prototype 做 prefill-only probing，近似得到全局 expert activation map，再把高频 expert 放进 VRAM、低频 expert 留给 CPU/host 路径。EAS 的意义不是改变 router 决策，而是让 placement 更接近这一批数据的真实 expert 热度。

实现上，作者扩展 Intel Extension for PyTorch（IPEX），让 AMX CPU kernel 可以和 NVIDIA GPU 协同执行；同时使用细粒度共享 CUDA streams、buffer sharing 和 transfer/compute overlap，减少 CPU-GPU pipeline 的空洞。论文没有把实现复杂度完全展开，但从这个描述看，CoX-MoE 更接近一个异构 runtime，而不是单纯的调度公式。

## 设计取舍

- **coalesced expert execution 换取更高 arithmetic intensity。** 收益是减少 micro-batch 对 expert GEMM 的破坏；代价是需要在 layer 内聚合 batch、协调 CPU/GPU 并行执行，可能增加 buffering、同步和在线请求排队。
- **attention offloading 换取 expert residency。** 收益是释放 VRAM 给 expert weights；代价是 attention/projection 的 activation movement 和 CPU compute latency 会变成新瓶颈，特别依赖 PCIe、AMX kernel、batch shape 和 sequence length。
- **静态 EAS 换取低 PCIe expert transfer。** 收益是用 workload-aware placement 提高 expert hit ratio；代价是需要 workload 事先可见，并且 activation distribution 一旦漂移，静态 placement 会变脆。
- **roofline 搜索换取简单可解释的策略空间。** 收益是实现上相对直接，能把 VRAM/PCIe/compute 放进同一个目标函数；代价是 tail latency、runtime interference、NUMA、kernel launch overhead、CPU cache pressure 等因素未必被准确建模。
- **单机 CPU-GPU 协同换取低显存可用性。** CoX-MoE 针对 resource-constrained single-GPU throughput inference 很清楚；但这也意味着结论不自动外推到多 GPU expert parallel serving、NVLink-rich server、或 cloud production scheduler。

## 实验与结果

- **profile 结论**：Qwen3-30B-A3B 在 RTX 6000 Ada + Xeon Platinum 8452Y 上，expert computation 占 E2E latency 超过 97.5%；micro-batch 变小会让 expert latency 近似翻倍，而 non-MoE computation 基本不变。
- **attention offloading 结论**：GPU attention baseline 中 intermediate data 占 VRAM partition 84.6%、expert weights 只有 11.5%；CPU attention 把 expert weights partition 扩到 58.5%，总体 latency 降低约 40%。
- **主结果设置**：平台包括 Xeon Platinum 8452Y + RTX 6000 Ada 48 GB PCIe 4.0、A100 80 GB PCIe 4.0、H100 80 GB PCIe 5.0；模型包括 Mixtral-8x7B-Instruct、DeepSeek-V2-Lite、Qwen3-30B-A3B；baseline 是 FlexGen 和 MoE-Lightning；主图 batch size 为 1024，覆盖 input length 97/800 与 output length 32/256。
- **主结果**：CoX-MoE 相对 MoE-Lightning 达到 1.7-2.4x throughput，相对 FlexGen 达到 3.4-7.1x；论文总结平均相对 SOTA 高 2.0x throughput。Mixtral 上提升最大，作者解释为 Mixtral hidden dimension 更大，decode-stage attention 对 PCIe transfer 更敏感，因此 CoX-MoE 的 attention/projection offload 更有效。
- **EAS 结果**：当 VRAM 只能容纳有限 expert（DeepSeek 最多约 30 个、Qwen3 最多约 50 个）时，EAS 比 random selection 高约 40% expert hit ratio；hit ratio 提升进一步带来 1.47-1.50x throughput improvement。
- **ablation**：以 System I 上 Qwen3、MoE-Lightning baseline、input length 1320、output length 128 为例，baseline 为 16.8 tokens/s；加入 coalesced expert micro-batch + AMX expert co-execution 后到 25.5 tokens/s（1.51x）；再加入 attention offloading 到 32.3 tokens/s（1.26x incremental）；加入 80% expert hit ratio 的 EAS 后到 34.1 tokens/s（1.05x incremental）。

## 批判性分析

### 论证链条

这篇的论证链条相当清楚：micro-batching 降低 expert arithmetic intensity，所以要 coalesce expert；attention intermediate data 挤压 expert residency，所以 attention offloading 可能比 expert weight offloading 更划算；expert activation skew 明显，所以 static placement 可以减少 PCIe transfer。三个 observation 都直接映射到设计，没有把一个孤立优化硬包装成完整系统。

最有价值的 conceptual shift 是它质疑了 offloading 系统里“micro-batch is always helpful”的默认前提。对 MoE batch inference 来说，micro-batch 不是纯粹的内存优化，它会改变 expert GEMM 的算术强度，进而改变瓶颈性质。这个 insight 比单个 2x speedup 更值得记。

但论文对“optimal”的表述需要保守理解。搜索策略依赖 roofline、VRAM budget 和 PCIe 模型；真实运行中，AMX kernel efficiency、NUMA、CPU background load、CUDA stream overlap、kernel launch 和 memory allocator 行为都可能让实际 optimum 偏离模型。论文证明了该策略在三种 GPU 和三种 MoE model 上有效，但还没有证明它是跨部署环境的稳定最优。

### 假设压力测试

CoX-MoE 最强的场景是整批输入事先可见、batch size 很大、GPU 显存不足以同时容纳 activation 和 hot experts、CPU 有 AMX 且没有被其他服务争用。如果这些条件成立，coalesced expert execution 和 EAS 的收益都很自然。

最脆的假设是 workload stationarity。EAS 的 expert map 来自 embedding clustering 和 prototype probing；如果线上请求来自多个 domain、batch 由 scheduler 临时拼接、或 prompt distribution 在运行中变化，static placement 可能迅速退化。论文展示了 CoQA/MBPP 等 benchmark 上的 hit ratio，但没有给出跨 workload shift 或 long-running trace 的结果。

第二个压力点是硬件代际。PCIe 4.0 的 32 GB/s 是 CoX-MoE 设计成立的重要背景；在 GH200/NVLink-C2C、CXL memory pool、unified memory、或 HBM 容量更大的 GPU 上，attention offloading 和 expert residency 的 tradeoff 会重新洗牌。反过来，如果 CPU 没有 AMX，或 AMX 与 host memory bandwidth 被其他任务争抢，CPU-GPU co-execution 也可能不再平衡。

### 实验可信度

实验覆盖 Mixtral、DeepSeek、Qwen3 以及 RTX 6000 Ada/A100/H100，说明结果不只是单模型单硬件偶然现象；baseline 选择 FlexGen 和 MoE-Lightning，也覆盖了经典 single-GPU offloading 与较新的 MoE batch inference pipeline。ablation 把 coalescing、attention offload、EAS 拆开，能看到最大收益来自 coalesced expert + AMX co-execution，这支持论文主 claim。

不足是 baseline 边界偏窄。论文相关工作提到 Fiddler、HybriMoE、[[KTransformers-SOSP25|KTransformers]] 等 CPU-GPU hybrid MoE 路线，但主实验没有直接比较这些系统。CoX-MoE 可以说自己优于 FlexGen/MoE-Lightning 这类 throughput offloading baseline，但“相对所有 MoE CPU-GPU co-execution 系统的 SOTA”还需要更完整对照。

另一个缺口是 preprocessing 成本和 tail behavior。EAS 需要 embedding、clustering、prototype probing，论文主要报告 hit ratio 与 throughput，没有把预分析耗时、batch size amortization threshold、或 distribution shift 后重跑成本讲透。系统指标也集中在 throughput，缺少 tail latency、CPU utilization、energy/cost、multi-tenant 干扰等 production 指标。

### 系统性缺陷

CoX-MoE 的实现复杂度不低：要扩展 IPEX 支持 NVIDIA GPU interoperability，还要协调 AMX CPU kernels、CUDA streams、activation/KV movement、expert placement 和 pipeline overlap。这些都是能影响可维护性和可观测性的系统边界，论文只给了概述，没有讨论 debug、fallback、failure recovery 或 deployment automation。

资源隔离也未被充分讨论。CoX-MoE 把 CPU 从控制面/host memory 角色提升为关键 compute device，这意味着 CPU core、LLC、DDR bandwidth、NUMA locality 都会进入 serving critical path。若同机还有 tokenization、networking、scheduler、storage I/O 或其他 inference job，AMX co-execution 的稳定性需要重新验证。

正确性层面，CoX-MoE 没有近似 router 或跳过 expert，所以理论上不改变模型输出；EAS 只是决定 expert 放在哪里，miss 时仍可走 CPU/host 路径。但论文没有把 placement miss 的尾部代价、dynamic fallback 路径、或极端 expert imbalance 下的 SLO 影响展开。

## 局限与后续工作

- **局限 1：目标 workload 较窄。** 论文明确面向 throughput-oriented batch inference；对 interactive serving、小 batch、多租户 request mixing、以及 production trace 的覆盖不足。
- **局限 2：EAS 的稳定性还没有被充分压力测试。** 需要在 domain shift、混合任务 batch、长时间运行 trace 下测量 expert activation map 的老化速度，以及何时值得重新 probing。
- **局限 3：硬件结论绑定 AMX + PCIe。** CoX-MoE 的 tradeoff 需要在 NVLink-C2C、CXL、larger-HBM GPU、dual-socket NUMA、以及无 AMX CPU 上重新刻画。
- **局限 4：系统指标偏 throughput。** 论文缺少 tail latency、energy per token、CPU/GPU utilization under contention、scheduler fairness、failure recovery 和 observability 成本。
- **Future work 1：在线自适应 expert placement。** 用运行时 router statistics 更新 EAS map，机器可验证指标是 distribution shift 后的 hit ratio、throughput、fallback latency 与 probing overhead。
- **Future work 2：把 [[KV-Cache]] placement 和 expert placement 联合优化。** CoX-MoE 主要讨论 attention offload 释放 VRAM；下一步可以把 KV cache、expert weights、activation buffer 作为统一内存对象，在不同 context length 和 output length 下搜索 Pareto frontier。
- **Future work 3：跨互连拓扑复现实验。** 在 PCIe 4/5、NVLink-C2C、CXL memory expansion、multi-GPU expert parallelism 下复现同一 workload，检验 CoX-MoE 的 observation 哪些是 MoE 固有，哪些只是 PCIe-era artifact。
- **Future work 4：和 CPU-GPU hybrid MoE 系统直连对比。** 尤其需要与 Fiddler、HybriMoE、[[KTransformers-SOSP25|KTransformers]] 这类 CPU expert execution 系统在相同模型、batch、hardware 上比较，区分 coalescing-aware orchestration 和 AMX kernel engineering 各自贡献。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Expert-Parallelism]]
- **同类系统 / 论文**：[[MOE-INFINITY-arXiv24]]、[[KTransformers-SOSP25]]、[[ContextAwareMoE-CXLNDP-arXiv25]]、[[OD-MoE-arXiv25]]、[[FluxMoE-arXiv26]]、[[FlexGen]]、[[MoE-Lightning]]
- **同会议**：[[DAC-2026]]
- **对比**：[[MOE-INFINITY-arXiv24]] 偏 personal-machine expert cache，[[OD-MoE-arXiv25]] 偏 prediction-driven cacheless offload，[[ContextAwareMoE-CXLNDP-arXiv25]] 偏 CXL-NDP cold expert compute；CoX-MoE 的独特点是 batch throughput 场景下把 expert micro-batch coalescing 和 AMX CPU-GPU co-execution 绑成一个 orchestration problem。
