---
type: paper
name: RLVR-LowData
full_title: "Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes"
authors: [Justin Bauer, Thomas Walshe, Derek Pham, Harit Vishwakarma, Armin Parchami, "et al."]
venue: MLSys
year: 2026
tags: [rlvr, fine-tuning, small-language-model, data-efficiency, reasoning]
source_pdf: "[[7f1de29e6da19d22b51c68001e7e0e54.pdf]]"
source_md: "[[7f1de29e6da19d22b51c68001e7e0e54]]"
---

# Learning from Less: Measuring the Effectiveness of RLVR in Low Data and Compute Regimes (MLSys 2026)

> **一句话总结**：在三个程序生成的 reasoning 数据集（counting、graph、spatial）上系统研究 RLVR 在 low data regime 的表现：mixed-difficulty 训练数据带来最多 **5× sample efficiency**，且 easier-task 训练能泛化到 harder task。

## 问题

现有 RLVR（Reinforcement Learning with Verifiable Rewards，DeepSeek-R1、GRPO 这条线）研究大多假设海量高质量 annotated 数据和无限 compute（如 DeepMath-103K 有 100K+ sample）。但实际场景里 annotated data 和 compute 都紧缺，现有结论是否迁移得过去不清楚。

已有工作主要关注 model size 和 compute scaling（ScaleRL 等），**data composition 和 low-data regime 研究不足**：小数据量下，task 难度分布如何影响 generalization？

## 核心方法

**Procedural 数据集**（三类全部程序生成，ground truth 可验证）：

1. **Counting Problems**：整数序列上的 filter + aggregation（count、unique count、bitwise、threshold 等共 20+ operator），1-4 个 filter + 0-3 个 transformation = 1-7 步 compositional reasoning
2. **Graph Reasoning**：5-25 节点图上的 20+ 操作（min vertex cover、max clique、Hamiltonian path、graph diameter 等），networkx 验证
3. **Spatial Reasoning**：2D 网格上粒子的 move/rotate，查询相对/绝对位置；基于 egocentric vs allocentric 两种 frame of reference

每个数据集生成 1500+ 题，跑 10 个主流模型（GPT、Claude、Gemini、Grok、Llama、Qwen）做 **multi-model calibration** 定难度：
- Easy：67-100% 模型做对
- Medium：34-66%
- Hard：0-33%

**训练配置**：
- Base：Qwen3-4B + [[LoRA]]（r=64, α=16，~100M 可训练参数）
- 算法：**GRPO**（Group Relative Policy Optimization），每 prompt 生成 K=5-8 个 completion，batch-wise advantage
- Reward：二元正确性 + 格式 bonus + reasoning step penalty（counting 用 5 步 soft cap，graph 用 JSON format bonus，spatial 用 exact match）
- Hardware：4× A100 80GB，5-12 小时/run
- 测试用 greedy decoding（T=0），holdout 每 50 步 eval

**对比配置**：
- Easy-only 训练子集：100/200/500 样本
- Mixed 训练子集：100/200/500 样本（Easy/Medium/Hard 各 ~33%）

## 关键结果

- **Mixed-difficulty 在 low data 下 sample efficiency 最多 5×**：同等数据预算下，mixed 配置比纯 easy 配置泛化效果显著更好
- **Easy → Hard 泛化**：在低复杂度任务上训练的模型可以泛化到高复杂度任务
- **Procedural data 的价值**：可精细控制 size/diversity/complexity，相比人工 curated 数据更适合做 ablation 和 scaling law 研究
- Figure 1 显示三个数据集在 10 个 foundation model 上的 pass rate 分布，验证了分层难度有实际判别力

**启示**：为未来 RLVR 的 data scaling law 研究（在 compute/data/difficulty 三维空间里）提供经验依据，鼓励用 procedural generator 做 fine-tuning 数据开发。

## 相关

- **相关概念**：[[RLVR]]、[[LoRA]]、GRPO、Reasoning、Data-Scaling-Law
- **同类工作**：ScaleRL（compute scaling）、LIMR（Less is More for RL）、DeepMath-103K
- **相关模型**：Qwen3-4B、DeepSeek-R1
- **同会议**：[[MLSys-2026]]
