---
type: paper
name: DistCA
full_title: "Efficient Long-Context Language Model Training by Core Attention Disaggregation"
authors: [Yonghao Zhuang, Junda Chen, Bo Pang, Yi Gu, Yibo Zhu, "et al."]
venue: MLSys
year: 2026
tags: [long-context, training, disaggregation, attention, load-balancing]
source_pdf: "[[93db85ed909c13838ff95ccfa94cebd9.pdf]]"
source_md: "[[93db85ed909c13838ff95ccfa94cebd9]]"
---

# Efficient Long-Context Language Model Training by Core Attention Disaggregation (MLSys 2026)

> **一句话总结**：提出 Core Attention Disaggregation (CAD)——把无参数的 softmax(QK^T)V 从 transformer 层剥离到独立 "attention server" 池上 token 级动态调度，消除长上下文训练中 DP/PP stragglers，512 H200 GPUs / 512K context 上相对现有系统 **1.35× 端到端吞吐加速**。

## 问题

长上下文训练（100K-1M token）普遍用 document packing 把变长文档拼成固定 chunk，但 attention 的 quadratic FLOPs 与其余层的 linear FLOPs 不匹配——一个 4K token chunk 放 1×4K 文档的 attention FLOPs 约是 4×1K 的 4×。在 DP 中 straggler 拖全组，在 PP 中单个 microbatch 慢拖整条流水，hybrid DP+PP 下效应叠加损失 1.34-1.44×。现有补救：
- **Variable-length chunk** 通过加更多短文档到短 chunk 以等化 attention FLOPs，但 activation 内存随 token 数线性增，DP=8 下 55% 时间 idle。
- **[[Context-Parallelism]] (CP)** 沿 sequence 切 shard，但 all-gather 开销随 CP degree 增（32 节点时占 40% 延迟），最后 rank 存整 KV 内存压力大，PP stragglers 完全解不了。

## 核心方法

**两个关键观察**：
1. **Statelessness**：Core Attention (CA) = 无参数的 softmax(QK^T)V，无训练状态，balancing 退化为 compute-bound 任务调度。
2. **Composability**：CA 可在 token 粒度切分，不同 doc 的 shard 可 re-batch 成单个高占用率 kernel（[[Flash-Attention]] 测试 tile≥128 时吞吐只看 aggregate token 数不看来源）。

**CAD 设计**：CA 调度到独立 "attention server" 池。Attention server 收 CA-task（Q shard 和它的 context KV shard），动态 rebatch 成大 fused kernel 调用。系统 DistCA 包含：

- **In-place attention server**：GPU 分时切换角色，CA 阶段做 attention、其他时间跑 context-independent 层，兼顾 compute 与 memory 利用。
- **Ping-pong execution**：microbatch 切成 Ping/Pong 两个 nano-batch 交错，一个做通信另一个做计算完全重叠；NVLink TP 通信与 IB 跨节点 CA 通信重叠。
- **Communication-aware greedy scheduler**：把 CA task 优先度量为 ΔF_max / V_comm（迁移 FLOPs 与通信量比），动态迁移 item 直到 per-server load 在 ε 容差内。
- **PP 兼容**：调整 1F1B schedule 让一个 tick 内所有 stage 同做 forward 或同做 backward，pipeline warmup/draindown 的空 GPU 也用来跑 CA task。

## 关键结果

- 基于 Megatron-LM 实现，~3K LoC。
- 512 H200 GPUs 上 512K context Llama 系列训练，相比现有系统端到端吞吐 **1.35× 加速**。
- DP/PP stragglers 完全消除，compute 和 memory 近完美平衡，weak scaling 接近线性。
- Llama-3-34B InfiniBand 带宽下可把 doc 切成最多 31 shards 且通信被 hide。

## 相关

- **相关概念**：[[Disaggregation]]、[[Attention]]、[[Flash-Attention]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：Megatron-LM、Ring Attention、per-document CP
- **同会议**：[[MLSys-2026]]
