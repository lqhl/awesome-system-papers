# KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads

**作者**：Yue Guan (UC San Diego), Yuanwei Fang (Meta), Keren Zhou (George Mason University & OpenAI), Corbin Robeck (Meta), Manman Ren (Meta), Zhongkai Yu (UC San Diego), Yufei Ding (UC San Diego & Meta), Adnan Aziz (Meta)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, 2025, Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/guan
**源文件**：[osdi25-guan.pdf](../../papers/osdi-2025/osdi25-guan.pdf)

---

## 一、背景

随着 AI 编译器（Triton、TVM 等）的广泛采用，GPU kernel 开发的重心正从手工调优（cuBLAS、CUTLASS）向编译器自动优化转移。现代 GPU 架构（如 Hopper）引入了 Tensor Core、Tensor Memory Accelerator（TMA）等异构执行单元，实现高性能的关键在于精细的 overlapping 技术——即软件流水线（Software Pipelining, SWP）和 Warp Specialization（WS）。

然而，要分析这些复杂的 intra-kernel 行为，需要具备程序语义（循环结构、warp 分配、流水线阶段等）的 profiling 工具，而现有工具均无法提供此类能力。

---

## 二、要解决的问题

**核心矛盾**：现有 profiler（NCU、NSys、TorchProfiler 等）与编译器相互孤立，缺少对编译器 IR 的感知。

具体痛点：

1. **缺乏程序语义**：现有工具在 binary 层面工作，无法关联循环层级、warp 分组、流水线阶段等高层构造。例如，无法追踪 SWP 跨 iteration 的 overlap 演化过程。

2. **无法支持 profile-driven 编译优化**：自动调优（auto-tuning）、关键路径分析等编译 pass 需要可编程的性能反馈，但现有工具无法作为编译器 pass 嵌入优化循环。

3. **不可移植、不可复用**：CUPTI、NVBit 等基础设施与程序和 instrumentation 框架强耦合，跨平台（Nvidia/AMD）迁移困难，且无法复用为 compiler pass 的一部分。

---

## 三、核心设计

**KPerfIR** 是一个基于 MLIR 的多层次编译器-centric profiling 基础设施，集成在 Triton 编译器中。其核心思路是：**将 profiling 能力实现为编译器 pass，与编译器 IR 深度融合**。

三个设计目标：

1. **Programmable tools with IR semantics**：通过在 IR 层插桩，profiling 工具能感知循环结构、warp 边界、pipeline 阶段等语义信息。
2. **Profile-driven compiler passes**：profiling pass 与优化 pass 直接交互，构成闭环的性能优化反馈回路。
3. **Reusable and portable tools**：在高层共享 IR 上实现的工具，可自然支持 Nvidia 和 AMD 两个平台。

**IR 设计**：KPerfIR 以 MLIR dialect 形式存在，介于 TTIR/TTGIR（Triton 高层 IR）与 LLVM IR 之间。核心操作包括：

| 操作 | 说明 |
|---|---|
| `RecordOp` | 主 profiling 标记，通过 name/isStart 标注代码区域 |
| `InitOp` | 初始化并分配 profiling buffer |
| `FinalizeOp` | 写回 profiling 数据到全局内存 |
| `ReadCounterOp` | 读取 GPU 硬件性能计数器（如 `%clock`，AMD `S_MEMTIME`）到寄存器 |
| `StoreCounterOp` | 将计数器值存入 buffer |
| `startInstrumentationOp` / `stopInstrumentationOp` | 触发/停止底层 instrumentation |

编译流程：原始程序 → TTIR 插桩（RecordOp）→ KPerfGPUIR → LLVM Dialect → 执行 → 原始记录 → Trace replay → 可视化/编译器 pass 反馈。

---

## 四、实现细节

**Region-based Timing Tool** 是 KPerfIR 的标志性示范工具：

**数据结构**：每条 profiling record 8 字节——4 字节 tag（1-bit START/END 标志 + 31-bit Region ID，AMD 额外含 12-bit 硬件签名）+ 4 字节 payload（32-bit 时钟周期数）。每个 region 插入 start 和 end 两条记录。

**内存管理**：
- **Warp-group 级 SMEM 分槽**：编译期预计算各 warp group 的存储基地址，通过 index 管理避免竞争。
- **循环缓冲（Circular Buffer）**：SMEM 有限（H100 可用约 1KB–4KB），用循环缓冲保留最近 N 次迭代的 trace，足以定位瓶颈。
- **AMD 协作存储**：AMD 的 warp 级 predication 会导致 thread divergence 和 icache miss（开销高达 600 cycles），KPerfIR 通过让所有线程写同一地址（保留最后一个写入）并附加 12-bit 硬件签名来对齐记录，消除分支。

**Trace Replay**：异步指令（MMA、TMA load）的 profiling 存在内在不准确性——插桩本身会影响 barrier 触发时机，导致 wait time 被低估（Reduced Bubble）甚至产生虚假 idle（Unexpected Idle）。KPerfIR 通过在异步指令前后插入两个 START record + 一个 END record，利用差分消除 profiling 开销，恢复准确的 wait time。

**用户接口**：提供 Python DSL 绑定（面向 Triton kernel 开发者）和 IR 级手工重写（面向编译器 pass 开发者）两种接口。

代码已开源：https://github.com/triton-lang/triton/tree/main/third_party/proton/dialect

---

## 五、实验结果

**实验环境**：NVIDIA H100-HBM3、AMD MI300X；Triton 3.0.0、LLVM 19.1。

**测试 workload**：GEMM-SWP（2/3 stage）、FA3-WS（vanilla/improved）。

**Profiling 开销**：

| 指标 | 结果 |
|---|---|
| 平均 latency overhead | ~8.2%（多数 kernel <10%，最复杂 SWP-3 stage 约 15%） |
| 相对误差（Relative Error） | ~2% |
| 单条 record 的 cycle 开销 | ~33 cycles（3 条 SASS 指令） |
| 优化降级（Optimization Degradation） | 实测 <2%（理论 vs 实际执行时间对比） |

**Shared Memory 开销**：最复杂的 SWP-GEMM 3-stage kernel 仍剩余 10.9 KB 可用 SMEM，不会 spill 到全局内存。

**FA3 优化案例**：

| Kernel | 性能 |
|---|---|
| FA2 (baseline) | - |
| 原始 manual FA3 | - |
| vanilla Triton-FA3 | 低于 manual FA3 |
| KPerfIR 辅助优化后 Triton-FA3 | **+24.1%** vs vanilla Triton-FA3；**+7.6%** vs best manual FA3 |

性能建模：SWP 模型用判别式 Δ 判断瓶颈在 load 还是 compute；WS 模型通过关键路径求和计算理论延迟；两者均基于 profiling 数据估算，在 head_dim=128、seq_len=4096 场景下预测精度良好（526.97 TFLOPs 实测 vs 582.44 TFLOPs 预测优化后）。

---

## 六、批判性分析

**1. FA3 优化效果的可泛化性存疑**

论文的核心 case study（FA3 +24.1%）仅在 H100 上的特定配置（batch=16, seq=4096, head_dim=128, heads=16）展示，且与 vanilla Triton-FA3 比较。没有展示在不同序列长度、不同 batch size 下的 end-to-end 收益分布，也没有给出 latency 数值（图 12 纵轴单位不清晰，图中只显示 TFLOPS 相对排序）。优化效果是否在所有配置下都稳定，并不清楚。

**2. 与 NCU 等的比较不公平**

论文将 KPerfIR 与 NCU 的主要区别定位为"具备 IR 语义"，但没有量化说明 NCU 能提供哪些信息、KPerfIR 额外获得了什么，以及这个信息差有多大。Table 1 的对比矩阵简化了 NCU 的能力（NCU 也支持 per-region 的 source counter 关联，只是不在编译器 pass 里）。

**3. 异步 profiling 准确性的边界条件**

Trace replay 的准确性依赖条件 `T_MMA - T_exe > T_a + T_b`（functional unit 执行时间需超过 profiling 开销，约 25 cycles），对于极短的 MMA 操作可能不成立。论文承认了这一问题但未给出在哪些场景下条件会被破坏，也没有实验验证边界。

**4. 循环缓冲的信息损失未量化**

循环缓冲只保留最近若干次迭代的 trace。对于 warm-up 阶段行为与稳态不同的 kernel（如 SWP 的前几个 stage），可能错过关键的初始 bubble。论文仅声称"保留最近迭代足以识别瓶颈"，但没有实验佐证。

**5. 性能建模精度验证不足**

Table 4 中的 SWP/WS 性能模型虽然公式清晰，但 Table 5 只给出了"实际 vs 理论"的粒度验证（偏差 <2%），没有跨多个 kernel 和配置验证模型预测的泛化准确率，也没有与现有分析模型（如 Roofline）的对比。

---

## 七、AI Infra / MLSys 视角

**对 AI Infra 研究的核心价值**：KPerfIR 将 profiling 从"外部观测工具"提升为"编译器一等公民"，为 profile-guided optimization（PGO）在 GPU kernel 编译领域提供了基础设施。这对以下方向有直接启发：

**1. 自动化 Overlapping 优化**
KPerfIR 展示的 FA3 优化路径（profiling → 关键路径识别 → 编译器 pass 调整 barrier → 性能提升）本质上是一个可以自动化的流程。未来研究可以探索：
- 基于 profiling 反馈的自动 WS/SWP stage 划分搜索（代替手工分析）
- 将 critical path 分析 pass 与 auto-tuning 框架（如 Triton 的自动 tile size 搜索）结合

**2. 分布式训练 kernel 的 compute-communication overlap 分析**
论文提到 KPerfIR 可用于 fused compute-communication kernel（如 FLUX 中的 All-Reduce + GEMM fusion），这正是当前 LLM 训练扩展的核心瓶颈。KPerfIR 提供的 intra-kernel 细粒度 timeline 可以帮助识别 collective 操作的 bubble，是当前缺乏的工具能力。

**3. 新架构（Blackwell、MI350）的快速适配**
KPerfIR 的 MLIR 多层架构使其理论上可以在新 GPU 架构上通过添加新 dialect 快速适配，这对需要频繁跟踪新硬件特性的 AI Infra 团队（如 Meta、NVIDIA 的内部编译器团队）有实际价值。

**4. 可操作的 future work 切入点**
- **64-bit clock 支持**：对于 long-running kernel（>4B cycles），当前 32-bit clock 会溢出，KPerfIR 本身已预留接口，可作为工程贡献快速落地。
- **Memory profiling 工具**：论文提到 bank conflict 分析和 L2 swizzling 优化需要类似基础设施，但没有实现，是一个值得跟进的完整研究方向。
- **与 PyTorch Inductor/XLA 集成**：KPerfIR 目前只集成在 Triton，将其移植到 Inductor 或 XLA 的 IR 体系可以覆盖更广的 AI 框架生态。

---

## 八、总结

KPerfIR 提出将 profiling 工具实现为编译器 pass，通过 MLIR 多层次 IR instrumentation 打通了 AI kernel 编译器与性能分析工具之间的语义鸿沟。以 region-based timing tool 为示范，KPerfIR 实现了对 GPU intra-kernel overlapping 行为的精细分析，并指导 FA3 kernel 优化取得 24.1% 的性能提升。主要局限在于：无法访问厂商私有硬件计数器，评估覆盖的 workload 类型有限，且 FA3 优化结果的泛化性未经充分验证。对于需要频繁分析和优化 AI kernel 的 MLSys 研究者和工业实践者而言，KPerfIR 提供了一个值得参考的开源基础设施范式。
