---
type: paper
name: METIS
full_title: "METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation"
authors: [Siddhant Ray, Rui Pan, Zhuohan Gu, Kuntai Du, Shaoting Feng, et al.]
venue: SOSP
year: 2025
tags: [rag, llm-inference, scheduling, configuration-adaptation]
source_pdf: "[[3731569.3764855.pdf]]"
source_md: "[[3731569.3764855]]"
---

# METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation (SOSP 2025)

> **一句话总结**:首个按 query 自适应调整 [[RAG]] 配置(chunks 数、synthesis 方法、summary 长度)并与 LLM 调度联合优化的系统,相同质量下延迟降低 1.64-2.54×,吞吐提升 1.8-4.5×。

## 问题

[[RAG]] 同时影响响应质量与延迟,但已有系统要么静态选一套配置(AdaptiveRAG 等靠手调)、只优化质量忽略延迟,要么只做 query 调度(vLLM、Parrot)不动配置。实际上配置该按 query 选:简单 query 只需 1 chunk + map_rerank,复杂 reasoning 需多 chunk + map_reduce。跨多个 knob 的组合空间巨大,和调度也耦合——一个吃 GPU 内存的配置看似 LLM call 少但实际排队更久。

## 核心方法

两步拆解:

- **Step 1 - Profile + prune**:用一个小 LLM 做 query profiling,估计需要多少条独立信息、是否需 joint reasoning。输入只是 query + RAG DB metadata,比 RAG 执行快约 10×。用 profile 过滤掉明显不合理的配置(如 NVIDIA 多季度对比至少 3 chunks),把配置空间压缩到"有希望的"小子集。
- **Step 2 - Joint configuration + scheduling**:在裁剪后的配置子集内,scheduler 按当前 GPU 资源挑出既能满足质量、又能尽快调度进 batch 的配置。避免"理论 LLM call 少但排队长"的陷阱。
- 三大 knob:`num_chunks`(chunk 数)、`synthesis_method`(map_rerank / stuff / map_reduce)、`intermediate_length`(map_reduce 的 summary 长度)。

## 关键结果

- 四个 RAG QA 数据集(含 Musique、KG RAG FinSec 等):相同或更高质量下,生成延迟 1.64-2.54× 低于 [[vLLM]]、Parrot、AdaptiveRAG。
- 相同延迟+相同质量下吞吐高 1.8-4.5×。
- 实证:per-query 选配置比全局固定配置质量高 12-15%,延迟低 2.5-3×。

## 相关

- **相关概念**:[[RAG]]、[[LLM-Inference]]、[[KV-Cache]]、query scheduling
- **同类系统**:[[vLLM]]、Parrot、AdaptiveRAG
- **同会议**:[[SOSP-2025]]
