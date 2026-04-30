---
type: paper
name: CacheBlend
full_title: "CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion"
authors: [Jiayi Yao, Hanchen Li, Yuhan Liu, Siddhant Ray, Yihua Cheng, Qizheng Zhang, Kuntai Du, Shan Lu, Junchen Jiang]
venue: EuroSys
year: 2025
tags: [kv-cache, rag, prefix-caching, selective-recompute, llm-serving]
source_pdf: "[[eurosys25-yao-cacheblend.pdf]]"
source_md: "[[eurosys25-yao-cacheblend]]"
---

# CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion (EuroSys 2025)

> **一句话总结**：RAG 场景中多个 text chunk 只有第一个是 prefix（能被 prefix caching 复用），其余 chunk 的 KV cache 无法直接复用——因为缺少与前文 chunk 的 cross-attention。CacheBlend 对非 prefix 的 chunk 做 selective KV recompute（只更新 <15% token 的 KV），把更新与下一层 KV cache fetch 做 pipeline，TTFT 降 2.2-3.3×、吞吐 2.8-5×，质量不降。

## 问题

RAG 场景中 LLM 输入通常包含多个 text chunk。已有的 KV cache 复用方案有两个极端：

- **Prefix caching**（[[vLLM]]/[[SGLang]]）：只复用第一个 chunk（prefix），因为只有 prefix 的 KV cache 不依赖后续内容。但 RAG 中后面几个 chunk 也需要复用
- **Full KV reuse**：强行复用非 prefix chunk 的 KV cache（调整 position embedding），但完全忽略 cross-attention（chunk 之间的 token 注意力），质量显著下降

## 核心方法

**Selective KV recompute**：非 prefix chunk 的大部分 token KV 可以直接复用（这些 token 的 self-attention 在 pre-computed KV cache 中已有），只需要 recompute 与前面 chunk 有 cross-attention 的那小部分 token 的 KV。

- **更新比例 <15%** 通常就能达到 full recompute 的质量——因为 attention matrix 天然稀疏，大部分 token 对前文的 cross-attention 很弱
- **Pipeline hide latency**：在 GPU recompute 某层部分 KV 的同时，并行 fetch 下一层的 pre-computed KV cache 进 GPU memory。这样即使 KV cache 存在慢设备（如 SSD），fetch 延迟也被藏在 compute 里

基于 [[vLLM]] 实现，支持 Llama 7B-70B，在 Musique / 2WikiMQA / HotpotQA 等 RAG/QA benchmark 上评估。

## 关键结果

- vs prefix caching：TTFT **降 2.2-3.3×**，吞吐 **提升 2.8-5×**
- vs full KV reuse：质量提升（QA F1 +0.1-0.2，Rouge-L +0.03-0.25），TTFT 几乎相同
- selective recompute 的额外 compute 开销不增加延迟（被 KV fetch pipeline 隐藏）
- 可与慢速存储设备（disk）搭配使用而不牺牲延迟

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[RAG]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、[[SGLang]]、RAGCache、CacheGen
- **后续工作**：[[LMCache-arXiv25|LMCache]]（CacheBlend 团队的全栈 KV cache 层）、CacheClip
- **作者线**：Jiayi Yao、Yuhan Liu、Kuntai Du ([[vLLM]])、Junchen Jiang ([[LMCache-arXiv25|LMCache]]) 均来自 UChicago
- **同会议**：EuroSys 2025
