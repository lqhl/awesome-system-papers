---
type: paper
name: CAGE
full_title: "CAGE: Curvature-Aware Gradient Estimation for Accurate Quantization-Aware Training"
authors: [Soroush Tabesh, Mher Safaryan, Andrei Panferov, Alexandra Volkova, Dan Alistarh]
venue: MLSys
year: 2026
tags: [quantization-aware-training, low-bit, straight-through-estimator, pareto-optimality, llama]
source_pdf: "[[d67d8ab4f4c10bf22aa353e27879133c.pdf]]"
source_md: "[[d67d8ab4f4c10bf22aa353e27879133c]]"
---

# CAGE: Curvature-Aware Gradient Estimation for Accurate Quantization-Aware Training (MLSys 2026)

> **一句话总结**：CAGE 给 STE 梯度加一个由 Pareto-optimality 条件推导的 curvature-aware 校正项，用 Adam 二阶矩近似曲率；3-bit weights+activations 预训练 Llama 的精度匹配此前最佳 4-bit QuEST，且 fine-tuning 场景下量化误差减半。

## 问题

Quantization-Aware Training (QAT) 的主流是 Straight-Through Estimator (STE)，后向绕过不可导的量化算子，梯度用 identity Jacobian 近似。但 STE 收敛慢、震荡，现有改进（LSQ、EWGS、ProxQuant 等）都是启发式且无收敛保证。从理论看，标准非凸 QAT 的收敛结果都带与量化误差成正比的 non-vanishing 项——因为 Q 不可逆，`∇f(Q(x*)) = 0` 一般不可达。

## 核心方法

把 QAT 看成 **multi-objective**：同时最小化任务损失 f(x) 和量化距离 ‖x - Q(x)‖。定义 λ-Pareto 最优：
$$
\nabla_{\lambda P} f(Q(x^*)) := \nabla f(x^*) + \lambda(x^* - Q(x^*)) = 0
$$

由此推出 **CAGE 更新**：在 SGD 下即
$$
x_{t+1} = x_t - \alpha(\tilde\nabla f(x_t) + \lambda(x_t - Q(x_t)))
$$

即在 STE 梯度上加 quantization error 的 error-feedback 项。对 stateful optimizer（Adam）提供 coupled（加到 gradient 再喂给 optimizer）和 decoupled（加到 optimizer 输出上）两种变体；coupled 版本经 Adam 二阶矩 `v_t` 缩放后自然得到 **对角 preconditioned 的曲率感知校正**（曲率由 Adam 已维护的 statistics 近似，零额外成本）。

**理论**：在光滑非凸 + 光滑量化算子假设下，SGD 版 CAGE 收敛到 Pareto 最优点，率为 O(1/√T)。对比 concurrent work LOTION 用 random rounding 光滑 loss 再二阶展开，CAGE 直接正则化 **training dynamics** 而非 loss，不需要三阶导数、兼容 weight+activation 联合量化。

## 关键结果

- **QAT fine-tuning**：相对 prior best 方法，quantization loss（accuracy gap）减半。
- **QAT pre-training Llama**（最大 800M 参数）：W3A3（3-bit weights+3-bit activations）精度匹配此前 SOTA QuEST 的 W4A4。
- Optimizer-agnostic：在 AdamW、Muon、Shampoo 上都 consistent 增益。
- Code: https://github.com/IST-DASLab/CAGE

## 相关

- **相关概念**：[[Quantization]]、Straight-Through Estimator (STE)、Error Feedback、Pareto-Optimality
- **同类方法**：LSQ、LSQ+、EWGS、ProxQuant、PARQ、AdaSTE、ReSTE、QuEST、LOTION
- **同会议**：[[MLSys-2026]]
