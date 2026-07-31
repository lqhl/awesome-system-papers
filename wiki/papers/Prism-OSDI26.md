---
type: paper
name: Prism
full_title: "Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning"
authors: [Shan Yu, Yifan Qiao, Mingyuan Ma, Yangmin Li, Shuo Yang, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, gpu-memory, multi-model, memory-ballooning, scheduling]
source_pdf: "[[osdi26-yu-shan.pdf]]"
source_md: "[[osdi26-yu-shan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 通过 GPU 内存气球实现低成本多 [[LLM|LLM]] Serving（OSDI 2026）

> **原题**：Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning

> **一句话总结**：Prism把model weights与KV的GPU allocation做成elastic balloon，在活跃model间回收/扩张，从一个机制统一space/time sharing；58-model trace下以16 GPUs达99% TTFT SLO，而MuxServe++需20，kvcached已部署10K+ GPUs。

## 问题与动机

providers必须常驻大量低流量模型；production traces表现为不断变化的bursty active groups，固定colocation无法回收idle model，纯swap又频繁activation，GPU duty常低于30%。

## 关键观察 / 隐含假设

- model working set随时间变化，memory比compute更适合作为统一共享控制面。
- weights/KV可按压力回收并重载，SLO可覆盖migration stall。
- global coordination比per-model static quota更能利用空闲memory。

## 核心方法

kvcached balloon driver在GPU内提供可动态expand/shrink的model/KV pool；global scheduler根据SLO-weighted request rate与KV pressure放置[[Tensor-Parallelism|TP]] parts，idle threshold触发weight eviction，active request按priority获得memory。local allocator维持contiguous layout降低page fault/migration tail。

## 实验与结果

- **设置**：Hyperbolic/Arena与company traces、58 models，对比MuxServe++、QLM/static，以TTFT/TPOT SLO attainment和GPU count为指标（§7）。
- Arena高load承载超过baseline 3× request rate；58 models以16 GPUs达99% TTFT，MuxServe++需20。
- production deployment平均throughput 3.89×、无SLO violation；elastic overhead使mean TTFT/TPOT只+3%–5%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| balloon统一space/time sharing | 图 5/9 | multi-model burst traces | 强 |
| production提升utilization | 图 11 | 10K+ GPUs rollout | 强 |

## 批判性分析

### 论证链条

bursty-group observation直接导出elastic working set，trace与deployment互相支持。

### 假设压力测试

所有模型同时burst或[[PCIe|PCIe]]拥塞时balloon不能创造capacity；过短idle threshold会反复swap。

### 实验可信度

多provider traces与生产规模强，但proprietary workload、model quality和migration failure细节有限。

## 局限与后续工作

- simultaneous bursts、failure与multi-tenant fairness。
- 跨node/remote memory balloon与cost model。

## 相关

- **相关概念**：[[LLM-Serving]]、[[GPU-Memory]]、[[Memory-Ballooning]]、[[KV-Cache]]
- **相关系统**：[[MuxServe]]、[[QLM]]
- **同会议**：[[OSDI-2026]]
