---
type: paper
name: TokenWeave
full_title: "TokenWeave: Efficient Compute-Communication Overlap for Distributed LLM Inference"
authors: [Raja Gond, Nipun Kwatra, Ramachandran Ramjee]
venue: MLSys
year: 2026
tags: [llm-inference, tensor-parallelism, allreduce, rmsnorm, compute-communication-overlap]
source_pdf: "[[e4da3b7fbbce2345d7772b0674a318d5.pdf]]"
source_md: "[[e4da3b7fbbce2345d7772b0674a318d5]]"
---

# TokenWeave: Efficient Compute-Communication Overlap for Distributed LLM Inference (MLSys 2026)

> **一句话总结**：TokenWeave 把 RMSNorm 重排到 AllReduce 内部并融合成 NVSHARP/Multimem 内核，再用 wave-aware 两路 token split 重叠计算与通信，在 1024 token 的小 batch 上仍相对 vLLM 获 1.28× 延迟收益、ShareGPT 吞吐 +19%。

## 问题

[[Tensor-Parallelism]] 推理每层两次 AllReduce，即便 NVLink 上仍占端到端延迟 9–23%；RMSNorm 另占 4–9%。现有 overlap 方案（Flux、TileLink、[[NanoFlow-OSDI25|NanoFlow]]）把 GEMM 拆 tile 或 nano-batch，但小 batch 下 wave quantization 让拆分本身比通信还贵，所以 [[vLLM]]、[[SGLang]]、TensorRT-LLM 默认都不开 TP overlap。低延迟 serving 的 chunk 常只有 1K–2K tokens，与训练侧 8K+ 的设计假设脱节。

## 核心方法

**Insight 1：RMSNorm 与 AllReduce 强耦合**。标准顺序是 AllReduce → residual → RMSNorm，四卡各算一遍冗余 RMSNorm。TokenWeave 把 AllReduce 拆成 ReduceScatter + RMSNorm + AllGather，但简单拆分因额外 HBM 读写反而更慢。

**Fused AllReduce–RMSNorm kernel**：在 token 边界切分后，各 GPU 只对本地 1/N shard 做 RMSNorm，再用 Multimem/NVSHARP 把通信与归一化压到 2–8 个 SM（对比先前方案 16–20+ SM），1.34–1.39× 快于顺序 AR+RMSNorm。

**Insight 2：wave-aware 两路 token split**。把 batch 切成 prefix/suffix 两路，用 smart-splitting 保证两路 CTA wave 总数不超过未拆分 kernel，避免 wave quantization 开销；一路 AllReduce+RMSNorm 与另一路 attention/FFN 用双 CUDA stream 重叠。小 batch 时只启用 fused kernel、不 split。

**Chunked attention**：suffix 依赖 prefix 的 KV，用 [[Chunked-Prefill]] 保证 prefix 先算。

已集成 vLLM-V1；代码 https://github.com/microsoft/tokenweave

## 关键结果

- Llama-3.3-70B @ 8×H100：端到端延迟最高 **1.28×**（baseline÷ours），**1K tokens 仍 1.2×**；≥4K 时甚至快于「无通信」反事实 baseline。
- Fused AllReduce–RMSNorm：64–32K token 稳定 **1.34–1.39×**。
- ShareGPT / arXiv trace：吞吐 **1.19× / 1.15×**。
- 对比 TileLink：2K tokens 反而变慢，8K+ 才到 1.2×；TokenWeave 在短序列更稳。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、AllReduce、RMSNorm
- **同类系统**：[[vLLM]]、[[SGLang]]、[[NanoFlow-OSDI25|NanoFlow]]、Flux、TileLink
- **同会议**：[[MLSys-2026]]