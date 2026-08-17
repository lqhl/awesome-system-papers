---
type: entity
kind: system
aliases: [vLLM]
status: active
last_updated: 2026-08-17
tags: [llm-inference, serving, paged-attention]
---

# vLLM

> vLLM 是以 [[PagedAttention]] 和按迭代动态组批为基础的开源大模型推理系统；它既提供可直接部署的服务引擎，也是后续内存、调度、通信和内核研究最常用的集成底座与强基线之一。

## 是什么

vLLM 最初要解决的不是 Attention 算力不足，而是在线生成时 [[KV-Cache]] 的显存利用率太低。[[vLLM-SOSP23]] 测得，连续预分配方案只有 20.4%–38.2% 的 KV 显存真正保存了 token 状态。PagedAttention 把每条序列切成固定 token 数的逻辑块，用 block table 映射到任意物理块；请求只在需要时申请新块，最后一个未填满的块是主要内部碎片。parallel sampling、beam search 和公共 prompt 还可通过引用计数与写时复制共享物理块。

运行时采用 [[Continuous-Batching|连续组批]]：每轮 decode 都可以移除已结束请求、加入新请求，而不是让一批请求互相等待到全部结束。单机多 GPU 时，原始实现使用 Megatron 式 [[Tensor-Parallelism|张量并行]]；各 worker 保存不同 Attention head 的 KV 分片，scheduler 维护统一 block table，并在每轮广播 token 和映射信息。

vLLM 的边界是完整的通用生成引擎，而不是单个 Attention kernel。它包含请求队列、KV 分配、preemption、模型执行、采样和 API 层；后续论文常只替换其中一个部件，例如 router、KV 分层、功耗控制、通信重叠或模型执行内核。因此，“某系统比 vLLM 快”通常只说明某个特定 workload、版本和配置下的改造有效，不能直接理解为对 vLLM 整体设计的否定。

还要区分三种关系：[[BEAM-MLSys26]]、[[SuperInfer-MLSys26]]、[[TokenWeave-MLSys26]] 等直接修改或集成 vLLM；[[EcoServe-OSDI26]]、[[BatchGen-OSDI26]] 等把它当通用在线服务基线；另一些论文只在“相关系统”中提到 vLLM。只有前两类能支持性能或设计判断。

## 关键观察 / 隐含假设

- **观察：分页首先解决容量浪费，不保证单个 kernel 更快。** 原始 PagedAttention kernel 比 FasterTransformer 对应 kernel 慢 20%–26%，但更高的显存利用率让系统容纳更大 batch，最终吞吐提高 2–4 倍。这个结果说明系统级容量收益可以超过局部间接寻址开销，但前提是 workload 确实受 KV 容量约束（[[vLLM-SOSP23]]）。
- **观察：block 抽象会把问题从“有没有空间”转成“怎样搬这些碎片”。** [[SuperInfer-MLSys26]] 在 GH200 上测得原生 vLLM KV 搬运约 10 GB/s，不到论文所用互连峰值的 5%；原因包括碎片小段、许多 `cudaMemcpyAsync` 和 H2D/D2H 串行。它用 block-first layout 与全双工传输修复这一特定路径，但只在 GH200 和自己的 vLLM fork 上证明有效。
- **观察：调度策略往往比推理内核更依赖 workload。** [[LMetric-OSDI26]] 在 16 张 H20、每卡一个 vLLM-v1 instance 的 trace replay 中，用 `P-token × batch size` 路由，相对 vLLM 内置路由把 mean TTFT/TPOT 分别降低 92%/24%；不过它只覆盖同构、prefill/decode 共置的集群，并展示了热门公共 prefix 会形成 hotspot 的反例。
- **观察：生产可观测性必须理解 token、rank 和 KV 路径。** [[StriaTrace-OSDI26]] 在 vLLM process group 上只保留异常 step 的完整 GPU trace，把高并发下 median TPOT/TTFT tracing overhead 控制在 0.6%/0.8%；论文还报告连续 6 个月覆盖 1,700 多个实例、每天约 1.8 亿次请求。这证明 vLLM 已是生产运行时，但结果只来自论文所在平台的 H20 配置。
- **观察：成熟基线让“小优化”更值得认真看。** [[VTC-OSDI26]] 在 vLLM V1 的 Llama-3-8B decoder layer 上只得到 1.011 倍加速，H100 强制虚拟化反而退化 8%；这比只报告算子峰值更能说明端到端剩余空间。[[TokenWeave-MLSys26]] 则在 8×H100 上通过 TP AllReduce–RMSNorm 融合取得 1.16–1.28 倍 prefill iteration 加速和最高 1.19 倍 ShareGPT 吞吐，收益边界也更清楚。
- **观察：框架、硬件和精度变化可能改变功能输出。** [[DriftBench-MLSys26]] 固定输入与权重，对 vLLM、SGLang、TensorRT-LLM、不同 GPU 和 FP16/FP8/FP4 做 236,985 次评测；Math 平均 flip rate 为 16.74%，Code 仅 0.09%。这不是 vLLM 独有缺陷，而是提醒部署者不能把“相同模型名”当成功能等价保证。
- **假设：固定大小 block 是可接受的长期公共接口。** 它适合 on-demand allocation、共享与批量 kernel；但 token 级稀疏、跨 CPU/SSD 的大块顺序 I/O、不同 KV dtype 和原地回滚都可能要求另一种布局。[[DiffKV-SOSP25]]、[[Bidaw-FAST26]]、[[SuperInfer-MLSys26]] 分别从压缩、分层存储和双向搬运方向暴露了这一张力。
- **假设：通用在线请求仍是主要目标。** [[BatchGen-OSDI26]] 表明，离线大批量 MoE 更关心整批完成时间，允许 sequence 在 Attention–MoE 边界暂停、合并和迁移；在 128×H20、10K requests 上，其 BCT 最多改善 2.3 倍。这个结果说明 vLLM 的“每轮完整 model forward”抽象对交互服务合理，却不必是所有生成 workload 的最佳抽象。

## 演进时间线

- 2023 SOSP：[[vLLM-SOSP23]] — 提出 PagedAttention、按需 KV block 分配、写时复制共享，并与连续组批组合；在论文配置下相对 FasterTransformer/Orca 达到 2–4 倍吞吐。
- 2025 OSDI：[[BlitzScale-OSDI25]] — 把模型权重加载、实时扩缩和 vLLM/DistServe 的峰值配置成本放到同一问题中；相同 SLO 下相对无自动伸缩方案减少 49% GPU。
- 2025 SOSP：[[DiffKV-SOSP25]] — 按 K/V、token 和 head 差异化压缩 KV，在其评测中把 KV 缩小 2.7–5.7 倍、吞吐提高 1.9–5.4 倍，说明分页之外还要改变“每个 token 存多少字节”。
- 2026 FAST：[[Bidaw-FAST26]] — 在 vLLM 上加入 host memory 与 SSD 两层 KV 管理；单 A800 的特定配置中相对 CachedAttention/FlashGen 延迟最高降低 3.58 倍、吞吐提高 1.83 倍。
- 2026 MLSys：[[BEAM-MLSys26]] — 在 vLLM V1 上联合控制 GPU 频率、chunk 和 microbatch；约 95% SLO 满足率下相对 vanilla vLLM 节省 51% GPU 能耗。
- 2026 MLSys：[[BreakingTheIce-MLSys26]] — 把 vLLM 冷启动分成六步，发现整体主要受 CPU 影响，且不同版本启动时间可相差 4 倍以上；其白盒预测器在 22 个 dense 模型上 MSE 为 2.42 秒。
- 2026 MLSys：[[SuperInfer-MLSys26]] — 针对 GH200 重做 KV rotation 与 SLO-aware 调度，高负载下 TTFT SLO 达标率相对所测 SOTA 最多提高 74.7%；结论不能外推到普通 PCIe GPU。
- 2026 MLSys：[[TokenWeave-MLSys26]] — 在 vLLM V1 中重叠 TP 计算与通信，展示成熟 engine 内仍可通过硬件特定融合取得约 1.2 倍级收益。
- 2026 OSDI：[[LMetric-OSDI26]] — 把 vLLM instance 的 KV locality 与 decode load 压成一个简单乘积路由指标，并给出生产 canary 证据。
- 2026 OSDI：[[EcoServe-OSDI26]] — 在 32×L20、普通 Ethernet 上用时间错开的 phase-disaggregation，相对 vLLM goodput 提高 1.96 倍；它优化的是部署拓扑与阶段干扰，不是 PagedAttention 本身。
- 2026 OSDI：[[StriaTrace-OSDI26]] — 将低开销异常 tracing 部署到大规模 vLLM 服务，补上系统长期运行时的诊断层。

## 设计边界与使用建议

- **比较版本。** vLLM 的 scheduler、prefix cache、CUDA Graph、kernel backend 和 V1/V0 路径变化很快；论文必须报告版本、commit 和开关。[[SGLang-NeurIPS24]] 的原始 vLLM baseline 是 v0.2.5，不能把当年的 6.4 倍峰值直接套到后来的版本。
- **比较相同目标。** 在线 TTFT/TPOT、离线 BCT、goodput、能耗和冷启动是不同目标。BatchGen、EcoServe、BEAM、BreakingTheIce 的数字不能排成一个统一“谁最快”榜单。
- **比较相同语义。** 量化、稀疏 Attention、early termination 和不同采样设置可能改变输出；只比较 token/s 不足以证明系统更好。
- **区分宿主与贡献。** 一篇论文在 vLLM 上实现，并不代表优化已进入 upstream，也不代表结果能自动迁移到其他模型、GPU 或生产配置。
- **保留端到端证据。** 算子快很多时，最好像 [[VTC-OSDI26]]、[[TokenWeave-MLSys26]] 一样同时给完整 layer 或 serving trace；否则很容易把局部峰值误写成服务收益。

## 相关概念

- [[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Prefix-Caching]]、[[Tensor-Parallelism]]、[[Disaggregation]]、[[Quantization]]、[[CUDA-Graph]]

## 相关论文

- [[vLLM-SOSP23]] — 原始系统论文，定义 PagedAttention 与 block manager 的基本语义。
- [[NEO-MLSys25]] — 以 SwiftLLM 原型验证本机 CPU attention/KV offload；论文未直接证明原生 vLLM 移植成本。
- [[BlendServe-ASPLOS26]] — 在 vLLM/SGLang/NanoFlow 路径上做离线 request reordering，峰值收益不代表在线 serving。
- [[Agentix-NSDI26]] — 在 vLLM continuous batching 上增加 program-aware preemption 与优先级。
- [[SGLang-NeurIPS24]] — 以结构化 LM program 和 RadixAttention 扩展跨调用 prefix 复用；原始比较使用较早的 vLLM。
- [[CacheBlend-EuroSys25]] — 在 vLLM 中只重算多文档 RAG 里受 cross-attention 影响的 token，展示非前缀 KV 复用需要改变 prefill 路径。
- [[BlitzScale-OSDI25]] — 研究模型加载和扩缩容，而不是单实例稳态执行。
- [[DiffKV-SOSP25]] — 改变 KV 的压缩粒度，并以 vLLM 类内存管理为系统背景。
- [[BEAM-MLSys26]] — 在 vLLM 上联合做 SLO-aware batching 与 DVFS。
- [[BreakingTheIce-MLSys26]] — 测量 vLLM engine initialization 的步骤、版本差异和 CPU 主导成本。
- [[SuperInfer-MLSys26]] — 针对 GH200 修改 vLLM 的调度和 KV 双向传输。
- [[TokenWeave-MLSys26]] — 在 8×H100 vLLM V1 中优化 TP 通信重叠。
- [[DriftBench-MLSys26]] — 衡量 vLLM 与其他框架、硬件和精度之间的功能输出漂移。
- [[BatchGen-OSDI26]] — 用离线 batch workload 反例挑战完整 forward 作为原子调度单位。
- [[EcoServe-OSDI26]] — 把 vLLM 作为共置服务基线，研究普通 Ethernet 上的阶段解耦。
- [[LMetric-OSDI26]] — 在 vLLM instance 集群外增加 locality/load 路由器。
- [[StriaTrace-OSDI26]] — 面向生产 vLLM process group 的低开销异常 tracing。
- [[VTC-OSDI26]] — 说明编译器级算子优化在成熟 vLLM 端到端路径中可能只剩很小收益，甚至会退化。
