---
type: paper
name: veScale-FSDP
full_title: "veScale-FSDP: Flexible and High-Performance FSDP at Scale"
authors: [Zezhou Wang, Youjie Li, Zhiqi Lin, Jiacheng Yang, Cong Xie, et al.]
venue: MLSys
year: 2026
tags: [fsdp, training, sharding, zero, moe, quantization]
source_pdf: "[[642e92efb79421734881b53e1e1b18b6.pdf]]"
source_md: "[[642e92efb79421734881b53e1e1b18b6]]"
---

# veScale-FSDP: Flexible and High-Performance FSDP at Scale (MLSys 2026)

> **一句话总结**：veScale-FSDP 用 RaggedShard 任意块粒度分片 + structure-aware planning + Distributed Buffer 零拷贝通信，在 10K+ GPU 上比现有 FSDP 吞吐高 5–66%、显存低 16–30%，原生支持 block-wise 量化与非 element-wise 优化器（Muon/Shampoo）。

## 问题

FSDP/ZeRO 是 LLM 训练基础并行手段，但现有实现（DeepSpeed ZeRO、PyTorch FSDP1/2、Megatron-FSDP）采用 element-wise 或 row-wise 均匀分片，与 **block-wise [[Quantization]]**、**矩阵优化器**（Shampoo、Muon）所需的块结构不对齐，迫使侵入式改模型/optimizer 或引入 padding/额外通信。同时 FSDP2 的 interleaved Copy-In/Out 和碎片化 AllGather 在万卡规模下成为吞吐与显存瓶颈。

## 核心方法

**RaggedShard**：新 DTensor placement，支持任意 sharding granularity（element/row/block）和任意 per-device 块分布，可与现有 Shard/Replicate/Partial 组合，直接复用 DTensor checkpointing。

**Grouped communication planning**：将 RaggedShard tensor 分组 bucket 通信，形式化为最小 per-device buffer 的 NP-hard 问题，用多项式启发式（Algorithm 1）排列 tensor 并在 tensor 间而非 tensor 内插入 padding，避免 sharded block 与 Copy-Out 开销。

**Distributed Buffer (DBuffer)**：RaggedShard 映射到全局 buffer slice，实现 zero-copy AllGather/ReduceScatter，减少碎片。

保留 PyTorch `fully_shard` API，ByteDance Seed 生产部署。

## 关键结果

- 密集与稀疏 LLM：**5–66% 更高吞吐**，**16–30% 更低显存**
- 万卡规模高效扩展
- Case study：原生支持 8-bit Adam block-wise 量化与 Muon 矩阵优化器，无需改模型代码
- RaggedShard 开源：https://github.com/volcengine/veScale

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[Quantization]]、[[Pipeline-Parallelism]]
- **同类系统**：PyTorch FSDP2、DeepSpeed ZeRO、Megatron-FSDP
- **同会议**：[[MLSys-2026]]