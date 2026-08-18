---
type: paper
name: Axe
full_title: "Axe: A Simple Unified Layout Abstraction for Machine Learning Compilers"
authors: [Bohan Hou, Hongyi Jin, Guanjie Wang, Jinqi Chen, Yaxing Cai, Lijie Yang, Zihao Ye, Yaoyao Ding, Ruihang Lai, Tianqi Chen]
venue: arXiv
year: 2026
tags: [ml-compiler, tensor-layout, gpu, distributed-computing, dsl, area/ai-infra]
source_pdf: "[[arxiv26-hou-axe.pdf]]"
source_md: "[[arxiv26-hou-axe]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# Axe：统一机器学习编译器布局抽象（arXiv 2026）

> **原题**：Axe: A Simple Unified Layout Abstraction for Machine Learning Compilers

> **一句话总结**：Axe 用带名字的物理 axes 和 `(Shard, Replica, Offset)` 映射统一寄存器/线程/内存 tile、跨 GPU sharding 与 accelerator-native memory，再据此构建多粒度 DSL；在 B200 [[MoE|MoE]]、8×B200 GEMM+Reduce-Scatter 和 Trainium-1 [[Attention|MHA]] 上相对强库最高分别提高 1.32×、1.40×、1.44×。

## 问题与动机

现有 layout abstraction 往往只覆盖单一层级：CuTe 精细表达 thread/register，Triton 偏 CTA collective，DTensor/parallel IR 表达 device mesh，专用 accelerator 又有多维 SRAM。跨层优化必须在互不兼容的 layout 语言间重复编码，阻碍 [[Tensor-Compilation]] 对单 kernel、分布式 collective 和异构 backend 的统一推理（§1）。

## 关键观察 / 隐含假设

- **观察 1：多数 placement 都可分解为 shard、replica 与 offset。** Axe 将 logical coordinate 映到 named axes（lane、warp、memory、gpuid 等），同一代数能表达 tensor-core tile、2×2 GPU mesh 与 Blackwell tensor memory（图 1–2）。
  - **依赖假设**：目标映射是规则 affine/strided set-valued map；高度 data-dependent 或 irregular layout 需要额外机制。
- **观察 2：layout semantics 足够明确时，compiler 可在 thread-local control 与 collective operator 间选择 schedule。** 用户保留必要的低层控制，标准 copy/GEMM/collective 交给 library-style operator lowering（图 3–8）。
  - **可能失效场景**：operator library 未覆盖的新 ISA 仍需专家写 schedule；“统一抽象”不会自动生成最优实现。
- **假设 1：跨 NVIDIA GPU、multi-GPU 与 Trainium 的三个 case 能证明 portability。**
  - **证据强度**：中；后端多样，但 workload 仍是少量 curated kernels/layers。

## 核心方法

Axe layout 是 logical index 到 named physical-axis coordinates 的集合映射：有序 D iters 做 sharding，无序 R iters 做 replication，O 指定固定资源 offset。canonicalize、group、tile、slice 等 operator 允许 compiler 比较和变换布局（§2）。

Axe DSL 提供 kernel/CTA/warpgroup/warp/thread execution scopes、携带 layout 的 tensor，以及带多种 schedule 的 collective operators。compiler 根据 input/output region 和 axes 选择 copy、GEMM、collective lowering，并生成 runtime layout consistency check（§3）。

## 设计取舍

- **统一代数换学习成本**：比多套 layout API 一致，但 named-axis set mapping 仍需要底层硬件知识。
- **operator abstraction 换 library completeness**：常见 pattern 简洁；新 intrinsic 性能取决于 schedule 维护。
- **显式 scope 换自动化**：可写 peak kernel，却没有从高层 model graph 完全自动生成 Axe program。
- **边界条件**：主结果集中于 NVIDIA B200/多 GPU 与 Trainium-1，未覆盖 AMD、动态 shape serving 和完整训练图。

## 实验与结果

- B200 Qwen3 MoE layer 相对 FlashInfer/[[SGLang|SGLang]] 最高 1.32×/1.23×（§5）。
- 8×B200 GEMM+Reduce-Scatter 相对 cuBLAS+NCCL 与 Triton-Distributed 最高 1.40×（§5）。
- Trainium-1 MHA 相对 vendor libraries 最高 1.44×，用于支持跨 accelerator 表达力（§5）。
- 论文以多个 kernel case 展示相对 hand-tuned 实现的代码缩减，但没有统一报告 end-to-end model latency 或开发人时。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Axe 能统一多级 layout 表达 | 图 1–2 与 formal operators | 规则 tensor mapping | 强 |
| Axe DSL 可接近/超过强库性能 | §5 三类硬件结果最高 1.23–1.44× | curated kernels/layers | 中到强 |
| 抽象降低完整 ML 系统开发成本 | 代码示例与复用设计 | 无人时、维护或大型应用实验 | 弱 |

## 批判性分析

### 论证链条

统一 layout 的表达例子与多后端 performance case 支持核心 abstraction；但“简单”和“降低开发成本”主要由 API/代码展示支撑，没有用户研究、porting effort 或 compiler complexity 对照。

### 假设压力测试

MoE routing、ragged attention、sparse gather 和 runtime-dependent placement 可能无法静态归约为规则 axes；需要与 [[EventTensor-MLSys26]] 类动态 dependency abstraction 组合。

### 实验可信度

baseline 包含 FlashInfer/SGLang、cuBLAS+NCCL、Triton-Distributed 与 vendor library，强度较好；但 headline 是各 case 最大值，缺完整 shape distribution、compile time 与端到端 SLO。

### 系统性缺陷

layout/runtime check、schedule dispatch、binary cache、fault handling 和跨版本 ABI 未充分讨论。统一 IR 还可能成为所有 backend 的新耦合点。

## 局限与后续工作

- **局限 1**：没有证明从标准 PyTorch/model graph 自动产生高质量 Axe program。
- **后续工作 1**：在真实 serving/training graph 上测 compile time、coverage、端到端 latency 与 porting LOC。
- **后续工作 2**：扩展 data-dependent/ragged layout，并与 dynamic megakernel scheduling 联合验证。

## 相关

- **相关概念**：[[Tensor-Compilation]]、[[Data-Parallelism]]、[[Expert-Parallelism]]、[[NCCL]]
- **相关工作**：[[EventTensor-MLSys26]]、[[MPK-OSDI26]]、[[PyTorch]]、[[Triton]]
