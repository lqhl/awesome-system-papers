---
type: paper
name: Mercury
full_title: "Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling"
authors: [Yue Guan, Xinwei Qiang, Zaifeng Pan, Daniels Johnson, Yuanwei Fang, et al.]
venue: SOSP
year: 2025
tags: [llm, multi-gpu, compiler, ir, attention, collective-communication]
source_pdf: "[[3731569.3764798.pdf]]"
source_md: "[[3731569.3764798]]"
---

# Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling (SOSP 2025)

> **一句话总结**:Mercury 用新型 loop-based IR「CommIR」把远程 GPU HBM 作为 first-class 调度层纳入多 GPU 算子编译器，自动生成包含 ring-style、shift、collective 的混合通信模式，相比 USP/Ulysses 等手工设计平均 **1.56× 加速**，相对 3D 并行达 1.62×。

## 问题

LLM 训练/推理的 [[Attention]] 和 GEMM 算子超出单 GPU 能力已成常态——Llama-3 70B 的 KV cache 282GB 已远超 H100 的 80GB。过去两年涌现了 20+ 篇手工多 GPU 算子论文（RingAttention、Ulysses、USP、LoongTrain、TokenRing 等），但都强耦合特定硬件拓扑、GPU 数量、head/context 长度等参数，**不可移植**。

现有编译器不够用的根本原因是**本地内存中心 (local-memory-centric) 假设**：所有输入必须先在每卡 HBM 里就绪才能计算，inter-GPU 通信只被当作交换中间结果的手段。这导致默认 schedule 是「同步复制 + 时间同步」——共享输入 B 在每卡完整复制、所有设备齐步访问，浪费 HBM 并阻碍 tiling。

Alpa/Centauri 等自动化方案仍用模板、限于同步模式；CoCoNet 支持 auto-tuning 但也限于同步集合通信，无法表达 async shift。

## 核心方法

Mercury 的核心 insight：把**远程 GPU HBM 视为显式、可调度的 memory hierarchy 层**，与本地 HBM 并列。

- **CommIR**: loop-based IR，除继承 tile/reorder/join/patch 等计算变换外，引入 4 个通信原语：
  - **parallelize(loop, mesh_level)**: 把 loop 迭代分布到某层网络 mesh（inter-node / intra-node）
  - **shift(local_loop, parallel_loop)**: 对本地 loop 索引按 parallel loop 偏移，产生 async staggered access（是 RingAttention、USP 等 shift 模式的通用抽象）
  - **shard(buffer, loop)**: 把 buffer 按 loop 切片到各 worker
  - **replicate(buffer, loop)**: 显式复制 buffer
- **组合能力**：shift 一个 loop + parallelize 另一个能表达所有已知手工方案；允许对 reduction 轴做 shift 或再 split（如 `J=J0*J1`，J0 做 parallel reduce + J1 shift）来探索人类没见过的 schedule（§5 的 pattern 8 就是 auto-tuner 搜出的新方案）
- **通信自动合成**：shard 组合下自动 lower 成 AllGather / Broadcast / ReduceScatter；shift 合成 P2P pattern，生成与手写 FlashAttention + ring 一致的代码
- **Auto-tuner**：两阶段生成设计空间——先算子 schedule，再通信 schedule，用硬件 mesh 约束剪枝，加上 memory upper bound 静态剪枝，10 分钟搜出 optimal
- **Graph-level resharding**: 维护每算子 sharding 候选库，动态规划找全局最优 input/output sharding 组合

**Patch 原语**可以把内层 subgraph 替换为 FlashAttention / cuBLAS 等手写 kernel，避免重复造轮子、同时缩小搜索空间。

## 关键结果

- Attention 算子相比 SOTA 手工 USP/Ulysses/RingAttention 平均 **1.56× 加速**
- 真实 LLM workload 相比 3D 并行（Megatron 风格） **最高 1.62×**
- 自动复现 RingAttention 和 Ulysses 的性能，且在某些配置下**发现手工忽略的更优 schedule**（如内外 shift 嵌套的 pattern 8）
- 搜索时间每算子 ~10 分钟
- 开源：https://github.com/ChandlerGuan/mercury_artifact

## 相关

- **相关概念**:[[Attention]]、[[GEMM]]、[[Tensor-Parallelism]]、[[Context-Parallelism]]、[[Collective-Communication]]、[[NCCL]]、[[FlashAttention]]
- **同类系统**:[[Alpa]]、[[Centauri]]、[[CoCoNet]]、[[RingAttention]]、[[DeepSpeed-Ulysses]]、[[USP]]、[[LoongTrain]]
- **同会议**:[[SOSP-2025]]
