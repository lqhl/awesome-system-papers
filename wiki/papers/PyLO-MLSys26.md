---
type: paper
name: PyLO
full_title: "PyLO: Towards Accessible Learned Optimizers in PyTorch"
authors: [Paul Janson, Benjamin Therien, Quentin Anthony, Xiaolong Huang, Abhinav Moudgil, "et al."]
venue: MLSys
year: 2026
tags: [learned-optimizer, pytorch, cuda-kernel, meta-learning, velo]
source_pdf: "[[c45147dee729311ef5b5c3003946c48f.pdf]]"
source_md: "[[c45147dee729311ef5b5c3003946c48f]]"
---

# PyLO: Towards Accessible Learned Optimizers in PyTorch (MLSys 2026)

> **一句话总结**：PyLO 把 VeLO / small_fc_lopt 等学习型优化器从 JAX 移植到 PyTorch，配合自定义 CUDA kernel，使 ViT-B/16 的优化器 step 吞吐从 49.73 samples/s 提升到 191.18 samples/s（约 4×）。

## 问题

Learned optimizers (L2O) 已有近 10 年研究，VeLO 花了 4000 TPU-months meta-train，理论上可替代 Adam 且无需调参。但落地受阻于四点：(1) 生态过度聚焦 meta-training 代码而非 deployment；(2) SOTA 实现只有 JAX 版，把约 80% 的 PyTorch 社区挡在门外；(3) 没有类似 HuggingFace Hub 的优化器权重分发机制；(4) 每个参数 tensor 需跑一个小 MLP，naive PyTorch 实现导致优化器 step 成为训练瓶颈。

## 核心方法

PyLO 是一个 PyTorch 库，严格遵循 `torch.optim.Optimizer` 接口，把学习型优化器的推理 (meta-testing) 与 meta-training 解耦：

- **模块化设计**：`pylo.optim`（accumulator 状态管理）、`pylo.models`（优化器网络权重，集成 HuggingFace Hub）、`pylo.csrc`（CUDA 加速）、PyLO-Examples（ImageNet / FineWeb EDU 评测）。
- **CUDA kernel 融合**：把 naive 实现的 74–252 个 kernel launch 压缩到 30–114 个；两个融合 kernel 完成 (1) feature statistics 收集 + (2) feature 构造 + normalization + MLP 前向 + 更新。每个参数 tensor 只保留 `d_feat ≈ 39` 维 register-level 累加器，避免物化 `m×n×d_feat` 临时 tensor。
- **内存层级利用**：features 和激活住 register；normalization 统计住 shared memory；global memory 只读 param/grad/optimizer state。
- **data-parallel 优化器分片**：把优化器 step 分散到多卡进一步降 step time。
- **可叠加 weight decay / LR schedule**：发现 learned optimizer 叠加传统技巧反而能显著增益。

## 关键结果

- ViT-B/16 (batch 32, A100) 训练吞吐：small_fc_lopt 39.36 → 205.59 samples/s（5.2×），VeLO 49.73 → 191.18 samples/s（3.8×）。
- 相比 JAX 官方实现，优化器 step 时间降低 >2×。
- 首次让 learned optimizer 规模化到 real-world pre-training（ImageNet、FineWeb EDU）。
- Code: https://github.com/Belilovsky-Lab/pylo

## 相关

- **相关概念**：learned optimization (L2O)、meta-learning、[[Flash-Attention]]（kernel fusion 思路类比）
- **同类工作**：Google learned_optimization (JAX)、Open-L2O（benchmark only）、VeLO
- **同会议**：[[MLSys-2026]]