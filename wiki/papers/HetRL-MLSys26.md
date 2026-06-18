---
type: paper
name: HetRL
full_title: "HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments"
authors: [Yongjun He, Shuai Zhang, Jiading Gai, Xiyuan Zhang, Boran Han, Bernie Wang, Huzefa Rangwala, George Karypis]
venue: MLSys
year: 2026
tags: [rlhf, heterogeneous-gpu, scheduling, distributed-training]
source_pdf: "[[7f39f8317fbdb1988ef4c628eba02591.pdf]]"
source_md: "[[7f39f8317fbdb1988ef4c628eba02591]]"
---

# HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments (MLSys 2026)

> **一句话总结**：把异构 GPU+跨区网络的 PPO/GRPO 调度建模为 NP-hard 联合优化，五级搜索 + nested SHA + 双层 swap GA，在 verl 上比 homo baseline 吞吐最高 9.17×、平均 3.17×（20k GPU-hour 评测）。

## 问题

RL workflow 含 actor/critic/reward/reference 四模型六任务，现有 verl/StreamRL 假设同构 GPU；跨区 A100/L40S/L4 与 1–60ms 延迟下 naive 调度浪费算力。

## 核心方法

**五级搜索**：task grouping → coarse GPU assignment → medium assignment → intra-model TP/PP → fine tasklet placement。

**Nested SHA**：L1/L2 用 successive halving 分配搜索预算；L3–5 用 genetic algorithm + 跨 task / 跨 tasklet 双层 swap。

**Cost model**：actor gen / inference / training 分项 + 异构带宽延迟；load balancer 调 DP batch 与 PP layer 分布。

基于 verl + Megatron + [[vLLM]]，~3k LOC。

## 关键结果

- Single-Region：vs verl **1.51–2.05×**（sync），vs StreamRL **1.1–1.31×**（async）
- Multi-Region-Hybrid async：vs verl **4.07–9.17×**，vs StreamRL **1.11–1.27×**
- Multi-Continent async：vs verl **4.38–10.76×**
- 64 GPU：24×A100 + 24×L40S + 16×L4；Qwen 4B/8B/14B GSM8k

## 相关

- **相关概念**：[[KV-Cache]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]
- **同类系统**：verl、StreamRL、OpenRLHF
- **同会议**：[[MLSys-2026]]