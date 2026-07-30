---
type: paper
name: TiDAR
full_title: "TiDAR: Think in Diffusion, Talk in Autoregression"
authors: [Jingyu Liu, Xin Dong, Zhifan Ye, Rishabh Mehta, Yonggan Fu, "et al."]
venue: MLSys
year: 2026
tags: [diffusion-lm, speculative-decoding, llm-inference, hybrid-architecture, kv-cache]
source_pdf: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7.pdf]]"
source_md: "[[67c6a1e7ce56d3d6fa748ab6d9af3fd7]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# TiDAR：在扩散中思考，在自回归中讨论（MLSys 2026）

> **原题**：TiDAR: Think in Diffusion, Talk in Autoregression

> **一句话总结**：在 H100 memory-bound 解码区利用「free token slots」——单次 forward 内用 structured hybrid attention 并行 diffusion drafting（Think）与 AR rejection sampling（Talk），单模型自 spec 且支持 exact [[KV-Cache]]；1.5B continual pretrain 后相对 Qwen2.5-1.5B **4.71×** 吞吐且 **lossless**，8B **5.91×** 且 minimal loss，首次让 diffusion LM 在 wall-clock 上超越 EAGLE-3 [[Speculative-Decoding]]。

## 问题与动机

AR LLM 解码在 batch=1 时 memory-bound：延迟主要由加载权重与 [[KV-Cache]] 主导，每步只产 1 token，GPU compute density 低。Diffusion LM（Dream、Llada 等）可并行预测多 token，但 intra-step token independence（从 marginal 独立采样）损害序列连贯性与正确性；且 bidirectional attention 难以 exact KV cache，进一步限制 serving 效率。

现有加速路线各有硬伤：**[[Speculative-Decoding]]**（EAGLE、Medusa、DeepSeek-V3 MTP）用小 draft model 或额外 AR 层，draft 容量受限，且 drafting 与 verification **串行**；纯 diffusion 若强行 left-to-right 单 token/step 则退化为 AR 速度，若并行多 token 则质量下降。作者 claim：需要 **单模型、高容量 draft、draft 与 verify 同一 forward 并行** 才能同时吃到 diffusion 并行性与 AR 链式因子化质量。

## 关键观察 / 隐含假设

- **观察 1：在 memory-bound 解码区，向单次 forward 追加有限数量 token slot 几乎不增加 wall-clock latency（「free token slots」）。** Fig. 1 在 H100 + Qwen3-32B + batch=1 + [[Flash-Attention]] 2 上，prefix 长度变化时，forward 内 token 数增至某阈值前 latency 基本平坦，之后才进入 compute-bound。TiDAR 把 drafting 与 sampling 塞进这些 slot。
  - **依赖假设**：目标硬件与 batch 仍处 memory-bound（论文主评 **batch=1**）；draft block 长度可 fit 进 free slot 预算。
  - **可能失效场景**：大 batch、长上下文已使 forward compute-bound 时，额外 slot 不再「免费」；不同 GPU/内核下 roofline 拐点可能不同。

- 观察 2：diffusion 并行解码的质量损失来自 intra-step 对 joint 的 marginal 因子化，而 AR 的链式条件化与语言建模天然对齐。 论文形式化 $P_{AR}$（链式因子）vs $P_{Diff}$（marginal 乘积）；多 token/step 等价于对 $P_{Diff}$ 再因子化，引入 token independence。TiDAR 用 diffusion draft、AR reject sampling 分离两种分布的角色。
  - **依赖假设**：one-step diffusion drafting 产出的 marginal 提议有足够 acceptance rate；AR rejection 能恢复链式分布下的质量。
  - **可能失效场景**：高熵开放生成、长程依赖强的任务上 draft acceptance 下降，有效 tokens/NFE 缩水；论文在 math/code 上 metric 更 robust，开放域外推需谨慎。

- 观察 3：相对 Block Diffusion，仅保留 最后一个 block bidirectional、prefix 全 causal，可同时算 NTP loss（prefix）与 diffusion loss（block），并支持 exact KV cache 与标准 AR likelihood 评估。 这是对 Block Diffusion 的关键改动：prefix 不再 intra-block bidirectional，避免 label leakage，NTP 信号更密。
  - **依赖假设**：训练时序列长度翻倍（append mask tokens）可接受；continual pretrain 数据量足够（1.5B **50B** tokens、8B **150B** tokens）。
  - **可能失效场景**：长上下文扩展需再处理 doubled-length 训练成本；小数据 continual pretrain 可能无法同时学好双模式。

- **假设 1：全 mask 训练 diffusion 段（非随机 corruption）与 one-step inference drafting 一致，且能简化 AR/diffusion loss 平衡。**
  - **证据强度**：中强。Table 5 ablation 显示 coding 任务质量明显提升；Fig. 6 显示 AR vs diffusion logits 在 well-trained 下可互换验证而不损质量。

- 假设 2：TiDAR 作为 standalone 模型 部署，无需独立 draft model 或额外层，serving overhead 低。
  - **证据强度**：中。单 forward 并行设计有 profiling 支撑，但实验为 native PyTorch + Flex Attention，非 [[vLLM]]/[[SGLang]] 生产栈端到端。

## 核心方法

TiDAR 是 **sequence-level hybrid**：同一 backbone 在单次 forward 内交替 causal（AR）与 block-bidirectional（diffusion）attention pattern。

**双模式训练（§3.1）**：输入序列翻倍——原 token + 等量 mask token。Prefix 段 causal self-attention + shifted NTP labels；diffusion 段 **全 mask**、block 内 bidirectional，labels 与 input 对齐。目标 $\mathcal{L} = \alpha \mathcal{L}_{AR} + (1-\alpha)\mathcal{L}_{diff}$，默认 $\alpha=1$。相对 Block Diffusion / SBD：仅末 block bidirectional，prefix 可算稠密 NTP loss；全 mask 使每 token 都有 diffusion loss、与 one-step inference 对齐。

**并行 self-speculative 生成（§3.2）**：每步三代分区——(1) **prefix**：复用上轮 causal KV；(2) **上步 draft**：对 marginal 提议做 AR rejection sampling，用当前步 causal logits 验证；(3) **下步 pre-draft**：diffusion 并行从 $P_{Diff}$ 预起草，**条件于 rejection 所有可能 accept 前缀**（受 Apple MTP 启发），保证任意 accept 长度都有对应 next draft。Draft 与 sample **同一 forward** 完成；接受长度 < draft 长度时 evict 多余 KV，无重算浪费。

**推理优化（§3.3）**：固定每步 token 数与 attention pattern → 预初始化大块 mask，按 prefix 长度切片复用（Flex Attention）；支持 exact [[KV-Cache]] 如 Block Diffusion。默认 **one-step** diffusion drafting，推理无额外超参（block size 训练时定，推理可 zero-shot 调 draft length）。

**初始化**：从 Qwen2.5-1.5B / Qwen3-8B continual pretrain（Megatron-LM + Torchtitan，bf16，max seq 4096）。

## 设计取舍

- **Diffusion draft + AR talk vs 纯 AR / 纯 diffusion**：赢得并行 drafting 与高 acceptance 质量；牺牲训练复杂度（双 loss、双倍序列长）与架构非标准（非 lossless 相对固定 AR teacher，除非 acceptance 路径等价）。

- **单模型 self-spec vs 独立 draft model（EAGLE）**：draft 复用 base 权重，容量高；无需第二模型驻留。代价是 continual pretrain 成本，且输出分布相对 base AR **不保证 bit-exact**（与经典 speculative decoding 的 lossless 保证不同）。

- **One-step full-mask diffusion vs 多步 denoising / 随机 mask 训练**：推理更快、mask 可复用；可能限制 draft 质量上限，论文用 ablation 论证 one-step 已够高 acceptance。

- **Trust AR vs trust diffusion logits（验证时混合）**：Fig. 6 显示 $\lambda$ 混合 AR/diffusion logits 后质量几乎不变，说明 **AR rejection sampling 机制** 而非某一模式知识主导质量-速度权衡；8B 上 math 任务略偏 trust diffusion。

- **边界条件**：batch=1、latency-critical 单请求解码最契合；block size 越大 T/NFE 越高但训练/显存压力增。相对 EAGLE-3 胜在 **conversion rate**（T/NFE→T/s），因 draft+verify 无串行 second forward。

## 实验与结果

**设置**：H100、batch=1、native PyTorch；baseline 含 Qwen2.5/3 AR、Dream、Llada、同配方 Block Diffusion、EAGLE-3（AngelSlim/Tengyunw open weights）。任务：coding（HumanEval/+、MBPP/+）、math（GSM8K、Minerva）、likelihood（MMLU、ARC、Hellaswag、PIQA、Winogrande）。lm_eval_harness 0.4.8。

- **吞吐**：TiDAR 1.5B 平均 **4.71×** vs Qwen2.5-1.5B；8B **5.91×** vs Qwen3-8B（Fig. 4）。
- **质量**：1.5B **lossless** vs AR counterpart；8B minimal loss。平均 **7.45**（1.5B）/ **8.25**（8B）tokens/NFE。
- **vs diffusion**：一致优于 Dream、Llada、同训练配方 Block Diffusion（Table 2）；diffusion baseline 用 1 token/NFE 保最佳质量。
- **vs EAGLE-3**：首次报告 diffusion 架构 wall-clock 超越 SOTA speculative decoding；raw acceptance 与 conversion rate 均更高（单 forward 并行）。
- **Likelihood**：可用纯 causal mask **单 NFE** 评估，与 AR 对齐且与 generative quality 一致（Table 3）；传统 DLM 需 MC 128 steps。
- **Pareto**（Fig. 5，同配方 1.5B）：TiDAR 在 quality–efficiency 前沿优于 Block Diffusion 多 threshold 与 base AR；50B tokens 训练后接近 fine-tuned AR，约 **7×** T/NFE。
- **全 mask ablation**（Table 5）：coding 任务质量显著提升，T/NFE 略升。
- **解码策略对比**（Table 4）：并行 draft+sample 优于 entropy/confidence-based dLM 解码与 block 内 left-to-right。

## 批判性分析

### 论证链条

链条：**测量** memory-bound 下 free token slots（Fig. 1）→ **形式化** AR 链式 vs diffusion marginal 的质量-并行矛盾 → **设计** hybrid mask 单 forward 并行 draft（$P_{Diff}$）+ AR reject sample（$P_{AR}$）→ **训练** full-mask + dual loss 对齐 one-step inference → **结果** 高 T/NFE、高 T/s、质量逼近 AR。

最强环节是系统动机（roofline + free slots）与 self-spec 表（Table 1）逻辑自洽；likelihood 单 NFE 评估证明 AR 模式未被 diffusion 训练「污染」。

薄弱环节：主结论 heavily 依赖 **continual pretrain 配方** 与 Qwen 初始化，非任意 AR checkpoint 即插即用；与 EAGLE-3 对比时 **lossless 语义不同**（TiDAR 改分布、EAGLE 保 base 输出），论文虽说明用途不同但 headline「beat speculative decoding」易过度解读。

### 假设压力测试

**Workload**：主评 generative 偏 coding/math（metric robust）；MMLU 等 likelihood 任务表现 competitive 但 generative 与 likelihood 的 gap 在 8B 上仍存在。高 batch serving、多租户、长多轮对话未覆盖。

**硬件**：Fig. 1 基于 H100 + FA2；其他 GPU、自定义 kernel、[[PagedAttention]]/[[Continuous-Batching]] 下 free slot 预算未知。论文承认 further system optimization 可放大收益，当前为 **未优化 PyTorch 下界**。

**模型规模**：仅 1.5B/8B（及 4B 部分结果）；更大模型是否仍 memory-bound、draft block 最优长度如何随规模变化——论文未给 scaling law。

**训练成本**：8B 需 150B tokens continual pretrain + 双倍序列长 + gradient checkpointing；相对 EAGLE 式轻量 draft head，** upfront 成本高**，适合 NVIDIA 式全栈预训练而非用户现成 checkpoint 加速。

### 实验可信度

优点：同初始化 Block Diffusion 对照、多 block size ablation、decoding strategy 矩阵、AR vs diffusion trust 曲线、full-mask ablation；效率与质量同图（Fig. 4/5）。

限制：**batch=1 only** 主评；EAGLE-3 用公开权重，公平性（训练数据、draft 大小）难完全审计；尾延迟、prefill/decode 分离、[[Prefix-Caching]] 未测；表格经 MinerU 解析，精确数值以 [[67c6a1e7ce56d3d6fa748ab6d9af3fd7]] 为准。

### 系统性缺陷

- **非 lossless 相对 base AR**：与生产 speculative decoding 的语义保证不同，回归测试、合规场景需额外验证。
- **训练序列翻倍**：长上下文扩展需专门 context parallelism（作者承认 future work），显存与训练吞吐压力大。
- **Serving 集成**：依赖 Flex Attention mask 切片与自定义 reorder；接入 [[vLLM]]/[[SGLang]] 的调度、KV 布局、多请求 batching 论文未实现。
- **Draft length 与质量**：block size 训练绑定，推理虽可调但 zero-shot 调参空间与最优点的关系仅部分 ablation。
- **可观测性与运维**：双模式 failure mode（acceptance 崩溃、draft-evict KV 不一致）的 debug 工具论文未讨论。
- **多租户 / 故障恢复**：论文未讨论。

## 局限与后续工作

- **局限 1**：效率 benchmark 聚焦 **batch=1**；大 batch 需 zero-shot 调 draft length 适配不同 compute profile（作者称可行但未系统评测）。
- **局限 2**：训练双倍序列长阻碍长上下文扩展；需 TiDAR 专用 context parallelism。
- **局限 3**：native PyTorch 实现，custom attention kernel 与硬件感知 scheduling 未做。
- **局限 4**：相对 base AR **非 bit-exact**；与 EAGLE 类 lossless SD 的定位差异需在部署时明确。

- **Future work 1**：在 [[vLLM]]/[[SGLang]] 等生产栈测量 TiDAR 的 prefill/decode 分离、[[Prefix-Caching]]、multi-tenant batch 下的 effective T/s 与 tail latency。
- **Future work 2**：针对目标 GPU 做 custom kernel，按 Fig. 1 roofline 动态选择 draft block 以最大化 free slot 利用率。
- **Future work 3**：系统评测 batch>1 时 block length 与 [[Continuous-Batching]] 的联合调度，对比 iso-FLOPs 下 AR + EAGLE-3。
- **Future work 4**：长上下文训练/推理 without 2× sequence blow-up（稀疏 mask、context parallel），验证 acceptance 是否随 context 长度衰减。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[Flash-Attention]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Prefix-Caching]]、diffusion language model
- **同类系统**：EAGLE-3、Medusa、Dream、Llada、Block Diffusion、Fast-dLLM、[[SpecDiff-2-MLSys26|SpecDiff-2]]、[[CDLM-MLSys26|CDLM]]、[[SparseSpec-MLSys26|SparseSpec]]
- **同会议**：[[MLSys-2026]]
- **对比**：相对 EAGLE 系用 **改架构单模型** 换并行 draft+verify、放弃 lossless；相对 [[CDLM-MLSys26|CDLM]]/Dream 用 **AR rejection** 闭合质量 gap 而非纯 diffusion 采样；与 [[SpecDiff-2-MLSys26|SpecDiff-2]] 同属 diffusion×spec 交叉，但 TiDAR 训练 target 本体而非冻结 verifier 旁路 drafter
