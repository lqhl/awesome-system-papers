---
type: paper
name: PRISM
full_title: "PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models"
authors: [Xuliang Wang, Yuetao Chen, Maochan Zhen, Fang Liu, Xinzhou Zheng, et al.]
venue: MLSys
year: 2026
tags: [speculative-decoding, draft-model, llm-inference, conditional-computing, sglang]
source_pdf: "[[65ded5353c5ee48d0b7d48c591b8f430.pdf]]"
source_md: "[[65ded5353c5ee48d0b7d48c591b8f430]]"
---

# PRISM: Parametrically Refactoring Inference for Speculative Sampling Draft Models (MLSys 2026)

> **一句话总结**：把 speculative decoding 的 draft model 按 draft step 拆成多个 processing module，每步只激活一个 module（类似 MoE 在 auto-regressive 步上的条件计算），参数量随 step 叠加但每步激活不变；在 SGLang 上相比高度优化的 baseline 引擎把 decoding throughput 提升 **>2.6×**，acceptance length 超 EAGLE-2/HASS/EAGLE-3。

## 问题

[[Speculative-Decoding]] 用小 draft model 预测 verify 大 target model 的 token。EAGLE 系列用 target 的 hidden state 作为额外输入提 acceptance rate。近期趋势是 draft model 越做越大（Table 1：从 0.68% 涨到 19.88% of target size），EAGLE-3、Scylla、Meta 的工作都在做 vertical stacking 或 MoE FFN。核心两难：drafter 越大 acceptance rate 越高，但 draft overhead 也越大，每步 forward pass 成本线性涨。

另一个观察：draft step 难度非均匀——越靠后的 step acceptance rate 急剧下降（Figure 1 LLaMA-3-8B）。统一架构让所有 step 共享参数，浪费了做 step-wise specialization 的机会。

## 核心方法

**PRISM 核心思想**：在 auto-regressive step 维度做 conditional computing。把 draft model 拆成 M 个 processing module（每个含 fusion layer + transformer layer），用 surjection $f_{map}: \{1, ..., K\} \to \{1, ..., M\}$ 把 K 个 draft step 分配到 M 个 module。每步只激活一个 module。

**关键架构细节**（Figure 3）：
- Prefill：用 module $L_{f_{map}(1)}$ 处理所有已接受 token，输出 KV cache 和最后隐状态 $\hat h_0$。
- Decode step $k$：用 module $L_{f_{map}(k)}$，fuse 上一步 token embedding 和 hidden state，处理并输出下一 token。
- **KV cache 跨 module 共享**（不同 step 的 module 虽然参数不同，但 KV cache 顺接）。
- 与 tree-based verification 和 stochastic sampling 完全兼容。

**两大好处**：
- **Adaptive representation complexity**：越靠后的 step 经过越深的级联计算（cascade of different parameter sets），匹配任务难度递增。
- **Decoupling capacity from cost**：总参数量可以大幅增加（表达能力上升），但每步激活参数保持不变（推理成本恒定）。

**训练**（两阶段）：
- **Warm-up**：只用 1 个 module 训，loss = CEL(draft, ground truth) + λ·MSE(draft hidden, target hidden)。
- **Phase 2**：复制 warm-up 的 transformer 权重 M 份，去掉 MSE loss，按 step-wise switch module 训，用 HASS 风格的 3-step context alignment 对抗 exposure bias。

**训练效率**：因为每个 draft step 的前向/反向只过一个 sub-network，相比 monolithic drafter 同参数量但每步穿透整网，训练 cost 更低。

**集成 SGLang**：大多数 speculative decoding 论文在 PyTorch 评估，高估加速（缺 CUDA graph、continuous batching）。PRISM 集成进 SGLang，配合 CUDA graph、continuous batching、其他优化。

## 关键结果

- Target 模型：LLaMA-2-7B 和 LLaMA-3-8B。
- Benchmarks：MT-bench、HumanEval、GSM8K、Alpaca、CNN/DM、Natural Questions。
- NVIDIA A800：LLaMA-3-8B 上 PRISM 的 acceptance length 和 TPS 全面超 Vanilla、Standard、EAGLE-2、HASS，例如 MT-bench T=0 时 AL=4.29 (HASS 3.93)、TPS=201.51 (HASS 180.50)。
- 相比 SGLang 原生高度优化的 baseline 引擎，decoding throughput 提升 **>2.6×**。
- Scaling law 验证：PRISM 随训练数据增长（100K → 800K samples）scale 更好，证明"模型容量扩 + 每步激活不变"这条新 scaling 路线有效。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[MoE]]、[[Conditional-Computing]]、[[KV-Cache]]、[[Tree-Attention]]
- **对比系统**：EAGLE/EAGLE-2/EAGLE-3、HASS、Scylla、Meta's MoE-drafter
- **相关框架**：[[SGLang]]
- **同会议**：[[MLSys-2026]]
