---
type: paper
name: FlashAgents
full_title: "FlashAgents: Accelerating Multi-Agent LLM Systems via Streaming Prefill Overlap"
authors: [Taosong Fang, Zhen Zheng, Zhengzhao Ma, Yaojie Lu, Hongyu Lin, Xianpei Han, Le Sun]
venue: MLSys
year: 2026
tags: [multi-agent, llm-inference, streaming, prefill-overlap, sglang]
source_pdf: "[[b6d767d2f8ed5d21a44b0e5886680cb9.pdf]]"
source_md: "[[b6d767d2f8ed5d21a44b0e5886680cb9]]"
---

# FlashAgents: Accelerating Multi-Agent LLM Systems via Streaming Prefill Overlap (MLSys 2026)

> **一句话总结**：在 [[SGLang]] 上实现多智能体 token 级流式 + 增量 prefill，重叠上游 decode 与下游 prefill；真实 workflow 端到端延迟最高降 40%，两 agent 微基准最高 **3.5×**，并加 intra-turn radix prefix cache 消除并发冗余 prefill。

## 问题

多智能体系统（MAS）中 Agent A 完整生成后 Agent B 才开始 prefill，链式依赖造成大量 idle。现有 [[vLLM]]/[[SGLang]] 优化面向独立请求或 [[Continuous-Batching]]，未处理 **inter-agent** 顺序依赖。持久 [[RadixAttention]] 只在请求完成 prefill 后更新，同 turn 并发下游无法共享 instruction template 的 prefill。

## 核心方法

1. **Inter-agent streaming + incremental prefill**：上游 decode 每产出 token 即写入下游 buffer；达阈值触发 `IncPrefill`，因果 attention 增量更新 [[KV-Cache]]；重叠时间 `T_overlap = min(T_decode,A, T_prefill,B)`
2. **Intra-turn prefix cache**：prefill trigger 时建临时 radix tree，共享前缀只算一次 KV，再沿路径组装各请求 cache（区别于持久 RadixAttention）
3. **实现**：扩展 SGLang streaming API + 调度器辅助 radix tree；AutoGen 异步 client 集成

支持线性链、fan-out/fan-in；fan-in 仅对 position-stable 前缀做增量 prefill。

## 关键结果

- 微基准（240 配置，A100）：相对 Sequential **1.05×–3.52×**；7B 并发=2 峰值 **3.52×**
- 真实 workflow（Chain / MapReduce / PPTAgent）：端到端最高 **~40%** 延迟降低
- 异构部署（7B upstream → 32B downstream）收益更大（上游 decode 快、下游 prefill 重）

## 相关

- **相关概念**：[[KV-Cache]]、[[RadixAttention]]、[[Continuous-Batching]]、multi-agent systems
- **同类系统**：[[SGLang]]、[[vLLM]]、AutoGen
- **同会议**：[[MLSys-2026]]