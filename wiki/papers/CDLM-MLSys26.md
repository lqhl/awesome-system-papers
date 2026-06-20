---
type: paper
name: CDLM
full_title: "CDLM: Consistency Diffusion Language Models for Faster Sampling"
authors: [Minseo Kim, Chenfeng Xu, Coleman Hooper, Harman Singh, Ben Athiwaratkun, "et al."]
venue: MLSys
year: 2026
tags: [diffusion-lm, consistency-model, kv-cache, inference, distillation]
source_pdf: "[[7cbbc409ec990f19c78c75bd1e06f215.pdf]]"
source_md: "[[7cbbc409ec990f19c78c75bd1e06f215]]"
---

# CDLM: Consistency Diffusion Language Models for Faster Sampling (MLSys 2026)

> **一句话总结**：开源 DLM 受双向 attention（无标准 [[KV-Cache]]）与 refinement steps ≈ 序列长度双重拖累；CDLM 用 bidirectional teacher 离线轨迹 + 三目标（distillation / consistency / DLM loss）把同权重 student 微调成 block-causal 架构，推理 confidence 并行 finalize 多 token 并 exact KV cache，Dream/LLaDA 上 steps **3.4–7.9×**↓、latency **3.6–14.5×**↓，部分 benchmark 吞吐超同尺寸 AR **1.1–4.2×**，训练仅 **8–16h**（4×A100）。

## 问题与动机

Diffusion Language Models（DLM）以每步并行更新全序列 token 摆脱 AR 的 token 级串行依赖，闭源系统（Gemini Diffusion、Mercury 等）报告可达 AR **10×** 吞吐，但开源 DLM（Dream、LLaDA）推理仍远慢于 AR。论文归纳两大结构性瓶颈：

1. **Cache 不兼容**：标准 DLM 用全序列双向 attention，每 denoising step 重算全上下文，无法像 AR 那样复用 [[KV-Cache]]。
2. **步数过多**：高质量生成常需与目标长度同量级的 refinement steps（N ≈ Lg），单步虽并行多 token，总迭代数仍巨大。

现有加速分两轴、 seldom 同时闭合：**训练无关**路线要么 approximate block KV cache（dLLM-Cache、Fast-dLLM dual cache），要么 confidence threshold 并行 unmask（Fast-dLLM Parallel），但前者 cache 近似、后者在推理时强行多 token finalize 易损质量（ParallelBench 等分析指出 inference-only parallelism 难可靠适配）。**训练相关**路线如 D2F、Fast-dLLM v2 引入 block-wise causality 以支持 KV cache，但步数削减仍有限。视觉扩散领域的 **consistency modeling** 已证明可把多步 denoising 压到少步/一步；CDLM 将这一范式迁入离散 token DLM，并与 block-causal 架构、teacher distillation 联合，声称同时解决「步数」与「cache」两轴。

## 关键观察 / 隐含假设

- **观察 1：开源 DLM 的推理代价可分解为「每步全序列双向重算」+「步数 ∝ 生成长度」，二者正交且可分别优化。** Vanilla DLM 在 bs=1 时 arithmetic intensity（AI）已超 ridge point（≈438.9），compute-bound；AR 解码 AI≈1，memory-bound。Block-causal DLM 介于两者之间（B=32 时 AI≈31.1），在小 batch 下更早进入 compute-bound，解释其相对 AR 的吞吐优势潜力。
  - **依赖假设**：评测固定 Lg=256、B=32、batch=1、4×A100 data parallel；roofline 模型（LLaMA-3.1 / LLaDA 配置）能代表 Dream/LLaDA 解码行为。
  - **可能失效场景**：更大 Lg、多租户高 batch、或 prefill-heavy 混合负载下，瓶颈可能从「步数×全序列重算」转向 KV 容量或调度；论文未测 serving 栈集成。

- **观察 2：单纯在推理时截断 refinement steps 或提高 parallel unmask 阈值，不经过训练则质量崩塌；consistency 目标单独优化也会训练失败。** Table 4：Dream/LLaDA 把步数强行压到与 CDLM 相近（48/56 steps）时 GSM8K 精度大幅下降；Table 3 ablation 显示 consistency-only（无 teacher distillation）直接 collapse，distillation-only 可收敛但步数与分数略差。
  - **依赖假设**：teacher 在 N=Lg、每步 finalize 1 token 的 block-wise 轨迹是「质量上界」；student 需显式学习「跨多步 jump」的 multi-token finalize。
  - **可能失效场景**：更强 open DLM 或不同 scheduling policy 可能改变 teacher 最优 operating point；小数据（~7.5k–15k prompts）下 student 可能过拟合 teacher 轨迹而非任务本身。

- **观察 3：Block-causal student 在块内保留双向 refinement，块间左到右因果，使 exact KV cache + early stopping 与 parallel unmask 可共存；但失去跨未来 block 的全局「生成长度预算」感知。** HumanEval 上 CDLM–Dream 生成长度显著短于 Fast-dLLM baseline（~97 vs ~200 tokens），pass@1 反而更高——说明更短输出不必然损质量，但也暗示 block-causal 与 bidirectional baseline 的解码动态不同。
  - **依赖假设**：math/code 类任务中 mild left-to-right inductive bias 可接受；τconf=0.9 的 confidence parallel decode 在块内足够稳定。
  - **可能失效场景**：需要全局规划、长链推理或 infilling 的任务可能受损；MATH 上 CDLM 精度下降（数据与 Lg=256 预算）已示警。

- **假设 1：Self-distillation（同尺寸 bidirectional teacher → block-causal student）+ 离线轨迹足以注入 multi-token finalize 能力，无需更大 teacher 或 AR teacher。**
  - **证据强度**：**中**。Dream/LLaDA 上 latency/steps 改善显著，但绝对精度仍常低于同尺寸 AR（如 MBPP-Instruct 53.0 vs 81.7）；论文承认 ceiling 受 teacher 限制。

- **假设 2：~7.5k（Dream）/ ~15k（LLaDA）条 math-heavy 轨迹 + LoRA 微调即可泛化到 GSM8K/MATH/HumanEval/MBPP。**
  - **证据强度**：**中偏弱**。LLaDA 上 GSM8K 从 77.1→73.9，加 math 数据可部分挽回；数据集选择对 LLaDA 敏感（SFT 易伤 math）。

## 核心方法

CDLM 是 **post-training 加速配方**，非新 backbone：teacher 为原始 bidirectional DLM（Dream-7B-Instruct / LLaDA-8B-Instruct），student 同权重初始化，换用 **block-wise causal attention mask**（Figure 2：可见 prompt、已完成 blocks、当前 block；块内双向）。

**离线轨迹收集（Algorithm 1）**：teacher 在 domain prompts 上 block-wise decode，N=Lg=256、B=32、每步 finalize 当前 block 最高 confidence 的 1 token（与 Nie et al. 报告的最优 operating point 对齐）。存 token trajectory Tx 与 **last hidden state buffer** Hx（每 finalize 写一行，比存 full logits 省 ~30× 存储）。多温度 τ∈{0.0, 0.5} 增广；τ=1.0 会破坏推理链（Figure 5）。数据来自 Bespoke-Stratos-17k 过滤子集（prompt ≤512），LLaDA 另加 7.5k DParallel math prompts；ground truth 用 Qwen2.5-7B 生成。

**三目标训练（Algorithm 2）**：采样轨迹中状态 y 及其 **block-completion** y*（至多 B 步之差）。
- **Distillation**：对 newly unmasked 位置 Uy，用 Hx 重建 teacher logits，student 对齐 forward KL。
- **Consistency**：对仍 mask 位置 Sy，最小化 student 在 y 与 y* 的预测分布 KL（qϕ− stop-gradient，Song et al. 2023 风格）。
- **DLM loss**：随机 mask ratio 的标准 masked denoising，保持 mask 预测能力。
总损失 L = wdistill·LDistillation + wcons·LConsistency + wdlm·LDLM；Dream 权重 (1.0, 0.5, 0.01)，LLaDA (1.0, 0.5, 0.1)。**LoRA** 作用于 attention + MLP，16 epochs，effective batch 64。

**推理**：block-causal decode，prompt 与已完成 blocks **exact KV cache**；块内按 Fast-dLLM 式 **confidence threshold**（τconf=0.9）并行 reveal 多 token；遇 <endoftext> **early stop**。刻意不用 inter-block parallelism（D2F 启发）以避免额外 task-dependent 超参。

## 设计取舍

- **Block-causal student vs 保持 bidirectional**：赢得 exact KV cache、步数可激进削减、early stop；牺牲跨 block 全局双向上下文与「生成长度预算」感知，块间仅因果可见。
- **Consistency + distillation vs 纯 inference trick**：训练成本 8h（Dream）/ 16h（LLaDA），但使少步 multi-token finalize 质量可接受；纯截断步数或 training-free parallel decode 在同等步数下精度崩塌（Table 4）。
- **Hidden-state distillation vs logits 存储**：存储与 I/O 更省，需 lm_head 重建 teacher 分布；论文称 forward KL + logit space 优于 reverse KL / MSE embedding distillation。
- **固定 B=32, Lg=256 训练与推理对齐**：Table/Figure 8 显示推理 B≠32（尤其 B=64）时 TPS 饱和甚至下降——train–inference block size 错位会脆化。
- **边界条件**：在 **math/code、中等生成长度、batch=1、开源 MDM backbone** 上收益最大；长推理链（MATH）、需全局双向规划的任务为已知弱点。

## 实验与结果

**设置**：GSM8K、GSM8K-CoT、MATH、HumanEval、MBPP；4× NVIDIA A100 80GB，batch=1 data parallel；Lg=256、B=32、greedy、τconf=0.9。Baselines：naive block-wise DLM、dLLM-Cache、Fast-dLLM (Par.)、Fast-dLLM (Par.+D.C.)；AR 对照 Qwen2.5-7B-Instruct（vs Dream）、Llama-3.1-8B-Instruct（vs LLaDA）。

- **CDLM–Dream**：refinement steps **4.1–7.7×**↓；latency 最高 **14.5×**（MBPP-Instruct）、**11.2×**（GSM8K-CoT）；部分 benchmark 精度持平或略升（MBPP-Instruct 51.8→53.0，HumanEval-Instruct 48.2→50.0），MATH 下降。
- **CDLM–LLaDA**：steps **3.4–7.9×**↓；GSM8K latency 28.3s→**3.3s**；HumanEval 37.8→40.2，MATH 24.1→28.3；GSM8K 77.1→73.9（加 math 数据可部分恢复）。
- **吞吐 vs AR**：CDLM 相对 naive DLM **3–21×** TPS；CDLM–Dream 在 GSM8K-CoT、MBPP 上 **1.2× / 1.1×** 于 Qwen2.5-7B；CDLM–LLaDA 在 GSM8K、HumanEval 上 **1.3× / 4.2×** 于 Llama-3.1-8B。每步 finalize 约 **2.2–2.4** tokens（Dream）。
- **Ablation**：distillation+consistency 耦合优于单独；wdlm 过小伤 math、过大影响 coding 收敛速度；confidence τ=0.9 为速度–质量折中（τ 0.85 更快但分略降）。
- **系统分析（§5.4）**：block-wise DLM 在 bs≈8（B=32）过 ridge point，解释小 batch 下相对 AR 的 compute 利用率优势；vanilla DLM 即使 bs=128 仍近 compute 饱和。

## Critical Analysis

### 论证链条

链条：**分解瓶颈**（无 KV cache + 步数多）→ **训练** block-causal + consistency/distillation 学 multi-token jumps → **推理** exact cache + parallel finalize → **结果** steps/latency/TPS 大幅改善且多数 benchmark 精度 competitive。

闭合较好的部分：ablation 证明「少步」必须配 consistency 训练；AI/roofline 分析解释 block-wise 相对 AR/vanilla DLM 的硬件定位；与 Fast-dLLM、dLLM-Cache 等同配置对比较完整。

薄弱环节：（1）**精度相对 AR 仍普遍落后**（如 MBPP-Instruct 53 vs 81.7），主 claim 是加速而非 beat AR on quality，但「部分 TPS 超 AR」易被误读为全面优势；（2）训练数据高度 math-focused、规模小，对 MATH/GSM8K 的外推与失败分析偏事后；（3）未实现 production serving stack（[[Continuous-Batching]]、[[PagedAttention]] 等），latency 来自自定义 generation routine 求和。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效 |
|------|-----------|----------|
| 离线 teacher 轨迹足以教 multi-token finalize | 相对 naive 截断步数质量保持 | 分布外任务、更长 Lg、不同 block policy |
| Block-causal 不损块内 refinement 能力 | 多块 benchmark 精度 competitive | 全局规划、长链 math、infilling |
| Lg=256 训练预算够 | Dream 多数任务 OK | MATH、复杂 multi-step reasoning |
| τconf=0.9 通用 | 两任务 ablation 稳健 | 高熵开放生成、非 greedy 采样 |
| LoRA 微调足够 | 8–16h 训练即显著加速 | 全参微调或更大数据是否必要——未对比 |

### 实验可信度

**强项**：双 backbone（Dream/LLaDA）、多 benchmark、步数/延迟/长度/精度同表、loss weight / step truncation / τconf / inference B 等 ablation、AI+roofline 系统模型、代码开源（github.com/SqueezeAILab/CDLM）。

**弱点**：（1）主表为 MinerU 图片表格，精确数字以 [[7cbbc409ec990f19c78c75bd1e06f215]] 为准；（2）未与 D2F 等同为 Lg=512 的 block-causal 训练方法公平对比（作者称 D2F 用 Base 非 Instruct）；（3）仅 batch=1，无多租户 tail latency；（4）AR baseline 与 DLM backbone 不同族，TPS 对比混合了架构与 decoding 算法差异；（5）质量指标偏 pass@1/exact match，无人类评测或长输出连贯性。

### 系统性缺陷

- **Teacher ceiling**：student 精度上限受 bidirectional teacher 约束；论文提出 distill 更强 DLM 或 AR teacher，但当前未做。
- **静态离线轨迹**：无 on-policy 或在线 teacher 修正；student 可能过拟合 ~15k 轨迹的 domain（math-heavy）。
- **KV cache 语义**：块间 causal 保证已完成 block cache 正确，但块内 parallel finalize 仍假设 token 条件独立（DLM 经典假设），高并行度时质量风险论文仅在 ablation 中间接讨论。
- **Serving 集成**：未接入 [[vLLM]]/[[SGLang]]；block-wise mask、early stop、动态步数与 batch scheduler 的交互**论文未讨论**。
- **故障恢复与可观测性**：**论文未讨论**。
- **运维**：轨迹 shard 25–30 GiB/15k samples，多温度增广放大存储；teacher 轨迹生成仍慢，大规模 corpus 构建成本**论文仅轻描淡写**。

## 局限与 Future Work

- **局限 1**：训练依赖离线静态轨迹，数据 ~7.5k–15k 且偏 math，MATH/GSM8K 等已现精度 gap。
- **局限 2**：Lg=256 训练与评测预算可能不够长推理；D2F 用 512 的方向被作者提及但未实验。
- **局限 3**：性能最终受 teacher 限制，未探索 AR teacher 或 30B→8B 跨规模 distill。
- **局限 4**：块间无双向 attention，缺少 D2F 式 inter-block parallelism，wall-clock 仍有优化空间。
- **Future work 1**：在 **Lg=512+、多样化 domain 轨迹、on-policy/在线 teacher 反馈** 上测量是否闭合 MATH/长推理 gap。
- **Future work 2**：将 CDLM student 作为 **[[Speculative-Decoding]] draft model**（论文 Appendix C 讨论）：少步 DLM draft + AR verify，需验证 draft 质量与接受率。
- **Future work 3**：与 Fast-dLLM dual cache、D2F inter-block parallel 等 **正交 inference trick 叠加**，在 production batching 下测端到端 tail latency。

## 相关

- **相关概念**：[[KV-Cache]]、[[LoRA]]、[[Speculative-Decoding]]、[[Attention]]
- **同类系统**：Fast-dLLM、dLLM-Cache、D2F、Dream、LLaDA
- **同会议**：[[MLSys-2026]]
- **对比**：与 TiDAR 等不同——CDLM **不改预训练架构目标**，而是在现有 MDM 上做 consistency post-training 加速采样；与 Fast-dLLM 等 training-free 方法正交，可潜在叠加