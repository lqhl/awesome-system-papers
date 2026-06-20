---
type: paper
name: KPerfIR
full_title: "KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads"
authors: [Yue Guan, Yuanwei Fang, Keren Zhou, Corbin Robeck, Manman Ren, et al.]
venue: OSDI
year: 2025
tags: [gpu-profiling, compiler, triton, mlir, ai-workloads]
source_pdf: "[[osdi25-guan.pdf]]"
source_md: "[[osdi25-guan]]"
---

# KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads (OSDI 2025)

> **一句话总结**：KPerfIR 把 profiling 做成 Triton/MLIR 上的可组合 compiler pass，示范 region-based timing 工具开销 **8.2%**、测量误差 **2%**，并借 FA3 case study 用洞察驱动 pass 使 Triton-FA3 再快 **24.1%**、超手工 FA3 **7.6%**。

## 问题与动机

[[Flash-Attention|FlashAttention]]-3 等 Hopper kernel 需 warp specialization、TMA pipeline 等精细重叠，但 NCU/RocTracer 等 **与编译器脱节**，缺少 loop/region 语义，难以指导 compiler pass 或反馈 auto-tuning。Mosaic/TK 仅在 PTX/DSL 层局部实现，不可复用、难跨 AMD/NVIDIA。

## 关键观察 / 隐含假设

- **观察 1**：现代 AI 编译栈（Triton→MLIR dialect）是 profiler 与 optimizer 共享的「语义总线」；IR 级插桩可关联 pipeline stage 与 framework op。
  - **依赖假设**：开发者主要使用 Triton/MLIR 路径（或愿迁移）。
  - **可能失效场景**：纯 cuBLAS 闭源 kernel、无 IR 的手写 SASS。
- **观察 2**：SWP/WS 重叠优劣取决于 stage 划分与 barrier 放置，聚合 counter 无法定位 idle bubble。
  - **依赖假设**：region-based timestamp + trace replay 可修正插桩扰动。
  - **证据强度**：强——FA3 case 24.1% 提升。
- **假设 1**：IR 插桩对底层 instruction reorder 干扰可控（<2% 额外退化）。
  - **证据强度**：强——Tbl.5 理论 vs 实际 1.02×。

## 核心方法

**KPerfIR 基础设施**：multi-level IR instrumentation；profiling 实现为 pass，可与优化 pass 同 pipeline 交换语义与指标。

**示范工具 region-based timing**：在 TTIR/TTGIR 等区域插桩，circular buffer 存 timestamp，replay 修正偏差；支持 NVIDIA+AMD。

**FA3 案例**：profiling 发现 bubble → 新 overlapping pass + performance model → 改进 Triton-FA3。

## 设计取舍

- **取舍 1**：绑定 Triton 生态首发，换深度与可编程性；非 universal GPU profiler。
- **取舍 2**：shared memory circular buffer 限制 profile 深度，换低开销。
- **边界条件**：极多 region 时仍可能 >15% 开销（三阶段 SWP GEMM）。

## 实验与结果

- 开销：latency ~8.2%（多数 <10%）；测量误差 ~2%；寄存器平均 +4.11。
- FA3：Triton 基线 +24.1% vs vanilla Triton-FA3；+7.6% vs 最佳手工 FA3。
- SWP GEMM 三阶段：开销 <15%；SMEM 仍余 10.9KB。

## Critical Analysis

### 论证链条

编译器与 profiler 割裂 → IR-centric 工具 → 可编程 region timing → 指导 pass → FA3 性能提升。链条在 Triton FA3 闭合；其他 frontend（纯 CUDA）需额外 dialect 支持。

### 假设压力测试

- 生产 kernel 若不经 Triton，KPerfIR 生态价值下降。
- IR 插桩与激进 compiler opt 组合可能偶发更大扰动。
- 与 [[Neutrino]] 汇编级探针互补但重叠边界未清晰。

### 实验可信度

FA3 案例深入；overhead 与 accuracy 量化好。baseline 含手工 FA3 公平。缺大规模 operator zoo 自动回归。

### 系统性缺陷

论文未讨论：多 GPU/multi-stream 时间线、生产环境默认开启 profiling 的安全策略。

## 局限与 Future Work

- **局限 1**：首发绑定 Triton；非 IR 路径覆盖弱。
- **局限 2**：极复杂 kernel 开销上界 ~15%。
- **Future work 1**：更多 pass（memory conflict、TMA overlap）插件化。
- **Future work 2**：与 [[PipeThreader]]/auto-tuning 闭环集成。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、Software Pipelining
- **同类系统**：NCU、CUPTI、Mosaic Profiler、[[Neutrino]]
- **同会议**：[[OSDI-2025]]