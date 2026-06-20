---
type: paper
name: SpecDiff-2
full_title: "SpecDiff-2: Scaling Diffusion Drafter Alignment for Faster Speculative Decoding"
authors: [Jameson Sandler, Jacob K. Christopher, Thomas Hartvigsen, Ferdinando Fioretto]
venue: MLSys
year: 2026
tags: [speculative-decoding, diffusion-models, llm-inference, drafter-verifier-alignment, distillation]
source_pdf: "[[14bfa6bb14875e45bba028a21ed38046.pdf]]"
source_md: "[[14bfa6bb14875e45bba028a21ed38046]]"
---

# SpecDiff-2: Scaling Diffusion Drafter Alignment for Faster Speculative Decoding (MLSys 2026)

> **一句话总结**：在 [[Speculative-Decoding]] 中观察到 diffusion drafter 的 position-wise acceptance 随 draft index 快速衰减、AR 蒸馏只修首 token 无效，SpecDiff-2 用 MDM 并行 draft + streak-distillation（训练时优化整窗 expected streak）+ self-selection acceptance（测试时 O(1) 采样 K 候选并由 verifier 选最优），在 Qwen2.5/LLaMA-2 上相比 EAGLE-2 平均 **+55%** tokens/s、相比 vanilla **5.5×** 加速且 **lossless**。

## 问题与动机

[[Speculative-Decoding]] 用 draft-then-verify 绕过 AR 串行瓶颈：小 drafter 一次提议 γ 个 token，大 verifier 并行打分，接受最长匹配前缀。实际加速取决于 (1) drafter latency 与 (2) drafter–verifier alignment——misalignment 导致 early rejection，浪费 draft 与 verify 算力。

前序 SpecDiff（NAACL 2025）用 masked discrete diffusion（MDM）做 **非自回归 drafter**：一次 denoising pass 并行产出整窗 draft，drafter cost 主要取决于 denoising 步数而非 γ，缓解瓶颈 (1)。但 diffusion 学的是整窗联合 denoising 分布，AR verifier 评估的是 prefix-conditional next-token 分布；token 级 miscalibration 让联合样本虽流畅却频繁被拒，瓶颈 (2) 仍在。

现有 AR 对齐路线（DistillSpec 等）默认 position-wise acceptance 可交换，只优化 prefix 后第一个位置的 TV 距离。论文测量（Fig. 2）显示 diffusion drafter 的 α_j 随 j 显著衰减，AR-distillation 把增益集中在早期位置、后段 acceptance 崩溃。SpecDiff-2 的 claim 是：**必须对整窗 draft 做 streak-aware 对齐**，并借 diffusion 的 position-wise marginals 在测试时廉价扩展多候选。

## 关键观察 / 隐含假设

- **观察 1：diffusion drafter 的 position-wise acceptance 非均匀，后段 token 是 throughput 的主要损失点。** Fig. 2 对比 Base / AR-distillation / streak-distillation：AR 风格对齐让 α_j 随 j 快速下降；streak-distill 在后段位置平均 **3.2×** 高于 AR-distill。这与 diffusion 并行生成、不 conditioning 于已接受前缀的机制一致。
  - **依赖假设**：draft window γ 固定（DiffuCoder γ=32、DiffuLLaMA γ=16），且 verifier 仍用标准 left-to-right acceptance。
  - **可能失效场景**：极短 γ、或 verifier 改用 block-wise / non-greedy acceptance 时，position decay 形态可能改变；open-ended QA 语义多样性高时后段 alignment 仍难（论文 QA 相对 math/code 增益收窄）。

- **观察 2：单次 MDM denoising 暴露全部 position-wise marginals，从中独立采样 K 个 joint draft 的边际成本近似 O(1)，而 AR multi-path（EAGLE-2 draft tree）随 K 有串行/树展开开销。** 论文主张 diffusion 使 test-time compute 可花在 verifier 侧选最优 draft，而非 drafter 侧重跑。
  - **依赖假设**：K 个候选的 verifier scoring 可用 tree-attention 批处理（App. B.8），且 K、γ 不大到使 flatten 序列过长。
  - **可能失效场景**：极大 K×γ 时 mask 构造与 verifier forward 内存/延迟可能反超收益；论文 largest 报告 K=8。

- **观察 3：7B 级 diffusion drafter 在并行 drafting 下 latency 仍可与 ~1B AR drafter（EAGLE-2）可比，但带来更长 accepted streak。** Table 2：更大 drafter 显著提高 TokensDraft，而 diffusion 单 pass 并行使 draft latency 未随 γ 线性爆炸。
  - **依赖假设**：仅 **1 步** denoising（T=1）已足够；A100 80GB、bf16、2 GPU 跑 70B+ verifier 的硬件栈。
  - **可能失效场景**：14B verifier 上 DiffuLLaMA-7B 因 drafter 相对过大、draft latency 不再 competitive，无法稳定超过 EAGLE-2（Table 4）；更多 diffusion steps 线性增 latency、acceptance 增益停滞（Fig. 9）。

- **假设 1：greedy-acceptance proxy（用 verifier 概率 p(x_j|s) 作 acceptance 权重、训练时不看 drafter posterior）足以指导 streak-distillation，且与 lossless verify 兼容。**
  - **证据强度**：中。理论连接到 Eq. (3) product-of-accepts；验证阶段改用 greedy rule 并缓存 verifier 概率。论文承认需 formal bias/variance 分析（Sec. 9）。

- **假设 2：streak-distillation 在有限 GPU-hour（≤75h、30k–60k steps）内对齐的 drafter 可泛化到与微调数据 **disjoint** 的 benchmark（Math-500、HumanEval、GPQA 等）。**
  - **证据强度**：中强。主表明确 OOD 评测；distillation corpus 混合 GSM8K/Alpaca/LiveCodeBench 等，但未见严格 domain shift 压力测试（如多轮对话、工具调用 trace）。

## 核心方法

SpecDiff-2 在 SpecDiff 的 MDM drafter 骨架上叠加两条 **只改 Q_diff、冻结 verifier P** 的对齐机制。

**Diffusion drafter（继承 SpecDiff）**：prefix s 后接 γ 个 [MASK]，少量 denoising step（实践 T=1）并行产出 position-wise marginals q_j(·|s)。draft cost ~ O(denoising steps)，与 γ 解耦。

**Streak-distillation（训练时）**：从 expected accepted streak TokensDraft(γ,s)（Eq. 3）出发，用 greedy-acceptance 构造可微 proxy：位置 j 的 α̃_j 化为 verifier 与 drafter 分布内积，再 pathwise 重写成对 teacher trajectory x_{1:γ}∼P(·|s) 的期望（Def. 5.1, Eq. 6）。**梯度上升**该目标 ≈ 直接最大化整窗 product-of-accepts，而非 AR-distill 只抬 α_1。Fig. 3：P 提供 reference，Q_diff 产出 q_1…q_γ，对 streak 目标更新 θ。

**Self-selection acceptance（测试时）**：单次 forward 得 {q_j} 后，独立采样 K 个候选 draft {x^(k)}（Alg. 1）。用 Eq. (7) 的 streak 指标（等价 Eq. 5b，期望 throughput）由 P 打分，选 x^max 再走 **lossless** greedy verification。K 路 scorer 用 tree-style attention 并行（Xiong et al. 2024 思路）。相对 EAGLE-2 的 AR draft tree：drafter 侧 O(1) vs O(log K·γ) 量级 token 生成。

**Greedy acceptance**：选中 draft 后按 verifier 概率逐 token Bernoulli accept；拒绝处从 residual 重采样。不依赖 drafter 概率，利于 cross-tokenizer 与无校准 diffusion 输出。

## 设计取舍

- **整窗 streak 对齐 vs 首 token TV 对齐**：赢得长 accepted streak 与后段 α_j，代价是 streak-distillation 目标更复杂、需 teacher sampling，训练算力高于 naive DistillSpec 扩展（Fig. 12：naive γ-window DistillSpec 仍因位置权重错误低 **~35%** throughput）。

- **大 diffusion drafter（7B）vs 小 AR drafter（~1B）**：7B 提升 alignment capacity 与 streak 长度；并行 drafting 控制 latency。牺牲显存 footprint、drafter 加载成本，且 **verifier 较小时 drafter 可能 oversized**（14B 上 DiffuLLaMA 不稳超 EAGLE-2）。

- **greedy acceptance vs 标准 min(q,p) rejection**：简化 verify、支持异构 tokenizer；可能改变 acceptance 统计，论文称仍 lossless 但未展开与经典 rule 的等价条件。

- **test-time K 与 temperature**：高 T 增加候选多样性利于 self-selection（K=8、T=2.0 额外 **~20%**），低 T 几乎无 scaling（Fig. 5）。默认 T≈1.5 折中质量与方差。

- **边界条件**：在 **结构化输出**（math、code、stepwise reasoning）上最亮眼（平均 **4.71×** vs EAGLE-2 **3.43×**）；open-ended QA 增益收窄（**3.24×** vs **2.80×**）。CoT + 固定 wall-time 预算下加速转化为更高 task accuracy（15s 预算 **+63%** vs vanilla）。

## 实验与结果

**设置**：Verifier Qwen2.5-14B/72B-Instruct、LLaMA-2-13B/70B-chat；drafter DiffuCoder-7B（Qwen tokenizer）、DiffuLLaMA-7B（LLaMA-2）；baseline SpS、EAGLE、EAGLE-2、SpecDiff（unaligned）。Benchmark：Math-500、HumanEval/LiveCodeBench、GPQA/MT-Bench；A100 80GB（70B+ 用 2 GPU）。输出 **lossless**（与 verifier 一致）。

- **端到端加速**（Table 2）：全设置平均 **4.22×** vs vanilla；相对 EAGLE-2 平均 **+30%** 以上（摘要称 **+55%** tokens/s）。DiffuCoder 专精 coding 时 **>5×** vs AR generation。
- **域分解**：math+code 平均 **4.71×**（EAGLE-2 **3.43×**）；open QA **3.24×**（EAGLE-2 **2.80×**）。
- **对齐消融**（Table 3, Sec. 7.3）：unaligned SpecDiff → SpecDiff-2 总提升 **40–50%**；其中 streak-distillation **~+30%**，self-selection **~+15%**（K=8 最高 **+20%**）。
- **训练 scaling**（Fig. 7）：30k→60k distillation steps，Qwen 14B/72B 各 **~+30%** speedup，≤**75** GPU-hours；超过 EAGLE-2 baseline。
- **test-time scaling**（Fig. 5）：K=1…8 平滑上升；T=2.0 在 K=8 最佳。
- **CoT wall-time**（Fig. 6）：Qwen2.5-72B Math-500，15s 思考预算下 SpecDiff-2 accuracy **+63%** vs vanilla、**+11%** vs unaligned SpecDiff；更多 distillation steps 与 self-selection 单调提升固定预算内准确率。
- **小 verifier**（Table 4, App. A）：Qwen2.5-14B 上 DiffuCoder 仍常超 EAGLE-2；DiffuLLaMA 不稳定——drafter 相对 verifier 过大时 draft latency 抵消 streak 收益。

## Critical Analysis

### 论证链条

链条：**测量** diffusion drafter 后段 α_j 衰减 + AR-distill 只修首 token（Fig. 2）→ **形式化** throughput = product-of-accepts（Eq. 3）→ **训练** streak-distillation 优化整窗 proxy（Eq. 6）→ **推理** self-selection 用廉价 K 候选放大 verifier 侧 alignment → **结果** 更长 streak、更高 tokens/s，且 OOD benchmark 上 lossless。

最强证据是 position-wise acceptance 曲线与 train/test 消融（Table 3, Fig. 5/7）对两条机制的分解；CoT fixed-budget accuracy（Fig. 6）把吞吐增益接到 test-time compute scaling 叙事，超出纯 latency 表。

薄弱环节：主对比混用 **不同量级 drafter**（7B DLM vs ~1B EAGLE）与 **不同 drafting 范式**（parallel diffusion vs AR tree）；论文用 latency 可比 + 更长 streak 辩护，但未给出 iso-parameter / iso-FLOPs drafter 对照。

### 假设压力测试

**Workload**：math/code 等低熵、结构约束输出收益最大；长 CoT、开放对话、工具调用等 high-entropy 场景 acceptance 可能接近 AR drafter 上限。固定 γ 对不同任务未必最优（Fig. 10：过大 γ 降 quality，过小 γ 限 streak）。

**硬件/部署**：实验为 research pipeline（A100、自定义 tree verify、LoRA merge 流程），非 [[vLLM]]/[[SGLang]] 生产栈端到端。论文 future work 明确指出缺 semi-AR kernel、diffusion draft 的 KV cache 支持——工程化 gap 大。

**Drafter 规模**：7B drafter 对 70B verifier 有效，对 14B verifier 可能过大；最优 DLM drafter vs verifier 比例未建立 scaling law（Sec. 9 承认 open problem）。

**Lossless 与 greedy rule**：主文声称分布等价于 verifier，但 greedy acceptance 偏离经典 speculative sampling 的 min(q,p) 规则；跨 tokenizer 场景的严格正确性需读者回 Appendix 验证，正文论证偏启发式。

### 实验可信度

优点：多 verifier×drafter 配对、OOD 评测、train/test 消融、distillation steps 与 K 的 scaling curve、与 DistillSpec 变体对比（Fig. 12）；明确报告 14B 上失败案例（DiffuLLaMA）。

限制：**无生产 serving 栈** baseline（batching、prefix cache、disaggregation 未测）；wall-clock 主要在 A100 单/双卡，缺 A100 以外硬件与 tail latency；文本质量 metric 因 lossless 省略，但不代表下游 task 在 **非-greedy / 采样** 模式下行为；EAGLE 实现依赖 released toolchain，hyperparameter 公平性难完全审计。

### 系统性缺陷

- **Drafter 内存与加载**：7B diffusion model 常驻显存显著高于 EAGLE ~1B；multi-tenant serving 中 drafter 副本成本论文未量化。
- **Tree verify 复杂度**：K 与 γ 增大时 attention mask 与 flatten 序列长度增长；论文有 profiling scope（App. B.8）但主文未报 verify 侧 tail latency。
- **KV cache**：diffusion draft 窗口与 AR verifier KV 衔接、跨 pass 截断（App. B 提到 crop）在生产环境的正确性与碎片风险论文未充分讨论。
- **可观测性与运维**：streak-distillation 需离线 teacher 数据与 fine-tune；drafter 版本与 verifier 升级后的再对齐成本未讨论。
- **故障恢复 / 多租户**：论文未讨论。

## 局限与 Future Work

- **局限 1**：greedy acceptance 的偏差/方差、最坏情况 miscalibration 缺乏形式化分析（作者自述）。
- **局限 2**：最优 diffusion drafter 规模、与 verifier 的 scaling law 未建立；14B verifier 上过大 drafter 已显示负收益。
- **局限 3**：缺专用 semi-AR / diffusion-draft KV kernel，端到端生产加速未验证。
- **局限 4**：评测以单轮 QA/math/code 为主，未覆盖长多轮对话、batch serving、[[Prefix-Caching]]、[[Disaggregation]] 等生产特性。

- **Future work 1**：在真实 serving 栈（[[vLLM]]/[[SGLang]]）测量 SpecDiff-2 的 drafter 驻留、tree verify 尾延迟与吞吐 Pareto，并与 EAGLE-3 等 iso-deployment 对比。
- **Future work 2**：系统扫描 verifier size → 最优 DLM drafter 参数/FLOPs 曲线，避免「7B drafter 一刀切」。
- **Future work 3**：形式化 greedy vs standard acceptance 的等价条件，并测试 cross-tokenizer / cross-family drafter–verifier 组合。
- **Future work 4**：K 个 **异构** drafter（代数 vs 代码 vs 数值）+ cost-aware self-selection，验证 diversity–alignment trade-off（Sec. 9 提出方向）。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、diffusion language model、knowledge distillation
- **同类系统**：EAGLE、EAGLE-2、SpecDiff（NAACL 2025 前序）、[[TiDAR-MLSys26|TiDAR]]、[[CDLM-MLSys26|CDLM]]、[[SparseSpec-MLSys26|SparseSpec]]、[[ReSpec-MLSys26|ReSpec]]
- **同会议**：[[MLSys-2026]]
- **对比**：相对 EAGLE 系用更大并行 diffusion drafter 换 streak 长度；相对 [[TiDAR-MLSys26|TiDAR]] 保持 verifier 冻结、不改造 target 架构；与 DistillSpec 争点在 **整窗 streak 目标** 而非单点 TV