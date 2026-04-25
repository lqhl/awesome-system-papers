---
type: paper
name: Aegaeon
full_title: "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market"
authors: [Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, gpu-pooling, multi-model-serving, auto-scaling, serverless]
source_pdf: "[[3731569.3764815.pdf]]"
source_md: "[[3731569.3764815]]"
---

# Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market (SOSP 2025)

> **一句话总结**：将模型 auto-scaling 从 request 粒度下推到 token 粒度，让单张 GPU 同时服务最多 7 个模型；在 Alibaba Cloud Model Studio 实测把服务数十个模型所需 GPU 从 1192 降到 213（82% 节省），比 ServerlessLLM/MuxServe 吞吐高 2–2.5×。

## 问题

Hugging Face 等 model market 上百万模型呈重尾分布：94.1% 的"冷"模型只占 1.35% 请求，17.7% 的 GPU 用来服务这 1.35%。现有方案都没能把 GPU 塞满多个模型：

- **Multiplexing**（空间/时间复用）受 GPU 显存限制，80GB A100 最多容纳 2–3 个 14B 模型
- **Auto-scaling**（如 ServerlessLLM、BlitzScale、ParaServe）按 request 粒度切换模型，LLM 请求服务时间长（平均 16.79s），Poisson arrival rate 0.037 时期望活跃模型数 E[m] = 46.55/100，request 粒度下必然 HOL blocking，实际效果上限仍 <3 模型/GPU

## 核心方法

Aegaeon 做 **token 级 auto-scaling**：在每生成一个 token 之间都可以抢占式把当前模型 scale down、把新请求对应的模型 scale up。配合 prefill/decoding [[Disaggregation]] 分别调度：prefill 用 grouped FCFS 最小化 TTFT，decoding 用 weighted round-robin 最小化 TBT SLO 违约。

为让 token 级切换在实际中可行，论文对 auto-scaling 全路径做了激进优化：
- **组件复用**：识别 inference engine 初始化的可复用部分，避免每次从头 re-init
- **显式内存管理**：GPU/host memory 自管，cache + prefetch 加速模型权重加载，消除 fragmentation 和 GC 开销
- **细粒度 KV cache 同步**：[[KV-Cache]] swap-in/out 与计算重叠、解耦，而不是粗粒度等待

三者合计把 auto-scaling 开销降低 97%，使 token 粒度切换从"几十秒"变成"实时可用"。

## 关键结果

- 比 ServerlessLLM、MuxServe 吞吐高 2–2.5×，goodput 高 1.5–9×
- 单 GPU 同时服务最多 **7 个模型**（比 multiplexing 的 2–3 个翻倍以上）
- auto-scaling 开销 **降低 97%**
- 在 Alibaba Cloud Model Studio beta 部署 3 个月，服务 1.8B–72B 共数十个模型，**GPU 从 1192 降到 213（82% 节省）**

## 相关

- **相关概念**：[[KV-Cache]]、[[Disaggregation]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[SOSP-2025]]
