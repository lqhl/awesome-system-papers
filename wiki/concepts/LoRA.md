---
type: concept
aliases: [lora, LoRA, Low-Rank Adaptation, low-rank adaptation, LoRA adapter, PEFT, QLoRA, DoRA, LoRA-FA]
parent: "[[LLM-Inference]]"
introduced_by: LoRA-ICLR22
last_updated: 2026-07-30
tags: [fine-tuning, peft, llm-training, model-compression]
---

# LoRA

> 大模型微调的主流方案：冻结原权重 \(W_0\)，给它加一个低秩增量 \(\Delta W = BA\)，\(B \in \mathbb{R}^{d \times r}\)，\(A \in \mathbb{R}^{r \times d}\)，\(r\) 常 8–64。可训练参数从 \(d^2\) 降到 \(2dr\)；推理时 \(W = W_0 + BA\) 合并回去，**零 latency overhead**。对 serving 侧的影响同样巨大：多租户共享 base model、每租户只挂一对小 adapter，显存从 \(N \times 70\)GB 降到 \(70\)GB + \(N \times\) few MB。

## 核心思想

LoRA 的核心观察是：fine-tune 产生的权重更新 \(\Delta W = W - W_0\) 经验上是 **low-rank** 的——即使 \(W \in \mathbb{R}^{d \times d}\)，有效秩往往只有几十。因此只训练低秩分解 \(BA\)，而不训练完整 \(\Delta W\)。

```
前向：y = W₀ x + B A x    （A 高斯初始化、B 零初始化，保证初始 ΔW=0）
反向：只更新 A、B
```

典型插入位置是 attention 的 Q/K/V/O projection 和/或 FFN 的 up/down projection。Rank \(r=8\) 够大多数任务，\(r=64\) 适合更大 domain shift。推理前 merge 进 \(W_0\) 则与 dense 模型无异；多租户 serving 则保留独立 adapter，由 kernel 支持 per-sequence 不同 LoRA（S-LoRA、Punica 等路线）。

LoRA 也是 **系统边界上的压缩与组合原语**：QLoRA 把 \(W_0\) 量化到 INT4 + LoRA FP16；联邦场景下 adapter 是通信与聚合的基本单位；扩散语言 model 用 LoRA 做 block-causal 蒸馏（[[CDLM-MLSys26|CDLM]]）；甚至与 KV-prefix 参数化（[[Cartridges-ICLR26|Cartridges]]、Prefix Tuning）形成对照——后者把下游知识压进 cache 而非权重矩阵。

## 为什么重要

LoRA 同时改变了 **训练经济学** 与 **serving 拓扑**。

训练侧：7B 模型 full fine-tune 的 Adam 状态可达约 56GB，LoRA 只需几十 MB 可训练参数，使单卡/消费级 GPU fine-tune 成为可能。联邦侧，[[FLoRIST-MLSys26|FLoRIST]] 指出 FedIT 平均 adapter 引入 cross-term noise、FlexLoRA 全矩阵 SVD 内存爆炸、FLoRA 通信随 client 线性膨胀——说明 **LoRA 的系统问题已从「怎么训」变成「怎么聚合、怎么通信」**。

Serving 侧：base model 共享一份权重，每租户挂 adapter pair，是 multi-tenant LLM 的默认模式。但 batched LoRA 要求 attention/FFN kernel 支持 per-token 不同 adapter，否则动态切换权重会成为吞吐瓶颈。

这些论文还揭示 LoRA 与相邻优化的 **正交可叠加性**：[[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] 的运行时 neuron 稀疏激活与 LoRA 正交；[[ZK-APEX-MLSys26|ZK-APEX]] 把可验证 fine-tuning 建立在 LoRA 低秩结构上，利用参数少降低证明成本。

## 关键观察 / 隐含假设

- **观察 1：权重更新的内在秩可远低于客户端设定的 rank。** [[FLoRIST-MLSys26|FLoRIST]] 测得聚合后部分层内在秩仅 **2–10**，即使 client rank=64；奇异值阈值可在通信与精度间找最优点（TinyLlama MMLU peak @ τ=0.99）。
- **观察 2：stacked adapter 可在 \(r \times r\) 中间空间 SVD，无需物化 \(m \times n\) 全矩阵。** [[FLoRIST-MLSys26|FLoRIST]] 相对 FlexLoRA server FLOPs 省约 **350×**，8 client 下载通信比 full FT 省 **227×**。
- **观察 3：LoRA 是轻量 post-training 的默认载体。** [[CDLM-MLSys26|CDLM]] 用 LoRA 在 8–16h 内把 DLM 蒸馏为 block-causal student，latency **3.6–14.5×**；[[RLVR-LowData-MLSys26|RLVR-LowData]] 在 low-data RL 中用 LoRA 做 policy 更新。
- **观察 4：KV-prefix 参数化在部分场景优于 LoRA。** [[Cartridges-ICLR26|Cartridges]] 在 memory-matched 对比中，prefix/KV 参数化在 in/out-domain 上强于 LoRA；serving 侧无需动态切换权重矩阵，但牺牲可解释性。
- **观察 5：长上下文与分布式训练对 LoRA 提出结构变体需求。** [[CDLM-MLSys26|CDLM]]、[[ProToken-MLSys26|ProToken]] 等从架构与系统两侧扩展标准 LoRA 的适用边界。
- **观察 6：多租户 adapter 会与静态编译/runtime 所有权冲突。** [[MPK-OSDI26]] 的 persistent mega-kernel 主结果未覆盖动态 LoRA adapter；若每个 sequence 使用不同 adapter，task graph specialization、权重地址和公平调度都需重新设计。

## 设计空间与取舍

- **低秩增量 vs 全量微调**：参数与通信效率极高，但表达能力受 rank 上限约束；[[FLoRIST-MLSys26|FLoRIST]] 的阈值截断类似正则，过高噪声伤 MMLU。
- **merge-at-inference vs dynamic per-tenant adapter**：merge 零 overhead 适合单任务部署；multi-tenant 需 S-LoRA/Punica 类 batched kernel，增加实现复杂度。
- **QLoRA vs FP16 LoRA**：单卡可训更大 base，但量化 \(W_0\) 与 adapter 精度交互需仔细评测。
- **联邦聚合策略**：FedIT（平均，有噪声）vs FlexLoRA（全矩阵 SVD，贵）vs FLoRA（stack 通信随 client 增）vs FLoRIST（stack + 小空间 SVD + 阈值）——取舍在数学准确性、server 算力与 download 带宽。
- **LoRA vs KV-prefix / Cartridge**：[[Cartridges-ICLR26|Cartridges]] 适合窄域、高复用 KV cache 装载；[[RAG]] 保留原文更可解释。LoRA 改权重，Cartridge 改 cache 对象。
- **与 serving 栈**：[[Continuous-Batching]]、[[KV-Cache]]、[[Quantization]]（QLoRA 训练、INT4 推理）需联合考虑。

## 引用本概念的论文

- [[FLoRIST-MLSys26|FLoRIST]] — 联邦 LoRA stacked SVD + 奇异值阈值，通信比 FLoRA **227×** 省、server FLOPs 比 FlexLoRA **350×** 省。
- [[CDLM-MLSys26|CDLM]] — 用 LoRA 微调 block-causal DLM student，推理 latency **3.6–14.5×**。
- [[ZK-APEX-MLSys26|ZK-APEX]] — 可验证 LoRA fine-tuning，利用低秩结构降低证明开销。
- [[RLVR-LowData-MLSys26|RLVR-LowData]] — low-data RL 场景用 LoRA 做 policy 更新。
- [[ProToken-MLSys26|ProToken]] — LoRA 分布式训练加速。
- [[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] — 运行时 neuron 稀疏激活与 LoRA 正交可叠加。
- [[Cartridges-ICLR26|Cartridges]] — 对比 KV-prefix 与 [[LoRA]] 在 per-corpus 表示与 serving 成本上的取舍。
- [[Katz-ATC25|Katz]]、[[Toppings-ATC25|Toppings]] — LoRA 与 serving/训练系统栈集成（见各 paper 页）。
- [[PLayer-FL-MLSys26|PLayer-FL]] — 联邦场景层选择与 LoRA 协同（见 paper 页）。
- [[MPK-OSDI26]]、[[CacheSlide-FAST26]] — OSDI 2026 与层级缓存系统共同提示 adapter、prefix cache 和静态编译需要联合评测。
- [[CLONE-ATC25]]、[[mTuner-ATC25]]、[[Jenga-ATC25]]、[[AssyLLM-ATC25]]、[[LLMStation-ATC25]]、[[Katz-ATC25]]、[[Toppings-ATC25]] — LoRA 训练与多 adapter serving 的资源共享路线。
- [[AccelOpt-MLSys26]]、[[OptiKit-MLSys26]]、[[MixLLM-MLSys26]]、[[MSA-arXiv26]] — adapter 与 compiler/runtime、优化器和混合 workload 的组合边界。
- [[TimesFM-Fin-arXiv24]]、[[PASTA-ICLR24]] — 垂直任务与参数高效适配场景。

## 已知局限 / 开放问题

- 联邦 LoRA 的 τ 自动选择、百/千 client upload 带宽、secure aggregation 与 DP 组合仍未系统评测（[[FLoRIST-MLSys26|FLoRIST]]）。
- 多 LoRA 组合的 task arithmetic / mixture 在 serving 侧的 batched kernel 与公平调度仍随 tenant 数扩展。
- LoRA 与 [[Prefix-Caching]]、[[Quantization]]、[[MoE]] expert 加载的交互在 production trace 上缺少端到端数据。
- KV-prefix（[[Cartridges-ICLR26|Cartridges]]）何时优于 LoRA 的任务分解标准仍开放：窄域 extractive vs 需 citation vs 频繁 corpus 更新。
- 恶意 client 污染 federated stack、adapter 版本与 base model 升级的兼容性矩阵未充分讨论。
