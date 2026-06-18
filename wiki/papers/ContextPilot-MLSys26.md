---
type: paper
name: ContextPilot
full_title: "ContextPilot: Fast Long-Context Inference via Context Reuse"
authors: [Yinsicheng Jiang, Yeqi Huang, Liang Cheng, Cheng Deng, Xuan Sun, Luo Mai]
venue: MLSys
year: 2026
tags: [long-context, kv-cache, rag, prefix-caching, prefill]
source_pdf: "[[38b3eff8baf56627478ec76a704e9b52.pdf]]"
source_md: "[[38b3eff8baf56627478ec76a704e9b52]]"
---

# ContextPilot: Fast Long-Context Inference via Context Reuse (MLSys 2026)

> **一句话总结**：ContextPilot 用 context index + alignment + de-duplication 在跨 session/多轮场景复用 context block 的 [[KV-Cache]]，较 CacheBlend/LMCache/RadixCache 等 prefill 加速 **1.5–3×** 且几乎不损准确率，长上下文下甚至提升推理质量。

## 问题

长上下文 RAG/agent 的 prefill 成为瓶颈。精确 prefix matching（[[RadixAttention]]/LMCache/RAGCache）在文档顺序变化时 hit ratio 极低（MultihopRAG 仅 **4.6%**）；近似 KV 匹配（CacheBlend）虽提速但准确率降 **9–11%**。真实 workload 在 session 间与多轮内存在大量重叠 context block，却未被系统利用。

## 核心方法

**Context index**：层次聚类建树，用 overlap+位置敏感的 distance 跟踪 prefix-cache 状态，支持跨 session 搜索与多轮遍历。

**Context alignment**：将 incoming context block 与已有 prefix 对齐以最大化 cache hit；辅以简洁 order annotation 恢复原始相关性排序。

**Context de-duplication**：多轮/跨 block 内容重叠时用位置注解指向已缓存片段，避免重复 prefill。

**调度**：按 search path 分组、组内按 path 长度降序执行，减少 eviction 导致的 reuse 失效。模块化接口兼容 FAISS/ElasticSearch、Mem0、[[SGLang]]/[[vLLM]]。

## 关键结果

- MultihopRAG、NarrativeQA、QASPER、MT-RAG 上 prefill 加速 **1.5–3×**，准确率损失可忽略；alignment 后 KV hit 可达 **38.9%**（baseline 4.6%）
- DeepSeek-R1 671B 上 16–32 GPU prefill 吞吐提升 **1.52–1.81×**
- OpenClaw agent 单卡 RTX 5090 prefill 延迟降 **63.6%**；Apple Silicon **2.4×**

## 相关

- **相关概念**：[[KV-Cache]]、[[RadixAttention]]、[[Chunked-Prefill]]、[[Prefix-Caching]]
- **同类系统**：[[vLLM]]、[[SGLang]]、LMCache、RAGCache、CacheBlend
- **同会议**：[[MLSys-2026]]