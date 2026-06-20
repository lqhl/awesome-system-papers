---
type: paper
name: DCP
full_title: "DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism"
authors: [Chenyu Jiang, Zhenkun Cai, Ye Tian, Zhen Jia, Yida Wang, Chuan Wu]
venue: SOSP
year: 2025
tags: [long-context, context-parallelism, llm-training, attention, hypergraph-partitioning]
source_pdf: "[[3731569.3764849.pdf]]"
source_md: "[[3731569.3764849]]"
---

# DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism (SOSP 2025)

> **一句话总结**：每 iteration 用 hypergraph partitioning 动态放置 attention Q/KV block，causal mask attention **1.19–2.45×**、稀疏 mask **2.15–3.77×**，端到端最高 **1.46×**。

## 问题与动机

[[Context parallelism]]（Ring-Attention、LoongTrain、TransformerEngine）静态均分序列，忽略：(1) 长度分布极度偏斜（Llama3 SFT 长样本仅 **0.11%**）导致短序列冗余 KV 通信；(2) shared question、lambda、sliding-window 等稀疏 mask 破坏均匀负载。CP 通信随集群规模上升（Fig. 1，8B GPT 16-way CP 通信占比显著）。

## 关键观察 / 隐含假设

- **观察 1**：FlashAttention 式 block-wise attention 可在 batch/head/SeqQ/SeqKV 四维切分；placement 可按 block 粒度混合 CP/DP。
  - **依赖假设**：planning 开销 << attention 计算；hypergraph partition 可在 iteration 前完成。
  - **可能失效场景**：极大 batch 导致 block 数爆炸，partition 求解变慢。
  - **证据强度**：强——microbenchmark 2×+ 加速。
- **观察 2**：同一 batch 内长短序列并存时，「长序列 CP + 短序列 DP」优于统一 CP 度数。
  - **依赖假设**：通信 cost 模型准确反映 ring/all-to-all 拓扑。
  - **可能失效场景**：网络拓扑非对称、 congestion 动态变化使静态 cost model 失效。
  - **证据强度**：中——Fig. 5 示意清晰，端到端增益 0.94–1.46× 说明非所有 setting 都赢。
- **假设 1**：data loader wrapper 预取 + 五类指令序列化 schedule，custom executor 开销可控。
  - **证据强度**：中——端到端有增益但 causal 部分 iteration <1×（0.94× 下界）。

## 核心方法

1. 细粒度 data block（Q/KV）+ computation block（mask 决定 Q-KV 是否计算）
2. 每 iteration hypergraph partitioning：最小化通信、平衡 memory/compute
3. 自动生成 per-device pipeline schedule（overlap comm/compute）
4. Fused kernel executor 执行五类指令

## 设计取舍

- **取舍 1**：每 iteration 重规划换自适应，planning CPU 开销换 GPU 通信节省。
- **取舍 2**：依赖 hypergraph partition 启发式，最优性无 guarantee。
- **边界条件**：长上下文 transformer 训练；非 attention 算子仍用常规 CP。

## 实验与结果

- Micro：causal **1.19–2.45×**，sparse **2.15–3.77×** vs TransformerEngine/LoongTrain
- End-to-end：causal **0.94–1.16×**，sparse **1.00–1.46×**
- 8B GPT on p4d.24xlarge，4-way TP + 16-way CP

## Critical Analysis

### 论证链条

input dynamism 两类方差 → block 表示统一刻画 → partition+schedule，逻辑闭合。0.94× 下界诚实暴露并非总赢。

### 假设压力测试

- 70B+ 模型 planning 时间是否成为新瓶颈？论文对 planner latency 讨论有限。
- 与 sequence packing（varlen）结合是否冗余或协同？未对比。
- RLHF 等多变 mask 生产 trace 验证偏少。

### 实验可信度

Micro 与 E2E 分离报告可信。Baseline 为 SOTA CP 框架。集群规模相对中小（AWS p4d）。

### 系统性缺陷

论文未讨论：与 [[Pipeline-Parallelism]]/[[Tensor-Parallelism]] 联合 planner；fault tolerance 下 block placement 一致性。

## 局限与 Future Work

- **局限 1**：部分 causal E2E <1×，说明 planning/executor 开销仍高。
- **局限 2**：cost model 对动态网络敏感。
- **Future work 1**：amortize partition across similar-length batches，降低 per-iteration 规划成本。

## 相关

- **相关概念**：[[Context parallelism]]、[[Ring-Attention]]、[[Flash-Attention|FlashAttention]]、long-context training
- **同类系统**：TransformerEngine、LoongTrain、Ring-Attention
- **同会议**：[[SOSP-2025]]