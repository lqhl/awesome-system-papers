---
type: paper
name: AgenticCache
full_title: "AgenticCache: Cache-Driven Asynchronous Planning for Embodied AI Agents"
authors: [Hojoon Kim, Yuheng Wu, Thierry Tambe]
venue: MLSys
year: 2026
tags: [embodied-ai, llm-inference, caching, multi-agent, planning]
source_pdf: "[[98f13708210194c475687be6106a3b84.pdf]]"
source_md: "[[98f13708210194c475687be6106a3b84]]"
---

# AgenticCache: Cache-Driven Asynchronous Planning for Embodied AI Agents (MLSys 2026)

> **一句话总结**：利用 embodied task 的 plan locality，用 2-gram plan transition cache + 后台 LLM updater 异步校验，避免逐步 LLM 调用；4 benchmark × 3 model 平均 success rate **+22%**、latency **-65%**、token **-50%**。

## 问题

Embodied agent 每步都调 LLM plan，>70% 仿真时间在 LLM 查询。parallel/speculative planning 仍每步需 LLM。plan 有强 locality（如 grasp→transport 占 59.7%），但纯 pattern 跟随会因环境变化失效。

## 核心方法

**Runtime cache**：2-gram ⟨Pi→Pj⟩ + task-state metadata range，score = Count × Importance（类似 hybrid branch predictor）。

**Cache Updater**：后台异步 LLM 校验/纠正；confirmation 则等当前 plan 结束再查，correction 则立即换 plan。

与 [[KV-Cache]]/context cache 正交——缓存的是高层 plan transition 而非 token activation。

## 关键结果

- 4 个 long-horizon multi-agent benchmark、3 种 model scale：success **+22%** avg，latency **-65%**，token **-50%**
- GPT-5 on TDW-COOK：latency 最高 **-86%**，cost **-79%**，success 仍 **97%** avg

## 相关

- **相关概念**：[[KV-Cache]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、[[SGLang]]、parallelized planning-acting、speculative planning
- **同会议**：[[MLSys-2026]]