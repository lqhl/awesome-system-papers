---
type: paper
name: BlendServe
full_title: "BlendServe: Optimizing Offline Inference with Resource-Aware Batching"
authors: [Yilong Zhao, Shuo Yang, Kan Zhu, Lianmin Zheng, Baris Kasikci, Yifan Qiao, Yang Zhou, Jiarong Xing, Ion Stoica]
venue: ASPLOS
year: 2026
tags: [llm-inference, offline-serving, batching, prefix-caching, resource-overlap]
source_pdf: "[[asplos26-zhao-blendserve.pdf]]"
source_md: "[[asplos26-zhao-blendserve]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# BlendServe：以资源感知批处理优化离线推理（ASPLOS 2026）

> **原题**：BlendServe: Optimizing Offline Inference with Resource-Aware Batching

> **一句话总结**：BlendServe 发现离线推理中按 prefix 排序有利于 [[Prefix-Caching]]，混排 compute-/memory-intensive 请求有利于 GPU resource overlap，两者却会冲突；resource-aware prefix tree 与 dual scanner 同时优化两者，相对 vLLM/SGLang 最多提高 1.44× 吞吐并达到实际最优上界的约 90%（§6，图 7–10）。

## 问题与动机

离线数据生成、评测和视频生成通常放松单请求 latency，只追求总吞吐。现有系统要么按 prefix tree DFS 最大化复用，要么打散请求让 prefill compute 与 decode memory access 重叠；单独优化任一目标都会破坏另一目标。

论文把每个请求按 token 数、生成长度与 operator profile 映射为 compute density，再利用离线“所有请求预先可见”的自由度重排。

## 关键观察 / 隐含假设

- **观察 1**：prompt/output 分布让请求呈现不同 compute–memory ratio，合理混合可填满 GPU 两类资源（§3.1，图 2）。
- **观察 2**：随机混合会摧毁共享 prefix，纯 DFS 又让同类请求聚集并造成资源振荡（§3.2–3.3）。
- **假设 1**：离线 workload 可重排，输出长度或 compute density 可由采样/profile 足够准确地估计。
  - **证据强度**：中；大 output variance 时附录已显示收益下降。

## 核心方法

系统先构建 resource-aware prefix tree，节点同时记录共享 token 和子树资源密度。dual scanner 从 tree 两端选择互补请求，使 batch 在保留 prefix locality 的同时接近 compute/memory balance。

运行时 scheduler 管理 tree、batch 和 [[KV-Cache]]；实现接入 [[vLLM]]、[[SGLang]] 与 NanoFlow execution backend。所谓 practical optimum 假设每一步可完美重叠资源，是评估上界而不是可部署 oracle。

## 设计取舍

- **离线重排换吞吐**：不适用于交互式 arrival 和严格 per-request deadline。
- **采样输出长度换可计划性**：预测误差会改变 compute density，长尾输出尤其脆弱。
- **双目标 heuristic**：实现简单，不能保证全局最优。

## 实验与结果

- Llama-3-8B/70B、A100 与四组真实/合成 trace 上，相对 vLLM-DFS 最高 1.44×，相对 NanoFlow-DFS 提高 19.34%–22.65%（§6.3，图 7）。
- 达到 practical optimum 的 86.55%/90.8%，prefix sharing 达理论最大值的 97% 以上（§6.3–6.4，图 7、9）。
- 65 个 profile-guided simulation workload 上平均提高 22.53%；模拟与四个实测 workload 的 speedup 平均差 0.91%（§6.5，图 11）。
- runtime tree operation 平均 0.08 ms、P99 0.23 ms；大 output variance workload 仅提高 1.08–1.31×（附录 A.4–A.5，图 13–15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| prefix reuse 与资源重叠必须联合优化 | 超过两类单目标 NanoFlow baseline（§6.3–6.4） | 离线、可重排 workload | 强 |
| dual scanner 接近实际最优 | 86.55%/90.8% of practical optimum（图 7） | 上界假设 perfect step overlap | 中 |
| 调度开销较小 | 0.08 ms average、0.23 ms P99（附录 A.5） | 论文 CPU 与 batch 规模 | 中强 |

## 批判性分析

### 论证链条

两个相互冲突目标被清楚测量，并分别用 tree 与 dual scanning 回应，ablation 支持设计。1.44× 是相对 vLLM 的峰值；对更强的 NanoFlow-DFS，典型增益约二成，更适合解读为调度层收益。

### 假设压力测试

输出长度难预测、prefix 少、workload memory density 单一或请求有 deadline 时，重排空间和收益都会缩小。不同 request 混合还可能带来 kernel interference，简单加法 profile 未必稳定。

### 实验可信度

真实 GPU 与 profile simulation 交叉校准，baseline 较强，并披露 output variance 边界。分布式其他模型主要靠 simulation，不能等同于实机扩展证据。

### 系统性缺陷

需要预先 tokenize 全部输入、构建树并估计输出；数据持续到达或执行失败重试会使计划过期。论文没有讨论公平性、任务优先级和失败恢复。

## 局限与后续工作

- 在不可预测输出、动态到达和 deadline-constrained batch 上测在线重规划。
- 把 energy、cost 与多 GPU topology 加入 resource density，而不只优化单 GPU 时间。

## 相关

- **相关概念**：[[Prefix-Caching]]、[[KV-Cache]]、[[Continuous-Batching]]、[[LLM-Inference]]
- **同类系统**：[[vLLM]]、[[SGLang]]、NanoFlow、DistServe
- **同会议**：ASPLOS 2026
