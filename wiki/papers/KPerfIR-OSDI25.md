---
type: paper
name: KPerfIR
full_title: "KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads"
authors: [Yue Guan, Yuanwei Fang, Keren Zhou, Corbin Robeck, Manman Ren, et al.]
venue: OSDI
year: 2025
tags: [gpu-profiling, compiler, mlir, triton, ai-systems]
source_pdf: "[[osdi25-guan.pdf]]"
source_md: "[[osdi25-guan]]"
---

# KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads (OSDI 2025)

> **一句话总结**：把 GPU 性能剖析当作 MLIR 编译 pass 做，在 Triton 里插入 IR 级计时与事件记录，基于此实现区域级 intra-kernel timing 工具，在 [[FlashAttention-3-NeurIPS24|FA3]] 等现代 kernel 上以 8.2% overhead、2% 误差驱动 warp specialization 重叠优化。

## 问题

现代 AI 编译器（Triton/MLIR）已经把 GEMM、softmax、[[Flash-Attention]] 等算子从高级框架下沉到 GPU 后端，但是配套的性能剖析工具链和编译器完全割裂：NCU、RocTracer、NvBit 等 profiler 工作在机器码或硬件计数器层，看不到 loop structure、warp specialization、software pipelining 等编译器语义。这导致两个痛点：(1) 开发者无法把 profile 指标精确归因到 IR 里的 region 或 loop iteration；(2) 像 [[FlashAttention-3-NeurIPS24|FA3]] 这类依赖 warp specialization 的 kernel，其 producer-consumer 在不同 warp-group 间的 overlap 行为没有工具能细粒度可视化。同时 autotune 类编译 pass 需要 feedback，也只能依赖外部独立 profiler 协同，loop 闭合代价高。

## 核心方法

KPerfIR 的核心立场：性能工具应该以编译 pass 的形式组合，而不是外挂。作者在 Triton 的 MLIR dialect 栈上新增两层 IR——高层 `KPerfIR`（包含 `RecordOp` 这一位置标记）和平台无关但 GPU 相关的 `KPerfGPUIR`（`InitOp`、`ReadCounterOp`、`StoreCounterOp`、`FinalizeOp`），再在 LLVM IR 层塞入 `startInstrumentationOp`/`stopInstrumentationOp` 负责最底层 timestamp/memory 分析。`RecordOp` 在下降时被 lowering pass 根据 `MetricType`（clock 等）、`Granularity`（warp-group/warp/thread）、`BufferStrategy`（circular/flush）展开成具体的读计数器+写缓冲区序列，计数器值走 stack-allocated index + shared memory 循环缓冲区，kernel 结束时 `FinalizeOp` 把数据 flush 到 global scratch。

作者还在这套基础设施上搭了一个 region-based timing 工具：为每个 warp-group 维护 8-byte record（START/END flag + 32-bit 时间戳），shared memory 做环形缓冲只保留尾部记录（生产 kernel 只有 1-4 KB shared mem 余量），并提出 trace replay 后处理——针对异步指令的 overhead 插入两个 START record 抵消测量误差，恢复出准确的 $T_{wait}$ 和 $T_{exe}$。这个工具是 [[FlashAttention-3-NeurIPS24|FA3]] 优化的眼睛：它暴露出 baseline 里 producer/consumer 的空转 bubble，作者据此改写 overlapping 策略（调整 GEMM1 与 softmax 的 region 顺序）并引入 performance model 预测新排布的效率。

## 关键结果

- 性能剖析开销 8.2%（平均），测量相对误差 2%
- 在 [[FlashAttention-3-NeurIPS24|FA3]] kernel 上基于 profile 指导的重叠优化可定位 idle bubble 并指导 producer-consumer 排布调整
- 支持 Nvidia（PTX）和 AMD（amdgcn）双后端，AMD 路径为避免指令缓存抖动采用 collaborative store 策略
- 比 MosaicGPU profiler（PTX 级）、TK timing interface（Nvidia-only，耦合 DSL）都更通用，是首个 region-based intra-kernel GPU timing 工具

## 相关

- **相关概念**：[[Flash-Attention]]、[[Tensor-Parallelism]]
- **同类系统/工具**：[[Neutrino-OSDI25]]（同会议，另一个 GPU profiler，走 assembly-level probing 路线，与 KPerfIR 编译器 pass 路线形成对比）
- **同会议**：[[OSDI-2025]]
