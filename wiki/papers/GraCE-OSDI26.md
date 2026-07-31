---
type: paper
name: GraCE
full_title: "GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads"
authors: [Abhishek Ghosh, Ajay Nayak, Ashish Panwar, Arkaprava Basu]
venue: OSDI
year: 2026
tags: [ml-systems, gpu, cuda-graphs, compiler, pytorch]
source_pdf: "[[osdi26-ghosh.pdf]]"
source_md: "[[osdi26-ghosh]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用编译器释放 CUDA Graph 性能（OSDI 2026）

> **原题**：GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads

> **一句话总结**：GraCE 观察到 CUDA Graph 的实际瓶颈不是 API 缺失，而是高层 PyTorch 程序的 CPU tensor/scalar、每次 replay 的大 tensor placeholder copy，以及约四分之一 graph 的负收益；它通过 IR 重写、pointer indirection 和 profile-guided selective deployment，在 25 个 H100 workload 上较 PyTorch2-CG 平均快 29%、最高 3.36 倍且不产生 regression。

## 问题与动机

现代 ML iteration 发射数百个仅运行数微秒的 kernel，而 CPU launch 本身约 5–10µs。CUDA Graph（CG）把一组 kernel 作为 DAG 一次 dispatch，理论上能消除 launch gap；但 capture 会按值固化参数，禁止同步 memcpy/malloc，replay 若参数变化可能 silent corruption 或 crash。

PyTorch2 的保守处理会放弃含 CPU scalar/tensor 的整个 FxGraph；即使 capture 成功，也把新 tensor 内容拷到静态 placeholder，每轮成本最多占 CG time 的 24%。更反常的是 116 个候选 graph 中 29 个（25%）启用后变慢，最差退化 397%，说明“能 capture”不等于“应该部署”。

## 关键观察 / 隐含假设

- **观察 1：一处高层 data placement 决策可阻止数百 kernel 被 capture。** XLNET-I 只因一个 CPU tensor 使 413 kernels 全部失去 CG；小改动后 XLNET/ST 分别快 3.17/2.28 倍（图 3、表 2）。
  - **依赖假设**：CPU tensor 移到 GPU 不改变可观察语义、lifetime 或 host-side consumer。
  - **可能失效场景**：input-dependent CPU update、host I/O、显存压力或 tensor 被 CPU 与 GPU 共同使用。
- **观察 2：mutable parameter 不必复制 data，只需稳定地址中的 pointer。** pointer-to-pointer 将最高 1GB replay copy 降到数百 bytes（表 3）。
  - **依赖假设**：kernel 可在开头 dereference，或 vendor graph node parameter 可由 prelude 安全更新；额外 H2D pointer copy 小于 D2D tensor copy。
- **观察 3：CG replay 存在 parameter copy、RNG reset 与 allocator/[[Garbage-Collection|GC]] fixed overhead。** 29/116 graph 负收益，必须 profile 而非 blanket enable（图 4）。
  - **依赖假设**：compile-time sample 的 cost/benefit 能代表 production shape、batch 与 contention。
- **假设 1：ML workload 的重复性足以摊薄最高 506s compilation。**
  - **证据强度**：中；steady [[LLM-Inference|model serving]]/training 成立，dynamic shape/ad-hoc job 不一定。

## 核心方法

[[CUDA-Graph|CUDA-Graph]]-aware Code Transformation（CGCT）从 InductorIR 中定位 CPU scalar、CPU↔GPU copy 或 CPU output，再借 debug mapping 回溯 TorchIR/Dynamo bytecode：把 tensor placement 改为 CUDA、将 memcpy hoist 到 constructor/capture 外，并重新 lower。目标是在不改源码的情况下扩大 entire-FxGraph capture coverage（图 6–7）。

Parameter Indirection（PI）为 mutable tensor 参数分配稳定 pointer placeholder，每轮只 H2D copy 8-byte pointer。Triton JIT kernel 由 LLVM/PTX pass 把 signature 改成 pointer-to-pointer 并在入口 dereference；cuBLAS 等不可修改 binary 则在 graph 前加入 prelude kernel，用 CUDA graph node update API 改 vendor kernel 参数（图 8–9）。

Selective CUDA Graph（SCG）在 compile/capture slow path 同时 profile graph 与普通 module 的 replay cost，只缓存有正收益方案。这样 fast path 无在线决策，也避免 EOS 这类 CG overhead 主导的 workload。GraCE 作为 PyTorch2 Dynamo/Inductor 扩展，无需 programmer annotation。

## 设计取舍

- **覆盖率换显存/语义风险**：把 CPU tensor 常驻 GPU 可开启 CG，却增加显存并可能改变 host-observed update timing。
- **少 data copy 换一次 indirection**：JIT rewrite 很轻；vendor prelude 参数多时超过 10µs，可能不如原 copy。
- **无 regression 换 compilation/profile 成本**：编译平均 2.21 倍、最高 3.2 倍，绝对最多 506s，peak compile memory 高 12%。
- **边界条件**：短 kernel、多 replay、静态 shape和高性能 GPU 上最好；长 compute kernel、small tensor、dynamic control/shape 或短生命周期 job 收益小。

## 实验与结果

- H100 上 25 个 TorchBench/HuggingFace/TIMM training/inference workload、每项 100 个不同 input 的 iteration 均值中，GraCE 较 PyTorch2-CG 平均快 29%、最高 3.36 倍；相对 No-CG 对每个应用至少不差于 PyTorch2 两种选择（图 10）。
- PyTorch2-CG 有四项至少慢 3%，EOS 最差慢 29%；SCG 在 123 个候选中启用 97 个，VM 禁用 17/21 graph 后整体再快 6%（图 10–11）。
- CGCT 使 XLNET-I/MMC/ST 较 PyTorch2-CG 快 3.14/2.31/2 倍；DALLE2 从 1.9 倍提升到 2.72 倍，部分 workload CG kernel coverage 超过 99%（表 2）。
- PI 将 MTCG-T/DGPT2/STCLM/DMLM 的 1GB/953MB/850MB/548MB copy 降至 312/136/136/136B，TKE 和 DR-I 分别快 23%/18%（表 3）。
- 4×H100 tensor parallel 下 GraCE 相对 PyTorch2-CG 平均快 75%、最高 3.56 倍；XLNET TP-4 相对 No-CG 达 3.48 倍（图 12）。A6000 上平均相对 PyTorch2-CG 仍为 1.18 倍且无 regression。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 编译器可显著扩大 CG 覆盖并提速 | 图 10、表 2：平均 +29%，最高 3.36倍 | 25 个 CG-sensitive workload、H100 | 强 |
| parameter indirection 消除 replay 大 copy | 表 3：最高约 1GB 降到 312B | mutable tensor 参数；vendor kernel 需 prelude | 强 |
| selective deployment 避免 CG regression | 图 10–11：25项均不差，EOS 避免 -29% | compile-time profile 与固定 input configuration | 中 |
| GPU 越快/TP 越宽，launch optimization 越重要 | 图 12：4×H100 最高 3.56倍、平均 +75% | 四个 TP workload、单机 NVLink | 中 |

## 批判性分析

### 论证链条

论文把“coverage、replay cost、是否值得”三个独立失败模式对应到 CGCT/PI/SCG，ablation 清楚。PyTorch2-No-CG 与 PyTorch2-CG 双 baseline 避免把禁用负收益 graph 伪装成新 speedup。主要外推是把每项固定配置的 100-run profile 视为真实 serving/training 的动态分布。

### 假设压力测试

dynamic batch/sequence/shape 会产生新 graph 或改变 cost model；SCG 旧决定可能失效。把 tensor 从 host 移到 device 可能增加 HBM pressure、改变 alias/lifetime 或令 CPU consumer 看到 stale value。PI 多一层 load，在 memory-latency sensitive kernel 或小参数上可能反而慢，论文也观察到 DALLE2 无收益。

### 实验可信度

25 个真实 suite workload、training/inference、H100/A6000 与 TP=1/2/4，且使用不同 input 做 correctness-sensitive replay，覆盖好。选择的是“对 CG 敏感”的子集，不代表整个 PyTorch workload 的 aggregate geomean；未报告数值输出 differential、dynamic shape recompilation rate、multi-tenant GPU 或长时间 allocator fragmentation。

### 系统性缺陷

GraCE 跨 Dynamo、Inductor、Triton LLVM/PTX 和 CUDA runtime 多层修改，版本维护成本高。vendor prelude 依赖 graph node update 细节；bytecode/device-placement rewrite 的 correctness surface 较大。平均 2.21 倍编译时间会影响 notebook、autoscaling 和 frequently changing model。

## 局限与后续工作

- **局限 1**：主要评测固定 shape/configuration，dynamic control/shape 与频繁 recompilation 未覆盖。
- **局限 2**：收益来自 25 个 CG-sensitive workload，不能外推为全部 ML application。
- **后续工作 1**：用 production shape trace 在线检测 profile drift，以 regression rate、reprofile cost 和 P99 iteration latency 评估 adaptive SCG。
- **后续工作 2**：对 CGCT 做 alias/lifetime 与 host-observability proof，并以随机 input differential test 检查输出等价。
- **后续工作 3**：在 multi-tenant MIG/共享 GPU 上测量 HBM pressure、capture cache eviction 和 compile amortization break-even iterations。

## 相关

- **相关概念**：[[CUDA-Graphs]]、[[GPU-Kernel-Launch]]、[[Tensor-Parallelism]]、[[ML-Compiler]]
- **同类系统**：[[PyTorch]]、[[TorchInductor]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
