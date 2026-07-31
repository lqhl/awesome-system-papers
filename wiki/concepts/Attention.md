---
type: concept
aliases: [attention, Self-Attention, Multi-Head-Attention, MHA]
last_updated: 2026-07-30
tags: [transformer, llm, kernel, sequence-modeling]
---

# Attention

> 注意力机制（attention）以 query 对 key/value 做内容寻址，是 Transformer 的核心算子；系统问题集中在二次序列复杂度、[[KV-Cache]] 带宽、数据布局与跨设备通信。

## 核心思想

scaled dot-product attention 计算 `softmax(QKᵀ)V`。训练和 prefill 处理完整序列，decode 每步只产生新 query 并读取历史 KV。FlashAttention 通过 tiling 与 online softmax 减少 HBM materialization；sparse attention 则减少被访问 token，但必须配套索引与 KV layout 才能兑现端到端收益。

## 为什么重要

OSDI 2026 显示 attention 优化已跨越 kernel 边界：[[DirectKV-OSDI26]] 让 kernel 直接访问 CPU-resident KV；[[ECHO-OSDI26]] 以 lossless prefetch 支持 native sparse attention offload；[[KAIROX-OSDI26]] 在 attention 后预测下一层 FFN hot neuron；[[Twill-OSDI26]] 联合求解 FlashAttention 的 SWP/WS schedule 并验证跨 Hopper/Blackwell 的最优性。

## 关键观察 / 隐含假设

- **观察：I/O complexity 与 FLOPs 同等重要。** [[FlashAttention-NeurIPS22]] 的关键是减少 HBM traffic，而非近似 attention。
- **观察：sparsity 不自动减少 KV footprint。** [[ECHO-OSDI26]] 需显式 offload/prefetch，[[IceCache-arXiv26]] 需语义聚类 page。
- **假设：相邻 query 的选择具有可预测性。** [[ECHO-OSDI26]] 利用 score boundary 稳定性；语义突变会降低 overlap。

## 设计空间与取舍

- **Dense exact / sparse exact / approximate**：精度、索引成本和可跳过数据比例不同。
- **Kernel fusion / modular operators**：fusion 减少 materialization，却压缩 scheduler 与 compiler 的组合空间。
- **GPU-resident / tiered KV**：resident latency 低但容量有限；tiering 扩容量但依赖预取准确率。

## 引用本概念的论文

- [[Twill-OSDI26]] — 自动求解 FlashAttention 软件流水与 warp specialization。
- [[DirectKV-OSDI26]] — CPU-memory-aware attention direct access。
- [[ECHO-OSDI26]] — sparse attention KV offload。
- [[TileLoom-OSDI26]] — attention kernel 的 tile-level 调度。
- [[FlashAttention-4-MLSys26]] — 新一代 GPU attention kernel。

## 已知局限 / 开放问题

- 动态稀疏、量化、长上下文与 tiered KV 的统一 layout 尚未形成。
- kernel microbenchmark 的最优 schedule 不一定等于 serving workload 的最优 SLO。
