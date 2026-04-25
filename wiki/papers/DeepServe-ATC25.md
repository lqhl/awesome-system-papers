---
type: paper
name: DeepServe
full_title: "DeepServe: Serverless Large Language Model Serving at Scale"
authors: [Junhao Hu, Jiang Xu, Zhixia Liu, Yulong He, Yuetao Chen, et al.]
venue: ATC
year: 2025
tags: [llm-serving, serverless, npc-cluster, pd-disaggregation, fast-scaling]
source_pdf: "[[atc2025-hu-junhao.pdf]]"
source_md: "[[atc2025-hu-junhao]]"
---

# DeepServe: Serverless Large Language Model Serving at Scale (ATC 2025)

> **一句话总结**：华为云在 Ascend NPU 大集群上落地的 serverless LLM 平台，提出 request-job-task 抽象 + 自研 FlowServe 引擎 + PD-aware 调度 + NPU-fork 快速扩缩，可在数秒内并行扩到 64 实例。

## 问题

云上 MaaS 平台同时承载长任务（fine-tuning，几小时到几天）和短任务（chat、agent，秒到分钟），还需保证 SLO。三大挑战：1) 工作负载粒度差异大，资源共享调度难；2) [[KV-Cache]] 复用、[[Disaggregation|PD-disaggregation]] 让 serving 变成有状态分布式；3) 流量波动剧烈，冷启动延迟高。已有开源系统（KServe、AIBrix、Dynamo 等）大多面向 GPU 集群，没有 NPU 集群和 post-training + serving 混部的统一抽象。

## 核心方法

四大组件：

- **Serverless 抽象**：request-job-task 三层模型。Job Executor (JE) 把请求拆成 task 派发给 Task Executor (TE)，Cluster Manager 统一管控扩缩与健康。
- **FlowServe 引擎**：微内核架构 + NPU-centric 执行 + SPMD 设计。Master 负责调度/缓存/网络决策，每个 NPU 上的 executor 执行模型 forward。包含 Relational Tensor Cache (RTC) 统一管理 prefix caching（含 [[Chunked-Prefill]]）和 position-independent caching；DistFlow 跨 TE peer-to-peer 传 tensor，scaled-out 走 HCCL P2P，scaled-up CloudMatrix384 SuperPod 直接走共享内存拷贝。支持 PD-disaggregated 与 PD-colocated 两种部署。
- **分布式调度**：locality-aware（prompt-tree 选 KV cache 命中最长的 TE）+ PD-aware（基于 prefill/decode 长度热图选择 disagg 还是 coloc，decode 长度由 84.9% 准确率的预测模型给出）+ load-aware 三者组合。
- **快速扩缩**：pre-warmed Pods/TEs（与 model/parallelism 无关）、DRAM 预加载 safetensors、NPU-fork（用 HCCS 高速链路从已运行 TE 复制权重）。

深度细节回 [[atc2025-hu-junhao]]。

## 关键结果

- 已在生产运行 1 年以上，落地 Huawei Cloud Ascend 大集群
- FlowServe v1→v2 异步调度 + IPC 优化使 TPOT 50ms SLO 下吞吐提升 2×；v2→v3 数据结构与 sampling 优化再提升约 20%
- TE pre-warming 把 TE-Pre-Load 时间减少约 35%，并将其移出关键路径
- NPU-fork 通过 HCCS 链路扩到 32 个 TE 仍保持高带宽，可秒级并行扩到 64 实例
- PD-aware 调度在中等 RPS（10 reqs/s）下 JCT 优于 round-robin

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Disaggregation]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、[[Pipeline-Parallelism]]、[[MoE]]
- **同类系统**：[[vLLM]]、[[SGLang]]、MemServe、Mooncake、ServerlessLLM
- **同会议**：[[ATC-2025]]
