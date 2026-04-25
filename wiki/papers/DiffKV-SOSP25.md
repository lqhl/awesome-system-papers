---
type: paper
name: DiffKV
full_title: "DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction"
authors: [Yanqi Zhang, Yuwei Hu, Runyuan Zhao, John C.S. Lui, Haibo Chen]
venue: SOSP
year: 2025
tags: [llm-inference, kv-cache, quantization, memory-management, gpu]
source_pdf: "[[3731569.3764810.pdf]]"
source_md: "[[3731569.3764810]]"
---

# DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction (SOSP 2025)

> **一句话总结**：DiffKV 把 [[KV-Cache]] 压缩细分到「键 vs 值」「token 重要性」「每 head 动态稀疏」三个维度，并配一个 GPU 原生并行 compaction 内存管理器，2.7-5.7× 压缩近乎无损、吞吐 1.9-5.4×。

## 问题

LLM 服务中 KV cache 占超 90% 显存，是 long context 与思考型模型的主瓶颈。现有压缩（pruning 与 [[Quantization|quantization]]）都一刀切：(1) pruning 在所有 attention head 上分配等同显存预算，无视 per-head 动态稀疏；(2) quantization 对 K 与 V 用相同 bit 宽度，忽视它们在 attention 中不同的作用；(3) 两者都对所有 request 同等对待，忽视请求级信息密度差异。从 Equation 中可以看出 K 向量影响所有 token 的 softmax 分母（attention score），V 只影响自己那一项，Llama3-8B 实测 attention score 跨 7 个数量级而 V 范数只跨 2 个，证明 K 比 V 更重要。

## 核心方法

三级差异化（Differentiation）+ 一个可扩展的 on-GPU 内存管理：

**压缩策略**：(1) K 比 V 用更高精度（K8V4 和 K4V2 优于 K4V8/K2V4）；(2) 按 attention score 把 token 分三档：最重要 → K8V4；中等 → K4V2；最不重要 → 直接 prune；(3) per-head per-request 动态分配，阈值 α_h, α_l 离线校准得到，长序列更激进压缩、短序列保留更多高精度。

**on-GPU 内存管理**：为处理上千 head × 数百请求的异构 page（每 step 万级），用三条 GPU 原生数据结构：**Unified Pages**（固定大小、动态配置精度）；**Circular Free Page List**（所有 page ID 在 GPU 驻留的循环列表，free 和 used 连续，用并行 prefix sum 分配回收）；**Bidirectional Page Table**（高精度 page ID 从左增长、低精度从右增长，一张表搞定两级精度）。整个 compaction 全在 GPU 并行完成，把压缩收益真正转成吞吐收益。基于 [[vLLM]] 实现。

## 关键结果

- 2.7-5.7× KV cache 压缩，近乎无损（包括 QwQ-32B、R1-Distill-Qwen-14B、R1-Distill-Llama-8B 等思考模型）
- 1.9-5.4× 吞吐提升
- 首个在 thinking model 与复杂 CoT 推理任务上评测的 KV compression 框架，FP16 级别生成质量

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Quantization]]、[[Attention]]、[[GQA]]
- **同类系统**：[[vLLM]]、H2O、SnapKV、PyramidKV、Atom、QServe
- **同会议**：[[SOSP-2025]]
