---
type: paper
name: Stream2LLM
full_title: "STREAM2LLM: Overlap Context Streaming and Prefill for Reduced Time-To-First-Token"
authors: [Rajveer Bachkaniwala, Chengqi Luo, Richard So, Divya Mahajan, Kexin Rong]
venue: MLSys
year: 2026
tags: [llm-inference, rag, streaming, scheduling, kv-cache]
source_pdf: "[[02522a2b2726fb0a03bb19f2d8d9524d.pdf]]"
source_md: "[[02522a2b2726fb0a03bb19f2d8d9524d]]"
---

# STREAM2LLM: Overlap Context Streaming and Prefill for Reduced Time-To-First-Token (MLSys 2026)

> **一句话总结**：在 [[vLLM]] 上扩展 streaming prompt 支持，用两阶段调度 + LCP 缓存失效 + 成本感知抢占，把 RAG/ANNS 多租户场景的 TTFT 降到非 streaming 基线的 3.9–11.0×，内存压力下 FCFS/LCAS 比朴素 streaming 调度 P99 快 10×，吞吐与非 streaming 持平。

## 问题

LLM 推理越来越依赖外部 context 检索（web crawler、DiskANN 等），检索延迟可达数百 ms 到数秒。传统做法等全部 context 返回再开 prefill，[[KV-Cache]] 闲置、TTFT 被检索主导；已有 streaming 方案（PipeRAG、AquaPipe）只证明单请求可行，忽视生产多租户：

- 多请求并发抢 GPU [[KV-Cache]] block，触发 swap/recompute
- chunk 到达异步，需动态重排优先级
- **append mode**（爬虫按序追加 doc）vs **update mode**（ANNS 迭代替换 top-k）——后者会让 prompt 前缀失效
- 全量失效浪费已算 block；盲目复用则输出 stale cache

## 核心方法

STREAM2LLM 基于 [[vLLM]] v1，面向 prefill-decode [[Disaggregation]] 中的 prefill 实例：

**两阶段调度**：Phase 1 只做优先级排序与可行性分析（不分配资源）；Phase 2 按序分配 GPU block，失败时从低优先级请求中选抢占对象，用硬件 profile 的 cost model 在 recompute vs swap 间择优。

**LCP-based 缓存失效**：prompt 更新时计算新旧 token 序列 longest common prefix，仅失效 LCP 之后 block，保留前缀 [[KV-Cache]]；对 update mode 至关重要。

**调度策略**：DEFAULT vLLM / FCFS / MCPS（按已算 token 数）/ LCAS（按最近 chunk 到达时间）。LCAS 在 append 与 update 均表现好——新 chunk 到达即拉高优先级。

**工作负载**：真实 trace 覆盖 web crawler（append）与 DiskANN ANNS（update），配合 AquaPipe 式 recall-aware prefetch。

## 关键结果

- Crawler（append）：低负载 TTFT 3.9–4.3×，QPS 4.0 时 median TTFT **10.8–11.0×** 于非 streaming
- ANNS（update）：QPS 1.0 时 P95 TTFT **2.49–2.63×** 于非 streaming；>10% 请求累计失效 >10k tokens 仍值得
- 内存压力实验：DEFAULT vLLM streaming P99 比非 streaming **差 10×**；FCFS/LCAS + cost-based 抢占 P99 仍快 **8–10×**
- Trace completion time 各方法相差 **<1%**——latency 收益不牺牲吞吐
- 平台：H100/H200 + Llama-3.1-8B-Instruct，TP=2

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Disaggregation]]、[[Prefix-Caching]]
- **同类系统**：[[vLLM]]、PipeRAG、AquaPipe
- **同会议**：[[MLSys-2026]]