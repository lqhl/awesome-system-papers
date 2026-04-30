---
type: paper
name: Libra
full_title: "Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference"
authors: [Jaehoon Yang, Yushin Kim, Seokwon Moon, Yeonhong Park, Jae W. Lee]
venue: arXiv
year: 2026
tags: [moe, load-balancing, llm-inference, expert-parallelism, sglang]
source_pdf: "[[16200_Libra_Effective_yet_Effi.pdf]]"
source_md: "[[16200_Libra_Effective_yet_Effi]]"
---

# Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference (arXiv 2026)

> **一句话总结**：Libra 用「投机执行下一层 gating function」获得 70-80% expert 激活预测精度（vs Lina 的 20-30%），并用 Two-Stage Locality-Aware Execution（先 MoE_local 后 MoE_remote）把均衡开销隐藏在本地计算窗口里，在 8×H200 上对 Qwen3MoE 235B / GLM-4.5 355B 实现 **prefill throughput +19.2%**，imbalance ratio 接近 1.0。

## 问题

[[MoE]] 推理的核心痛点是 **expert load imbalance**：随着模型放弃严格的 load-balancing loss 以换取专家专精度（DeepSeek-V3、Qwen3MoE、GLM-4.5），少数 hot expert 的 GPU 成为 straggler，决定整层延迟。

现有 system-level 方案在「均衡有效性」与「均衡开销」之间二选一：
- **EPLB**（DeepSeek）：基于历史统计周期性 expert replication，简单但预测精度低，token sharding 是随机分配
- **Lina**：用 expert-selection-path 查表预测下层 expert，但准确率仅 20-30%
- **HarMoEny**：用本层精确 routing 决策，效果好但同步执行 LB 算法把延迟摊在关键路径上

## 核心方法

**关键洞察**：Transformer hidden states 在相邻层间演化缓慢——可以**用当前层的 hidden states 投机执行下一层的 gating function**，从而预测下一层的 expert 激活。这种 runtime-based 预测达到 70-80% 准确率，远超 lookup table 方案。

**Two-Stage Locality-Aware Execution**：把 MoE 计算拆成 `MoE_local`（同 GPU 内的 token-expert 对）和 `MoE_remote`（跨 GPU 的 token-expert 对）。`MoE_local` 不依赖 token sharding 决策，可以立即开始；token sharding 复杂逻辑搬到 CPU 上与 `MoE_local` 并行执行。Dispatch 用 AllGather 而非 All2All，使 dispatch 也能与 token sharding 并行。

**Locality-Aware Expert Replication Planning** 两阶段：
1. 每 GPU 拉取 `N×α` 个本地 token 最频繁请求的 remote expert（扩大 `MoE_local` 窗口）
2. 剩余 `N×(1-α)` 配额用于跨 GPU 负载均衡（hottest expert from most loaded GPU → least loaded GPU）

实现于 [[SGLang]] v0.4.10，核心算法用 Cython 写成 SGLang 原生模块；用 PyTorch SymmetricMemory 做 P2P expert 拷贝；double-buffer 对偶数/奇数层 pipeline。

## 关键结果

- **Prefill throughput**：8×H200 上 Qwen3MoE / GLM-4.5 比 SGLang baseline 提升最高 **+19.2%**，比 EPLB 和 Lina 也持续领先
- **预测精度**：4 个 dataset 上 Libra 70-90% vs Lina 11-47%（GLM-4.5 上 Lina 几乎瞎猜）
- **动态稳定性**：在混合 dataset 模拟分布漂移的场景下 Libra 维持 imbalance ratio ~1.0，baseline 大幅波动
- **延迟分解**（Qwen3MoE seq=1024 batch=32）：Libra 9.07 vs Lina 11.33 vs SGLang 13.61（μs/layer）。Libra 的额外开销（metadata transfer、broadcast、token sharding）被完全隐藏

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Speculative-Decoding]]（思想类似：用早期 layer 信号预测后续 layer 行为）、[[Disaggregation]]（评估假设 prefill-decode 分离）
- **同类系统 / 对比对象**：EPLB（DeepSeek）、Lina（Li 2023）、HarMoEny（Doucet 2025）
- **底层框架**：[[SGLang]]（Libra 实现于 SGLang v0.4.10）
- **相关 MoE 通信工作**：[[fabric-lib-MLSys26|fabric-lib]]（同期 P2P 通信库，可作为 Libra 跨节点扩展的底层）、[[LatencyOptimal-MoELB-INET4AI25|INET4AI 联合优化]]（同期工作，关注 EPLB 的搬运代价优化）
- **评估模型**：Qwen3MoE 235B、GLM-4.5 355B、DeepSeek-V3 671B
