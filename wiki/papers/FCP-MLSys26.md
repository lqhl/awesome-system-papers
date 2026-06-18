---
type: paper
name: FCP
full_title: "Unleashing Scalable Context Parallelism for Foundation Models Pre-Training via FCP"
authors: [Yilong Zhao, Xiaonan Nie, Kan Zhu, Shuang Ma, Zhichao Lai, "et al."]
venue: MLSys
year: 2026
tags: [context-parallelism, long-context, load-balancing, pretraining, ring-attention]
source_pdf: "[[d1f491a404d6854880943e5c3cd9ca25.pdf]]"
source_md: "[[d1f491a404d6854880943e5c3cd9ca25]]"
---

# Unleashing Scalable Context Parallelism for Foundation Models Pre-Training via FCP (MLSys 2026)

> **一句话总结**：FCP 把变长序列切成固定大小 block 做 bin-packing 调度，打破 ring topology 约束，在 256 GPU 上 attention MFU 比 ByteScale/WLB-LLM/RingAttention 高 1.13–2.21×。

## 问题

Foundation model 预训练数据呈长尾长度分布（短文本到 512K token 视频 patch），现有 context parallelism (CP) 两派都有缺陷：Ring Attention 均匀切 N 份导致短序列 over-shard（len(B)<2K 时 MFU 仅 25%）且多余通信占总量 ~50%；按长度分组（ByteScale）则 outlier 长序列造成严重负载不均。最优 (G, M) 调度是 NP-complete，ring topology 进一步锁死搜索空间。

## 核心方法

**FCP**（Flexible Context Parallelism）核心：

- **固定 block 粒度**：每序列切成固定 token block（如 1K），长短序列产生不同 block 数，作为调度与计算基本单元。
- **Workload-aware block distributor**：估计每 block 计算/内存，用 LPT 变体把 block 分到最轻负载 GPU，近最优负载均衡。
- **Congestion-free communication planner**：把 block 传输建模为二分图，每轮 maximal matching 保证每 GPU 至多一发一收，避免网络热点。
- **Block-level pipeline**：pull remote KV → compute attention → push local KV 按 block 交错，重叠通信与计算。
- **Transparent reshuffler**：进入 attention 前 reshuffle 到 FCP layout，退出后恢复，与 FSDP/[[Tensor-Parallelism|TP]]/[[Expert-Parallelism|EP]]/SP 透明组合。

## 关键结果

- 256× NVIDIA GPU 近线性扩展。
- 三种长度分布 workload 上 attention MFU 比 SOTA 高 **1.13–2.21×**。
- 对比 ByteScale、WLB-LLM、RingAttention、MagiAttention。
- Llama-3-70B 配置评测。

## 相关

- **相关概念**：[[Flash-Attention]]、ring attention、sequence parallelism、long-context training
- **同类系统**：DeepSpeed Ulysses、ByteScale、WLB-LLM、MagiAttention
- **同会议**：[[MLSys-2026]]