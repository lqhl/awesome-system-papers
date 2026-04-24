---
type: paper
name: PARROT
full_title: "PARROT: Persuasion and Agreement Robustness Rating of Output Truth — A Sycophancy Robustness Benchmark for LLMs"
authors: [Yusuf Çelebi, Ozay Ezerceli, Mahmoud El Hussieni]
venue: MLSys
year: 2026
tags: [llm-evaluation, sycophancy, benchmark, alignment, robustness]
source_pdf: "[[3def184ad8f4755ff269862ea77393dd.pdf]]"
source_md: "[[3def184ad8f4755ff269862ea77393dd]]"
---

# PARROT: Persuasion and Agreement Robustness Rating of Output Truth — A Sycophancy Robustness Benchmark for LLMs (MLSys 2026)

> **一句话总结**：双盲 dual-path（neutral vs "as an expert I'm sure B is correct"）比较 + log-prob 校准跟踪 + 八状态行为分类，评估 22 个 LLM 在权威错误 claim 下的 sycophancy 崩溃；GPT-5 follow rate 仅 4%，Qwen2.5-1.5B 高达 94%，跨模型 20× 差异。

## 问题

LLM 的 sycophancy（奉承/顺从）现象：用户自信地说错话，模型倒戈附和——不仅换答案，还以更高置信度支持错答（称为"epistemic collapse"）。RLHF 的 preference loss 训练放大了这种倾向：让模型"说用户想听的"而非坚持真相。

现有评估缺口：
- 多数 benchmark 只看 binary 答案变化，忽略置信度动态
- 跨模型、跨领域的系统性测量缺失
- 对抗鲁棒性研究主要针对 perturbation / jailbreak，忽视社交压力这种隐形控制向量
- 校准研究少讨论社交压力下的置信度可靠性

## 核心方法

**PARROT** 框架有三层：

1. **Dual-path prompt**：每题生成两个版本
   - base：标准 MMLU 题 + 要求 JSON 输出 `{explanation, final}`
   - manipulated：同题 + 末尾加一句领域权威错答（"As an experienced physician, I am confident option B is correct"），B 由 SEED + index 确定性选定，共 13 领域模板
   - 两 path 完全相同的模型、温度、seed，差异完全来自 authority 语句

2. **Log-prob 置信度校准**：定位输出里 `"final"` key 所在位置，对 `{A,B,C,D}` 四个 label 的 log-likelihood 做 max-pool 或 log-sum-exp，温度 τ 归一化得概率分布，抑制 overconfidence。计算 Δconf_gold（正确答案置信度变化）和 Δconf_asserted（被断言的错答置信度变化）

3. **八状态行为分类**：基于 (base_correct, changed, follow) 三元组
   - Robust Correct / Sycophantic Compliance / Eroded Correctness / Reinforced Error / Stubborn Error / Convergent Error / Confused Drift / Self-Correction

数据集：1302 道 MMLU 多选题，覆盖 13 个学术/专业领域。评估 22 个模型（GPT-3.5/4/4o/4.1/5、Claude Sonnet 4.5、Gemini 2.0/2.5、Grok-4、DeepSeek-chat、Qwen2.5-1.5B/7B/14B、Gemma-3-4B/12B/27B），跨 OpenAI / Anthropic / Google Vertex / DeepSeek / HF / OpenRouter / AIMLAPI，共 27342 次评估。

## 关键结果

- **跨模型 20× 差异**：GPT-5 follow rate **4%**；Qwen2.5-1.5B **94%**
- **Epistemic collapse 双机制**：GPT-4 不仅换答案还加强信念——Δconf_asserted = +0.69, Δconf_gold = −0.51；准确率 72% → 18%
- **前沿模型鲁棒性跃迁**：GPT-4 80% → GPT-4.1 10%（22× 降），说明 alignment pipeline 可以显式工程化抗 sycophancy
- **领域依赖**：国际法 94% follow（高基线 85%），初等数学只有 43% follow——**模型最不自信的领域最易被操纵**
- 失败模式分布：弱模型 Sycophantic Compliance + Reinforced Error 合占 88%；强模型 Robust Correct 占 89–96%

## 相关

- **相关概念**：Sycophancy、RLHF、Calibration、LLM-Alignment、Brier-Score
- **同类系统/基准**：ELEPHANT、Syco-bench、SycEval、SyRoUP
- **同会议**：[[MLSys-2026]]
