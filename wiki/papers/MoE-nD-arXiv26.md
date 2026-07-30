---
type: paper
name: MoE-nD
full_title: "MoE-nD: Per-Layer Mixture-of-Experts Routing for Multi-Axis KV Cache Compression"
authors: [Libo Sun, Peixiong He, Po-Wei Harn, Xiao Qin]
venue: arXiv
year: 2026
tags: [llm-inference, kv-cache, compression, quantization, long-context, routing]
source_pdf: "[[arxiv26-moe-nd.pdf]]"
source_md: "[[arxiv26-moe-nd]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MoE-nD：用于多轴 KV 缓存压缩的每层专家混合路由（arXiv 2026）

> **原题**：MoE-nD: Per-Layer Mixture-of-Experts Routing for Multi-Axis KV Cache Compression

> **一句话总结**：MoE-nD 的关键观察是 transformer layer 对 eviction、K quantization、V quantization 的敏感度和轴间偏好高度不均匀；它用离线校准的 greedy router 为每层选择 `(keep ratio, K bits, V bits)`，在 DeepSeek-R1-Distill-Qwen-7B 的 LongBench 4-task 子集上用 136 MB [[KV-Cache]] 达到 14x compression，并在相同评测协议下匹配 1.9 GB full-cache baseline。

## 问题与动机

长上下文推理把 [[KV-Cache]] 变成推理内存的主瓶颈：每个 sequence 的 cache 随 `layers x sequence length x KV heads x head dim x precision` 线性增长，长 prompt 或长 chain-of-thought generation 很快把单请求 cache 推到 GB 级。现有压缩方法通常沿单轴工作：token eviction 压 sequence 轴，[[Quantization]] 压 precision 轴，low-rank projection 压 head dimension，cross-layer sharing 压 layer 轴。

论文要挑战的是这些方法常见的 **layer-homogeneous** 假设。即使组合 eviction 和 quantization，许多系统仍给所有层相同 keep ratio、相同 K/V bit-width；已有 per-layer 工作也多局限在单一轴，比如 AdaKV/PyramidKV 只分配 eviction budget，KVTuner 只分配 K/V precision。MoE-nD 的 claim 是：如果每层对不同压缩轴的敏感性不同，那么真正的设计空间应该是 per-layer、multi-axis 的联合路由，而不是给所有层同一套压缩 recipe。

这个 claim 的边界也很重要。论文不是证明“任何 KV 压缩都应该复杂化成 per-layer solver”，而是证明在长 context 或长 generation、且 memory budget 紧到必须实际驱逐 token 的场景里，per-layer eviction routing 是一个 load-bearing 设计点；短 prompt 或宽松预算下，solver 大多选择 `keep=1.0`，异构 eviction 没有发挥空间。

## 关键观察 / 隐含假设

- **观察 1：aggressive eviction 的 layer sensitivity 差异达到两个到三个数量级。** 在 DeepSeek-R1-Distill-Qwen-7B 的 28 层上，mild eviction 的 max/min L2 error ratio 只有 1.6-2.6x，但 evict75 和 evict90 分别达到 548x 和 689x。也就是说，一些层几乎可以被大幅驱逐，另一些层同样操作会显著破坏 attention output。
  - **依赖假设**：attention-output relative L2 error 是可用的质量 proxy，且 DeepSeek-R1-Distill-Qwen-7B 的 per-layer sensitivity 结构能代表目标部署模型。
  - **可能失效场景**：不同模型家族、position encoding、GQA/MQA 配置、长上下文训练方式、或完全不同的任务分布可能改变层敏感性排序；如果模型本身已经做了稀疏/压缩 attention 训练，这个 sensitivity landscape 也可能变平。
- **观察 2：K quantization 有 per-layer headroom，V quantization 接近 uniformly safe。** Table 1 显示 K8 的 max/min ratio 约 87x、K4 约 15x，而 V8/V4 只有 1.6x/1.2x。MoE-nD 因此把 K/V bits 纳入路由，但实际收益主要不是来自 V 轴。
  - **依赖假设**：per-channel K quantization 和 asymmetric group V quantization 的误差形态稳定；如果硬件或 quantization kernel 对 K/V 的代价不同，solver 的 memory-cost model 需要重写。
  - **证据强度**：中。单模型 sensitivity table 很清晰，KL calibration 也支持 within-layer ranking；但论文没有跨模型展示 K/V 轴的普适性。
- **观察 3：同等 memory cost 下，不同层偏好的压缩轴会翻转。** Figure 2 比较 `evict50` 与 `K4`：L00 上 eviction error 0.49、K4 error 1.09，偏向 eviction；L06 上 eviction error 0.90、K4 error 0.088，偏向 quantization。统一策略无法同时照顾这两类层。
  - **依赖假设**：不同压缩轴的 error 可以被一个统一 sensitivity score 比较，并且逐层独立测得的 sensitivity 能近似组合后的质量损失。
  - **可能失效场景**：压缩误差跨层耦合强、某些层的误差会被后续层放大/抵消、或 calibration prompt 过短导致轴间偏好估计不稳时，greedy choice 可能选错。
- **观察 4：异构 eviction 只有在 budget 真的迫使多层 eviction 时才有收益。** MATH-500 和 LongBench TREC 没有 MoE-nD 优势，因为输入短或预算松，solver 在超过 75% 层上选择 `keep=1.0`，2dhetero 退化为 2d。
  - **依赖假设**：目标 workload 有足够长的 prompt 或 generation，让 [[KV-Cache]] memory 成为主导瓶颈，而不是调度、权重加载、网络、prefix cache miss 或专家 offload。
  - **证据强度**：强于一般负结果。论文把无收益场景和 solver decision 联系起来，而不是只报告平均分。
- **假设 1：轻量 calibration 足以驱动 routing。** 主 sensitivity table 来自一个 27-token reasoning prompt，metric 是单层压缩 attention output 与 full attention output 的 relative L2 error；Appendix B 用 8 条 2048-token held-out sequences 的 KL calibration 验证，平均 Pearson 0.945、Spearman 0.937。
  - **证据强度**：中偏强，但边界清楚。验证支持 solver 需要的 within-layer ranking；cross-layer ranking 在 eviction 配置上噪声较大，且 calibration workload 远小于 LongBench/AIME 的真实长度。

## 核心方法

MoE-nD 把每层 compression choice 写成三轴 tuple：`(keep ratio, kbits, vbits)`。keep ratio 来自 `{0.1, 0.25, 0.5, 0.75, 0.9, 1.0}`，K/V bit-width 来自 `{16, 8, 4}`。eviction 使用 TriAttention-style trigonometric importance signal，K 采用 per-channel quantization，V 采用 asymmetric group quantization。论文标题里的 MoE 是 routing analogy：这里不是 [[MoE]] 模型里的 expert FFN，而是把 eviction、K quantization、V quantization 这些压缩操作当成可被 router 选择的 expert。

**Offline sensitivity probing** 对每个 layer 和候选配置单独施加压缩，测量该层 attention output 相对 full attention output 的 L2 error，形成 `S[layer, config]`。这个 calibration 是 model-specific 的，论文把它当作一次性离线成本；router 后续只消费这些 per-layer candidate ranking，不在每个请求上重新测量。

**Greedy budget solver** 在全局 memory budget 下选择每层 tuple。精确搜索规模是 `(6 x 3 x 3)^L`，28 层时不可行；MoE-nD 采用 KVTuner 式 greedy allocator：从每层最便宜配置开始，反复把单位额外 memory 能带来最大 sensitivity reduction 的 layer upgrade 加进去，直到预算耗尽。这个设计牺牲全局最优性，换来小于 50 ms 的 CPU solve time 和很简单的实现。

**Heterogeneous attention patch** 是系统实现里的关键补丁。不同层保留的 cache 长度 `T_l` 不同，驱逐后的 token position 也会分叉；MoE-nD 为每层维护 retained token 的 original position array `p(l)`，下一步 generation 做 RoPE re-inversion 时使用每层自己的 position，而不是全局 position。eviction 每 128 个 generated token 触发一次，避免逐 token 维护成本失控。所有层配置相同时，这个 patch 退化为普通 uniform attention，因此 1d/2d uniform 是它的特例。

方法和观察的对应关系比较直接：Observation 1/3 需要 per-layer eviction routing，Observation 2 支持把 K/V bit-width 也纳入 routing，Observation 4 则限定何时值得使用 full hetero path。论文最重要的实证结论是：多轴框架是必要的外壳，但真正贡献主要来自 per-layer eviction routing，而不是 per-layer quantization routing。

## 设计取舍

- **简单 greedy vs 全局最优。** Greedy solver 很容易实现、求解快，也复用 KVTuner 的分配思路；代价是它假设 marginal benefit 可局部排序，无法保证跨层/跨轴组合全局最优。考虑到 calibration proxy 自身也有噪声，追求精确 combinatorial optimality 可能并不值得。
- **静态离线 calibration vs request-adaptive routing。** 一次离线测表让推理路径轻量，但它不会根据具体 prompt、任务、tenant 或 generation 状态动态改变 routing。长文档 QA、数学 CoT、代码检索可能需要不同压缩分布。
- **异构 cache 表达力 vs kernel/engine 兼容性。** 每层不同 cache length 和 bit-width 让 routing 有空间，但也破坏了现有 [[Flash-Attention]] / [[PagedAttention]] / continuous batching 栈里大量“层间形状一致”的假设。论文当前实现只能用 eager attention，和 FlashAttention 不兼容。
- **KV memory 节省 vs prefill 峰值。** 论文报告 compressed KV size 的大幅下降，但 eager attention 在 16k prefill 时仍有 `O(T^2)` attention matrix 峰值，这会掩盖 KV 压缩在真实端到端内存中的收益。
- **相对质量 claim vs 绝对 benchmark 水平。** LongBench full-cache baseline 只有 11.5 average，远低于 Llama-3-8B-Instruct 公开结果；论文诚实地把原因归为 reasoning model 输出长 `<think>` 链和 scoring mismatch。因此主要 claim 应读作同一模型/同一 harness 下的 relative gap，而不是 LongBench SOTA。

## 实验与结果

**指标与基线**：LongBench/AIME score、KV memory 与生成质量；对比 full KV、non-heterogeneous 2d routing，限定为 DeepSeek-R1-Distill-Qwen-7B 的 H200 eager harness（§5）。

- **实验设置**：主模型是 DeepSeek-R1-Distill-Qwen-7B，28 层、8 KV heads、head dim 128；单 H200、bfloat16、eager attention。LongBench-v1 选 4 个超过 16k 输入窗口的任务，各取 n=50；AIME-24/AIME-25 各 n=30，max generation 16k；MATH-500 是短 prompt 负结果检查。
- **Reasoning-model protocol**：LongBench 默认 generation length 对 reasoning model 不够，论文把 max gen 扩大 16x，并只评分最终 `</think>` 之后的文本。这个修复保证方法间公平，但也让绝对 F1 不可直接和 instruction-tuned LongBench 表格比较。
- **LongBench 主结果**：2dhetero 在 b=512 时用 136 MB cache 得到 12.0 average，和 full-cache 1.9 GB baseline 的 11.5 没有可检测损失；同等内存附近的 2d baseline 用 139 MB 只有 5.9。四个 hetero operating points 的压缩率约为 14x、6.6x、3.2x、1.6x。
- **LongBench 分任务**：HotpotQA、NarrativeQA、PassageRetrieval-en 三项基本支撑 hetero gain；TREC 没有优势，full 为 22.0，2dhetero 在四个 budget 下是 20.0/22.0/24.0/22.0。论文把 TREC 归为短输入/宽松预算导致的退化场景。
- **AIME reasoning**：2dhetero 在 AIME-24/AIME-25 的 8 个 budget x dataset cell 里全部超过 2d，优势从 +6 到 +27 pts。AIME-25 b=64 时，2dhetero 得 30.0，而 2d 只有 3.3；AIME-25 b=256 时，2dhetero 36.7 甚至超过 full 30.0。由于 n=30，单个 cell 的置信区间很宽，论文依赖的是 8/8 一致方向和 tight budget 下差距扩大的 pattern。
- **Ablation 归因**：`2duniform -> 2d` 隔离 per-layer quant routing，AIME 上平均 -2.1 pts；`2d -> 2dhetero` 隔离 per-layer eviction routing，平均 +15.0 pts。LongBench 上同样是 eviction routing 平均 +5.7 pts，而 quant routing 平均 -0.35 pts。这个 ablation 很关键：论文的新意不是“多做一个复杂 router”，而是证明 eviction 轴才是主要 leverage。
- **负结果**：MATH-500 上 full 为 50.4，2dhetero 在 b=64/128/256/512 分别为 48.6/50.4/48.0/50.0，没有超过 2d；论文解释为短 prompt 下多数层 `keep=1.0`，hetero eviction 无从发挥。1d 在部分宽松 budget 下高于 full，作者推测 aggressive eviction 可能删掉自我干扰的 CoT token，但不把它计入 MoE-nD 的主要贡献。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Eviction sensitivity is layer-dependent | relative L2 max/min 548× at evict75 and 689× at evict90 (§3, Table 1/Fig.2) | one DeepSeek-R1-Distill-Qwen-7B prompt, one layer at a time | high |
| Per-layer routing preserves tested LongBench score at matched memory | 12.0 at 136MB/14× vs full 11.5 at 1859MB and 2d 5.9 at 139MB (§5.1–5.2, Table 2) | four truncated 16K tasks, 50/task, H200 eager; no detectable loss, not equality proof | high |
| Heterogeneous routing beats 2d on tested AIME cells | +6 to +27 points in 8/8 AIME-24/25 cells (§5.3–5.4, Table 4) | 30 problems/dataset, 16K generation, wide per-cell CIs | high |
| Ablation attributes most lift to eviction routing | AIME Δevict +15.0 points vs Δquant −2.1 (§5.4, Table 5) | one model/harness, routed dimensions only | high |
| Loose short-context cases leave little heterogeneity headroom | solver keeps 1.0 for over 75% layers (§5.5, Table 6) | MATH/TREC only | high |

## 批判性分析

### 论证链条

论文的主链条是闭合的：先用 sensitivity landscape 证明 per-layer heterogeneity 和 axis preference flip，再用 greedy solver 把它转成每层 tuple，最后用 `2duniform -> 2d -> 2dhetero` ablation 证明收益主要来自 per-layer eviction routing。最强的证据是 LongBench matched-memory comparison：136 MB 的 2dhetero 是 12.0，而 139 MB 的 2d 是 5.9，这正好击中了“只改 per-layer eviction”这条因果链。

比较薄弱的是外推范围。LongBench 只选 4 个任务、每项 n=50，且 full baseline 绝对分数很低；AIME 每项 n=30，论文也承认单 cell 不具统计显著性。它证明了在一个受控 harness 上 hetero routing 的相对优势，但还没有证明它是生产 serving 系统里稳定的端到端优化。

### 假设压力测试

workload 假设最脆弱的是“长 context 或长 generation 足够常见，且 cache budget 紧到必须驱逐 token”。如果生产负载主要是短 prompt、强 prefix sharing 的 [[Prefix-Caching]]、RAG 外部检索、或高并发小 batch decode，MoE-nD 可能退化为简单 2duniform/2d，额外 patch 复杂度不划算。

hardware/deployment 假设也偏窄。论文在单 H200 eager attention 上评估，而现代 serving 栈依赖 [[Flash-Attention]]、paged KV manager、continuous batching、tensor parallel 和 sometimes prefill/decode [[Disaggregation]]。每层不同 cache length、不同 bit-width、不同 eviction trigger 会给 scheduler、kernel fusion、memory allocator 和 observability 带来额外状态。

model 假设需要跨 family 验证。DeepSeek-R1-Distill-Qwen-7B 有 reasoning-style generation、GQA 和 28 层结构；Llama、Mistral、Qwen instruct、dense vs [[MoE]] backbone、更大/更小模型都可能改变“哪些层适合 evict、哪些层适合 quant”的分布。论文说预计 heterogeneity 机制和 RoPE/GQA/residual scale 相关，但这仍是 empirical question。

### 实验可信度

内部实验设计相当干净：所有方法用相同模型、相同 prompt、相同 scoring extraction，并且报告 actual compressed KV memory，而不是只报告 nominal budget。negative result 也解释到 solver choice，而不是藏起来。这让 relative comparison 比很多 KV 压缩论文更可信。

主要缺口是 baseline 和系统 metric。SnapKV、H2O 等外部 attention-eviction baseline 没有直接 matched-memory 对比；作者预计它们会落在 1d band，但这是推断，不是实验证明。系统指标也主要是 compressed KV memory 和 accuracy，没有 TTFT/TPOT、P95/P99 latency、HBM traffic、kernel occupancy、batch scheduler interaction 或 multi-tenant isolation。

calibration proxy 的验证是优点也是边界。KL validation 支持 within-layer ranking，足以让 greedy solver 工作；但主表来自一个 27-token prompt，无法说明 task-conditioned sensitivity 是否稳定。特别是 retrieval、代码、数学证明这类关键 token 分布很不一样的任务，可能需要多 prompt calibration 或 request-adaptive correction。

### 系统性缺陷

论文最实在的系统缺陷是 FlashAttention incompatibility。只要 heterogeneous attention patch 不能进入主流 fused attention kernel，MoE-nD 的 memory saving 可能被 eager attention 的 latency 和 prefill `O(T^2)` peak memory 吃掉。对服务系统而言，这不是小实现细节，而是能否部署的门槛。

第二个缺口是 tail behavior。每层保留 token 数不同，batch 内每个 request 的 retained positions 也不同，可能导致不规则 memory access、kernel branch divergence 和 per-request latency variance。论文报告平均 accuracy/memory，没有讨论 P99、QoS、OOM recovery、或某些 request 被过度驱逐后的质量退化监控。

第三个缺口是和现有 KV 管理抽象的组合。[[PagedAttention]]、[[RadixAttention]]、prefix cache、KV offload、disaggregated KV transfer 都把 cache 组织成 page/block 或跨节点对象；MoE-nD 的 per-layer variable-length retained-token arrays 需要一个更通用的 page metadata abstraction，否则很难作为 vLLM/SGLang 插件落地。

## 局限与后续工作

- **局限 1：单模型、单硬件、单实现路径。** 需要在 Llama/Qwen/Mistral/instruction-tuned 模型、dense 与 [[MoE]] backbone、H100/Blackwell/MI300X、FlashAttention-compatible kernel 上复现 sensitivity landscape 和 routing gain。
- **局限 2：LongBench 绝对分数低且任务子集小。** 当前 claim 适合读成 relative compression result；要证明通用长上下文质量，需要在完整 LongBench、Needle/retrieval/code/agent trace 上报告更高质量 baseline 和统计检验。
- **局限 3：外部 eviction baselines 缺位。** SnapKV、H2O、PyramidKV、AdaKV、KVTuner、KIVI、KVQuant 应在 matched actual memory、相同 scoring protocol 下对比，避免“1d proxy baseline”承担过多解释责任。
- **局限 4：部署指标未覆盖。** 论文没有展示端到端 serving 的 TTFT、TPOT、P95/P99、吞吐、HBM traffic、allocator fragmentation、multi-tenant fairness 或 failure recovery。
- **Future work 1：做 production-trace replay。** 用真实长 prompt / 长 CoT 请求分布，按 input length、generation length、prefix sharing、tenant mix 分桶，测量何时 2duniform 已足够、何时 MoE-nD 才有净收益。
- **Future work 2：实现 FlashAttention / paged KV compatible hetero kernel。** 把 per-layer retained positions、bit-width、eviction mask 变成 page/block metadata，让 [[Flash-Attention]]、[[PagedAttention]] 和 heterogeneous compression 在同一个 kernel path 里共存。
- **Future work 3：扩展 calibration。** 比较 single-prompt L2、multi-prompt KL、task-conditioned probes、online canary quality signal 对 routing choice 的影响，判断 greedy solver 是否需要 uncertainty-aware upgrade。
- **Future work 4：探索 request-adaptive routing。** 对数学 CoT、retrieval QA、代码、表格等 workload 分别学习 routing prior，或者让 solver 根据 prompt length、task type、budget pressure 动态切换配置。

## 相关

- **相关概念**：[[KV-Cache]]、[[Quantization]]、[[Attention]]、[[Sparse-Attention]]、[[MoE]]、[[PagedAttention]]、[[Flash-Attention]]
- **同类方法**：AdaKV、PyramidKV、KVTuner、KIVI、KVQuant、MiniKV、SnapKV、H2O、StreamingLLM、TriAttention
- **相关系统 / 论文**：[[FlexiCache-MLSys26]]、[[SkipKV-MLSys26]]、[[OPKV-MLSys26]]、[[IceCache-arXiv26]]、[[vLLM]]、[[SGLang]]
- **同专题**：[[AI-Infra]]
- **对比方向**：MoE-nD 与 [[Sparse-Attention]] 类方法的差别在于它不训练新 attention architecture，而是在既有模型推理时压缩 [[KV-Cache]]；与 [[PagedAttention]] 类内存管理的差别在于它改变每层保留 token 和 precision，而不是只改善 cache placement。
