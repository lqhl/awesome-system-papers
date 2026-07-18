---
type: paper
name: PRISM
full_title: "PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models"
authors: [Xuliang Wang, Yuetao Chen, Maochan Zhen, Fang Liu, Xinzhou Zheng, et al.]
venue: MLSys
year: 2026
tags: [speculative-decoding, draft-model, sglang, llm-inference, conditional-computing]
source_pdf: "[[65ded5353c5ee48d0b7d48c591b8f430.pdf]]"
source_md: "[[65ded5353c5ee48d0b7d48c591b8f430]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models (MLSys 2026)

> **一句话总结**：观察到 [[Speculative-Decoding]] 中 draft acceptance rate 随 step 急剧下降、而堆层 drafter 把容量与 per-step 计算纠缠；PRISM 将不同 draft step 映射到不同 transformer 参数集（总参数量扩展但每步激活恒定），在 [[SGLang]] 上相对已高度优化的推理引擎再提 **>2.6×** 解码吞吐，acceptance length 与数据 scaling 优于 EAGLE-2/HASS，小数据下优于 EAGLE-3。

## 问题与动机

[[Speculative-Decoding]]（Draft-and-Verify）用轻量 drafter 连续提议候选 token，再由 target LLM 单次 forward 并行验证；acceptance length（每轮验证期望接受的 token 数）直接决定端到端加速。EAGLE 系列证明：利用 target 上一验证步的 hidden states 作为 drafter 输入，可显著提升 draft 质量。

但行业趋势正走向**更大 drafter**（EAGLE-3、Scylla、Meta 堆层/MoE 扩展，见 Table 1）。传统架构中，**模型容量与每步推理成本纠缠**：多堆 transformer layer 虽提高 acceptance，draft latency 同步上升，可能抵消系统收益。论文要回答：**能否在保持 per-step draft 开销恒定的前提下扩展 drafter 总容量？**

测量动机来自 Figure 1：在 LLaMA-3-8B 上，acceptance rate 随 draft step **单调下降**——后段 token 更难预测。若所有 step 共用同一参数集，等于用同一「深度」处理难度不均的任务。架构与训练细节回 [[65ded5353c5ee48d0b7d48c591b8f430]] 或 [[65ded5353c5ee48d0b7d48c591b8f430.pdf]]。

## 关键观察 / 隐含假设

- **观察 1：draft step 难度非均匀，后段 acceptance 显著低于前段。**
  - **证据**：Figure 1 显示 LLaMA-3-8B 上 step-wise average acceptance rate 呈陡峭下降；作者将此作为 specialization 设计的直接动机。
  - **依赖假设**：该 pattern 在多种 target model、采样策略（greedy / non-greedy）和 tree topology 下稳定；step index 能代理预测难度。
  - **可能失效场景**：极短 draft depth、任务类型使 token 分布高度可预测（如模板化代码补全），或 drafter 已极强时 step-wise 差异缩小，step-specialization 收益递减。

- **观察 2：decode 阶段 memory-bandwidth-bound，draft 额外 forward 的 activated parameter 数是 draft latency 的主导因素之一。**
  - **证据**：Background 节将 decoding 刻画为 HBM 参数加载瓶颈；Table 1 显示业界 drafter 相对 target 体积持续增大，但单步激活参数决定实际 draft 成本。
  - **依赖假设**：实验硬件（A800/4090）上 draft 仍偏 memory-bound；per-step 激活参数恒定即可维持 draft latency，而总参数量扩展主要影响训练与存储。
  - **可能失效场景**：大 batch 使 decode 更 compute-bound（论文 Figure 7 显示 speculative 收益随 batch 递减）；draft 与 target 共置时的资源争用、或 draft 算子未充分融合时，latency 模型可能偏离「激活参数主导」。

- **观察 3：与 naive 垂直堆层相比，按 step 分配不同参数集能在不增加 per-step 激活量时获得更好 scaling。**
  - **证据**：Figure 4 中 EAGLE-2/HASS 在 >400K 样本后 acceptance length 平台化，PRISM 在 600K+ 仍上升；Figure 6 ablation 显示直接堆两层 transformer（同 context alignment、同数据）scaling 明显差于 PRISM。
  - **依赖假设**：训练数据规模与任务多样性足以让不同 module 学到 step-specific 表示；warmup→复制权重→多 module 训练流程有效。
  - **可能失效场景**：数据极少或分布单一，多 module 退化为冗余参数；target model 换代后 hidden state 分布漂移，需重训。

- **假设 1：draft step 到 processing module 的 surjection（多 step 可共享 module）足以表达难度梯度，无需每 step 独立参数。**
  - **证据强度**：**中**——主实验仅用 **2 个 module**（module 1 专责 prefill，module 2 覆盖所有后续 decoding step），已获全面领先；未系统扫描 module 数与 step 映射粒度。

- **假设 2：在 [[SGLang]] 生产栈（CUDA graph、continuous batching）上测得的加速可代表真实部署，而非 PyTorch toy 高估。**
  - **证据强度**：**中**——相对多数仅在 PyTorch 评测的 drafter 是明确卖点；但实验固定 batch size 1，未覆盖高并发 serving 或 prefill-decode 混部。

## 核心方法

**PRISM**（Parametrically Refactor Inference for Speculative Sampling draft Models）沿用 EAGLE 系惯例：transformer-based drafter，以 target 最后层 hidden states 与 token embedding 经 fusion layer 融合后送入 draft 网络。

**1. Step-specialized processing modules**

架构由 token embedding、vocabulary head、以及一串 **processing module**（各含 fusion layer + 一个 transformer layer）组成。核心创新：**draft step → module 为 surjection**——每个 step 唯一指定一个 module，多个 step 可共享同一 module，但每步只激活一个 module 的参数。

效果类比棱镜色散：总参数量随 module 数扩展，**每步 activated parameter 恒定**，从而解耦「学习能力」与「推理成本」。相对 EAGLE-2/HASS 的单 transformer 反复前向，PRISM 在 cascade 结构中让后段 step 累积更深有效计算深度（Figure 2），对应观察 1 的难度梯度。

**2. Draft 推理与 KV 传递**

- **Prefill**：对已接受 token 序列，融合 embedding 与 target hidden states，单次 forward 经指定 transformer，产出初始预测状态与 [[KV-Cache]]。
- **Decoding steps**：每步融合上一 token embedding 与上一 hidden state，经**当前 step 映射的 module** forward；KV cache 在 module 间传递（Figure 3b）。
- 兼容 **tree-based draft**（SpecInfer 式多分支验证）与 stochastic sampling；正文以线性路径表述仅为清晰。

**3. 训练：warmup + 权重复制 + context alignment**

借鉴 HASS 式 context alignment（对齐训练/推理的 hidden states 与 KV），缓解 exposure bias。PRISM 的训练优势在于：context alignment 需每 draft step 单独 forward，但 PRISM 每步 backprop **仅限当前子网络**，相对同参数量单体深网络更省。

流程：
1. **Warmup**：仅 1 个 processing module，CEL + MSE（对齐 target hidden states）联合损失。
2. **扩展**：复制已训 transformer 权重为 M 份，进入第二阶段；去掉 MSE，在 forward 间切换 module。

数据：ShareGPT、UltraChat、OpenThoughts2 共约 **800K** 样本（截断 2048 token）；baseline 同数据公平对比。

**4. [[SGLang]] 系统集成**

在 [[SGLang]] engine 内实现 PRISM，配合 CUDA graph、continuous batching 等推理优化；作者强调 PyTorch 原型会高估 speculative 收益，系统级评测是贡献之一。

## 设计取舍

- **Step specialization vs 堆层深度**：总容量可通过加 module 扩展，但主实验仅 2 module、第二 module 服务所有 decoding step——工程简单、latency 可控，牺牲了对「每一步独立专家」的细粒度 specialization。
- **Surjection vs 每 step 独立参数**：共享 module 降低总参数与切换开销，但后段多 step 共用同一 transformer，可能限制对极难后段 token 的表达能力。
- **KV 跨 module 传递 vs 独立 cache**：复用 KV 减少重算，但增加实现复杂度与 cache 一致性管理；论文未详述 reject 后 KV 回滚成本。
- **HASS 式 alignment vs EAGLE-3 train-time test**：选 HASS 风格 3-step alignment，训练更轻；EAGLE-3 用更多 target hidden states 与 train-time test，后段预测更强（Figure 1：EAGLE-3 在后段 step 优于 PRISM）。
- **SGLang 深度集成 vs 框架无关**：系统证据强，但移植到 [[vLLM]]、TensorRT-LLM 需重做 parameter switching 与 graph capture；论文未提供多框架适配。
- **Lossless speculative 约束**：保持 rejection sampling 无损分布，不引入近似解码；所有收益必须来自 acceptance × draft speed，不能靠牺牲质量换吞吐。

## 实验与结果

**设置**：Target 为 LLaMA-2-7B-chat、LLaMA-3-8B-Instruct；6 benchmark（MT-Bench、HumanEval、GSM8K、Alpaca、CNN/Daily Mail、Natural Questions）；greedy 与 non-greedy；**batch size 1**；6-step 4-branch tree，每轮最多验证 16 token。主实验 PRISM 为 **2 processing modules**。训练规模 100K–800K 样本，8×A100-40G + 4×A100-80G。

**主结果（Table 4，A800 80G）**：

- 相对 vanilla auto-regressive：**>2.4×** 加速（全文 claim **>2.6×** decoding throughput boost over highly optimized engine）。
- 相对同推理激活量的 EAGLE-2：acceptance length 平均 **+14.09%**，TPS **+14.21%**。
- 相对 HASS：AL **+5.69%**，TPS **+6.10%**。
- CNN/Daily Mail 等长上下文 summarization workload 上优势尤其明显。
- 4090 双卡子实验（Table 5）趋势一致。

**Scaling（Figure 4–5）**：

- 全数据规模上 PRISM acceptance length 持续优于 EAGLE-2/HASS；后者在 ~400K 样本后平台化，PRISM 在 600K+ 仍上升。
- vs EAGLE-3：小数据 PRISM 数据效率更高；大数据两者 acceptance length **收敛相同**（作者归因于数据集复杂度上限）。
- Step-wise：PRISM 前段 step 更强，EAGLE-3 后段更强—— specialization 与 richer input 的互补 tradeoff。

**Ablation（Figure 6）**：去掉 step-wise 参数分配、仅堆两层 transformer → 预测与 scaling 显著变差，支撑核心创新而非单纯「更多参数」。

**超参（Figure 7–8）**：

- Batch size 增大时加速递减，但 PRISM 在较大 batch 仍保留合理 speedup。
- 更大 tree（更深更宽）一般提升 PRISM，但 draft/verify 开销导致收益渐饱和；固定验证 token 数时，**更深更窄**优于更宽更浅。

## Critical Analysis

### 论证链条

observation（step-wise acceptance 下降 + 堆层 entangle 容量与 cost）→ design（per-step module surjection + 恒定激活）→ result（更高 AL/TPS + 更好 data scaling + SGLang 系统验证）在 **batch-1、EAGLE 系 drafter 对比** 框架内较闭合。Ablation 将收益归因于 step disaggregation 而非参数总量，是关键证据。

脆弱跳步：(1) **2.6× 相对「已高度优化 engine」** 的 baseline 具体构成（是否含 speculative、何配置）需对照 Table 4 细读，读者易把「相对 vanilla AR」与「相对最强 baseline drafter」混淆；(2) EAGLE-3 大数据收敛到同 AL，说明 PRISM 的 specialization 未突破数据集 expressiveness 上限，**>2.6× 系统加速是否随更强 drafter 等比维持** 未证明；(3) 声称「不增加 activated parameter 即可 scale 预测能力」在极限数据下与 EAGLE-3 打平，更准确的表述是 **在更低 per-step 成本下达到可比上限**。

### 假设压力测试

**Workload**：6 个 benchmark 覆盖对话、代码、数学、摘要、QA，但全为 instruction-tuned chat 场景；多轮 tool use、超长上下文、多模态 target 未测。CNN/Daily Mail 上优势暗示长上下文任务更受益，但缺少 production trace。

**模型与词汇**：LLaMA-2（SentencePiece）与 LLaMA-3（BPE、GQA）差异大，论文称 drafter 对 vocab/GQA 敏感——PRISM 在两类上均有效是加分，但是否泛化到 Mistral、Qwen、MoE target 未验证。

**部署规模**：batch size 1 贴近 latency-sensitive 单用户，但与 continuous batching 高吞吐 serving 脱节；Figure 7 仅展示「仍有 speedup」，未给出与「放弃 speculative、纯大 batch」的 Pareto 前沿。

**Tree / verify 成本**：更深 tree 提升 AL 但 verify FLOPs 上升；论文在固定验证节点预算下比较 topology，production 中动态 tree 与 SLO 约束可能改变最优 operating point。

### 实验可信度

**强项**：(1) 800K 统一训练数据，baseline 公平；(2) [[SGLang]] 集成 + A800/4090 双环境；(3) greedy/non-greedy 双设定；(4) scaling 曲线 + 堆层 ablation；(5) 与 EAGLE-2/3、HASS 等同代强 baseline 对比。

**弱点**：(1) 主配置仅 **2 module**，module 数、step 映射策略的 sensitivity 不足；(2) 无 draft latency 微基准（仅端到端 TPS），难以独立验证「per-step 成本恒定」；(3) EAGLE-3 大数据打平后，PRISM 的 **绝对** 优势主要来自效率而非 acceptance 上限；(4) 未报告质量指标（下游 task accuracy），仅依赖 speculative decoding 无损性间接保证；(5) 训练成本 1 天–2 周随数据变化，但 inference 侧工程维护成本（多 module 切换、CUDA graph 碎片化）论文未量化。

### 系统性缺陷

- **Parameter switching 开销**：每 draft step 切换 module 在 CUDA graph 下需预编译多条路径或动态 dispatch；论文声称集成成功，但未报告 switching 在极短 draft depth 下的摊销成本。
- **内存 footprint**：总参数量随 module 数线性增，edge 部署或 draft 与 target 同卡共置时可能挤占 [[KV-Cache]] 预算；论文未讨论。
- **Stale drafter / 在线学习**：RL 或持续微调场景下 target 分布漂移会使 drafter stale（对比 ReSpec 等问题）；PRISM 未涉及在线更新。
- **多 tenant 与 tail latency**：仅报 throughput 与 AL，未报 P99 latency、draft reject 回滚路径的尾延迟；论文未讨论。
- **可观测性**：多 module 下 per-step acceptance、module 利用率等运维指标论文未提供。

## 局限与 Future Work

- **局限 1**：主实验固定 2 processing module、第二 module 覆盖全部 decoding step，specialization 粒度较粗；更细 step→module 映射是否进一步增益未充分探索。
- **局限 2**：大数据 regime 下与 EAGLE-3 acceptance length 收敛，表明当前 800K 混合数据可能不足以拉开预测上限；更复杂数据或 target 规模下结论待验证。
- **局限 3**：实验以 batch size 1 为主，高 batch serving 下 speculative 收益递减（Figure 7），与生产默认配置可能不一致。
- **局限 4**：仅 LLaMA-2/3 两个 target；缺少跨系列、MoE target、不同 tensor parallel 配置的验证。
- **局限 5**：论文承认 tree 越大开销越高，最优 topology 依赖 drafter 特性，但未给出自动调参或 workload-aware 策略。
- **Future work 1**：系统扫描 module 数量与 surjection 映射（如每 k 个 step 一 module），测量 AL–draft latency–总参数的三维 Pareto 前沿。
- **Future work 2**：结合 EAGLE-3 式多 hidden state 输入与 PRISM step specialization，验证前段/后段优势能否同时保留（Figure 1 已暗示互补性）。
- **Future work 3**：在 batch>1、prefill-decode 混部的 [[SGLang]] 生产 trace 上测量 goodput 与 tail latency，明确 PRISM 相对「大 batch 无 speculative」的交叉点。
- **Future work 4**：将 conditional draft 思想扩展到 RL rollout（与 ReSpec、SPEC-RL 等结合），评估 target 频繁更新时 module 化是否更易做局部 online fine-tune。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、draft-and-verify、context alignment
- **同类系统**：[[SGLang]]、EAGLE-2、EAGLE-3、HASS、Scylla、[[ReSpec-MLSys26]]、[[SparseSpec-MLSys26]]
- **同会议**：[[MLSys-2026]]
