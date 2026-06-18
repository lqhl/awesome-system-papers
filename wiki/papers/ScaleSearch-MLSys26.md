---
type: paper
name: ScaleSearch
full_title: "Search Your Block Floating Point Scales!"
authors: [Tanmaey Gupta, Hayden Prairie, Shirley Wu, Reyna Abhyankar, Qingyang Wu, Austin Silveria, Pragaash Ponnusamy, Jue Wang, Ben Athiwaratkun, Leon Song, Tri Dao, Daniel Y. Fu, Chris De Sa]
venue: MLSys
year: 2026
tags: [quantization, nvfp4, attention, kv-cache, block-floating-point]
source_pdf: "[[3ef815416f775098fe977004015c6193.pdf]]"
source_md: "[[3ef815416f775098fe977004015c6193]]"
---

# Search Your Block Floating Point Scales! (MLSys 2026)

> **一句话总结**：ScaleSearch 利用 NVFP4 block scale 的 E4M3 mantissa 在可表示邻域搜索最优 scale，量化误差降 **27%**、MATH500 PTQ +15 分；ScaleSearchAttention 让 Llama 3.1 70B Wikitext-2 PPL 改善 **0.77** 且近零精度损失。

## 问题

Blackwell NVFP4/MXFP4 等 microscaling BFP 默认用 block max 定 scale，对实际分布未必最优。[[KV-Cache]] 与 attention 的 FP4 路径仍欠探索；标准 max-scaling 在 outlier 与 attention 动态下误差大。实现可接入 [[vLLM]] nvfp4 rounding 路径。

## 核心方法

**ScaleSearch**：在每个 16 元 micro-block 上搜索 E4M3 scale 邻域，最小化 MSE；可嵌入 PTQ 与低精度 attention。

**ScaleSearchAttention**：Q/K/V 与 partial attention 矩阵均 NVFP4 化，QKᵀ 与 PV 直接在 Tensor Core 上无 dequant matmul；结合 incoherence processing、矩阵分解降 outlier，attention-sink 混合精度 cache（首/近 token 全精度）。

## 关键结果

- NVFP4 合成高斯数据量化误差 **-27%**；Qwen3-8B MATH500 PTQ **+15** 分
- Mochi VQA-t FP4 attention 较 SageAttention3 **+14** 分
- Llama 3.1 70B PPL **3.4→2.63**；8B Instruct GPQA Diamond **+5** 分
- 量化开销 **1.74×**（FP32→NVFP4），attention 吞吐达 SageAttention3 **98.3%**

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[Flash-Attention]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、SageAttention3、QuIP#
- **同会议**：[[MLSys-2026]]