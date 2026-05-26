---
type: paper
name: PipeThreader
full_title: "PipeThreader: Software-Defined Pipelining for Efficient DNN Execution"
authors: [Yu Cheng, Lei Wang, Yining Shi, Yuqing Xia, Lingxiao Ma, et al.]
venue: OSDI
year: 2025
tags: [dnn-compiler, gpu, pipelining, tensor-cores, flash-attention]
source_pdf: "[[osdi25-cheng.pdf]]"
source_md: "[[osdi25-cheng]]"
---

# PipeThreader: Software-Defined Pipelining for Efficient DNN Execution (OSDI 2025)

> **一句话总结**：PipeThreader 把 GPU 内 TensorCore/TMA/CUDA core 等异构专用单元抽象成 sEU，把 DNN 计算拆成 sTask-graph 并在软件层显式调度，自动重现并超越 [[FlashAttention-3-NeurIPS24|FlashAttention-3]]，Mamba2 ChunkScan 比手写 Triton 快 1.71–1.99×。

## 问题

现代 GPU 加入了异构专用硬件单元——TensorCore（矩阵乘加）、TMA（Tensor Memory Accelerator，异步 bulk 搬运）、CUDA core。要喂饱它们需要仔细的流水线调度，但：

1. 传统 GPU 通过硬件调度器靠大量并发线程摊平 stall；但专用单元粒度变大（tensor tile），并发线程数急剧下降，硬件调度不再有效。
2. operator fusion（[[Flash-Attention]] 类）让 kernel 内部流水更深，硬件调度器看不到这么复杂的依赖。
3. 结果：SOTA kernel 都是手写的，[[FlashAttention-2-ICLR24|FlashAttention-2]] 到 [[FlashAttention-3-NeurIPS24|FlashAttention-3]] 做了整整一年；新硬件（H100 / MI300X）、新模型（Mamba）、新 tensor shape 都要重写一遍。

现有 DNN 编译器（TVM、Triton、Roller、Welder）把 GPU 抽象成同构 EU（SM），隐藏了内部异构性，没法表达跨专用单元的流水，也暴露不出细粒度调度原语。

## 核心方法

把**调度能力从硬件转到软件**。三个抽象：

- **sTask**：在某类专用单元上执行的细粒度任务（load、mma、softmax、rescale…），处理一个 tile，带 `target_sEU`、`shape`、tensor 表达式。
- **sEU**：每个 EU（= 一个 SM/CU）内部的异构专用单元集合；同步/异步标志决定能否并发。H100 上 TMA 和 TensorCore 都是异步 sEU。
- **sTask-graph / sProgram**：operator DFG 经 sTask-partition 得到 sTask-graph；把 sTask 按 `sProg[sEU][order]` 二维数组 map 到 sEU 得到 sProgram；barrier-sTask 负责同步依赖。

三个调度原语：`Append(sTask, <EU, sEU>)`、`Wait(sTask, list)`、`Propagate(graph, tileShape)`——最后一个会从输出 tile shape 反向推断全图 tile shape。

两层调度策略：**inter-EU** 层做 SPMD 式切分（按输出 sTask 不同 tile partition 枚举，把子图均分到各 EU）；**intra-EU** 层贪心地把 sTask 按优先级（异步且少依赖且能解锁下游的优先）Append 到 sEU，并用 profiler 估时间、检查 on-chip memory 不超。与传统 tiling 不同，PipeThreader 还把 **reduction dim tiling** 提到一等公民，用更细 tile 换更深流水，在内存与流水深度之间做 joint search。

实现 8.5k LoC C++/Python，基于 TVM + Ladder；支持 NVIDIA H100（CUTLASS/CuTe template + warp specialization + mbarrier）和 AMD MI300X（s_waitcnt、lgkmcnt）。[[Flash-Attention]] kernel 只要 68 行 Python，对比手写 840 行 CUDA。

## 关键结果

- H100 上 [[Flash-Attention]]：平均 **1.07× 超过 [[FlashAttention-3-NeurIPS24|FlashAttention-3]]**（最高 2.18×），1.82× 超过 PyTorch（[[FlashAttention-2-ICLR24|FA2]]），1.36× 超过 Triton。
- MatMul：追平 cuBLAS（1.06×），超过 PyTorch 1.24×、Ladder 2.07×。
- 低比特 MatMul（WFP4AFP16）：超过 PyTorch+bitsandbytes **3.92×**（dequant 阶段带来更深流水，空间更大）。
- Mamba2 ChunkScan / ChunkState：平均 **1.71×/1.98×** 超过手写 Triton（最高 2.59×）。
- 端到端：LLaMA3-8B/70B FP16 下比 vLLM 快 1.10×，比 TensorRT 快 1.28×；WFP4AFP16 下比 vLLM 快 2.16×。
- AMD MI300X 上同样的抽象也能直接工作。
- 代码开源：https://github.com/tile-ai/tilelang

## 相关

- **相关概念**：[[Flash-Attention]]、Tiling、Tensor-Cores、Warp-Specialization、Operator-Fusion
- **同类系统**：Triton、TVM、Ladder、CUTLASS、TensorRT
- **同会议**：[[OSDI-2025]]
