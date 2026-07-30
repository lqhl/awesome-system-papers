---
type: paper
name: ContextAwareMoE-CXLNDP
full_title: "Context-Aware Mixture-of-Experts Inference on CXL-Enabled GPU–NDP Systems"
authors: [Zehao Fan, Yayue Hou, Zhenyu Liu, Hadjer Benmeziane, Liu Liu, Yunzhen Liu, Kaoutar El Maghraoui]
venue: arXiv
year: 2025
tags: [llm-inference, moe, cxl, ndp, quantization, expert-offloading]
source_pdf: "[[arxiv25-context-aware-moe-cxl-ndp.pdf]]"
source_md: "[[arxiv25-context-aware-moe-cxl-ndp]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ContextAwareMoE-CXLNDP：支持 CXL 的 GPU–NDP 系统上的上下文感知混合专家推理（arXiv 2025）

> **原题**：Context-Aware Mixture-of-Experts Inference on CXL-Enabled GPU–NDP Systems

> **一句话总结**：这篇把 [[MoE]] expert offloading 的核心假设改成“prefill routing 可以预测 decoding routing”，用一次 prefill 统计同时决定 GPU/CXL-NDP expert placement 和 NDP 侧 1-4 bit mixed precision；在 Ramulator 模拟的 1×H100 + 1×DDR-NDP 系统上，Mixtral-8x7B/8x22B 相对 MoNDE decoding throughput 最高提升 11.5x，3-bit 配置在 Mixtral-8x7B 上平均 accuracy 只降 0.13 个点。

## 问题与动机

[[MoE]] 模型用 sparse expert 扩参数，但 inference 时所有 expert 权重必须可访问。Mixtral-8x22B FP16 约 280 GB，远超单卡 HBM；如果把 expert 放在 CPU/CXL memory，需要在 decoding 每步按 router 结果把权重搬回 GPU，论文引用的 prior measurement 里 expert migration 可超过 Transformer block latency 的 90%。因此，MoE serving 的瓶颈不是单纯算子 FLOPs，而是“稀疏但动态”的 expert working set 与低带宽外部内存之间的冲突。

CXL-attached NDP 给出另一种分工：把冷 expert 留在内存设备侧计算，只跨 CXL/PCIe 传 activation 和 expert output，避免大块参数迁移。已有 GPU-NDP MoE 系统如 MoNDE、PIMoE 已经利用 hot/cold expert skew，但多依赖 static 或 reactive policy。论文认为这仍然不够，因为 expert 热度随输入 context、layer、decode step 变化；静态 placement 会把突然变热的 expert 留在 NDP，reactive migration 又会把节省的带宽重新花在搬权重上。

第二个动机是 NDP compute budget。即使 cold expert 不再搬到 GPU，如果 NDP 侧全部 FP16 执行，瓶颈会从 CXL transfer 转到 NDP 的有限 systolic array / scratchpad / power budget。论文因此把问题拆成两个耦合决策：哪些 expert 值得留在 GPU FP16，哪些 expert 可以留在 CXL-NDP 并降到低 bitwidth。

## 关键观察 / 隐含假设

- **观察 1：同一个 MoE 模型里 expert activation 高度偏斜，但偏斜不是全局静态常数。** Mixtral-8x7B 在 WikiText-2 上的 expert activation heatmap 显示不同 layer/expert 频率差异明显；C4 上两个随机样本的 decode-step heatmap 又显示同一数据集内部也有不同 activation pattern。
  - **依赖假设**：hot/cold skew 足够稳定，能支撑 device-aware placement；同时 skew 又足够 context-dependent，使 per-sequence placement 比全局 placement 有价值。
  - **可能失效场景**：如果模型使用更强的 load balancing、expert choice routing、shared expert 或者 routing 被训练成更均匀，hot/cold 差异会减弱；如果服务端做大 batch/continuous batching，单 sequence 的 context-aware 决策可能与 batch-level device utilization 冲突。

- **观察 2：prefill-stage routing distribution 能预测 decoding-stage routing。** 论文在 Mixtral-8x7B + TruthfulQA 上计算每层 prefill/decoding expert activation probability 的 cosine similarity，平均为 0.89。这个观察让系统只在 prefill 后做一次 placement，而不是 decode 每步迁移 expert。
  - **依赖假设**：一次 prefill 统计足以代表后续输出期，尤其是长输出、multi-turn、RAG/tool-use 这类 context 会持续演化的请求。
  - **可能失效场景**：图中 per-layer similarity 有可见低谷，最低层附近约 0.82；如果这些层刚好承载 latency-heavy expert，固定 placement 可能产生 NDP hot spot。论文没有展示随 output length 增长的 similarity decay。

- **观察 3：NDP 侧低精度收益很大，但 uniform sub-4-bit 会伤精度。** GPTQ 等 PTQ 方法让 4-bit practical，但论文认为 1/2/3-bit uniform quantization 会忽略 expert 重要性和量化敏感度差异，因此需要 mixed precision。
  - **依赖假设**：offline calibration 得到的 per-expert MSE loss table 与在线任务 accuracy 相关；prefill importance 排序也能作为 bitwidth priority。
  - **证据强度**：中等。2-bit 时 Expert Bitwidth Selector 把平均 accuracy 从 63.48 提到 66.68，说明 selector 有实效；但 accuracy 只在 Mixtral-8x7B 上测，未覆盖 8x22B 或生成质量指标。

- **假设 1：CXL-NDP 的主要价值来自“搬 activation 而不是搬参数”。**
  - **证据强度**：中等偏弱。性能评估基于与 MoNDE 同配置的 Ramulator NDP simulator，硬件设定清楚，但不是真实 CXL-NDP 设备；activation transfer、CXL contention、driver/runtime overhead 在生产部署中可能比 simulator 更复杂。

- **假设 2：每 sequence 一次 migration 是可接受的控制粒度。**
  - **证据强度**：中等。它直接回应了 reactive migration 的 bandwidth 问题，但论文没有给出 placement/migration overhead、prefill latency impact 或 tail latency breakdown。

## 核心方法

系统由两个共享 prefill statistics 的模块组成。

第一是 **Expert Placement Module**。在每个 sequence 的 prefill 阶段，系统为每层每个 expert 收集两类统计：activation count 和 accumulated routing score。前者表示 expert 被选中的频率，后者表示 router 对这些选择的置信度。两者归一化后用参数 `alpha` 线性混合，得到 expert importance score。每层选择 top-k important experts 放入 GPU HBM 并保持 FP16；其余 expert 留在 CXL-NDP。Mixtral-8x7B 的实验配置是每层 4 个 GPU hot experts + 4 个 NDP experts；Mixtral-8x22B 是 2 个 GPU hot experts + 6 个 NDP experts。

第二是 **Expert Bitwidth Selector**。系统不在线量化，而是在 CXL-NDP 侧为 NDP-resident experts 预先缓存 GPTQ 量化的 1/2/3/4-bit replicas。对每层 NDP experts，它用 C4 calibration set 构造 loss table：每个 expert 在不同 bitwidth 下相对 FP16 reference output 的 MSE。在线时复用 placement 阶段的 importance order，在 layer-wise average bitwidth budget 下做 prefix-structured assignment：更重要的 NDP experts 得到更高 bitwidth，越靠后的 experts 使用更低 bitwidth。

这个 bitwidth 分配本质是一个小规模离散搜索。以 1-bit 为初始状态，平均 bitwidth 预算可以转成“bitwidth increment”预算；系统枚举 4-bit 和 3-bit expert 个数，再由约束推出 2-bit 和 1-bit 个数，用 prefix sums 常数时间评估总 quantization-loss reduction。复杂度约为每层 `O(E_NDP^2)`，因为 Mixtral 每层只有 8 个 experts，论文认为该开销相对 inference 可忽略。

执行路径上，prefill 后配置固定，decoding 每步只判断 selected expert 属于 GPU set 还是 NDP set。GPU hot experts 在 HBM FP16 执行，NDP cold experts 用所分配 bitwidth 在 CXL-attached memory device 上 near-data 执行，GPU 侧聚合 expert output。这个设计刻意避免 decode-step expert migration，把动态性压缩到 sequence 边界。

和 [[MOE-INFINITY-arXiv24]]、[[FluxMoE-arXiv26]]、[[KTransformers-SOSP25]] 这类 expert offloading 路线相比，这篇的独特点不是把 expert 做成 cache/page，而是把 routing context 当成一次性 placement oracle；和普通 [[Quantization]] 工作相比，它量化的目标也不是单纯压模型容量，而是降低 CXL-NDP 侧 compute pressure。

## 设计取舍

- **一次 placement 换低迁移开销**：prefill 后固定 GPU/NDP mapping，避免 reactive policy 在 decoding 中反复搬 expert；代价是无法纠正长输出或话题转移导致的 routing drift。
- **per-sequence context awareness 换调度复杂度**：每个 sequence 都可能有不同 hot experts。单请求看更精细，但服务端如果采用 [[Continuous-Batching]]、multi-tenant batching 或 [[Expert-Parallelism]]，不同 sequence 的 placement 冲突会让 GPU HBM residency、NDP queueing 和 batch kernel fusion 更难。
- **mixed precision 换 NDP throughput**：2/3-bit NDP execution 显著降低 latency，但质量依赖 calibration loss table 和任务分布；2-bit 平均 accuracy drop 仍达约 3.35 个点。
- **缓存多个 quantized replicas 换在线低开销**：预存 1/2/3/4-bit candidates 避免在线量化，但会增加 CXL-NDP memory footprint 和模型加载复杂度。论文强调 CXL 容量大，但没有系统评估 replica storage overhead、load time 或更新成本。
- **模拟器可控性换外部有效性**：复用 MoNDE 的 GPU-NDP simulator 有利于公平对比，但真实 CXL-NDP hardware 的带宽隔离、cache coherence、DMA/runtime overhead 和故障行为没有被验证。

## 实验与结果

- **模型与任务**：Mixtral-8x7B（32 layers、8 experts、top-2、46.7B params）和 Mixtral-8x22B（56 layers、8 experts、top-2、140.6B params）。Accuracy 用 EleutherAI LM Evaluation Harness，覆盖 MMLU 5-shot，以及 MathQA、HellaSwag、ARC-Easy/Challenge、BoolQ、WinoGrande、PIQA zero-shot。
- **系统配置**：1×H100 GPU + 1×DDR-based NDP，PCIe Gen4 x16；GPU 为 132 SM、989.4 TFLOP/s、80 GB HBM3；NDP device 为 512 GB capacity、512 GB/s bandwidth、64 个 4×4 systolic arrays、1 GHz。NDP simulator 基于 Ramulator，并沿用 MoNDE methodology。
- **Baselines**：主要性能 baseline 是同一 GPU-NDP 系统上的 MoNDE；另有 GPU-only mixed-precision expert offloading baseline HOBBIT。Accuracy baseline 用 original full-precision model，也等价于 MoNDE 的 lossless expert execution。
- **Latency**：Mixtral-8x7B 上，Ours-3bit 相对 MoNDE end-to-end speedup 为 6.6-8.3x，Ours-2bit 为 7.9-10.6x；Mixtral-8x22B 上，Ours-3bit 为 7.6-8.7x，Ours-2bit 为 9.5-11.2x。
- **Decoding throughput**：Mixtral-8x7B 上，Ours-3bit/Ours-2bit 相对 MoNDE 最高分别到 8.7x/11.2x；Mixtral-8x22B 上最高分别到 8.9x/11.5x。图中 128/2048 配置下，8x22B 的 throughput 从 MoNDE 的 1.714 tokens/s 提到 15.321（3-bit）和 19.795（2-bit）。
- **NDP-side latency**：单看 NDP execution，3-bit 和 2-bit 分别约有 5x 和 8x latency reduction，说明 quantization 不只是省容量，也确实缓解了 NDP compute bottleneck。
- **GPU-only 对比**：相对 HOBBIT，Ours-2bit 在 Mixtral-8x7B 上最高 18x speedup，在 Mixtral-8x22B 上最高 19x speedup。不过这主要反映 GPU-only offloading 在该硬件设定下被 PCIe parameter transfer 卡住。
- **Accuracy**：Mixtral-8x7B 上 full precision average 为 70.03，Ours-3bit 为 69.90，下降 0.13 个点；Ours-2bit 为 66.68，下降约 3.35 个点。Bitwidth Selector 对 3-bit 提升很小（69.71 到 69.90），对 2-bit 明显（63.48 到 66.68）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Prefill routing 对 decoding routing 有预测信号 | cosine similarity 平均 0.89（§3.2，Fig. 4） | Mixtral-8×7B、TruthfulQA、8 expert/layer；不是 top-k overlap 或 tail-latency 指标 | medium |
| Context-aware low-bit design 降低 end-to-end latency | 8×7B 3-bit/2-bit 为 6.6–8.3×/7.9–10.6×；8×22B 为 7.6–8.7×/9.5–11.2×（§5.2，Fig. 5） | 与 MoNDE 同 GPU–NDP 的 Ramulator simulation | medium |
| 设计提高 decoding throughput | 3-bit 为 8.7×/8.9×，2-bit 为 11.2×/11.5×（§5.2，Fig. 6） | 单 GPU–NDP simulated setup，不是 multi-tenant serving | medium |
| low-bit NDP compute 是主要性能杠杆 | NDP latency 在 3-bit/2-bit 约为 5×/8× reduction（§5.2，Fig. 5） | NDP simulator/precision setting；未单独 ablate migration reduction | medium |
| bitwidth selector 在 3-bit 保持较好 accuracy | full precision 相对 Ours-3bit/Ours-2bit 的平均 accuracy drop 为 0.13%/3.4%，2-bit selector gain 3.2%（§5.3，Table 3） | Mixtral-8×7B、MMLU + seven zero-shot task、1024 C4 calibration | medium |

## 批判性分析

### 论证链条

论文的主链条是闭合的：MoE expert working set 超 HBM → 参数迁移主导 latency → CXL-NDP 可以把参数留在 near-memory → 但 NDP 侧 placement/precision 不能 context-agnostic → prefill routing 预测 decoding routing → 一次 placement + mixed precision 降低迁移和 NDP compute。这个逻辑比单纯“加 NDP”更强，因为它指出了 MoE routing 的时间结构：prefill 是一个便宜的在线 profile 阶段。

最关键的跳步在于从 “average cosine similarity = 0.89” 外推到 “decoding 阶段固定 placement 足够好”。cosine similarity 是 distribution-level 指标，不直接等价于 top-k expert set 的稳定性，也不等价于 latency-sensitive hot expert 不会落错设备。论文如果补充 top-k overlap、per-layer miss penalty、output length 分桶和 tail latency，会让这个 claim 更扎实。

### 假设压力测试

**Workload 变化**：TruthfulQA/C4/WikiText-2 支撑了基本语言任务，但 production MoE serving 里常见 multi-turn chat、tool use、RAG long context、code generation 和 agentic planning。后几类 workload 的 decoding 可能引入更强话题转移，prefill routing 与后续 routing 的相似性可能下降。尤其长输出场景下，prefill 只看 prompt，不看模型已经生成的新状态。

**硬件变化**：论文默认 1×H100 + 1×DDR-NDP + PCIe Gen4 x16。若未来 CXL-NDP compute 更弱，quantization 必须更激进，accuracy 风险升高；若 GPU memory 更大或 NVLink/CXL 带宽更强，parameter migration 的相对痛点下降，CXL-NDP 的收益窗口变窄。多 GPU / 多 NDP device 下还会出现 placement consistency、load balancing 和 CXL fabric contention 问题。

**模型变化**：Mixtral 系列每层 8 experts、top-2，便于 `O(E_NDP^2)` selector 和每层 top-k placement。DeepSeek/Qwen3 这类更大 expert count、shared experts、grouped routing 或 FP4-native MoE 可能改变 expert importance 分布和 quantization sensitivity。若模型训练时已经用 FP4/FP8 或 routing-aware load balancing，NDP-side GPTQ replicas 的收益和质量边界都要重新测。

### 实验可信度

公平性上，复用 MoNDE system configuration 是优点，能隔离 context-aware placement + quantization 对 GPU-NDP baseline 的增益。性能数字也覆盖两个模型和多个 input/output length。

不足是 ablation 还不够分解。论文报告 NDP-side latency 和 without-Selector accuracy，但没有清楚拆出“prefill-guided placement 单独贡献多少”“mixed precision 单独贡献多少”“activation count vs routing score 的 alpha 是否敏感”“top-k GPU expert budget 改变时是否仍然稳定”。如果没有这些 ablation，很难判断 8-11x throughput 中有多少来自更少迁移，有多少来自低 bitwidth NDP compute。

Baseline 也偏窄。MoNDE 是最直接 GPU-NDP baseline，但 2024-2025 的 MoE offloading 生态还包括 MoE-Lightning、Fiddler、[[MOE-INFINITY-arXiv24]]、[[KTransformers-SOSP25]]、HybriMoE、[[FluxMoE-arXiv26]] 等不同层级方案。论文可以说自己解决 GPU-NDP context-unaware 的问题，但 “state-of-the-art method” 的边界应理解为 MoNDE-style GPU-NDP，而不是所有 MoE serving。

### 系统性缺陷

论文未讨论 tail latency 和 SLO。Context-aware placement 如果偶尔把 hot expert 放错设备，平均 throughput 仍可能好看，但 P99 token latency 会受到 NDP queueing 和 CXL contention 放大。服务端真正关心的是 TTFT、TBT、deadline miss 和 batching fairness，而不只是 end-to-end latency bar。

资源隔离和多租户也没有展开。每个 sequence 都有独立 hot expert set，会让 GPU HBM 中 expert residency 随请求混合变化；多个 tenant 同时服务时，迁移预算、NDP compute units、CXL bandwidth 和 quantized replica cache 都需要调度策略。论文把这些问题留在单 sequence / 单 simulator 设定之外。

可运维性方面，系统需要 offline calibration loss table、多个 bitwidth replicas、per-sequence prefill statistics、placement decision、GPU/NDP execution overlap，以及 simulator/硬件 runtime 支持。任何一个组件的观测或校准失准，都可能表现为质量下降或 tail latency spike；论文没有给出监控指标、fallback policy 或在线纠错机制。

## 局限与后续工作

- **局限 1：prefill predictiveness 的证据维度较窄。** 需要在长输出、多轮对话、code/RAG/tool workload 上测 top-k expert overlap、similarity 随 decode step 的衰减，以及 placement miss 对 P50/P99 latency 的影响。
- **局限 2：真实硬件外部有效性未证明。** 当前结果依赖 Ramulator GPU-NDP simulator；后续应在可用 CXL memory/NDP prototype 或至少 full-system CXL simulator 上验证 CXL transaction overhead、runtime overhead 和 contention。
- **局限 3：accuracy 只覆盖 Mixtral-8x7B aggregate benchmarks。** 2-bit 已有 3.35 个点平均下降，应该补 8x22B accuracy、generation quality、calibration set sensitivity 和 per-task failure analysis。
- **局限 4：缺少 serving-level调度评估。** 没有 continuous batching、多 tenant、arrival trace、SLO miss 和 tail latency；这些正是 per-sequence placement 进入生产时会暴露的系统边界。
- **Future work 1：设计带 miss detection 的 adaptive placement。** 例如 prefill 后固定 placement，但在线监测 routing drift；只有当 top-k miss 或 NDP queueing 超阈值时才触发少量 correction migration，可用迁移次数、P99 latency 和 throughput 共同评估。
- **Future work 2：把 bitwidth selector 变成 SLO/quality-aware 控制器。** 当前只用 average bitwidth budget；可以在 per-request latency slack、task confidence 或 quality risk 下动态选择 2/3/4-bit，并以 lm-eval、困惑度和 token latency 联合验证。
- **Future work 3：扩展到 batch-level placement。** 多请求共享 GPU/NDP 时，应该优化的是一批 sequence 的 expert residency，而不是每个 sequence 独立 top-k；可测 GPU HBM churn、NDP load imbalance 和 CXL bandwidth utilization。

## 相关

- **相关概念**：[[MoE]]、[[Quantization]]、[[Expert-Parallelism]]、[[Disaggregation]]
- **同类系统 / 论文**：MoNDE、PIMoE、HOBBIT、Fiddler、MoE-Lightning、[[MOE-INFINITY-arXiv24]]、[[KTransformers-SOSP25]]、[[FluxMoE-arXiv26]]、[[OD-MoE-arXiv25]]、[[CoX-MoE-DAC26]]
- **硬件方向**：[[CXL]]、Near-Data Processing、GPU-NDP co-execution、CXL-attached memory
- **可对照问题**：[[MoE-Serving-Tax-MLSys26]] 关注 MoE serving 相对 dense 的系统税；[[DeepSeek-V4-arXiv26]] 代表模型侧 FP4 / 大规模 MoE 可能改变本文假设的方向。
