---
type: paper
name: Shannonic
full_title: "Shannonic: Efficient Entropy-Optimal Compression for ML Workloads"
authors: [Kareem Ibrahim, Mohammadjavad Maheronnaghsh, Andreas Moshovos]
venue: MLSys
year: 2026
tags: [compression, quantization, federated-learning, llm-inference, entropy-coding]
source_pdf: "[[98dce83da57b0395e163467c9dae521b.pdf]]"
source_md: "[[98dce83da57b0395e163467c9dae521b]]"
---

# Shannonic: Efficient Entropy-Optimal Compression for ML Workloads (MLSys 2026)

> **一句话总结**：在 ANS 上做 range partitioning，把 8-bit tensor 切成 16 个非均匀子区间，codec 仅 **530B** state 即达 Shannon 熵 **1%** 以内；联邦学习 WiFi/LTE 上 ResNet-18 训练 **1.3–3.1×** 更快，Llama2-7B 边云推理延迟降 **29–32%**。

## 问题

量化后 tensor 仍有非均匀符号统计，通用无损压缩（tANS 4–16KB tables）对 ML 部署太重。理想 codec 需：近熵极限压缩、高吞吐、数百字节 state、每 symbol 极少操作。

## 核心方法

离线 DP 把 256-symbol alphabet 分成 K=16 contiguous ranges，每值编码为 (range index via 128-state tANS, fixed-width offset)。Theorem 1 给出 partition 优于 direct tANS 的条件；范围内分布近均匀使 offset 开销极小。

运行时 encode/decode 仅 shift/mask/lookup；Raspberry Pi 5 单流 decode **286 MB/s**，i9 24 线程 **9.76 GB/s**。

## 关键结果

- 多种 8b 量化模型：coding efficiency 在 Shannon limit **1%** 内，state **530B**（比 tANS 少 8–16×）
- 联邦学习：**1.3–3.1×** 更快；Llama2-7B 协作推理 E2E 延迟 **-29% ~ -32%**

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]
- **同类系统**：FlexGen、tANS/Zstd FSE、ANS
- **同会议**：[[MLSys-2026]]