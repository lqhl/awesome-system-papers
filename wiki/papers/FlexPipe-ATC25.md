---
type: paper
name: FlexPipe
full_title: "FlexPipe: Maximizing Training Efficiency for Transformer-based Models with Variable-Length Inputs"
authors: [Hairui Zhao, Qi Tian, Hongliang Li, Zizhong Chen]
venue: ATC
year: 2025
tags: [pipeline-parallelism, llm-training, variable-length, dynamic-reconfiguration, transformer]
source_pdf: "[[atc2025-zhao-hairui.pdf]]"
source_md: "[[atc2025-zhao-hairui]]"
---

# FlexPipe: Maximizing Training Efficiency for Transformer-based Models with Variable-Length Inputs (ATC 2025)

> **一句话总结**：第一个支持 PP 阶段数与 GPU 分组在迭代间无停顿动态调整的 pipeline 框架，通过 TwinLayer + Heuristic Bound Search 把 variable-length transformer 训练吞吐相比 SOTA 平均提升 1.25×。

## 问题

Transformer 用 mixture 数据集训练（FLANv2 等）时输入长度差异巨大（FLANv2 中样本长度差可达 60000），现有方案（zero padding、packing、bucketing、[[Flash-Attention]] 等）只优化"单 iteration 内"的浪费，但 iteration 间计算与显存需求剧烈波动，静态 [[Pipeline-Parallelism]] 切分（基于最大序列长度）让大多数迭代 GPU 利用率 < 55%、显存利用率 < 39%。

## 核心方法

- **Live Flexibility Mechanism (LFM)**：为每节点的层在 host memory 维护"TwinLayer"副本（含 optimizer state），减少初始化与跨设备传输开销。增减 stage 时把数据/参数 copy 与初始化重叠到上一个 iteration 的 backward 之后，通信与计算 pipeline 化，单次切换从 7.16s 降到 0.79s。
- **Flexible Memory Optimization Problem (FMOP)**：建模为给定下个 iteration 最大 seq len µ，找最优 (S→G mapping, O_plan) 最小化 T，同时考虑 LFM overhead 与重计算/offload 等 memory optimization 的成本。
- **Heuristic Bound Search Algorithm (HBSA)**：(1) 二分找出能容纳 M_peak 的最小 stage 数 N_stage；(2) 利用 transformer 同质性，给每 stage 的层数 |s_i| 与每组 GPU 数 |g_i| 设上下界 [⌊L/N⌋, ⌊L/N⌋+L%N]，剪枝掉极端不均的切分；(3) 在四种解（保持 / memory opt / grow / shrink）中根据条件 A/B/C/D 决定是否触发 LFM。
- **DP 利用 redundant GPU**：当短序列释放 GPU 后用作 DP 实例提升吞吐，动态 redistribute mini-batch。

详见 [[atc2025-zhao-hairui]]。

## 关键结果

- BERT-large（8 GPU）和 GPT 6.7B（16 GPU）变长训练上，相比 SOTA 平均训练吞吐 1.25×。
- 单次 PP stage 切换 overhead 从 non-live 7.16s 降到 0.79s。
- HBSA 通过 bounds 剪枝有效避开 OOM 与极端 DP 度的低效组合。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]、[[Flash-Attention]]、[[Attention]]
- **同会议**：[[ATC-2025]]
