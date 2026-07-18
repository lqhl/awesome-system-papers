---
type: paper
name: CAGE
full_title: "CAGE: CURVATURE-AWARE GRADIENT ESTIMATION FOR ACCURATE QUANTIZATION-AWARE TRAINING"
authors: [Soroush Tabesh, Mher Safaryan, Andrei Panferov, Alexandra Volkova, Dan Alistarh]
venue: MLSys
year: 2026
tags: [quantization, qat, llm-training, ste, optimization]
source_pdf: "[[d67d8ab4f4c10bf22aa353e27879133c.pdf]]"
source_md: "[[d67d8ab4f4c10bf22aa353e27879133c]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# CAGE: CURVATURE-AWARE GRADIENT ESTIMATION FOR ACCURATE QUANTIZATION-AWARE TRAINING (MLSys 2026)

> **一句话总结**：[[QAT]] 默认 [[STE]] 无收敛保证且低比特精度差，CAGE 将量化约束与 loss 最小化视为多目标 Pareto 平衡，用 curvature-aware 项 **λ(Q(x)−x)** 修正梯度（可用 [[Adam]] 二阶统计高效实现），微调压缩误差减半、Llama **W3A3** 预训练 loss 优于 QuEST **W4A4**。

## 问题与动机

[[LLM]] 部署主流 [[PTQ]]，但 [[Quantization-Aware-Training]] 可在训练期适应量化误差。STE 用 identity 代替 ∂Q/∂x，不稳定、慢收敛、无理论保证。LSQ/ProxQuant 等启发式多，缺非凸下 Pareto 最优收敛表述。

CAGE 从「同时降 loss 与量化误差」的多目标视角推导 principled gradient correction。

## 关键观察 / 隐含假设

- **观察 1：QAT 不可只求 ∇f(Q(x*))=0，因 Q 非可逆，应求 λ-Pareto 点：∇f(x*) = λ(Q(x*)−x*)。**
  - **依赖假设**：smoothness 下 quantization error 可视为隐式正则 ∇ϕ(x)。
  - **可能失效场景**：极低比特或 per-channel 动态 Q 非 smooth 时理论假设弱化。

- **观察 2**：STE 等价 error-feedback 仅当 Hessian≈I 时精确；一般曲率下需把量化误差 `e_t=x_t−Q(x_t)` 耦入更新。
  - **依赖假设**：局部 Hessian 信息可近似（Adam 方差统计）。
  - **可能失效场景**：Muon/Shampoo 等与 CAGE 耦合收益因优化器而异（论文测了多种）。

- **观察 3：微调 QAT 压缩误差约减半；800M Llama 预训练 W3A3 loss 低于 QuEST W4A4。**
  - **依赖假设**：动态量化网格与 CAGE 实现兼容。
  - **可能失效场景**：>70B 规模预训练成本与稳定性未展示。

- **假设 1**：coupled vs decoupled correction 两种注入方式对多数优化器有效。
  - **证据强度**：**强**——合成实验+微调+预训练三层验证。

## 核心方法

**Pareto 条件** → **CAGE gradient** = STE gradient + curvature-aware term，利用 loss 局部二阶信息抵消量化所致 loss 上升。

**实现**：optimizer-agnostic；高效版复用 Adam 统计估 curvature；支持 coupled（误差加入梯度前）/ decoupled（加入 optimizer 更新后）。

**理论**：smooth non-convex 下 ergodic 收敛到 Pareto-optimal 点（论文定理）。

## 设计取舍

- **曲率修正 vs 开销**：比全 Hessian 便宜，比纯 STE 多少量统计。
- **W3A3 极致压缩 vs 训练稳定性**：需与 LR/量化网格协同。
- **vs PTQ 生态**：QAT 贵但缩 accuracy gap；CAGE 降 QAT 调参痛苦。
- **边界条件**：最大 800M 预训练；W4/W3 为主。

## 实验与结果

- 合成 4-bit quadratic benchmark（condition number 1/10/100、10 个 seed）中，CAGE 的最终 validation loss 低于 STE-SGD/STE-Adam（§4.1，Fig. 1–2）。
- Llama-3.2-3B 在 Tulu-SFT 的 MXFP4 QAT 中，作者报告 CAGE 相对 QuEST 将 quantization accuracy loss 约减半；指标为 GSM8K exact match 与 HellaSwag/WinoGrande accuracy（§4.2，Fig. 3）。
- C4 上 30M–800M Llama-style pretraining（100 tokens/parameter、8×H100、3 seed）中，CAGE W3A3 的 validation loss 低于 QuEST W4A4（§4.3，Fig. 5，Table 1）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| CAGE 的理论保证不含非消失量化误差项 | 论文给出 `O(1/sqrt(T))` ergodic convergence 到定义的 Pareto-optimal state，并对比 prior QAT guarantee 的 quantization-error term（§3.2，Theorem 1 discussion） | smooth non-convex loss 与 Assumption 3；理论保证，不是生产性能保证 | high |
| CAGE 在合成低比特目标上降低 final validation loss | 4-bit quadratic、condition number 1/10/100、10 seed 中均优于 STE-SGD/STE-Adam（§4.1，Fig. 1–2） | 固定 step budget 的 synthetic objective；图中无可靠精确差值 | high |
| CAGE 在 3B instruction fine-tuning 中降低量化 accuracy loss | 作者报告相对 QuEST 的 MXFP4 QAT accuracy loss 约减半，使用 GSM8K/HellaSwag/WinoGrande（§4.2，Fig. 3） | 单个 3B model、4-bit float；不能外推为所有模型的固定倍率 | medium |
| CAGE W3A3 在预训练 grid 中优于 QuEST W4A4 | 30M–800M 的 C4 validation loss 报告为 Pareto-superior（§4.3，Fig. 5，Table 1） | 8×H100、3 seed，测 validation loss 而非下游任务 | high |
| CAGE 改善拟合的 parameter efficiency | 4-bit 时大于 10%、2-bit 时 20%，相对 QuEST（§4.3，Fig. 6） | scaling-law fit，不是直接硬件吞吐或成本测量 | medium |

## Critical Analysis

### 论证链条

STE 缺陷 → 多目标 Pareto → curvature correction → 理论与多场景 SOTA，闭合好。大模型外推主要靠 loss 非下游 task 全评。

### 假设压力测试

推理期 dynamic quant + CAGE 训练分布偏移未测。与 [[KV-Cache]] 量化、[[MoE]] 联合 QAT 未覆盖。

### 实验可信度

QuEST 等强 baseline；理论+实证双轨。缺：70B+、生产 serving 端到端 latency after QAT。

### 系统性缺陷

论文未讨论 CAGE 训练 wall-clock vs STE、分布式 QAT 缩放。量化算子硬件支持碎片化风险仍在。

## 局限与 Future Work

- **局限 1**：大规模 LLM QAT 训练成本与稳定性证据有限。
- **局限 2**：非 smooth 量化器理论保证减弱。
- **Future work 1**：70B 级 QAT + 下游 benchmark 闭环。
- **Future work 2**：与 [[Kitty]] 等 KV 量化算法联合测 W/A/KV 协同 QAT。

## 相关

- **相关概念**：[[Quantization-Aware-Training]]、[[STE]]、[[PTQ]]、[[Adam]]
- **同类方法**：LSQ、ProxQuant、QuEST、ReSTE
- **同会议**：[[MLSys-2026]]
