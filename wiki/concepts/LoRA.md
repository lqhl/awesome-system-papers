---
type: concept
aliases: [lora, LoRA, Low-Rank Adaptation, low-rank adaptation, LoRA adapter, PEFT, QLoRA, DoRA, LoRA-FA]
parent: "[[LLM-Inference]]"
introduced_by: "[[LoRA-ICLR22]]"
last_updated: 2026-04-24
tags: [fine-tuning, peft, llm-training, model-compression]
---

# LoRA

> 大模型微调的主流方案：冻结原权重 `W₀`，给它加一个低秩增量 `ΔW = BA`，B∈R^{d×r}，A∈R^{r×d}，r 常 8-64。可训练参数从 d² 降到 2dr（百倍到千倍少），16GB GPU 都能 fine-tune 7B 模型；推理时 `W = W₀ + BA` 合并回去，**零 latency overhead**。衍生版本 QLoRA（W₀ INT4 + LoRA FP16）进一步把硬件门槛降到单张消费卡。对 serving 侧的影响也巨大：多租户共享 base model、每租户只挂一对小 LoRA，显存从 N × 70GB 降到 70GB + N × few MB。

## 核心思想

Hu et al. 2022 的观察：fine-tune 产生的权重更新 `ΔW = W - W₀` 经验上是 low-rank 的——即使 `W ∈ R^{d×d}`，`ΔW` 的有效秩只有几十。所以不必训练整个 `ΔW`，只训练它的低秩分解即可。

```
前向：y = W₀ x + B A x    （A 初始化为高斯、B 初始化为 0，保证开始时 ΔW=0）
反向：只更新 A、B
```

典型插入位置：attention 的 Q、K、V、O projection 和/或 FFN 的 up/down projection。Rank r = 8 够大多数任务，r = 64 适合更大的 domain shift。

## 为什么实用

- **参数效率**：7B 模型 FFT 需 ~56GB optimizer 状态（Adam FP32），LoRA 只要 ~几十 MB
- **存储 / 分发**：每个下游任务只存 LoRA adapter（几 MB）而非完整 checkpoint
- **可组合**：多个 LoRA 可以加法合并或线性插值，实现 task arithmetic
- **推理时零开销**：可以把 `BA` merge 进 `W₀`，与原模型无异

## 变体

| 变体 | 要点 |
|---|---|
| **LoRA** (原始) | 低秩 B、A |
| **QLoRA** | W₀ 量化到 INT4 + LoRA FP16，单 24GB GPU fine-tune 33B |
| **DoRA** | 把权重分解成方向 + 模长，只低秩调方向 |
| **LoRA-FA** | A 冻结，只训 B，再省一半 |
| **VeRA / Tied-LoRA** | 跨层共享 A/B |
| **MoLE / LoRAHub** | 多 LoRA 的 mixture-of-experts 式组合 |

## Serving 侧的 LoRA

多租户 serving：base model 共享一份权重，每租户挂自己的 LoRA pair。关键是让 attention / FFN kernel 支持"每 sequence 用不同 LoRA"（batched LoRA）：
- **S-LoRA** (MLSys 2024)：unified paging 管理 LoRA，一次 kernel call 处理 >2000 个 LoRA
- **Punica**：segmented LoRA kernel（SGMV），把所有 LoRA 的 A/B 拼成一个大矩阵按 token 分组算

## 引用本概念的论文

- [[FLoRIST-MLSys26|FLoRIST]] — LoRA 训练系统
- [[CDLM-MLSys26|CDLM]] — 长上下文 LoRA 变体
- [[ZK-APEX-MLSys26|ZK-APEX]] — 可验证 LoRA fine-tuning
- [[RLVR-LowData-MLSys26|RLVR-LowData]] — low-data RL 用 LoRA 做 policy 更新
- [[ProToken-MLSys26|ProToken]] — LoRA 的分布式加速
- [[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] — 运行时 neuron 稀疏激活与 LoRA 正交可叠加

## 相关概念

- 上游：[[LLM-Inference]]、微调范式
- 互补：[[Quantization]]（QLoRA）、[[Distillation]]、[[In-Context-Learning]]（作为微调的对照）
- Serving：[[Continuous-Batching]]、[[KV-Cache]]
