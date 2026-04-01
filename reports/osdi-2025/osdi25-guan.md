# KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads

**作者**：Yue Guan (UC San Diego), Yuanwei Fang (Meta), Keren Zhou (George Mason University / OpenAI), Corbin Robeck (Meta), Manman Ren (Meta), Zhongkai Yu (UC San Diego), Yufei Ding (UC San Diego / Meta), Adnan Aziz (Meta)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/guan
**源文件**：[osdi25-guan.pdf](../../papers/osdi-2025/osdi25-guan.pdf)

---

## 一、背景

AI 编译器（如 Triton）在连接高层 ML 框架算子与底层 GPU 机器码方面日益重要。GPU 架构快速迭代——NVIDIA Hopper 引入了第 5 代 Tensor Core 和 TMA，AMD 也有类似的加速单元——使得高性能 kernel 开发越来越依赖复杂的 tiling、software pipelining 和 warp specialization 等技术。在此背景下，性能分析工具（profiler）对识别瓶颈、指导编译器优化至关重要。

然而，现有 GPU profiler（如 NCU、RocTracer、NSys）与编译器系统是割裂的：它们作为外部工具运行，缺乏对编译器 IR 语义的感知，无法提供与框架算子语义对齐的、细粒度的 intra-kernel 性能洞察。这种断裂严重制约了 AI 编译器和高性能算子的开发效率。

---

## 二、要解决的问题

1. **Profiler 与编译器脱节**：传统 profiler 独立于编译流程，无法获取循环结构、region 边界等编译器语义信息，难以将性能指标精确归因到高层程序行为（如 software pipelining 各 stage 的重叠情况）。
2. **缺乏 intra-kernel 细粒度 profiling**：现有工具提供的是聚合结果（kernel 级别），无法追踪 warp group 之间的异步行为、pipeline stage 的演进和 overlapping 效率。
3. **工具不可复用、不可移植**：已有 profiling 方案（如 Mosaic GPU profiler 在 PTX 层插桩，ThunderKitten 绑定自身 DSL）缺乏跨框架和跨平台（NVIDIA/AMD）的可移植性。
4. **编译器优化 pass 缺少性能反馈**：auto-tuning 等优化技术需要精确的性能数据来指导决策，但编译器与 profiler 之间没有原生的反馈机制。

---

## 三、洞察与设计

**关键洞察**：现有 profiler 与编译器系统的隔离是根本问题——将 profiling 能力直接集成到编译器 IR 中，以 compiler pass 的形式实现 profiling 工具，就能同时获得程序语义感知、可编程性和跨平台可移植性。

基于此洞察，KPerfIR 设计为一套多层级的 MLIR dialect，集成到 Triton 编译器中：

- **多层 IR 设计**：
  - **KPerfIR（高层）**：定义 `RecordOp` 作为通用程序标记，语义解释由 lowering pass 配置决定。开发者在 TTIR/TTGIR 层标注关注区域。
  - **KPerfGPUIR（中层）**：vendor-independent 但 GPU-specific 的操作，如 `ReadCounterOp`（读硬件计数器）、`StoreCounterOp`（存入 buffer）、`InitOp`/`FinalizeOp`（资源管理）。
  - **LLVM IR（底层）**：`startInstrumentationOp`/`stopInstrumentationOp` 控制底层库插桩，链接高层数据对象到硬件寄存器。

- **三大设计优势**：
  1. **可编程性**：profiling 工具可以访问 IR 语义（循环结构、warp 分配等），捕获 software pipelining 跨 iteration 的演进行为。
  2. **Profile-driven 编译优化**：profiling pass 直接与 optimization pass 交互，形成闭环反馈。
  3. **可复用性**：工具在共享的高层 IR 上实现，可无缝 lower 到 NVIDIA 和 AMD 后端。

- **接口设计**：提供 command-line API（全局插桩）和 Python API（`KPerfIR.patch()`/`unpatch()` 选择性插桩），支持第三方工具通过回调注册处理 profiling 数据。

---

## 四、实现细节

**集成于 Triton 编译器**，基于 MLIR 实现，代码已开源在 Triton 仓库的 `third_party/proton/dialect`。

**核心 IR 操作**（见 Table 2）：
- `RecordOp`：高层标记，输入 name + isStart
- `InitOp`：使用 stack allocation 分配 buffer index（利用 LLVM register promotion 优化）
- `ReadCounterOp`：读取硬件性能计数器（NVIDIA `%clock`，AMD `S_MEMTIME` 低 32 位）
- `StoreCounterOp`：将计数器值存入 profiling buffer
- `FinalizeOp`：将 profiling 数据写回 global memory

**Lowering 流程**：KPerfIR → KPerfGPUIR → LLVM IR，通过 MLIR pass options（`BufferType`、`BufferStrategy`、`MetricType`、`Granularity`）控制具体生成的操作。

**Region-based Timing Tool**（showcase 工具）：
- **数据结构**：每条 record 8 字节（4B tag + 4B payload），tag 含 1 bit flag（START/END）+ 31 bit region ID（NVIDIA）或附加 12 bit 硬件签名（AMD）
- **Shared memory circular buffer**：按 warp group 划分不重叠的 record slot，使用循环覆盖策略平衡容量与精度（仅保留尾部迭代记录）。典型配置：64 slots = 0.5KB/SM
- **AMD 协作存储策略**：所有线程写同一 shared memory 位置以避免 thread divergence 导致的 instruction cache miss（最高 600 cycles 开销）
- **Trace Replay 后处理**：通过插入两个 START record（异步指令前后）+ 一个 END record（barrier 前），精确计算异步等待时间 $T_{wait} = CLK_2 - CLK_1$，消除 profiling 自身开销

**平台适配**：
- NVIDIA：硬件负责指令调度，PTX 基本保持插桩程序顺序，影响可忽略
- AMD：软件控制指令调度，提供三级配置：手动 KPerfIR hints、直接 amdgcn 插桩、显式 barrier mask 指定调度窗口

---

## 五、实验结果

**实验平台**：NVIDIA H100-HBM3 和 AMD MI300X，Triton 3.0.0 + LLVM 19.1

**Benchmark**：GEMM（SWP 2/3 stages）和 Flash-Attention 3（FA3，warp specialization）

| 指标 | 结果 |
|------|------|
| **Profiling 延迟开销** | 大多数 < 10%，最复杂的 3-stage SWP GEMM < 15%，平均约 8.2% |
| **每条 record 开销** | 3 条指令，约 33 cycles（NVIDIA H100） |
| **精度** | 理论 vs 实际性能偏差 < 2%（相对误差） |
| **Shared memory 占用** | 最密集工况（3-stage SWP GEMM）仍剩余 10.9KB 未使用空间 |

**FA3 优化案例**：
- 通过 region-based timing 发现 vanilla Triton-FA3 的 Load V stage 被 consumer warp group 的 arrival barrier 阻塞，导致 critical path 过长
- 将 V 的 arrival barrier 前移，解除 GEMM1 region 与 K tensor loading 的依赖
- 优化后性能：
  - 比 vanilla Triton-FA3 提升 **24.1%**
  - 比手工优化的 FA3 kernel（Shah et al.）提升 **7.6%**
- 性能模型预测：2-stage SWP 达 467.07 TFLOPS，vanilla FA3 达 526.97 TFLOPS，improved FA3 达 582.44 TFLOPS

---

## 六、批判性分析

1. **Vendor-specific counter 可见性受限**：论文在 Limitations 中提到了这一点，但轻描淡写。实际上 NCU 通过 privileged access 可获取大量未公开的硬件计数器（如 L2 cache hit rate、SM occupancy 细节等），这对性能分析至关重要。KPerfIR 只能读取 ISA 暴露的计数器（如 `%clock`），这意味着在很多实际调优场景中仍需依赖 vendor 工具，"替代"效果有限。

2. **FA3 案例的代表性问题**：论文的核心实验围绕单一 kernel（FA3）展开，且优化本质上是手动发现的 barrier 位置调整——这更像是一个 "profiler 帮助人找到了 bug" 的故事，而非展示系统性的自动化优化能力。论文虽然展示了性能模型，但并未实现真正的 auto-tuning 闭环。

3. **AMD 平台评估不足**：虽然论文声称支持 AMD MI300X，但 FA3 优化案例仅在 H100 上进行，AMD 平台只展示了 GEMM 的 overhead 数据。跨平台可移植性是论文的核心卖点之一，但缺乏对等的 AMD 端到端评估。

4. **Circular buffer 丢弃策略的隐含假设**：论文假设 "观察最近几个迭代足以识别瓶颈"，但这对 warmup 阶段、动态负载变化、或非稳态行为的分析可能不适用。论文未讨论何时应切换到 flush 策略。

5. **Overhead 数据的选择性呈现**：8.2% 是 "平均" 开销，但 Fig. 13 显示某些配置接近 15%。对于 production 环境的 always-on profiling 来说，这一开销可能不可接受，但论文未讨论采样模式或选择性开关机制。

6. **与 CUPTI/NVBit 的定位对比不充分**：论文将 KPerfIR 与 NCU、RocTracer 等对比，但忽略了 CUPTI 的 range profiling API 和 NVBit 的 binary instrumentation 在灵活性上的优势。Table 1 的对比过于简化。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴价值**：
- KPerfIR 展示了将 profiling 从 "外部工具" 转变为 "编译器原生能力" 的设计思路。这对 AI Infra 中日益复杂的 kernel 优化（如 fused attention、MoE routing kernel）具有重要参考价值——当 kernel 复杂到传统 profiler 的 kernel-level 粒度不再有用时，intra-kernel profiling 成为刚需。

**可迁移的技术**：
- **Multi-level IR instrumentation** 的思想可以迁移到其他 MLIR-based AI 编译器（如 XLA、IREE）中，为它们增加原生 profiling 能力。
- **Trace Replay 消除异步 profiling 误差** 的技巧（通过精心放置 record 点抵消 overhead）是一个通用技术，可用于任何涉及异步执行的性能分析场景。
- **Circular buffer 在 shared memory 中的 profiling 数据管理** 适用于所有 GPU kernel 内部 tracing 场景。

**值得跟进的 Future Work**：
1. **Profile-guided auto-tuning 闭环**：论文仅展示了手动分析 + 手动优化的流程。将 KPerfIR 的 profiling 数据自动反馈到 Triton 的 auto-tuning pass（如与 Ansor/MetaSchedule 结合），实现 overlapping 策略的自动选择（SWP vs WS），是最有价值的方向。
2. **Distributed kernel profiling**：论文在 Discussion 中提到支持分布式场景，但对 fused compute-communication kernel（如 Flux 风格的 kernel fusion）的 profiling 尚未实现。这对理解 LLM 训练中 all-reduce 与 computation 的 overlap 效率至关重要。
3. **推理场景的 dynamic batching profiling**：对于 vLLM 等推理框架中动态变化的 batch size 和 sequence length，如何在不同工况下自动切换 profiling 策略值得研究。

**最有价值的切入点**：基于 KPerfIR 实现 Triton 的 auto-tuning pass，特别是自动选择 attention kernel 的 overlapping 策略（SWP stage 数、WS producer/consumer 分配、barrier 放置位置），以替代目前手工调优的方式。

---

## 八、总结

KPerfIR 提出了将 GPU 性能分析工具集成到编译器 IR 中的新范式，通过多层 MLIR dialect 实现了可编程、可复用、跨平台的 intra-kernel profiling 基础设施。其核心贡献在于打通了编译器与 profiler 之间的语义鸿沟，使得 profiling 工具能够感知循环结构、warp 分配等程序语义。在 FA3 kernel 上的案例研究展示了该方法的实用价值（24.1% 性能提升）。主要局限在于 vendor-specific counter 的可见性受限、AMD 平台评估不足、以及尚未实现真正的自动化优化闭环。该工具适用于需要深入理解 GPU kernel 内部行为的 AI 编译器开发者和高性能算子作者。
