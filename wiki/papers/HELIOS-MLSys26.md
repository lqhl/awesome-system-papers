---
type: paper
name: HELIOS
full_title: "HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving"
authors: [Avinash Kumar, Shashank Nag, Jason Clemons, Lizy John, Poulami Das]
venue: MLSys
year: 2026
tags: [llm-inference, early-exit, model-switching, serving, throughput]
source_pdf: "[[1f0e3dad99908345f7439f8ffabdffc4.pdf]]"
source_md: "[[1f0e3dad99908345f7439f8ffabdffc4]]"
---

# HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving (MLSys 2026)

> **一句话总结**：作者测量发现单模型 EE-LLM 既无法覆盖长尾 token 的 exit 深度、又因 worst-case 全层加载而零显存收益；据此用 **多模型互补 early-exit** + **低置信 token 仍可 greedy 退出** 两条观察，配合在线 profiling 与 greedy partial load，相对 Chen et al. 2024 EE-LLM 框架吞吐 **1.48×**、batch size **15.14×**，perplexity 仅 +0.01。

## 问题与动机

Early-Exit LLM（EE-LLM）在中间层满足置信阈值时提前输出 token，跳过深层计算以降延迟。但现有 serving 框架（Chen et al., 2024）几乎都用 **单个 EE-LLM**，在真实 [[Continuous-Batching]] 场景下暴露出两条结构性瓶颈。

**计算侧**：exit 深度只有运行时才知道；批内 token 退出层不一致时，要么等最慢 token（同步开销），要么退化为 batch=1——现有 EE-LLM 默认后者。更糟的是，单模型上「退不出」的 token 必须穿完全部层，平均 token 延迟被长尾主导，latency savings 被稀释。

**内存侧**：框架为 worst-case exit depth **预加载全部层权重**，并为所有层建 [[KV-Cache]]——因为未来 token 可能不早退、需要 attend 到完整历史。结果是 EE-LLM 的 HBM footprint 与 vanilla autoregressive decoding **几乎相同**（论文 Fig. 1：CodeLlama-34B + Llama2-70B 权重在 B100 上占可用 HBM 的 68%，vanilla 与 EE-LLM 曲线重合）。Llama3.1-405B 在 8×B100 上权重 alone 占 **52%** HBM。显存不省，batch size 就上不去——吞吐优化的两条路径（降延迟、扩 batch）都被堵死。

HELIOS 的目标是在 **不显著牺牲精度** 的前提下，同时最大化 early-exit token 比例 **和** 可支撑 batch size，把 EE-LLM 从「算力省一点、内存不变」推进到「延迟 + 内存双优化」。

## 关键观察 / 隐含假设

- **观察 1：不同 EE-LLM 的 early-exit 分布互补，可联合覆盖长尾 token。** OPT-1.3B（24 层）在标准 benchmark mix 上 74% token 仅需前 6 层；剩余 26% 中 57% 换 OPT-6.7B（32 层）只需 9 层即可。双模型联合可把 early-exit 比例从 74%/77% 提到 **92%**，仅 **8%** 需穿全层。
  - **依赖假设**：服务商会维护 **多个已 fine-tune early-exit 的候选模型**（不同规模/家族），且请求流在模型间存在可切换的 exit 互补性。
  - **可能失效场景**：单一模型族、同质 workload、或所有候选模型 exit 分布高度重叠时，切换收益趋零；频繁切换的加载/迁移开销可能吞噬 latency 节省。
- **观察 2：未达置信阈值的 early-exit token，穿完剩余层后输出往往不变。** OPT-6.7B Layer-9 上，即使置信度低至 0，**85%** token 与 Layer-32 最终输出相同；CodeLlama-34B Layer-16 在 CNN/DM 上 **90%** 不变（Appendix D 跨 6 数据集一致）。因此可 **greedy 早退** 并只加载「最可能用到的层」。
  - **依赖假设**：下游任务精度在某一中间层深度后已饱和（论文 Fig. 10：CodeLlama-34B 在 layer-28、Llama2-7B 在 layer-24 后 accuracy plateau）；perplexity 可在线代理精度。
  - **可能失效场景**：高熵生成（数学推理、代码补全）、高置信阈值、或需要深层 refinement 的任务；greedy 退出可能累积误差。
- **观察 3：请求流存在 temporal locality，使在线 profiling 的 exit 分布在短期内仍准确。** 多轮对话、few-shot prefix、system prompt 等使连续请求共享上下文模式（论文引用 PARROT/OSDI'24 与 prompt caching 实践）。
  - **依赖假设**：RI=150 次请求内 workload 特征相对稳定；Model Repository 已有离线吞吐/精度 telemetry。
  - **可能失效场景**：高频任务交错、突发 topic shift、或 RI 过大导致 PHT 过时——论文 Fig. 12 显示 RI>250 吞吐下降，且高 RI 有 undetected accuracy drift 风险。
- **假设 1：固定层数的 greedy partial load 可消除 batch 内 exit 深度同步。** 同一 timestep 所有 token 从相同 partial model 的同一 exit 层输出，无需 per-token 层数对齐。
  - **证据强度**：强。设计直接回应 EE-LLM batch=1 痛点，batch size 实验（最高 **15.14×**）支撑该机制有效。
- **假设 2：perplexity 足以在 inference-time 做模型选择与 accuracy guard。** 无 ground truth 时，用同 tokenizer 模型族的 perplexity 比较选模与触发 CBC 补救。
  - **证据强度**：中。Table 1 显示 profiling 后选模优于 MR 静态数据；但下游 ROUGE-2 实验规模有限，perplexity 与 task metric 的 gap 未系统量化。

## 核心方法

HELIOS 是在 Chen et al. 2024 EE-LLM 框架之上的 **自适应 serving orchestrator**，四步闭环（Fig. 4）：

**Step 1 — 候选选择**：从 Model Repository 按用户 SLO 与硬件约束选 TopK（默认 K=3）EE-LLM 候选，控制 profiling 开销。

**Step 2 — 在线评估**：对每个候选跑 **5 个请求** profiling，收集吞吐、perplexity 与 **early-exit 分布**，写入 Performance History Table（PHT，<1 KB）。评估 token **不丢弃**——因候选已预筛，输出直接服务请求。默认串行评估（GPU 不够并行跑多模型）。

**Step 3 — Greedy partial load + 服务**：选 PHT 最优模型 M′，按 exit profile **只加载高概率层**（如 OPT-1.3B 仅 6 层、OPT-6.7B 仅 9 层），释放的权重 + [[KV-Cache]] 显存用于扩 batch。Low-Exit Token（LT）直接早退；High-Exit Token（HT）触发二选一：**补全当前模型剩余层** vs **切换到另一候选的 partial load**——比较 PHT 中的资源开销 telemetry，选更省者。

**Step 4 — 周期性重 profiling**：每 RI=150 请求重跑 Step 2，适应 workload 漂移。SLO/硬件变化时才重选候选（论文观察到 Llama3-8B/Llama2-13B 跨任务稳定领先，GPT2-124M 稳定落后）。

**Accuracy safeguard — Confidence Breach Counter（CBC）**：在 100-token 窗口内，未达置信阈值的 token 计数；超过 CBCmax=50 才触发「补层 vs 换模」决策，利用观察 2 容忍零星低置信退出。该 amortization 减少切换频率。

**Latency spike 缓解**（§5.8）：预分配 HBM pool 避免 runtime `cudaMalloc`；加载新层与当前层计算 overlap；换模时同样 greedy partial load + pipeline。

与 [[Speculative-Decoding]] 对比：HELIOS 在同一模型族内 skip 层、无需 draft-verify 双模型并行验证；论文称 OPT-125M+OPT-6.7B speculative 在 CNN/DM 上能耗比 OPT-6.7B dual-exit 高 **1.49×**。LayerSkip 的 speculative draft 层静态，HELIOS 按请求流动态切换/补层。

## 设计取舍

- **Greedy 早退 vs 严格置信**：为扩 batch 与降延迟，允许未达阈值 token 退出；用 CBC + 补层/换模兜底。Table 8 显示「只切换不补层」吞吐最高但 perplexity 最差；「只补层不切换」精度好但吞吐低；默认动态二选一折中。
- **在线 profiling 开销 vs 分布准确性**：每候选 5 请求、RI=150 是 sweet spot；RI=50 吞吐最优但重评估频繁。1087 请求 trace 上切换/补层仅 **6 次**，单次 profiling 开销 **220ms**，相对 1.48× 吞吐增益可忽略。
- **多模型驻留 vs GPU 数量**：默认最多 3 候选、串行 profiling，避免多模型并行占满 GPU；生产需权衡候选多样性与硬件分区。
- **固定 exit 层 per timestep vs per-token 动态深度**：消除同步、解锁 batching，但可能对部分 token 过度计算或过早退出——依赖 CBC 与周期性重评估纠错。
- **Perplexity 代理精度**：实现简单、reference-free，但对 summarization/ROUGE 等任务的在线 guard 是否充分，论文只做了有限 downstream 验证（Table 7 ROUGE-2 可比）。

## 实验与结果

- **主吞吐**（prompt mix，batch=1 隔离 exit 收益）：相对单模型 EE-LLM，HELIOS 平均 **1.48×**（vs OPT-1.3B）、**2.13×**（vs OPT-6.7B）；91% token 在最早 exit 层处理（standalone 仅 73%），需全层的仅 **7.39%**（约 3× 降低）。
- **Batch size**（ShareGPT 等，greedy load 释显存）：相对现有 EE-LLM 框架最高 **15.14×**；内存 footprint 最多降 **67.4%**（Table 6）。Llama2-70B 在 4×A100 上权重占 **81.6%** 可用显存，HELIOS partial load 收益随模型增大而放大。
- **端到端 serving**：CodeLlama-34B + Llama2-70B on ShareGPT，相对 vanilla 吞吐 **+45%**（单模型 EE-LLM 仅 **+16%**）。
- **延迟**：TPOT 最高降 **46.6%**；TTFT 显著低于大模型 standalone（小模型 + 浅层 prefill）。OPT 场景 TTFT 相对 OPT-6.7B 最高 **30×** 改善（长输入 CNN/DM 段）。
- **精度**：prompt mix perplexity 仅比 OPT-1.3B 高 **0.01**；三候选（Llama2-7B/13B、Llama3-8B）下游 ROUGE-2 与 full-depth baseline 可比（Table 7）。
- **Ablation**：RI=150 默认；confidence threshold 升高时 standalone EE-LLM 吞吐骤降，HELIOS 仍稳定（Fig. 11）。能耗 SLO 下 0.45 Wh/prompt vs OPT-6.7B 1.01 Wh（**10%** 节省）。
- **硬件**：4×NVIDIA A100-40GB，NVLink 400 GB/s；Llama2-70B/CodeLlama-34B 分别 TP=4/2。

## Critical Analysis

### 论证链条

论文链条较完整：**测量单模型 EE-LLM 零显存收益 + batch=1 同步困境（§2.2, Fig. 1）→ 互补 exit 分布（Fig. 3, 6）与低置信不变性（Fig. 5, 13）支撑两条 insight → greedy partial load 释显存 + 固定 exit 层解锁 batch（§5.3）→ 1.48× 吞吐与 15.14× batch（§5.1, 5.3）**。CBC/补层/换模 ablation（Table 8）说明 accuracy guard 不是装饰，而是平衡 greedy 与精度的必要件。

较弱环节是把 **batch=1 吞吐实验** 与 **batch size 实验** 分拆报告：前者证明 multi-model exit 最大化，后者证明内存 机制——两者乘积才是 production 总收益，但论文未给出「大 batch + multi-model」联合饱和曲线。CodeLlama-34B + Llama2-70B 的 +45% vs vanilla 更接近真实 serving，但仍限于 4×A100 与固定候选集。

### 假设压力测试

- **候选模型可得性**：方法假设 MR 中已有多个 EE-LLM（LayerSkip 预训练或自 fine-tune OPT）。若运营商只部署单一最强模型，Insight-1 失效，HELIOS 退化为带 greedy load 的单模型 EE-LLM。
- **Greedy 退出边界**：Table 8「without loading」配置 perplexity 最高，说明仅靠切换不够；高 CBCmax 或激进 greedy 在 reasoning/code 任务上可能未被充分压测——主实验 entropy 偏高数据集（Fig. 14）反而对 greedy 友好。
- **Workload 漂移 vs RI**：RI=150 是工程默认，Fig. 12 显示 RI=50 吞吐更高；生产若 RI 过大且 CBC 未触发，可能长时间用过时 exit profile——论文承认风险但未给 detection metric。
- **多模型切换开销**：§5.8 优化后换模/补层开销小，但实验规模（6 次切换/1087 请求）是否代表百万 QPS 生产流量未知；与 [[Disaggregation]]、权重 offloading 混部时的交互 **论文未讨论**。
- **与量化/KV 压缩正交性**：论文声明可与 [[Quantization]]、KV compression 叠加，但未实验验证组合后 CBC/perplexity guard 是否仍稳。

### 实验可信度

- **Workload**：ShareGPT 代表 server-scale 对话；prompt mix 覆盖 summarization/reasoning/code/completion，entropy 分析表明预测难度不低。但到达过程与 tenant 混部细节未展开。
- **Baseline**：公平对比 Chen et al. 2024 同一 EE-LLM 框架的单模型模式；未与 [[Speculative-Decoding]]、[[vLLM]] + 静态量化、或 [[FlexiCache-MLSys26]] 类 KV 优化系统端到端对比——相关工作中能耗对比仅一点。
- **Scale**：限 3 候选、4×A100；Llama3.1-405B 仅作 memory 占比引用，未实测 HELIOS。TP 设定随模型变化，multi-node 扩展 **论文未覆盖**。
- **Metric**：吞吐/latency/perplexity 较全；缺 P99 尾延迟 SLO 违约率、multi-tenant 隔离、切换失败恢复。下游 accuracy 仅 ROUGE-2 子集。

### 系统性缺陷

- **尾延迟**：切换/补层即使有 pool 与 overlap，仍可能引入非确定性 spike；论文未报 P99/P999 TPOT 或 SLO 违约。
- **运维复杂度**：PHT、CBC、RI、候选集、partial load 状态使系统比单模型 EE-LLM 难调试；**可观测性/故障降级策略论文未讨论**。
- **正确性监控**：依赖 perplexity 而非 task-specific metric 或 LLM-judge；对无 ground truth 的开放生成，CBC 阈值是否跨模型族稳健未验证。
- **资源隔离**：多候选 profiling 串行占 GPU 周期，可能影响同节点其他 job 的 fairness。
- **兼容性**：需 EE-LLM 专用框架与 early-exit 权重变体；与标准 [[vLLM]] 单模型路径的集成成本 **论文未讨论**。

## 局限与 Future Work

- **局限 1**：GPU 有限，仅评 3 候选、串行 profiling；未验证大规模 model zoo 或超 70B 集群上的切换策略。
- **局限 2**：accuracy guard 基于 perplexity + CBC heuristic；高 RI 下 workload 漂移可能 undetected（§5.6 自述）。
- **局限 3**：batch 吞吐与 batch size 实验分拆，缺统一 production-like 饱和点测量；尾延迟与 SLO 未系统评估。
- **Future work 1**：在真实 multi-tenant trace 上测量「切换次数 / 补层次数 / P99 延迟」与吞吐的联合 frontier，自适应 RI 与 CBCmax。
- **Future work 2**：与 [[Quantization]]、KV tiering、[[Speculative-Decoding]] 组合，量化 greedy partial load 与内存优化技术的叠加边界。
- **Future work 3**：用 task-specific 在线 metric（或轻量 verifier）替代纯 perplexity，在 reasoning/code 等高熵 workload 上压测 greedy 退出的安全域。

## 相关

- **相关概念**：[[KV-Cache]]、[[Continuous-Batching]]、[[Speculative-Decoding]]、[[Quantization]]
- **同类系统**：EE-LLM 框架（Chen et al., 2024）、LayerSkip、[[vLLM]]
- **互补方向**：[[FlexiCache-MLSys26]]（KV 管理）、[[MorphServe-MLSys26]]（runtime 形变释显存）
- **同会议**：[[MLSys-2026]]