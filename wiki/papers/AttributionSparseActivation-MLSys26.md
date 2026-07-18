---
type: paper
name: AttributionSparseActivation
full_title: "ATTRIBUTION-BASED SPARSE ACTIVATION IN LARGE LANGUAGE MODELS"
authors: [Jifeng Song, Xiangyu Yin, Boyuan Yang, Kai Huang, Weichen Liu, Wei Gao]
venue: MLSys
year: 2026
tags: [llm-inference, sparsity, runtime-adaptation, attribution, quantization]
source_pdf: "[[c9e1074f5b3f9fc8ea15d152add07294.pdf]]"
source_md: "[[c9e1074f5b3f9fc8ea15d152add07294]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# ATTRIBUTION-BASED SPARSE ACTIVATION IN LARGE LANGUAGE MODELS (MLSys 2026)

> **一句话总结**：论文用 Corrected G×O 估计 sparse activation 的 layer-dependency error；在 Llama-3-8B/TruthfulQA、60% sparsity 下，BLEU 为 21.66，优于 uncorrected G×O 的 3.59 与 magnitude 的 11.97；Phi-2、70% sparsity 的 cold-start 单请求中，forward latency / GPU memory 为 1.06 秒 / 7.91GB，相对 dense 的 1.59 秒 / 13.76GB（§7.1/7.6，Table 1/5）。

## 问题与动机

[[LLM]] 推理成本高；离线剪枝/量化需重训且难随输入/runtime 适配。[[Sparse-Activation]] 可在前向中按输入动态关闭 neuron，与 [[LoRA]]、[[Speculative-Decoding]]、[[KV-Cache]] 压缩正交。传统 lossless 做法只关零输出 neuron，对 ReLU 时代 [[OPT]] 有效，但对 GeLU/SiLU 的高参数效率模型（[[Llama-3]]、Phi-2、Gemma）几乎无零激活。

强行按 output magnitude 关 neuron 会在多步生成中破坏跨 token 一致性。作者转向 **lossy** attribution-based sparse activation：关「低贡献」neuron，并修正 G×O 指标在层间依赖下的排序错误。

## 关键观察 / 隐含假设

- **观察 1：magnitude-based 稀疏在 Phi-2/Llama-3-8B 上极低激活率即大幅掉点，而 G×O/IG attribution 显著更稳。** TruthfulQA 上 IG 与 G×O 接近，G×O 只需单次 forward+backward。
  - **依赖假设**：生成任务的多步 forward 中，单步 attribution 排序足以指导整步 neuron mask。
  - **可能失效场景**：tool-call 导致 attention 模式突变、或极短输出任务收益有限。

- **观察 2：neuron 停用会改变同层/后续层 attribution（层间依赖），高激活率时 MLP 层排名翻转最严重。** Phi-2 上 attribution 变化随激活率上升而放大；逐 neuron 精确计算太贵。
  - **依赖假设**：层间依赖误差可用解析 corrective term 一次向量化解，不必逐层迭代重算。
  - **可能失效场景**：极深网络或强非线性层（MoE routing）下界可能不紧。

- **观察 3：Corrected G×O 在所测表格配置中优于未修正 attribution；速度与内存收益随模型、任务与 activation ratio 变化，应分开报告（§7.1、§7.6，Table 1/5）。**
  - **依赖假设**：框架 sparse API 能把 deactivated weight column 置零并走 sparse kernel；host 内存足够。
  - **可能失效场景**：无高效 sparse GEMM 的硬件/框架路径时，理论 FLOPs 节省变不成 wall-clock。

- **假设 1：layer-wise 固定激活比例 + top fraction 阈值足以 runtime 调稀疏度。**
  - **证据强度**：**中**——多模型多 benchmark 一致，但未与 adaptive per-input 比例系统对比。

## 核心方法

每 token：forward 收集 neuron 输出（hook）→ 用 **Corrected G×O** 算 attribution（理论量化层间依赖误差上下界并加 corrective term）→ layer-wise 阈值选 top 比例 neuron → 未激活列权重置零转 sparse format → 仅激活 neuron 参与 MHA/MLP 计算。与 [[PTQ]] 可叠加（减操作数 vs 减每 op 位宽）。

## 设计取舍

- **Lossy vs lossless**：赢得 70% 稀疏与 runtime 适配，牺牲严格等价于 dense forward 的语义。
- **Corrected 一次-shot vs 逐层迭代**：计算省，但 corrective 基于界近似，极高稀疏率可能仍排序错。
- **Per-layer 固定比例 vs 全局预算**：实现简单，可能 MLP/Attention 最优比例不同。
- **边界条件**：评测为 Llama-3、Phi-2、Gemma、MobiLlama 上 QA/摘要/改写；未集成 [[vLLM]] serving 级 batching/[[PagedAttention]]。

## 实验与结果

- **Attribution quality**：Llama-3-8B/TruthfulQA、60% sparsity 下，Corrected G×O BLEU 为 21.66；uncorrected G×O 为 3.59、magnitude 为 11.97、SNIP/Fisher 为 6.89、IG 为 3.59（§7.1，Table 1；batch 1、H100-80GB、open-ended generation）。
- **Sparsity boundary**：原文以“绝对 BLEU 点数损失少于 5”的口径报告 Phi-2/Gemma/MobiLlama 最大 sparsity 为 60%/70%/70%；MobiLlama AR30%（70% sparsity）为 4.07 vs dense 5.45（§7.1，Table 1）。
- **Cold-start example**：Phi-2/TruthfulQA、AR30%（70% sparsity）中，sparse forward latency 为 1.06 秒 vs dense 1.59 秒，GPU memory 为 7.91GB vs 13.76GB，BLEU 为 26.8 vs 33.9（§7.6/Table 5、§7.1/Table 1；H100-80GB、batch 1、load/release session，不是 steady-state serving）。
- **Component ablation**：Phi-2/TruthfulQA、AR50% 下，MLP Cor-G×O / G×O 为 33.2/20.2，attention 为 31.3/17.0（§7.2，Table 2；作者据此解释 MLP 更可稀疏）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Corrected G×O 在 Llama-3-8B TruthfulQA 上优于所测 attribution baselines | §7.1, Table 1 | 60% sparsity；batch 1；H100-80GB；BLEU | strong |
| Phi-2/Gemma/MobiLlama 在作者的 BLEU-loss 口径下达到 60%/70%/70% sparsity | §7.1, Table 1 | TruthfulQA；绝对 BLEU 差异，不是相对 accuracy percent | medium |
| Phi-2 cold-start single-request 例子降低 latency 与 GPU memory | §7.6, Table 5 | AR30%；H100-80GB；batch 1；非 steady-state serving | strong |
| Corrected attribution 在 MLP/attention ablation 中均优于 G×O | §7.2, Table 2 | Phi-2；TruthfulQA；AR50%；BLEU | strong |

## Critical Analysis

### 论证链条

「新 LLM 无零 neuron」→ magnitude 失效 → attribution 更好但层间依赖致错 → 可证界+corrective → 70% 稀疏低损，链条清晰。将 PIQA 等短输出结论外推到长链推理需更多长生成曲线证据。

### 假设压力测试

若不使用论文的离线 mask predictor，逐 token backward 不适合高 QPS serving；实际部署路径先离线跑完整 pipeline，再以 hidden states 训练 MLP mask predictor。论文未量化 predictor accuracy、training/refresh cost 或 batch-serving 行为（§6）。

### 实验可信度

多模型多任务；baseline attribution 公平。缺：与 [[MoE]] 模型、量化 KV 联合、及端到端 [[TTFT]]/[[TPOT]] under production scheduler。

### 系统性缺陷

论文未讨论错误 deactivate 的安全边界、多租户一致性、与 flash attention fused kernel 的集成。CPU/offload 路径未覆盖。

## 局限与 Future Work

- **局限 1**：逐 token backward 的 serving 开销与 batch 行为未充分刻画。
- **局限 2**：corrective term 对复杂架构（MoE、Mamba）的界可能松。
- **Future work 1**：测量 attribution 周期 vs 稀疏收益 trade-off，找可接受的重算间隔。
- **Future work 2**：与 [[KV-Cache]] 量化/[[FlexiCache]] 类系统联合 profiling 端到端内存-延迟 Pareto。

## 相关

- **相关概念**：[[Sparse-Activation]]、[[Model-Pruning]]、[[PTQ]]、[[Integrated-Gradients]]
- **同类系统**：[[StreamingLLM]]、[[SnapKV]]
- **同会议**：[[MLSys-2026]]
