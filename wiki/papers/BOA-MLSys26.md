---
type: paper
name: BOA
full_title: "Toward Principled LLM Safety Testing: Solving the Jailbreak Oracle Problem"
authors: [Shuyi Lin, Anshuman Suri, Alina Oprea, Cheng Tan]
venue: MLSys
year: 2026
tags: [llm-safety, jailbreak, red-team, search, evaluation]
source_pdf: "[[66f041e16a60928b05a7e228a89c3799.pdf]]"
source_md: "[[66f041e16a60928b05a7e228a89c3799]]"
---

# Toward Principled LLM Safety Testing: Solving the Jailbreak Oracle Problem (MLSys 2026)

> **一句话总结**：形式化 jailbreak oracle 问题并实现 BOA 两阶段搜索（BFS 采样 + DFS priority search），在 ϵ=10⁻⁴  likelihood 预算下 Vicuna-7B JDR 达 95.31%，揭示解码策略微调即可 catastrophic 削弱对齐，且 greedy 评测严重低估部署风险。

## 问题

Jailbreak 评测多为 ad hoc：改 prompt 测 success rate、多用 greedy decoding，无法回答「给定模型+prompt+解码策略，是否存在 likelihood ≥ τ 的 harmful 响应」。采样解码下搜索空间 $O(k^n)$ 指数爆炸，缺乏系统化安全认证框架。

## 核心方法

**Jailbreak oracle**：判定是否存在响应 $\hat r$ 使 $J(p,\hat r)=1$ 且 $Pr_D(\hat r|M,p) > \tau(n)$，其中 $\tau$ 由 n-token response likelihood 与用户参数 $\epsilon$ 相对定义。

**BOA** 两阶段：
1. **Phase 1**：$n_{sample}$ 次随机采样，快速命中高概率 jailbreak
2. **Phase 2**：DFS priority search，用 modified judger $\hat J$ 给 partial generation 打分；前 $n_{align}$ token 均匀采样避开高概率 refusal，之后按模型概率采样；refusal filter + response cache 加速

实现可插拔 [[vLLM]]/HuggingFace serving；开源 https://github.com/shuyilinn/BOA

## 关键结果

- 8 模型 JO-Bench（128 prompts）：Vicuna-7B **95.31% JDR**；Gemma-3 **34.38%**；Llama-3.1-8B **24.22%**；Llama-2 **7.03%**
- 解码参数微小变化可 dramatically 改变 vulnerability profile
- 比 naive sampling 显著更高 jailbreak discovery rate
- Sat 可证漏洞存在；Unsat 仅在搜索预算内提供 bounded 安全证据

## 相关

- **相关概念**：jailbreak、alignment、red teaming
- **同类系统**：JailbreakBench、HarmBench、[[vLLM]]
- **同会议**：[[MLSys-2026]]