---
type: paper
name: BOOST
full_title: "BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank Large Language Models"
authors: [Zhengyang Wang, Ziyue Liu, Ruijie Zhang, Avinash Maurya, Paul Hovland, "et al."]
venue: MLSys
year: 2026
tags: [low-rank, tensor-parallelism, training, bottleneck, gpu-utilization]
source_pdf: "[[fe9fc289c3ff0af142b6d3bead98a923.pdf]]"
source_md: "[[fe9fc289c3ff0af142b6d3bead98a923]]"
---

# BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank LLMs (MLSys 2026)

> **一句话总结**：BOOST 为低秩瓶颈架构（CoLA / LORO / LaX）设计 Bottleneck-aware [[Tensor-Parallelism]]——TP chunk 边界移到瓶颈 narrow 处，在低维 r 上做 collective；相比 full-rank 加速 **1.46–1.91×**，相比 vanilla low-rank TP **1.87–2.27×**。

## 问题

低秩瓶颈架构（d×d → d×r, r×d）在小规模已验证减参/显存/算力。但 Megatron 式 [[Tensor-Parallelism]] 直接套用会导致：

1. **通信爆炸**：每 block 从 2bsd 涨到最高 **6.5×**（vanilla low-rank TP）
2. **GPU 利用率低**：沿 r 切分使 GEMM reduction 维更小，MLP 块 AI 仅 full-rank TP 的 **0.2×**

## 核心方法

**Bottleneck-aware TP (BTP)**：
- Chunk 边界：up-projection (r×d) column-parallel + 下一 down-projection (d×r) row-parallel
- **沿 d 切分、在 r 上通信**：payload 7bsr，r=d/4 时通信量比 vanilla TP 降 **5.7×**、比 full-rank 低 **1.14×**

**Online RMSNorm**：local 归一化 + 与下一 GEMM all-reduce 融合传 local stat，per-row 修正，数学等价 Sync RMSNorm

**Linear Layer Grouping**：QKV / gate+up 的 batched-GEMM 融合，per-block **1.16×**（bz=1）

**Comm-free low-rank activation checkpointing**：checkpoint 边界与 BTP chunk 对齐，re-forward 无额外 collective（Eff_ckpt **1.70×** vs vanilla）

集成 Nanotron；支持 CoLA / LORO / LaX / SVD。

## 关键结果

- **1.46–1.91×** vs FullRank-TP；**1.87–2.27×** vs Vanilla-TP（1B–30B LLaMA-2，Perlmutter 4×A100）
- 7B @ bz=4：**1.48×**；MLP 块 BTP AI 为 vanilla 的 **2.5×**
- 通信：比 Vanilla-TP 快 **5.3×**、比 FullRank 快 **8%**
- CoLA/LaX/SVD 上均 **1.5–2.2×** vs FullRank

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、Low-Rank、Activation-Checkpointing、[[Flash-Attention]]
- **同类系统**：Megatron-LM、Nanotron、DeepSpeed、CoLA、LORO、LaX
- **同会议**：[[MLSys-2026]]