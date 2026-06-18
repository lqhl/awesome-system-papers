---
type: paper
name: FlexiCache
full_title: "FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management"
authors: [Nazmul Takbir, Hamidreza Alikhani, Nikil Dutt, Sangeetha Abdu Jyothi]
venue: MLSys
year: 2026
tags: [kv-cache, llm-serving, sparse-attention, vllm, long-context]
source_pdf: "[[76dc611d6ebaafc66cc0879c71b5db5c.pdf]]"
source_md: "[[76dc611d6ebaafc66cc0879c71b5db5c]]"
---

# FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management (MLSys 2026)

> **一句话总结**：按 KV head 的 top-K 页时序稳定性分层：stable head 只留 GPU top-K、其余 offload host 并每 16 步 rerank；在 [[vLLM]] 上 GPU 内存降最多 70%、离线吞吐 1.38–1.55×、在线 TPOT 降 1.6–2.1×，精度保留 ~99%。

## 问题

长 context+长 generation 下 [[KV-Cache]] 撑爆 GPU；Quest 每步 rerank 算力贵且全量驻留 GPU；LServe 永久丢弃部分 head KV 伤长生成精度。

## 核心方法

**Head 分类**：RCO（random-corrected overlap）量化稳定性；最不稳定 25% head 全留 GPU，stable head GPU 只留 top-K。

**Sparse decode**：Quest 式 min-max page score；stable head 每 16 步 rerank，只拉新 promoted 页。

**实现**：扩展 [[vLLM]] block table 为 per-head-layer；dirty tracking、physical block reuse、UVA CUDA 直传减 PCIe 碎片。

## 关键结果

- 精度：LongBench/L-Eval **~99%** dense baseline
- GPU KV  footprint：最多 **-70%**
- 离线 token throughput：**1.38–1.55×**（Llama-3.1-8B / Mistral-7B）
- 在线 mean TPOT：0.4 req/s 时 **2.1×**（34.6 vs 71.5 ms）
- Decode kernel：batch 40 最高 **4×** speedup

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Sparse-Attention]]
- **同类系统**：[[vLLM]]、Quest、LServe
- **同会议**：[[MLSys-2026]]