---
type: paper
name: ProTrain
full_title: "ProTrain: Efficient LLM Training via Automatic Memory Management"
authors: [Hanmei Yang, Jin Zhou, Yao Fu, Xiaoqun Wang, Ramine Roane, "et al."]
venue: MLSys
year: 2026
tags: [llm-training, memory-management, zero, gradient-checkpointing, offloading]
source_pdf: "[[a3c65c2974270fd093ee8a9bf8ae7d0b.pdf]]"
source_md: "[[a3c65c2974270fd093ee8a9bf8ae7d0b]]"
---

# ProTrain: Efficient LLM Training via Automatic Memory Management (MLSys 2026)

> **一句话总结**：把 ZeRO 分片、tensor swapping、gradient checkpointing 统一到结构化配置空间，靠 memory-aware profiler 建 runtime/memory cost model 自动搜最优配置，训练吞吐比 DeepSpeed/Colossal-AI/FSDP 高 1.43x-2.71x。

## 问题

DeepSpeed 暴露 18+ 相互耦合的低级 knob（`stage3_max_live_parameters`、`stage3_max_reuse_distance` 等），手工调优需要深厚系统知识。不同配置技术还互斥或竞争：checkpointing 和 tensor swapping 互斥决策，activation swapping 与 parameter prefetching 争 CPU-GPU 带宽。同一套配置换硬件（3090 ↔ A100）就失效，经常 OOM。

根因：缺合适抽象，没有人工能 jointly 探索指数级的搜索空间。

## 核心方法

**三大组件**：

1. **Structured Memory Strategies** — 用两个协同策略统一所有内存技术：
   - **Hierarchical Chunk Management** 管 model states：inter-chunk 分 persistent（常驻 GPU，直接更新）与 non-persistent（offload CPU），unify ZeRO sharding 与 offloading；intra-chunk 按执行序组织参数，避免 ping-pong access，用 pre-allocated buffer 做确定性预取。
   - **Interleaved Block Management** 管 activations：在 transformer block 粒度给每个 block 选 swap / checkpoint / none，interleave 布局提高 overlap 机会并降峰值内存。

2. **Memory-Aware Profiler** — 捕获传统 profiler 遗漏的 transient 内存与 unhookable operator（`nn.functional.softmax` 等），用 intra/inter-operator memory delta 两类测量补齐。通过 on-demand tensor management 在单 GPU 上跑大模型完整 trace，再静态 reconstruct 不同配置下峰值内存（预测误差 <4%）。

3. **Automatic Memory Management** — 把内存策略抽象成一组 tunable 参数（`n_persist`、`n_buffer`、`n_swap`、`n_checkpoint`），建 runtime + peak memory 两个 cost model，formulate 成 constrained search，exhaustive + 剪枝（按内存递增序，超 capacity 早停）选 per-iteration runtime 最小配置。

## 关键结果

- 4xRTX 3090 上 GPT-2 10B 平均 2090 tokens/s，比 DeepSpeed/Colossal-AI/FSDP 高 1.77-2.71x。
- 4xA100 上比 DeepSpeed/Colossal-AI/FSDP 分别快 1.85x / 1.43x / 2.22x。
- 最大可训模型：单 RTX 3090 34B vs DeepSpeed 15B；单 A100 75B vs FSDP 10B（2.47x 和 7.5x）。
- runtime 和 memory estimator 预测误差均 <4%。

## 相关

- **相关概念**：[[ZeRO]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：DeepSpeed、Colossal-AI、FSDP
- **同会议**：[[MLSys-2026]]
