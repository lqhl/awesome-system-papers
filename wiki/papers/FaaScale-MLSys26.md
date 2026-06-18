---
type: paper
name: FaaScale
full_title: "FaaScale: Unlocking Fast LLM Scaling for Serverless Inference"
authors: [Minchen Yu, Rui Yang, Chaobo Jia, Zhaoyuan Su, Sheng Yao, "et al."]
venue: MLSys
year: 2026
tags: [serverless, llm-inference, model-scaling, rdma, cold-start]
source_pdf: "[[1ff1de774005f8da13f42943881c655f.pdf]]"
source_md: "[[1ff1de774005f8da13f42943881c655f]]"
---

# FaaScale: Unlocking Fast LLM Scaling for Serverless Inference (MLSys 2026)

> **一句话总结**：PipeCast 把 binomial multicast 与动态 pipeline-parallel 推理重叠——模型 block 还在传就开始 serving，BurstGPT  trace 上 P90 TTFT 比 SOTA 低 2.4–5×，GPU 成本降 17.8%–31.3%。

## 问题

Serverless LLM inference 面临三重矛盾：请求 **突发**（数十秒内涨 10×+）、单模型 **显存巨大**（Llama-70B ~140GB，冷启动分钟级）、**模型爆炸**（Hugging Face 50 万+ 微调变体）。远程拉模型慢、GPU over-provisioning 违背 pay-per-use、host memory cache 命中率低（生产 trace 上 36%–64% 仍走 SSD，Llama-70B SSD→GPU >30s）。需要在不额外常驻 GPU 的前提下做到 **sub-second scale-out**。

## 核心方法

**FaaScale** 的核心原则是 **pipelined multicast inference**：模型分发与 [[Pipeline-Parallelism|pipeline-parallel]] 推理执行协同，部分权重到达即可开工。

**PipeCast** 三件事：
1. **Inference-aware multicast**：模型切成细粒度 block，用 binomial pipeline + **k-way transmission**（子组间 circular shift 传 block 顺序）最大化链路并行；离线 profiling 选 block size 平衡点传带宽与 PP 中间结果开销。
2. **Pipelined inference execution**：multicast 路上动态拼 **execution pipeline**（跨节点 PP）；互补 block 到齐就启动 pipeline，不必等全员收完整模型；收全后切 local mode 去掉跨节点通信。
3. **Mode switching + locality-driven startup**：GPU hot / host warm / remote cold 多级启动；tensor packing + GPU 预分配降低运行时开销；用 GPUDirect [[RDMA]] 做 block 传输。

系统 ~10K Python + 1K C++，cluster manager + worker model manager；推理基于 Meta Llama 框架扩展，传输基于 Derecho/RDMC。

## 关键结果

- 模型 multicast：比 FaaSNet / NCCL 端到端延迟最高快 **1.82× / 1.53×**（大模型、多节点收益更大）。
- 高压负载：50 请求全部开始 serving 只需 **1.1s**（vs FaaSNet 2×、NCCL 1.4×、ServerlessLLM 8× 慢）；k=4 时 ramp-up 可从 ~0.6s 降到 ~0.15s（Llama-2 7B）。
- BurstGPT 30 分钟 trace：P90 TTFT **2.4–5×** 优于 SOTA；累计 GPU 时间比 FaaSNet/NCCL/ServerlessLLM 少 **17.8% / 18.1% / 31.3%**，距 ideal scaling 仅 4.3%–18.6% gap。
- 支持单 GPU 与 multi-GPU per node；可与 [[KV-Cache]] 复用系统（如 Mooncake）互补。

## 相关

- **相关概念**：[[RDMA]]、[[Pipeline-Parallelism]]、[[KV-Cache]]、[[Disaggregation]]
- **同类系统**：ServerlessLLM、FaaSNet、NCCL broadcast、BlitzScale、DynamoLLM
- **同会议**：[[MLSys-2026]]