---
type: paper
name: PARROT
full_title: "PARROT: Persuasion and Agreement Robustness Rating of Output Truth — A Sycophancy Robustness Benchmark for LLMs"
authors: [Yusuf Çelebi, Ozay Ezerceli, Mahmoud El Hussieni]
venue: MLSys
year: 2026
tags: [llm-safety, sycophancy, benchmark, alignment, calibration]
source_pdf: "[[3def184ad8f4755ff269862ea77393dd.pdf]]"
source_md: "[[3def184ad8f4755ff269862ea77393dd]]"
---

# PARROT: Persuasion and Agreement Robustness Rating of Output Truth (MLSys 2026)

> **一句话总结**：PARROT 用 neutral vs 权威错误断言的双路径 MMLU 评测 + logprob 置信度追踪 + 8 态行为分类，在 22 模型上揭示 sycophancy 异质性：GPT-5 follow rate **4%**，GPT-4 达 **80%**，Qwen2.5-1.5B **94%**。

## 问题

LLM 在高风险场景易受用户权威/说服压力产生 sycophancy（附和错误断言），导致 epistemic collapse。现有 benchmark 多窄域、少置信度动态、难量产对比。部署前缺乏可复现、可集成的「抗过度顺从」评测基础设施。

## 核心方法

**Dual-path evaluation**：同一题 base prompt vs 追加领域权威错误断言，固定 decoding（T=0）与 logprobs 采集。

**Confidence derivation**：对最终选项锚定 log-mass，temperature scaling 后比较 Δconf_gold 与 Δconf_asserted，检测置信度反转。

**8-state taxonomy**：如 Robust Correct、Sycophantic Compliance、Reinforced Error、Self-Correction 等，超越二元准确率。

**Pipeline**：run→derive→analyze 三阶段，artifact 自包含可离线重放。

## 关键结果

- **1302** MMLU 题 × **22** 模型 = **27,342** 次评估
- Frontier：GPT-5 follow **4%**、GPT-4.1 **10%**、Claude Sonnet 4.5 **11%**
- Legacy/small：GPT-4 follow **80%**（72%→18% acc）、Qwen2.5-1.5B **94%**
- 领域脆弱性：international law follow **>85%**；elementary math 相对韧性 **43%**

## 相关

- **相关概念**：[[Quantization]]
- **同类系统**：Syco-bench、SycEval、ELEPHANT
- **同会议**：[[MLSys-2026]]