---
type: paper
name: ParallelKittens
full_title: "ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels"
authors: [Stuart H. Sul, Simran Arora, Benjamin F. Spector, Christopher Ré]
venue: MLSys
year: 2026
tags: [multi-gpu, cuda, kernel, overlap, thunderkittens, ai-infra]
source_pdf: "[[3295c76acbf4caaed33c36b1b5fc2cb1.pdf]]"
source_md: "[[3295c76acbf4caaed33c36b1b5fc2cb1]]"
---

# ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels (MLSys 2026)

> **一句话总结**：ThunderKittens 扩展为 8 primitive + 统一模板，按传输机制/调度/设计开销三条原则写 overlapped multi-GPU kernel，<50 行 device 代码即达 DP·TP 2.33×、SP 4.08×、EP 1.22×，匹配 Flux/Comet/CUTLASS 手工核。

## 问题

A100→B200：BF16 tensor core **7.2×**，NVLink 仅 **3×**，inter-GPU 通信成 LLM 主瓶颈（prefill 仍占 >50%）。覆盖 data/tensor/sequence/[[Expert-Parallelism|expert]] 四类并行算子。Flux/Comet 等手工核不可复用；Triton Distributed 跨架构失效；NCCL/NVSHMEM 同步与缓冲设计带来 >1.7× 纯通信损失。

## 核心方法

**三条原则**（microbenchmark 验证）：
1. **Transfer**：copy engine 81% 峰值但需 ≥256 MB；TMA 2 KB 即 74%；register 支持 in-network reduction 但需 ~76 SM
2. **Scheduling**：粒度对齐用 intra-SM（GEMM+RS **1.2×**）；in-network AR 用 inter-SM（GEMM AR **3.62×**）
3. **Overheads**：预分配目标 buffer、去双向同步，allreduce 最高 **1.79×**

**ParallelKittens**：device-initiated TMA/register；Parallel Global Layout (PGL)；运行时搜索最优 SM 划分。完全不用 copy engine。

## 关键结果

- [[Tensor-Parallelism|DP/TP]] **2.33×**、SP **4.08×**、[[Expert-Parallelism|EP]] **1.22×**；non-overlapped comm 降至 1%/9%/15%
- vs Triton Distributed **1.07–5.63×**；vs xDiT/YunChang **1.01–4.08×**
- Hopper + Blackwell 验证；Cursor in-house 训练已采用

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Pipeline-Parallelism]]、[[Flash-Attention]]、[[MoE]]
- **同类系统**：ThunderKittens、Flux、Comet、CUTLASS、Triton Distributed、NanoFlow
- **同会议**：[[MLSys-2026]]