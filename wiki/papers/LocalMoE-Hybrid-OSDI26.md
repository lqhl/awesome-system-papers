---
type: paper
name: LocalMoE-Hybrid
full_title: "Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design"
authors: [Wenxin Wang, Yule Hou, Yu Ji, Peng Qu, Youhui Zhang]
venue: OSDI
year: 2026
tags: [llm-serving, mixture-of-experts, cpu-gpu, local-inference, expert-parallelism]
source_pdf: "[[osdi26-wang-wenxin.pdf]]"
source_md: "[[osdi26-wang-wenxin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用 CPU–GPU 混合设计实现本地 MoE 云级 SLO（OSDI 2026）

> **原题**：Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design

> **一句话总结**：系统以stream-loading prefill、双GPU SmallEP、节点内P/D disaggregation与AVX-512 FP8 GEMV协同，让完整FP8 DeepSeek-V3在commodity dual-socket CPU+consumer GPU达到21.5 tok/s，INT4达28 tok/s，32K prompt TTFT少于30秒。

## 问题与动机

本地MoE通常将routed experts放CPU、attention/shared expert放GPU，但prefill因CPU expert streaming慢，decode低于20 tok/s，mixed P/D concurrency更差；为勉强运行还常量化/蒸馏/改routing，损失模型质量。目标是在有限VRAM但大system DRAM的平台运行原始precision/model。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

Stream-Loading Prefill按layer/expert把weights流式送GPU，并与dense compute重叠，使GPU执行高吞吐GEMM；Distributed SLP用SmallEP在两张RTX 5090分配activated experts。节点内[[Disaggregation|P/D disaggregation]]共享zero-copy weights，dual-batch把[[Attention|attention]]与[[MoE|MoE]]重叠，避免两套模型副本。Decode端用AVX-512 optimized [[Quantization|FP8]] GEMV与fine-grained CPU parallelism直接执行sparse experts。

依赖dual-socket高memory bandwidth、AVX-512 FP8能力与consumer GPU；[[NUMA|NUMA]] placement和[[PCIe|PCIe]] contention是核心。

## 实验与结果

- 单GPU SLP达1,200 prefill tok/s，32K prompt在30秒内；双RTX 5090 DSLP达1,800 tok/s、45K/30s。
- P/D disaggregation使concurrent latency increase少于15%、throughput +50%。
- FP8 CPU kernel latency低4×–5×；INT4 DeepSeek-V3 decode 28 tok/s，完整FP8 V3为21.5 tok/s。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

论文以多个专门优化共同达到“SLO”，更像完整recipe而非单一抽象；consumer platform可及性有价值。cloud-grade定义选取30s TTFT/20 tok/s，不代表cloud multi-tenant availability/tail。双socket+RTX5090仍昂贵且高功耗，成本/energy/token未充分对比租云。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 报告P99、energy/token、不同DDR/PCIe/CPU generation。
- 自动选择precision、SLP/DSLP与P/D资源以满足用户SLO。
- 扩展更多MoE routing/top-k与multi-user fairness。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[Prefill-Decode-Disaggregation]]、[[Expert-Parallelism]]、[[CPU-GPU-Offloading]]
- **相关系统**：[[DeepSeek-V3]]、[[KTransformers]]
- **同会议**：[[OSDI-2026]]
