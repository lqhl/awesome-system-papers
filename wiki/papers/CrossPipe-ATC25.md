---
type: paper
name: CrossPipe
full_title: "CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training"
authors: [Tiancheng Chen, Ales Kubicek, Langwen Huang, Torsten Hoefler]
venue: ATC
year: 2025
tags: [llm-training, pipeline-parallelism, cross-datacenter, scheduling, distributed-training]
source_pdf: "[[atc2025-chen-tiancheng.pdf]]"
source_md: "[[atc2025-chen-tiancheng]]"
---

# CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training (ATC 2025)

> **一句话总结**：把 [[Pipeline-Parallelism]] 和 [[Data-Parallelism]] overlap 一起建模为 latency + bandwidth-aware 约束优化问题，针对跨数据中心训练给出 solver-based optimal 调度和 greedy 近优算法，相同显存预算下比传统 1F1B 减少 33.6% 训练时间。

## 问题

LLM 训练算力需求年增 4×，单数据中心电力撑不住，跨 DC 训练成趋势（Microsoft / Google / Amazon 已转向核电厂房 + 多 DC）。但跨 DC 链路相比单 DC：

- Same-campus：10 µs / 800 Gb/s（开销可忽略）；
- Cross-campus：10-200 µs / 200 Gb/s；
- Same-region cloud：~1 ms / 11.3 Gb/s；
- Cross-region cloud：30-100 ms / 1.4-5.0 Gb/s。

[[Tensor-Parallelism]] / [[Sequence-Parallelism]] / [[Expert-Parallelism]] 频繁 collective 不适合跨 DC；只剩 PP（点对点 send/recv 在 stage 边界）和 DP（gradient sync）。但传统 1F1B 调度在跨 DC 下的关键路径有 O(n_mb) 次跨 DC 通信，bubble 被放大；Megatron 的 grouped send/recv 还引入隐式同步。

## 核心方法

**CrossPipe** 提供 latency + bandwidth-aware 性能模型 + 两种调度生成器 + 灵活执行引擎：

- **性能模型**：用 alpha-beta 通信模型，把 PP send/recv 和 DP collective 都建成 first-class operation；考虑链路 occupancy 引入的 queueing delay；
- **Optimal schedule**：把调度建成约束优化（CO）问题，决策变量 = 每个 op 的开始时间 + 共享 device/link 的执行顺序；约束包括数据依赖、资源不重叠、device 显存、microbatch 顺序；目标 minimize makespan；同时建模 [[ZeRO]] stage 1 的 Allgather overlap；
- **Greedy schedule**：solver 在大规模时太慢，提出 sub-block 切分（每个 F/D/W 块切成 n_sub 子块）+ 贪心 stage selection，本地决策即可生成近优；
- **Execution engine**：两层抽象解耦 block scheduling 与 communication arrangement，避免静态 grouped send/recv 的隐式同步导致 bubble 传播。

支持 F / D（DGrad）/ W（WGrad）三种粒度块（参考 Zero Bubble），traversal 模式覆盖 UD / BD / Loop / Wave。

## 关键结果

- 相同显存预算下，比传统 pipeline schedule 训练时间减少 **最高 33.6%**。
- 显存预算放宽时，效果接近无通信延迟的 idealized schedule。
- 在 Llama 3 405B 上分析：cross-DC PP 优于 cross-DC DP，特别是 [[MoE]] 模型（专家层放大 DP 通信量）。
- Greedy 算法在大规模/动态系统下比 solver 实用，调度开销 <<迭代时间。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[ZeRO]]、[[Cross-Datacenter-Training]]、[[1F1B]]、[[Zero-Bubble-Pipeline]]
- **同会议**：[[ATC-2025]]
