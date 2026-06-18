---
type: paper
name: EventTensor
full_title: "Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel"
authors: [Hongyi Jin, Bohan Hou, Guanjie Wang, Ruihang Lai, Jinqi Chen, et al.]
venue: MLSys
year: 2026
tags: [compiler, megakernel, llm-inference, moe, gpu-scheduling]
source_pdf: "[[07e1cd7dca89a1678042477183b7ac3f.pdf]]"
source_md: "[[07e1cd7dca89a1678042477183b7ac3f]]"
---

# Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel (MLSys 2026)

> **一句话总结**：把 GPU 同步事件升为一等公民的多维 Event Tensor（symbolic shape + data-dependent 索引），ETC 编译器生成动态 megakernel，GEMM+Reduce-Scatter 融合 1.40×、MoE 层 1.23×、低 batch 端到端 decode 比 [[vLLM]] 快 1.48×，engine warmup 35 s vs vLLM 123 s（3.5×）。

## 问题

LLM 推理两大系统瓶颈：（1）kernel launch 5–10 µs，快 kernel 仅 2 µs；（2）kernel 边界粗同步阻断可重叠的 inter-kernel 并行。CUDA Graph 只消 launch overhead；手写 megakernel（ThunderKittens 等）难扛 **shape dynamism**（[[Continuous-Batching]] 变 batch）与 **data-dependent dynamism**（[[MoE]] 路由决定 task 依赖），且编程/维护成本极高。

## 核心方法

**Event Tensor**：event（SM 级 task 完成）组织成多维 tensor，元素带 wait count，支持 `notify()`/`wait()`。升成 compiler IR 一等对象，复用 symbolic shape（batch B 等）与 index 表达式。

- **Shape dynamism**：一套模板 runtime 实例化，无需重编译或 CUDA Graph 重采集（真 AOT）
- **Data-dependent dynamism**：`topk` 驱动 event update；`exp_indptr` 前缀和驱动 variable-count task trigger（MoE GroupGEMM）

**ETC 编译器**（Apache TVM passes）：
- **Static scheduling**：预计算 per-SM 队列 + counter semaphore，适合 GEMM+All-Gather 等可预测 overlap
- **Dynamic scheduling**：GPU 上 atomic push/pop task queue，适合 MoE 不规则路由与通信抖动
- Event Tensor 降为 integer tensor + atomic notify/wait，runtime 无需 materialize 整张 task graph

已并入某主流开源 serving 系统。

## 关键结果

- GEMM + Reduce-Scatter（8×B200，TP=8）：相对 cuBLAS+NCCL 最高 **1.40×**
- Qwen3-30B-A3B MoE 整层（单 B200）：相对 Triton/FlashInfer 最高 **1.23×**（1024 tokens）
- 低 batch serving decode TPOT：Qwen3-30B-A3B batch=1 比 vLLM **1.48×**、比 [[SGLang]] **1.20×**；Qwen3-32B batch=1 比 vLLM **1.15×**
- Engine warmup（Qwen3-32B）：ETC **35 s** vs vLLM 123 s / SGLang 583 s

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Continuous-Batching]]、megakernel、CUDA Graph
- **同类系统**：[[vLLM]]、[[SGLang]]、Triton Distributed、ThunderKittens
- **同会议**：[[MLSys-2026]]