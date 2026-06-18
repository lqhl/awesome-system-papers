---
type: paper
name: AIRS
full_title: "AIRS: Scaling Live Inference in Resource Constrained Environments"
authors: [Nilesh Jagnik, Xiaohao Yang, Chelsea Chen, Tuan Do, GM Harshvardhan]
venue: MLSys
year: 2026
tags: [llm-serving, tpu, search-quality, batching, caching]
source_pdf: "[[7f6ffaa6bb0b408017b62254211691b5.pdf]]"
source_md: "[[7f6ffaa6bb0b408017b62254211691b5]]"
---

# AIRS: Scaling Live Inference in Resource Constrained Environments (MLSys 2026)

> **一句话总结**：Google Search Quality 的 AI Rater Service 用 rating fulfillment 队列 + 共享 TPU 池 + quota 优先级 + 客户端缓存，在 TPU 预算远小于需求时仍日处理 1 亿+ Page Quality 等 autorater 请求，AR1 模型 TPU duty cycle 峰值近 1、缓存命中率约 40%。

## 问题

搜索质量评估需对海量 query-result 对打 PQ、Needs Met 等分；人工贵且慢，LLM autorater 可即时打分但需求爆发（新 AI 产品、新 metric），而大部分 TPU 留给 live traffic。离线 MapReduce 不可靠、与评估 pipeline 脱节。

## 核心方法

**双组件架构**：
- **Rating Fulfillment**：接收 workflow 任务 → 指纹查 archive → 入队 → Rating Generator 调 autorater API → State 表跟踪 PENDING/COMPLETED；workflow 全完成后通知下游算 metric
- **Model Management**：长驻 TPU model server、动态 replica 伸缩、共享 TPU pool 再分配

**吞吐优化**：客户端 90 天 freshness 缓存（~40% hit，等效砍掉 40% TPU 负载）；默认 batch=12；integrated 模式下 quota check 先于 RPC，失败短 backoff 重试；traffic shaping 把尖峰 QPS 压成 sustained load。

**Quota Management**：按 evaluation 优先级、用户、RID 限流；高优 workflow fast-track；模型侧也按 priority reject 低优请求。

## 关键结果

- 顶层 PQ autorater：日约 1 亿+ rating 请求；数百实验 × 数十万 query
- AR1 8 天观测：mean TPU duty cycle 峰值近 1.0；缓存命中率 ~40%；post-cache QPS 约为峰值 20–40%，实际打到 model 仅 1–4%（quota 限流）
- 可靠性：中位失败率 0.8%，80th percentile 成功率 97.8%
- P75 metric latency 稳定（Fig. 10）

## 相关

- **相关概念**：[[Continuous-Batching]]（batching 提 TPU 利用）
- **同类系统**：离线 MapReduce rating、通用 model hosting
- **同会议**：[[MLSys-2026]]
- **对比**：资源受限 live inference vs 专用 TPU 池