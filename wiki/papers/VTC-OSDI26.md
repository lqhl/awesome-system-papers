---
type: paper
name: VTC
full_title: "VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination"
authors: [Muyan Hu, Ahan Gupta, Jiachen Yuan, Vima Gupta, Taeksang Kim, Xin Xu, Janardhan Kulkarni, Ofer Dekel, Vikram Adve, Charith Mendis]
venue: OSDI
year: 2026
tags: [tensor-compiler, gpu, data-movement, virtual-tensor, dnn-inference]
source_pdf: "[[osdi26-hu-muyan.pdf]]"
source_md: "[[osdi26-hu-muyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用虚拟 Tensor 消除 DNN 数据搬运（OSDI 2026）

> **原题**：VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination

> **一句话总结**：Transpose、Split、ScatterND 等纯数据搬运算子只改变元素位置，却会把中间结果完整写回再读出；VTC 用“物理 tensor 指针 + index mapping”表示不落地的 virtual tensor，再通过 profile-guided VTOG 搜索选择值得虚拟化的路径，在五类模型组件、A100/H100、batch 1/16 上相对每项最快 compiler 最多快 1.93 倍、论文报告平均快 1.28 倍，但完整模型训练、动态 shape、多 GPU 和 greedy 最优性都没有验证。

## 问题与动机

GPU 的计算能力增长快于显存带宽。DNN compiler 已能让 MatMul、attention 等计算算子高效使用 Tensor Core，但 Transpose、Split、ScatterND、Slice、Expand 等算子不做数值计算，仍要在 global memory 中读出、重排、写回整块 tensor。随着模型越来越 memory-bound，这些搬运可能比相邻计算更慢（图 1）。

现有 layout optimization 通常只探索 Reshape、Transpose 等少数 layout；operator fusion 又依赖能否把相邻计算合成一个 kernel，或依赖手写 pattern。Llama 3 8B decode 是一个具体例子：TensorRT 已把 QKV projection 合成一个 MatMul，也把 attention 做成 FlashDecoding，却仍用 6 个 kernel 完成中间的 Split、KV-cache update、Expand 和 layout change。这个区段要 0.9083 ms，比前后两个 compute kernel 的 0.7926 ms 总和还长（图 2）。

VTC 的核心问题是：中间 tensor 是否一定要有一块完整、连续的 global-memory storage？作者观察到，Tensor Core 等计算单元要求进入 on-chip buffer 的 tile 连续，却不要求整个 global tensor 都连续。只要 load/store stage 能根据 index mapping 访问多个物理区域，计算主体可以保持不变，中间搬运算子也可以消失。

## 关键观察 / 隐含假设

- **观察 1：纯数据搬运算子可以写成 output index 到唯一 input element 的映射。** 它改变位置而不改变 value，因此可保存 mapping，而不保存一份新 tensor（定义 2–3、§2.2、§4.1）。
  - **依赖假设**：算子语义可由 VTC 支持的 mapping rule 表达，不涉及 reduction、数值计算、不可见 side effect 或必须 materialize 的 graph input/output。
  - **可能失效场景**：custom operator、复杂 alias/in-place update、动态 value-dependent layout，或外部 library 必须接收普通 contiguous pointer。
- **观察 2：global memory 只需“局部连续”也能 coalesce。** Llama 的 head dimension 为 128，大于 warp size 32；QKV output 分写到 Q 与 [[KV-Cache]] 时，每个连续 chunk 仍足够宽，不必先生成完整 QKV tensor（图 3、定义 4–5）。
  - **依赖假设**：连续 chunk 大于最小 memory transaction，mapping branch 不发散，额外 address arithmetic 小于省掉的 read/write。
  - **可能失效场景**：chunk 很小或 irregular、映射跨许多物理 tensor，或 TMA/CUTLASS 对 tile layout 有更强约束。
- **观察 3：虚拟化不是越多越好。** 非连续访问会让 compute kernel 变慢；图 2 的 QKV MatMul 就从 TensorRT 的 0.1034 ms 变成 VTC 的 0.1403 ms。只有省掉的搬运大于这个回归时，整体才更快。
  - **依赖假设**：目标 GPU 上的 profile 能代表 deployment configuration；compiler 可以在收益为负时保留 materialization。
- **观察 4：数据搬运机会在新模型结构中更大。** A100 breakdown 中，TensorRT 的 data-movement 占比在 Gemma batch 16 达 72%，而部分 CNN 只有约 13%–28%；论文相应看到 Transformer 的平均收益更高（图 10）。
  - **依赖假设**：所选 decoder layer/[[Attention|attention]] block 能代表完整应用的热点，而不是只代表一个有利子图。
- **假设 1：greedy profiling 能找到足够好的全局组合。**
  - **证据强度**：中。五类组件上结果良好，但一般 latency set function 不是 submodular，论文没有 approximation bound 或与 exhaustive optimum 的对比（§5.2）。

## 核心方法

**1. Virtual tensor 只保留逻辑 index space。** 一个 virtual tensor 写成 `(F, P1, ..., Pn)`：`P` 是实际物理 tensor 指针，`F(x)` 告诉访问逻辑位置 `x` 时应去哪个 `Pj[y]`。mapping 可以组合，因此连续的 Reshape、Split、ScatterND 不必每步都 materialize。computation-graph 的 input/output 保持物理 tensor，VTC 只虚拟化中间结果（定义 3、算法 1）。

**2. 只改 kernel 的 global-memory I/O。** 普通 kernel 可分为 global→on-chip load、on-chip compute、on-chip→global store 三段。VTC overload `tl.load/tl.store`，根据已知 mapping 生成专用 address code；MatMul 或 attention 的计算主体不变。producer 可以直接把 merged QKV output 写入 Q 与 KV cache，consumer 也可以从分散的 cache 直接读入连续 on-chip tile（图 3、§4.2）。

**3. 用连续性判断明显有利的机会。** fully contiguous mapping 被归为 Type I，论文定理 1 称它总是有利；partial-contiguous mapping 在 chunk 足够宽时通常有利；其他 Type II 情况交给 profile。VTC 为 Split、Expand、ScatterND 等算子手写 mapping 与双向虚拟化规则。ONNX 中数据搬运算子数量有限，论文举例为 18 个，但这也意味着新算子仍要开发者补规则（§4.3–4.4）。

**4. Virtual Tensor Opportunity Graph（VTOG）枚举机会。** fusion 后的 computation graph 中，每个 tensor 成为 VTOG node；若删掉一个 data-movement operator 后 `u` 可由 `v` 表示，就添加 `u→v` edge。某些 outgoing edge 会让同一逻辑 index 指向互斥的 storage，系统将它们记为 conflict set。删除冲突 edge 后得到 points-to graph，它一一对应一套全局 virtual/materialized 策略（图 6–8、§5.1）。

**5. Global greedy 选择实际策略。** 全局最优需要对一般、只能实测的 latency function 做指数搜索，论文指出问题为 NP-hard。VTC 从必须物理化的 anchor 开始，每轮选择当前非冲突 marginal saving 总和最大的 node/edge set；加入新 virtual tensor 后，重新 profile 指向它的 edge。最大 saving 为负时停止，因此系统可以完全跳过一个不利机会。算法控制逻辑约为二次复杂度，但硬件 profiling 才是主要编译成本（算法 2、§5.2）。

**6. 编译器集成。** VTC 在 [[TorchInductor]] 加 analysis pass 和 transformation pass：前者构造 VTOG/points-to graph，后者删除搬运 node、修改 IR 的 load/store，再交给 [[Triton]] 生成专用 Python/CUDA code。单次被 profile 的 configuration 少于 10 s，所测完整 graph 的总编译时间少于 10 min。作者声称与原 compiler 保持端到端数值等价，但正文没有给误差阈值或 differential-test 规模（§6）。

## 设计取舍

- **少 materialization 换地址计算。** 节省 global read/write 和 allocation，却可能让 producer/consumer 的 memory access 更散，并增加 mapping、branch 与 register 压力。
- **通用抽象换 operator rule 维护。** virtual tensor 能组合多种搬运，但每种新 data-movement operator 仍需开发者写正确的映射和冲突规则。
- **profile robustness 换编译时间。** 不必准确建模不同 GPU，代价是每个 shape/batch/hardware configuration 都可能需要数分钟重新搜索。
- **greedy 换可实现性。** 二次搜索比指数枚举简单，但一般情形没有最优保证，也没有证明局部 edge saving 可可靠预测组合收益。
- **接在 fusion 后换低侵入。** VTC 可复用现有 compute kernel，但上游 fusion/layout 已经作出的决定也可能提前关闭更好的 virtual strategy。
- **适用边界。** 大中间 tensor、多段纯搬运、连续 chunk 足够宽时收益大；domain-specific kernel 已手工消除搬运、compute kernel quality 主导或 graph boundary 频繁 materialize 时收益小。

## 实验设置

- 硬件是单张 A100 80 GB [[PCIe|PCIe]] 或 H100 NVL；软件为 Ubuntu 22.04、CUDA 12.1。没有 multi-GPU、B200/TMA 或训练实验（§7.1）。
- 五类 workload 是 Llama 3 8B decoder layer、Gemma 2 9B decoder layer、EfficientViT attention block、YOLOv11n C3K2 block 和 ShuffleNet ShuffleUnit，batch 为 1 或 16（表 1）。论文称“end-to-end inference”，但评测单位实际是这些模型组件，不是完整模型服务。
- baseline 是 [[PyTorch|PyTorch]] 2.6 `torch.compile`、ONNX Runtime 1.21.1、XLA 和 TensorRT 10；每个 case 与四者中最快的一个比较。Transformer 使用 BF16，vision component 使用 TF32。
- 主延迟一共有 5 组件×2 batch×2 GPU 的 20 个 case；显存只在 A100 上相对 PyTorch 测 10 个 case。没有真实 arrival、tail latency、能耗或 strategy-search optimum。

## 实验与结果

- **组件级端到端延迟**：20 个 model-component/batch/GPU case 中，VTC 相对每项最快的 PyTorch、ONNX Runtime、XLA、TensorRT baseline 最多快 1.93 倍，论文报告平均快 1.28 倍；最大值来自 A100、Llama decoder layer、batch 16，相对 TensorRT（图 9、§7.2）。
- **模型与硬件差异**：Transformer 三类组件平均快 1.36 倍，YOLOv11/ShuffleNet 两类 CNN 平均快 1.15 倍；同一组件与 batch 的 10 对 A100/H100 比较中，有 7 对在 H100 上收益更大，但 H100 并非所有 case 都单调更好（图 9、§7.2）。
- **搬运消除与计算回归**：A100 的 10 个 component/batch case 中有 7 个把显式 data-movement operator 全部消除；VTC 的 compute 部分在多数 case 反而比 TensorRT 慢。Llama batch 16 子图中，搬运由 6 kernels、0.9083 ms 降到 0，attention 从 0.6892 降到 0.2812 ms，但 QKV MatMul 从 0.1034 增到 0.1403 ms，总子图约快 4 倍（图 2、10、§7.4）。
- **峰值显存**：仅在 A100、相对 PyTorch built-in monitor 的结果中，VTC 最多节省 60%、平均 17.5%；最大值是 Llama batch 16，从 1,787.3 MB 降到 714.5 MB。ShuffleNet batch 1 只省 0.9%，说明收益取决于是否能虚拟化大中间 tensor（表 2、§7.3）。
- **强 vLLM 对照**：[[vLLM]] V1、Llama 3 8B、4096-token input、BF16 下，A100 的 QKV-to-attention 子图由 1.972 降到 1.890 ms，仅快 1.043 倍；整个 decoder layer 由 9.152 降到 9.055 ms，只快 1.011 倍。H100 默认 profile 选择不优化，与 vLLM 相同；强制虚拟化会让 decoder layer 从 4.230 增到 4.600 ms，退化 8%（表 3–4、§7.5）。
- **搜索与边界 case**：每个 profile configuration 少于 10 s、所测 graph 总编译少于 10 min（§6）。EfficientViT 因现有 fusion 已覆盖多数机会，只获得约 1.1 倍加速和约 4.4% 显存节省；YOLOv11 则能把大 Split/Concat 中间 tensor 都指向最终 `Y`（图 11–12、§7.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| virtual tensor 能显著减少 compiler 未消除的数据搬运 | 图 9–10：最多 1.93 倍；A100 10 项中 7 项无显式搬运 | 五种模型组件、batch 1/16、单 A100/H100 | 强 |
| 虚拟化可同时降低峰值显存 | 表 2：最多 60%、平均 17.5% | 仅 A100、相对 PyTorch、组件级 graph | 强 |
| profiling 能避开负优化 | 表 3：H100 默认保持 1.000 倍，强制版本为 0.920 倍 | 单个 vLLM/Llama decoder 配置 | 强 |
| VTC 对强 domain-specific serving 的端到端收益很小或没有 | 表 3：A100 decoder layer 仅 1.011 倍，H100 为 1.000 倍 | vLLM V1、Llama 3 8B、4096-token input | 强 |
| greedy strategy 接近全局最优 | §5.2：一般问题 NP-hard，算法按 marginal profile 贪心 | 无 exhaustive、ILP 或 approximation-gap 实验 | 弱 |

## 批判性分析

### 论证链条

论文先用纯数据搬运的 index semantics 建立 virtual tensor，再把 kernel 改写限制在 I/O stage，最后用 VTOG 和 profile 解决“哪些值得做”，从语义到实现再到性能的主链是闭合的。图 2 很好地说明了关键取舍：VTC 允许 compute kernel 变慢，只要删除搬运后的总时间更短。作者的“覆盖所有不必要数据搬运”仍应收窄为：在已写 mapping rule、满足一对一表示、允许改写 load/store 且 graph boundary 不要求 materialize 的范围内搜索；它不是任意 tensor program 的完备证明。

### 假设压力测试

收益取决于搬运占比、连续 chunk、backend kernel quality 和 graph boundary。H100 vLLM 强制版本退化 8% 已证明“compute/memory gap 变大”不会自动让 VTC 更好：cuBLAS MatMul 比 Triton 快得多时，删除一个小 copy 也不划算。动态 sequence、training backward、activation alias、custom CUDA op 和 collective 会扩大 mapping/conflict 空间，并迫使更多 tensor materialize。新 TMA bulk-transfer 还可能让原本昂贵的搬运变便宜，改变 profile 结论。

### 实验可信度

每项取四个 compiler 中最快者，包含 TensorRT 的手工 attention pattern，baseline 较强；两代 GPU、Transformer/CNN、batch 1/16、显存、breakdown 和 vLLM 负结果也让证据比较诚实。主要外部边界是评测单位：表 1 实际只跑 decoder layer 或 block，不是完整 [[LLM|LLM]]/CNN、scheduler 和 data pipeline。五类组件、两个 batch 也不足以说明 arbitrary composition；没有重复次数、方差、tail、数值误差、training、multi-GPU 和真实 serving trace。

### 系统性缺陷

virtual tensor 没有独立 storage，debugger、profiler、checkpoint 和外部 custom kernel 若期待普通 tensor，就必须理解 mapping 或临时 materialize。错误 mapping 可能静默读写错误地址；正文只声明 zero precision loss，没有展示 systematic differential test。VTOG 规则、conflict detection、specialized codegen 和 profile cache 都增加 compiler correctness surface。数分钟编译还会影响 autoscaling，论文也没有讨论 cache key、版本升级和 OOM/failure fallback。

## 局限与后续工作

- **局限 1**：只测 single-GPU inference component，没有完整模型服务、training/backward、dynamic shape 或 multi-GPU collective。
- **局限 2**：数据搬运规则需按 operator 编写；custom op、alias/in-place 和外部 kernel compatibility 未覆盖。
- **局限 3**：一般 latency function 下 greedy 没有最优保证，profile 搜索又可接近 10 min。
- **局限 4**：实现依赖 Triton，H100 vLLM case 已显示其 compute kernel 可输给 cuBLAS，Blackwell/TMA 尚未验证。
- **后续工作 1**：对小 VTOG 用 exhaustive 或 ILP 求 optimum，按 graph size、conflict density 报 greedy 的 latency gap、profile 数和 compile time。
- **后续工作 2**：扩展到完整 training graph，对 forward/backward alias、optimizer、activation checkpoint 做随机 shape differential test，并报告数值误差与峰值显存。
- **后续工作 3**：在真实 LLM arrival trace 上集成完整 vLLM，测 TTFT、TPOT、P99、goodput、KV-cache capacity 与策略 recompile 次数，而不是只测一个 decoder layer。
- **后续工作 4**：给 CUTLASS/TMA 增加 virtual I/O，在 H100/B200 上比较 memory transaction、compute regression 和 profile 选择是否翻转。
- **后续工作 5**：定义跨 custom kernel 的 materialization ABI，注入错误 mapping、unsupported op 和 OOM，验证安全 fallback、debug trace 与 cache invalidation。

## 相关

- **相关概念**：[[Tensor-Compiler]]、[[Data-Movement]]、[[Operator-Fusion]]、[[Virtual-Tensor]]、[[KV-Cache]]
- **同类系统**：[[TorchInductor]]、[[TensorRT]]、[[vLLM]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
