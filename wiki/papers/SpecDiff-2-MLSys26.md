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

> **一句话总结**：用离散扩散模型（MDM）做非自回归 drafter 解决 speculative decoding 的 drafter 延迟瓶颈，并提出 streak-distillation（训练时）+ self-selection acceptance（测试时）两个机制校准 diffusion drafter 与 AR verifier，在 Qwen2.5-14B/72B 和 LLaMA-2 上相比前 SOTA 提升 +55% tokens/s，相比 vanilla decoding 达 5.5× 加速，**无精度损失**。

## 问题

[[Speculative-Decoding]] 通过 draft-then-verify 加速 LLM 推理，但受限于两大瓶颈：(1) drafter 的自回归依赖限制并行度；(2) drafter 与 verifier 的分布差异导致频繁拒绝。前序工作 SpecDiff 用扩散 drafter 解决瓶颈 (1)，但 AR verifier 学的是 prefix-conditional next-token 条件分布，而 diffusion drafter 学的是整窗的联合 denoising 分布，token 级 miscalibration 让接受率仍然低。简单沿用 AR 蒸馏目标（仅优化第 1 个位置 TV 距离）对 diffusion drafter 无效：后段位置的 acceptance 快速衰减。

## 核心方法

**1. Diffusion Drafter**：沿用 MDM（masked discrete diffusion）作为 drafter，drafting cost 只与 denoising 步数有关，与窗口 γ 无关，一次 pass 并行产出整个 draft window 的 position-wise marginals。

**2. Streak-Distillation（训练时对齐）**：
- 从 acceptance rate 出发，推导 greedy-acceptance proxy：位置 j 的 acceptance $\tilde\alpha_j(s) = \mathbb{E}_{x_{1:j-1}} \mathbb{E}_{x_j \sim P}[Q^{\text{diff}}(x_j|s)]$。
- 把 token/draft 期望写成 pathwise 形式（Eq. 6）：$\mathbb{E}_s \mathbb{E}_{x_{1:\gamma} \sim P(\cdot|s)}\left[\sum_{m=1}^\gamma \prod_{j=1}^m q_j(x_j|s;\theta)\right]$。
- 对其做梯度上升等价于直接优化整个 draft 窗口的 expected accepted streak，而不是只对齐第一个位置（AR-distillation 的做法）。实验显示 streak-distill 在后段位置比 AR-distill 高 3.2× acceptance。

**3. Self-Selection Acceptance（测试时对齐）**：
- 单次 denoising 产出 γ 个 position-wise marginals $\{q_j\}$，从中独立采样 K 个候选 draft（附加开销 O(1)）。
- 用 verifier P 对每个候选计算 streak 指标 $\sum_m \prod_j p_j(x_j|x_{<j})$，选出 throughput 最大的 draft $x^{max}$。
- 对 $x^{max}$ 套用标准 lossless acceptance。K 个候选用 tree-attention 并行计算，避免了 EAGLE-2 式 AR multi-path 的 O(log K) 串行开销。

## 关键结果

- Qwen2.5-14B/72B-Instruct 和 LLaMA-2-13B/70B-chat 上，用 DiffuLLaMA-7B 和 DiffuCoder-7B 作为 drafter。
- 相比 vanilla decoding 平均 5.5× 加速；相比 EAGLE-2 / SpecDiff 等 SOTA 平均 +55% tokens/s。
- Aligned drafter 比 base SpecDiff drafter 快 >40%（Math500 基准）。
- 完全 lossless：输出与 verifier 同分布。
- 后段位置（draft 中靠后 token）的 acceptance 从 AR-distill 的快速衰减变为较平缓，平均 3.2× 提升。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[Diffusion-Language-Models]]、[[Distillation]]、[[Tree-Attention]]
- **相关系统**：EAGLE、EAGLE-2、SpecDiff（前序工作）
- **同会议**：[[MLSys-2026]]
