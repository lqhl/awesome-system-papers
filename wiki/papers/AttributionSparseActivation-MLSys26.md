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
---

# ATTRIBUTION-BASED SPARSE ACTIVATION IN LARGE LANGUAGE MODELS (MLSys 2026)

> **一句话总结**：新 LLM（[[Llama]]/Phi/Gemma）几乎无零激活 neuron，magnitude-based sparse activation 失效；论文用 Corrected G×O attribution 修正层间依赖误差，在 QA/摘要等生成任务达 **70%** 稀疏且精度损失 **<5%**，实测延迟降 **35%**、GPU 内存降 **40%**。

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

- **观察 3：70% 稀疏下 Corrected G×O 比 baseline attribution 精度高 **≥30%**，且带来 **35%** 延迟、**40%** GPU 内存节省。**
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

- 70% 稀疏，困难生成任务精度损失 **<5%**（作者 claim 接近 OPT 上旧工作水平）。
- 延迟 **-35%**，GPU 内存 **-40%**（真实系统测量）。
- Corrected G×O vs SNIP/Fisher/IG/magnitude：70% 稀疏时精度优势 **≥30%**。
- Corrective term 额外计算开销可忽略。

## Critical Analysis

### 论证链条

「新 LLM 无零 neuron」→ magnitude 失效 → attribution 更好但层间依赖致错 → 可证界+corrective → 70% 稀疏低损，链条清晰。将 PIQA 等短输出结论外推到长链推理需更多长生成曲线证据。

### 假设压力测试

每 token 一次 backward 算 attribution，高 QPS serving 下可能抵消延迟收益；论文强调开销小但未给 per-token µs 与 batch 扩展。与 [[Speculative-Decoding]] 等多 forward 路径叠加时 attribution 频率未讨论。

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