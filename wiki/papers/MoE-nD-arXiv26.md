---
type: paper
name: MoE-nD
full_title: "MoE-nD: Per-Layer Mixture-of-Experts Routing for Multi-Axis KV Cache Compression"
authors: [Libo Sun, Peixiong He, Po-Wei Harn, Xiao Qin]
venue: arXiv
year: 2026
tags: [llm-inference, kv-cache, compression, quantization, long-context]
source_pdf: "[[arxiv26-moe-nd.pdf]]"
source_md: "[[arxiv26-moe-nd]]"
---

# MoE-nD: Per-Layer Mixture-of-Experts Routing for Multi-Axis KV Cache Compression (arXiv 2026)

> **一句话总结**：MoE-nD 把 [[KV-Cache]] compression 的 eviction ratio、K bits、V bits 当作可路由 expert，为每层选择不同压缩组合；在 DeepSeek-R1-Distill-Qwen-7B 的 LongBench 4-task 子集上，hetero variant 用 136 MB cache 达到 14x compression 且匹配 1.9 GB full-cache baseline。

## 问题

现有 KV cache 压缩通常只沿单一轴操作：token eviction、precision quantization、head-dimension low-rank projection 或 cross-layer sharing。即便组合 eviction + quantization，也常把同一配置均匀应用到所有层。

论文的核心观察是：不同 transformer layer 对 eviction、K quantization、V quantization 的敏感度差异很大，且「该压缩 eviction 还是 quantization」并没有全局一致答案。统一策略会在敏感层压太狠、在不敏感层浪费预算。

## 核心方法

MoE-nD 把每层的 compression choice 写成三轴 tuple：`(keep ratio, K bits, V bits)`。离线阶段对每个 layer 和候选配置测量 attention output relative L2 error，构成 sensitivity table；作者还用 8 条 2048-token held-out sequences 的 KL calibration 验证这个轻量 proxy，平均 Pearson 0.945、Spearman 0.937。

给定全局 memory budget 后，solver 从每层 cheapest config 出发，反复选择单位额外 memory 能带来最大 sensitivity reduction 的 layer upgrade，直到预算用完。推理时，一个 heterogeneous attention patch 同时应用每层不同的 eviction 和 quantization，并为每层维护 retained token 的 original positions，以保证 RoPE re-inversion 正确。

论文标题中的 MoE 是一种 routing analogy：不是 [[MoE]] 模型 expert parallelism，而是把多种 cache compression 操作当作 expert，由 router 为每层选择组合。

## 关键结果

- LongBench-v1 4-task 子集上，2dhetero 在 136 MB cache 达到 12.0 average，和 uncompressed 1.9 GB full cache 的 11.5 无可检测损失；同等内存附近的 2d baseline 只有 5.9。
- 14x compression 下匹配 full-cache baseline；四个 hetero operating points 的 compression ratio 为 14x、6.6x、3.2x、1.6x。
- AIME-24/AIME-25 上，2dhetero 在 8/8 个 budget x dataset 配置中都超过 non-hetero 2d baseline，紧预算时优势达到 +6 到 +27 pts。
- Ablation 显示主要收益来自 per-layer eviction routing：AIME 上平均 +15.0 pts，LongBench 上平均 +5.7 pts；per-layer quant routing 平均约 0 或略负。
- 负结果同样明确：MATH-500 和 LongBench TREC 这类短输入/宽松预算场景，solver 多数层选择 keep=1.0，heterogeneous routing 没有发挥空间。

## 相关

- **相关概念**：[[KV-Cache]]、[[Quantization]]、[[MoE]]
- **同类方法**：AdaKV、PyramidKV、KVTuner、KIVI、KVQuant、MiniKV
- **边界条件**：长 context 或长 generation 且预算紧时最有价值；短 prompt 场景可退化为简单 uniform 方案

