---
type: paper
name: EventTensor
full_title: "Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel"
authors: [Hongyi Jin, Bohan Hou, Guanjie Wang, Ruihang Lai, Jinqi Chen, et al.]
venue: MLSys
year: 2026
tags: [compiler, megakernel, llm-inference, moe, gpu-scheduling]
source_pdf: "[[07e1cd7dca891345f7ba84e9b0bc6f44.pdf]]"
source_md: "[[07e1cd7dca891345f7ba84e9b0bc6f44]]"
---

# Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel (MLSys 2026)

> **一句话总结**：把 GPU 同步事件抽象成一等公民的多维 tensor（Event Tensor），用 symbolic shape 和 data-dependent 索引表达 megakernel 里 task 级的细粒度依赖，配套的 ETC 编译器对 [[vLLM]]/[[SGLang]] GEMM+Reduce-Scatter 达 1.40× 加速、MoE 1.23×，同时 engine warmup 降 3.5×。

## 问题

现代 GPU 工作负载（尤其 LLM 推理）有两大瓶颈：
1. **kernel launch 开销**：PyTorch 每个 kernel 5–10 µs launch latency，最快的 kernel 只跑 2 µs，开销占主导
2. **kernel 边界的粗粒度同步**：后续 kernel 只依赖前一 kernel 的子集结果，本可重叠但被边界阻塞

CUDA Graph 只解决了 launch overhead，保留 kernel 边界。现有 megakernel（ThunderKittens、Mirage 等）手写 fuse 出持久 kernel 暴露 inter-kernel 并行，但扛不住两种 dynamism：
- **shape dynamism**：continuous batching 变 batch size，每种 shape 都重编译成本高
- **data-dependent dynamism**：[[MoE]] 路由、token grouping、GroupGEMM 依赖运行时 topk，静态 task graph 表达不了

且手写 megakernel 需逐个推理 task 依赖，错误多、维护难。

## 核心方法

**Event Tensor 抽象**：把 event（SM 粒度 task 集合的完成）组织成多维 tensor，每个元素带 wait count。支持 `E[i].notify()` / `E[i].wait()`。关键创新是把这些 semaphore 升成 compiler IR 的一等 tensor 对象，复用已有的 symbolic shape 支持。

- **Shape dynamism**：Event Tensor 维度允许 symbolic（如 batch B），一套模板 runtime 按实际值实例化，不需要重编译或 CUDA Graph 重采集
- **Data-dependent dynamism**：两个机制处理 [[MoE]]
  - *Data-Dependent Event Update*：MoE 里 grouping tile 按 runtime 的 `topk` 更新对应 expert event
  - *Data-Dependent Task Triggering*：`exp_indptr` 前缀和决定每个 expert 触发多少 GroupGEMM tile

**ETC 编译器**两种 scheduling transformation：
- *Static scheduling*：编译期把 task 分配到 SM 执行队列，用 counter-based semaphore + spin-wait 同步，开销最小
- *Dynamic scheduling*：GPU 上轻量级 task scheduler，event 触发时 atomic push consumer task 进共享队列，SM 空闲 pop 执行，天然负载均衡，适合不可预测任务

Event Tensor lowering 成简单 integer tensor，`notify()` = atomic decrement，`wait()` = spin on zero，runtime 极薄。

## 关键结果

对比基线都是重度优化过的 [[vLLM]]、[[SGLang]]（带 CUDA Graph / PDL / torch.compile）：

- Tensor-parallel GEMM+Reduce-Scatter 融合：**最多 1.40× 加速**
- MoE GroupGEMM 等 data-dependent 工作负载：**最多 1.23×** vs 专用 library
- Dynamic-shape、低 batch 推理：匹配或超越基线
- **engine warmup 开销降 3.5×**（真正 AOT，消除运行时重编译/CUDA Graph 重采集）
- 已集成到主流开源推理系统

## 相关

- **相关概念**：[[MoE]]、[[Tensor-Parallelism]]、[[Attention]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Mirage、ThunderKittens（Spector et al. 2025）
- **同会议**：[[MLSys-2026]]
