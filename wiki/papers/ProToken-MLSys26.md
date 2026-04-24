---
type: paper
name: ProToken
full_title: "ProToken: Token-Level Attribution for Federated Large Language Models"
authors: [Waris Gill, Ahmad Humayun, Ali Anwar, Muhammad Ali Gulzar]
venue: MLSys
year: 2026
tags: [federated-learning, llm, attribution, provenance, privacy]
source_pdf: "[[3988c7f88ebcb58c6ce932b957b6f332.pdf]]"
source_md: "[[3988c7f88ebcb58c6ce932b957b6f332]]"
---

# ProToken: Token-Level Attribution for Federated Large Language Models (MLSys 2026)

> **一句话总结**：联邦 LLM 场景下，每生成一个 token 就用「选定后期 transformer 层 + 梯度加权 activation 内积」给每个 client 打分，在 4 模型×4 领域 16 配置上达到 98.62% 平均 client 归因准确率；55 client 规模下仍 >92%。

## 问题

联邦学习（FL）让多个机构（医院、银行）用各自私有数据合训一个全局 LLM。当这个全局 LLM 给出一个问题响应时，**哪些 client 的数据最影响了这段输出**？这个 provenance 问题对 debug、恶意 client 识别、公平奖励分配至关重要，但此前没有工作解决：
- Centralized attribution 方法（LIME、IntegratedGrad、SHAP）定位输入 feature，不是 client。
- FL provenance 已有工作（Gill 等）只支持分类模型，依赖离散输出，对生成式 LLM 不适用。
- 挑战：自回归 token 间的依赖、十亿参数量的计算可承受性、大部分 neuron 与当前 token 无关。

## 核心方法

**核心数学性质：FL aggregation 是线性的**

FedAvg 下 $\theta_{\text{global}} = \sum_i \rho_i \theta_i$，因此对任一输入 $h$，全局 neuron 输出可分解为 $\sum_i \rho_i (\theta_i^\top h)$。这给了「每个 client 的 hypothetical contribution」。

**三个关键设计**

1. **Layer selection for tractability**：transformer 后期层（self-attention output projection + 最终 FFN）集中 task-specific signal，只对这些层做 attribution，避开数十亿参数全量计算（1B 模型 + 5 client + 100 token 原本需 500B 次 neuron 计算）。
2. **Gradient-based relevance weighting**：每个 token 用 $\mathbf{g}^\ell = \partial \text{logit}_{x_j} / \partial \mathbf{h}_G^\ell$ 当权重，和 client 模型在选中层的 activation 做内积 $\langle \mathbf{h}_i^\ell, \mathbf{g}_{x_j}^\ell \rangle$——自动 filter 掉与当前 token 无关的 neuron。
3. **Autoregressive aggregation**：每个生成 step 算 per-token per-client 分数，再 summation + softmax 得最终 attribution。

**评测框架**：用 backdoor injection 制造 verifiable ground truth——给目标 client 注入独特 trigger→sentinel response 对，任何 sentinel response 出现就明确归属到那个 client。

## 关键结果

- **平均 attribution 准确率**：16 configs（4 架构 Gemma/Llama/Qwen/SmolLM × 4 领域 medical/finance/math/code）上 **98.62%**。
- **可扩展性**：55 client（9.2× 放大）下仍 >92%，且 contributing vs non-contributing 有明显 binary 分离。
- **首个 federated LLM token-level provenance 方法**。

## 相关

- **相关概念**：[[LoRA]]（FL LLM 常用 PEFT）
- **同类系统**：Gill 等的分类 model provenance、LIME、SHAP、IntegratedGradients
- **同会议**：[[MLSys-2026]]
