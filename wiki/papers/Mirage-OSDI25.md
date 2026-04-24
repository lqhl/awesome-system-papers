---
type: paper
name: Mirage
full_title: "Mirage: A Multi-Level Superoptimizer for Tensor Programs"
authors: [Mengdi Wu, Xinhao Cheng, Shengyu Liu, Chunan Shi, Jianan Ji, et al.]
venue: OSDI
year: 2025
tags: [compiler, tensor-program, gpu-kernel, superoptimizer, llm-inference]
source_pdf: "[[osdi25-wu-mengdi.pdf]]"
source_md: "[[osdi25-wu-mengdi]]"
---

# Mirage: A Multi-Level Superoptimizer for Tensor Programs (OSDI 2025)

> **一句话总结**：Mirage 用统一的 µGraph 表示同时刻画 kernel / thread block / thread 三层 GPU 层级，通过抽象表达式剪枝的枚举搜索 + 概率化有限域等价验证，自动发现跨层的代数 + 调度联合优化以及全新的 custom kernel，在 GQA/RMSNorm/LoRA 等被重度优化的负载上比最好手写/现有编译器提速 **最多 3.3×**。

## 问题

现有张量程序优化器只覆盖搜索空间的子集：TVM/Ansor/Triton 这类 schedule-based 工具要求用户先写死算法再优化 schedule；TASO/PET 这类 algebraic superoptimizer 只能在 kernel 级做代数变换，依赖库里预定义的 kernel 实现。像 [[Flash-Attention]] 这样真正高性能的实现需要**同时**做代数变换（重排 softmax 与 matmul 顺序）、schedule 变换（调整并行度和数据布局）、以及生成全新的 custom kernel——这些都在现有自动化工具的搜索空间之外，只能靠专家手写（Triton 版 FlashAttention 超过 700 行）。

## 核心方法

Mirage 的核心是 **µGraph**，一种层级图表示，把 GPU 执行层级 (kernel graph → block graph → thread graph) 统一建模，每层的算子、数据布局、imap/omap/fmap、for-loop 等都是可搜索变量。这样代数、调度、以及自定义 kernel 发现都可以在同一个搜索空间里做。

搜索分三步：(1) **表达式引导的 µGraph 生成器**，按 canonical form 增量枚举 kernel/block 算子序列，用 **abstract expression 剪枝**——为每个中间张量计算抽象表达式，只有当其为目标计算的子表达式时才保留该前缀，在保留最优解的前提下把 > 10 小时的搜索时间降到秒级；thread 层用基于融合的规则生成。(2) **概率化等价验证器**：限制到 LAX fragment（multi-linear + 有限除法/指数），把验证转化为有限域 $\mathbb{Z}_p \times \mathbb{Z}_q$ 上的多项式恒等测试 (PIT)，给出任意可调的错误率上界。(3) **µGraph 优化器**：用 ILP 选 tensor layout、用深度调度最少化 `__syncthreads()`、穷举枚举内存分配。Mirage 能自动复现 [[Flash-Attention]] / FlashDecoding 的 µGraph，并进一步发现人工都没想到的变体。

## 关键结果

- A100/H100 上六个 DNN benchmark（GQA、QKNorm、RMSNorm、LoRA、GatedMLP、nTrans）相对最佳基线提速 **最多 3.3×**
- GQA (LLaMA-2-70B, TP=4) 比 FlashDecoding / TensorRT-LLM 快 **最多 2.2×**，通过自动选择 grid dim 和沿 KV-head 维度并行
- RMSNorm 单 kernel 融合比 PyTorch 手写 CUDA 快 **1.5×/1.9×**（A100/H100）
- 端到端四个 DNN（LLaMA-3、Chameleon、nGPT、LoRA）提速 0.9–1.9×
- 抽象表达式剪枝把 11-op block graph 的搜索时间从 >10 h 降到 28 s
- 一次性编译 < 4 h，部署后与 PyTorch JIT 集成只需几行代码

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[LoRA]]、[[Chunked-Prefill]]（作为 LLM 编译优化语境）
- **同类系统**：TVM、Ansor、Triton、TASO、PET、TensorRT-LLM
- **同会议**：[[OSDI-2025]]
