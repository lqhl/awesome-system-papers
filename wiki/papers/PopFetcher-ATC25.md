---
type: paper
name: PopFetcher
full_title: "PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch"
authors: [Junyi Zhang, Chuanhu Ma, Xiong Wang, Yuntao Nie, Yuqing Li, et al.]
venue: ATC
year: 2025
tags: [moe, expert-parallelism, prefetch, all-to-all, distributed-training]
source_pdf: "[[atc2025-zhang-junyi.pdf]]"
source_md: "[[atc2025-zhang-junyi]]"
---

# PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch (ATC 2025)

> **一句话总结**：基于专家热度预测的 expert-wise prefetch，利用 non-MoE 计算阶段空闲网络链路提前拉取热门专家，把 MoE 训练时间相比 SOTA 缩短 15%–94.5%。

## 问题

[[MoE]] 模型训练中，由于专家稀疏激活与跨 worker token dispatch，All-to-All 通信占据 MoE 层 50–60% 的时间，且 hot expert 引发严重负载不均。已有方案：FasterMoE 周期性广播 partial expert（同步开销大）、Janus 在训练前静态选择 fetch-expert 还是 push-token（不能适应专家参数 vs token 数据量动态变化）。这些粗粒度方案与 All-to-All 并行执行，仍存在通信瓶颈。

## 核心方法

PopFetcher 在 [[Expert-Parallelism]] 基础上，利用 Transformer 中 non-MoE 层（Attention 等）的计算阶段网络链路空闲这一窗口期，提前 prefetch 下一个 MoE 层的热门专家。

- **Lightweight popularity prediction**：发现相邻 MoE 层之间专家选择具有相关性 Pr(E^{h,j+1} | E^{i,j})，结合 sliding window（s=10 iterations）的历史选择数据，对下一层热门专家做轻量预测。
- **Hybrid push-pull paradigm**：当 token 数量超过专家参数大小时拉专家到本地，否则推 token 到远端。基于 H=1024 float32，临界点约 2048 tokens。
- **优化 prefetch 决策**：把端到端 latency（含 forward / backward 计算与通信）建模为 MILP，通过 expert prefetch pruning 把搜索空间从 O((kN)^M) 缩减到 ≤ k×N，仅当 ε=P_w/W_{n,w} > 3αH 时 prefetch 才有收益。
- **优先 All-to-All 流**：backward 中将 All-to-All 优先级置于 All-Reduce 之上，缓解通信阻塞。

详见 [[atc2025-zhang-junyi]]。

## 关键结果

- 相比 SOTA（FasterMoE / Janus / Tutel 等），训练时间减少 15%–94.5%。
- 在 8-worker GPT-MoE 上 All-to-All 占比从 56–58% 显著下降。
- Expert prefetch pruning 将候选专家数从全局规模降到 ≤ k×N。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]
- **同会议**：[[ATC-2025]]
