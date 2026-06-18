---
type: paper
name: DreamDDP
full_title: "DreamDDP: Accelerating Data Parallel Distributed LLM Training with Layer-wise Scheduled Partial Synchronization"
authors: [Zhenheng Tang, Zichen Tang, Junlin Huang, Xinglin Pan, Rudan Yan, Yuxin Wang, Amelie Chi Zhou, Shaohuai Shi, Xiaowen Chu, Bo Li]
venue: MLSys
year: 2026
tags: [distributed-training, local-sgd, geo-distributed, communication-overlap, llm-training]
source_pdf: "[[9f61408e3afb633e50cdf1b20de6f466.pdf]]"
source_md: "[[9f61408e3afb633e50cdf1b20de6f466]]"
---

# DreamDDP: Accelerating Data Parallel Distributed LLM Training with Layer-wise Scheduled Partial Synchronization (MLSys 2026)

> **一句话总结**：把 Local SGD 的全模型同步拆成 layer-wise partial synchronization（PLSGD），in-place overlap 参数通信与 backward；32 GPU 上 ResNet/GPT-2/Llama-2 迭代时间比 SOTA **1.49–3.91×** 更快，收敛率与 S-SGD 同阶。

## 问题

Geo-distributed DDP 低带宽下通信主导（10Mbps–1Gbps）。Local SGD 每 H 步全模型同步，硬同步点阻止像 WFBP 那样 overlap comm 与 BP，GPU/链路空闲交替。

## 核心方法

**Partial Local SGD (PLSGD)**：每 iteration 只同步部分 layer，理论收敛与 LSGD 可比。

**In-place overlap**：layer l 的 BP 完成后立即 launch 其参数 sync，与后续 layer BP 并行，无额外 GPU memory。

**DFS scheduler**：基于 layer-wise profile，利用 optimal hiding / delayed CO / at-least-one 三性质剪枝 **H^L** 搜索空间；bubble filling 插入额外 sync 加速收敛。

## 关键结果

- 32 GPU 两集群：GPT-2、Llama-2、ResNet-18/50 迭代时间 **1.49–3.91×** vs LSGD/ASC-WFBP
- 收敛速度与 S-SGD 相近（理论保证同阶）

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：WFBP、ASC-WFBP、INTELLECT-1 Local SGD
- **同会议**：[[MLSys-2026]]