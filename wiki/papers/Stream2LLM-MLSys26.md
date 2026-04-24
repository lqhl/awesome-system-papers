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

> **一句话总结**：在 [[vLLM]] 之上扩展 streaming prompt 支持，用两阶段调度 + LCP（最长公共前缀）缓存失效 + 成本感知抢占，把 RAG/ANNS 场景的 TTFT 降到基线的 1/11（最多 11× 改善），保持吞吐与非 streaming 基线持平。

## 问题

LLM 推理越来越依赖外部 context 检索（web crawler、DiskANN 等），检索延迟几百 ms 到数秒。传统做法等全部 context 返回再开 prefill，TTFT 被拖长；已有 streaming 方案（PipeRAG、AquaPipe）只证明单请求场景可行，忽视了生产环境多租户的现实：

- 多请求并发抢 GPU KV 内存，触发 swap/recompute
- chunk 到达异步，哪些请求该优先推进？
- 两种模式：**append**（爬虫按序追加 doc）vs **update**（ANNS 迭代替换 top-k 候选）——后者会让 [[KV-Cache]] 前缀失效
- 简单全量失效浪费已计算 block；保留不验证会用 stale cache 输出错答

## 核心方法

STREAM2LLM 建在 [[vLLM]] v1 上，瞄准 prefill-decode [[Disaggregation]] 中的 prefill 实例：

**两阶段调度（核心解耦）**：
- Phase 1：优先级排序 + 可行性分析，只计算哪些请求"理论上能跑"，不分配资源
- Phase 2：按优先级分配 GPU block，分配失败时按 cost model 选 recompute 还是 swap
- 好处：调度策略和抢占机制解耦，不同策略可定义不同抢占行为

**LCP-based 缓存失效**：prompt 从 `[d1, d2, q]` 变成 `[d1, d2', q]` 时，计算新老 token 序列的 longest common prefix，仅失效 LCP 之后的 KV block，LCP 之内的复用。对 update mode 至关重要。

**成本感知抢占**：离线 profile 每块 GPU（A40/H100/H200）的 `recomputation_latency(T)` 和 `swap_latency(C)` 分段线性模型，运行时按预测延迟选较快的策略。

**调度算法**：实现 DEFAULT vLLM / FCFS / MCPS（按已算 token 数）/ LCAS（按最近 chunk 到达时间）。LCAS 在 append 和 update 两种模式都表现好——新 chunk 到达就把请求拉到最高优先级。

## 关键结果

- TTFT 最多 11× 改善（3.9–11.0×），相对非 streaming 基线
- 高内存压力下调度策略差异放大，朴素调度尾延迟最差比 LCAS 差 10×
- 吞吐与非 streaming 基线持平
- 评估用真实 trace：web crawler（append）+ ANNS DiskANN（update），Llama-3.1-8B，H100/H200
- 关键洞见：**streaming 是必要但不充分的——没有聪明调度 streaming 在生产无法部署**

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Disaggregation]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、PipeRAG、AquaPipe
- **同会议**：[[MLSys-2026]]
