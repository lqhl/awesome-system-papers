---
type: paper
name: MoEBlaze
full_title: "MoEBlaze: Breaking the Memory Wall for Efficient MoE Training on Modern GPUs"
authors: [Jiyuan Zhang, Yining Liu, Siqi Yan, Lisen Deng, Jennifer Cao, et al.]
venue: MLSys
year: 2026
tags: [moe, training, memory-efficiency, kernel, activation-checkpointing]
source_pdf: "[[2b44928ae11fb9384c4cf38708677c48.pdf]]"
source_md: "[[2b44928ae11fb9384c4cf38708677c48]]"
---

# MoEBlaze: Breaking the Memory Wall for Efficient MoE Training on Modern GPUs (MLSys 2026)

> **一句话总结**：[[MoE]] 训练用轻量 index 列表替代物化 routing buffer，融合 on-the-fly gather/scatter 与 SwiGLU activation checkpoint，单层 H100 上 vs Megablocks 1.4–6.2× 加速、激活显存最高降 3.6×（SiLU）/4×（SwiGLU）。

## 问题

[[MoE]] 稀疏激活放大 memory wall：
- **Routing buffer** `O(L×K×d)`：DeepSeek 量级 L=2M、K=4、d=6144 时单层 **~94 GB**
- **FFN 中间激活** `O(L×h)`：h=24576 时单层 **~98 GB**
- token dropping 损精度；dropless 仍要巨大 compact buffer；radix sort 类 dispatch 多 pass、launch 开销大

## 核心方法

**免物化 token dispatch**：`expert_token_indices`、`expert_token_offsets`、`token_index_map` 驱动 forward gather 与 backward scatter，不建 routed activation buffer。

**Atomic-free 三步构建** dense bitmap → per-expert count → location map 并行写入，避免全局 sort。

**SwiGLU kernel + checkpoint 协同**：双投影与 SiLU epilogue 融合，forward 只存两层 MLP 间中间结果；backward 重算 SiLU，消除 a/b/σ 等多份 global buffer。

## 关键结果

单 H100、7 组 MoE 配置 vs Megablocks：
- **SiLU**：显存 3.6× 节省（conf4：22 GB→6.1 GB）；速度 **1.4–3.7×**
- **SwiGLU**：显存约 **4×** 节省（conf3：40 GB→10 GB）；速度 **2–6.2×**
- 无 token drop/padding，精度与 dropless baseline 一致

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]
- **同类系统**：MegaBlocks、DeepSpeed-MoE、Tutel、TurboMoE
- **同会议**：[[MLSys-2026]]