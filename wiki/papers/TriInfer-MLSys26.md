---
type: paper
name: TriInfer
full_title: "TriInfer: Hybrid Disaggregated Scheduling for Multimodal Large Language Model Serving"
authors: [Xianzhe Dong, Tongxuan Liu, Yuting Zeng, Weizhe Huang, Xiaoyang Zhao, et al.]
venue: MLSys
year: 2026
tags: [mllm, inference, disaggregation, scheduling, serving]
source_pdf: "[[6974ce5ac660610b44d9b9fed0ff9548.pdf]]"
source_md: "[[6974ce5ac660610b44d9b9fed0ff9548]]"
---

# TriInfer: Hybrid Disaggregated Scheduling for Multimodal Large Language Model Serving (MLSys 2026)

> **一句话总结**：TriInfer 用 Hybrid EPD 解耦（encode/prefill/decode 可配置分片）+ 双流 vision/language 并行 + stage-level batching，在 90% SLO 满足下相对 [[vLLM]]/[[SGLang]] 最高 **2.4×** goodput（POPE），并随 workload 自动选 E+P+D / EP+D / ED+P。

## 问题

MLLM 推理分 encode（vision tower）、prefill、decode 三阶段，资源与 SLO 特征异构。现有系统（[[vLLM]]、[[SGLang]]）按 LLM 架构顺序处理图文，未利用跨模态并行；continuous batching / stall-free scheduling 粒度太粗，难精确控制 TBT；固定一种 PD/EPD 解耦策略无法适配不同 TTFT/TBT SLO。

## 核心方法

**TriInfer** 三大设计：
1. **Dual-stream**：vision stream 跑 encode，language stream 并行 prefill/decode
2. **Stage-level batching**：按实例类型（E/EP/P/D 等）设不同 batch 上限与 latency budget（encode 饱和 ~6 图，prefill ~1 req，decode ~512）
3. **Hybrid EPD Disaggregation**：实例可配置执行 encode/prefill/decode 子集；根据历史 trace + SLO 自动选 E+P+D、EP+D 或 ED+P 及实例比例

Migrate Scheduler 在实例间动态迁移请求平衡负载。

## 关键结果

- 90% SLO 满足下 goodput：MME **1.2×**、POPE **2.4×**、TextCaps **1.5×**、TextVQA **1.8×**、VizWiz **1.7×**（vs vLLM/SGLang SOTA）
- 不同 TTFT/TBT 约束下最优解耦方式不同（E+P+D 在严格 TTFT 下优势大）
- encode 与 prefill 算术强度介于 decode 与 prefill 之间，并行可提升利用率

## 相关

- **相关概念**：[[Disaggregation]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、MLLM serving
- **同类系统**：[[vLLM]]、[[SGLang]]、Sarathi-Serve、Mooncake
- **同会议**：[[MLSys-2026]]