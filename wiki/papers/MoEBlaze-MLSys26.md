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

> **一句话总结**：[[MoE]] 训练的 token 路由不再物化 per-expert buffer，而是用轻量 index 列表配合 on-the-fly gather/scatter 融合 kernel，同时与 SwiGLU activation checkpoint 协同设计，实测 > 4× 加速、> 50% 显存节省。

## 问题

现代 [[MoE]] 训练的 "memory wall" 被稀疏性放大：

- **Token routing buffer**：传统做法把 token 按 expert 重新排列物化成 per-expert 紧凑 buffer，占 `O(L × K × d)`。DeepSeek 配置下 L=2M、K=4、d=6144 时单层 routing buffer 就是 **94 GB**
- **Intermediate activation**：SwiGLU/SiLU 的 FFN 中间激活 `O(L × h)`，h=24576 时单层 **98 GB**
- Switch Transformer 的 token dropping 能控 buffer 但掉精度；dropless 方案保精度但 buffer 仍很大

两项加起来单层上百 GB，直接卡住 batch size 和 sequence length。

## 核心方法

**端到端 token dispatch 免物化**：不再建 per-expert routed buffer，而是 3 个轻量 index 数据结构驱动：
- `expert_token_indices`（L×K）：每个 expert 的 token id 列表，跨 expert 拼接
- `expert_token_offsets`（E+1）：每 expert 的前缀和
- `token_index_map`（L×K）：每 token 在拼接数组里的位置，反向 gather 用

**Atomic-free GPU 构建 3 步**：
1. 建 dense token-expert bitmap（warp 级并行写，每 (i,e) 只写一次无冲突）
2. 每 CTA 扫 dense map 的一列统计 expert lengths，外部 prefix sum 得 offsets
3. 两阶段 location map 构造：tile-level scan + 全局 offset 相加，得最终写入位置；全并行无原子

融合 kernel：第一层 MLP 用 `expert_token_indices` 从原始未重排 activation 上 gather；第二层 MLP 的输出直接按 `token_index_map` 做 on-the-fly scatter-add 进最终输出 tensor，**消除 routed token buffer 物化**。反向对称：不 expand 梯度，直接用 index 做 scatter。

**SwiGLU 激活 checkpoint 协同设计**：传统 kernel 对 SwiGLU 要把 `a=xW1`、`b=xW2`、`σ(a)`、`SiLU(a)` 和最终 product 都存进 global memory 供反向用。MoEBlaze 把 kernel 和 activation checkpoint 重新设计，只 checkpoint 必要的中间结果（两层 MLP 之间那个），其余反向时重算，既省显存又减 global memory 流量。

## 关键结果

- vs 现有 MoE 框架：**> 4× 加速、> 50% 显存节省**
- 不用 token drop、不用 padding，精度与 dropless baseline 一致
- 避免多 kernel pipeline（radix sort + segmented scan + index recovery），单 kernel 融合减少 launch overhead
- Meta 真实 MoE 训练场景验证

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、SwiGLU、activation checkpointing
- **同类系统**：MegaBlocks (Gale et al. 2023)、DeepSpeed-MoE、Tutel、Switch Transformer、GShard
- **同会议**：[[MLSys-2026]]
