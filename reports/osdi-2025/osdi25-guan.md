# KPerfIR: Towards a Compiler-centric Ecosystem for GPU Kernel Performance Tooling

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | KPerfIR: Towards a Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling on Modern AI Workloads |
| 作者 | Yue Guan (UCSD), Yuanwei Fang (Meta), Keren Zhou (George Mason/OpenAI), Corbin Robeck (Meta), Manman Ren (Meta), Zhongkai Yu (UCSD), Yufei Ding (UCSD/Meta), Adnan Aziz (Meta) |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/guan |

## 研究背景与动机

在 AI 时代，AI 编译器（如 Triton）在弥合高层 ML 框架算子和底层硬件代码之间发挥关键作用。然而，现有编译器在处理复杂优化（如 GPU 上细粒度执行单元的 overlap）时仍难以超越手工优化实现（如 cuBLAS、ROCBLAS、CUTLASS）。

**现状问题**：
1. **Profiling 工具与编译器脱节**：现有 profiler（NCU、PyTorch Profiler 等）是外部工具，与编译过程隔离，无法提供框架级操作感知的优化洞察
2. **缺乏程序语义信息**：传统工具无法追踪软件流水线如何跨阶段演化和 overlap，缺乏循环级信息
3. **可编程性有限**：难以定制化分析特定算子的性能行为

**AI 编译器新挑战**：
- Nvidia Hopper 架构引入 Tensor Cores 和 TMA（Tensor Memory Accelerator）
- Flash Attention 3 使用复杂 tiling 和 pipelining 技术
- Warp Specialization、Software Pipelining 等优化技术的效果难以准确测量

## 核心问题

如何构建一个**编译器中心化的性能工具基础设施**，让 profiling 功能作为编译器 pass 实现，提供：
1. 可编程、可重用的性能分析框架
2. 与编译器 IR 语义深度集成的 profiling
3. 支持复杂 GPU 优化的细粒度洞察（如 intra-kernel overlap）
4. 跨平台（NVIDIA/AMD）支持

## 主要贡献

1. **KPerfIR：首个编译器中心化的 GPU 性能工具基础设施**：集成到 Triton 编译器，支持 AMD 和 NVIDIA 平台
2. **Region-based Timing Tool**：首个 GPU region 级计时工具，提供 intra-kernel overlap 的精细分析
3. **MLIR dialect 设计**：定义 KPerfIR 和 KPerfGPUIR 操作符，实现 IR 语义到硬件的链接
4. **对 FA3 内核的深入案例研究**：发现 idle bubble 区域并提出优化，7.6% 性能提升
5. 开源：https://github.com/triton-lang/triton/tree/main/third_party/proton/dialect

## 研究方法与设计

### 核心洞察

**现有 profiler 的问题**：
- Kernel-exclusive（仅捕获粗粒度指标如 FLOP/s）
- Hardware-dependent（依赖特定硬件性能计数器）
- Sampling-based（无法提供程序语义信息）

**KPerfIR 解决方案**：在并行汇编层构建 profiling 基础设施，弥合编译器和 profiler 之间的鸿沟。

### KPerfIR IR 设计

**三层 IR 结构**：

1. **KPerfIR（最高层）**：程序表示层
   - `RecordOp`：通用程序标记，操作语义由 KPerfGPUIR 配置决定

2. **KPerfGPUIR（中间层）**：GPU 特定层
   - `ReadCounterOp`：读取性能计数器到标量寄存器
   - `StoreCounterOp`：存储计数器值到缓冲区
   - `InitOp`/`FinalizeOp`：profiling 生命周期管理
   - 配置选项：MetricType、Granularity、BufferType、BufferStrategy

3. **LLVM 层**：硬件相关层
   - `startInstrumentationOp`/`stopInstrumentationOp`：控制低级库级插桩

### 编译 Pass

**KPerfIR → KPerfGPUIR**：将 RecordOp 转换为 ReadCounterOp + StoreCounterOp，插入资源分配和 setup/clean-up 操作

**KPerfGPUIR → LLVM**：生成特定供应商代码（PTX/amdgcn），包括：
- `InitOp` → `llvm.alloca`（栈分配）
- `ReadCounterOp` → 性能计数器读取
- `StoreCounterOp` → 带 tag 创建的寄存器值存储

### 内存管理

**Structured Map**：解决 GPU 并行写入的竞态条件问题：
- **Thread-level map**：用于值 profiling，每个线程独立保存（#Grid × #Block × cap 布局）
- **Warp-level map**：用于时间 profiling，仅 warp 首领线程保存（#Grid × #Warp × cap 布局）
- **环形缓冲区**：处理 profiling 记录存储空间有限的问题

### Region-based Timing Tool

利用 KPerfIR 实现首个 GPU region 级计时工具：
- 插入 `kperfir.record` 标记程序区域
- 高效更新 profiled region 时间戳（寄存器级）
- 提供直观的时间线可视化

**应用**：分析 Flash Attention 内核的 overlap 行为：
- 识别 idle bubble 区域
- 提供 warp specialization 优化建议

## 关键实现细节

- **Hook Driver**（约 2500 行 C）：提供运行时支持、代码缓存等
- **Probe Engine**（约 2000 行 Python）：反编译、分析、插桩、重编译 GPU 二进制
- **DSL Compiler**（约 1000 行 Python）：将 Python Tracing DSL 转换为平台特定汇编
- Triton 编译器集成
- 支持 NVIDIA（CUDA 驱动）和 AMD（ROCm 驱动）

## 实验结果与分析

### 开销评估

**延迟开销**：
- 大多数场景 < 10%（8.2% 平均）
- 即使最复杂的 3 阶段 SWP GEMM 内核也 < 15%

**共享内存开销**：
- 有效控制在共享内存限制内
- SWP GEMM 3 阶段：使用 10.9 KB 缓冲后仍有余量

### Region-based Timing Tool

**Flash Attention 案例研究**：
- 识别 idle bubble 区域
- 提供 warp specialization 优化洞察
- **改进 FA3 编译器优化套件**：相比 vanilla Triton-FA3 提升 24.1%，比最优手工实现高 7.6%

### 指令级开销

- 每个 KPerfIR record 在 SASS ISA 级别降低为 3 条指令（时钟读取 + 整数移动 + 条件存储）
- 平均指令开销 33 周期
- 优化影响在 2% 以内

## 潜在问题与局限性

1. **供应商特定性能计数器**：无法访问供应商私有性能寄存器（如 NCU 的某些指标）
2. **编译器 IR 级别的插桩干扰**：集成 profiling 语义到 IR 级别会牺牲对底层优化的控制（如指令重排序）
3. **AMD 平台支持**：ROCm 生态的文档和工具链成熟度不如 CUDA，实践中可能遇到更多兼容性问题
4. **长期运行内核的 profiling**：环形缓冲区设计可能在超长运行的内核上丢失数据
5. **与生产部署的差距**：当前评估主要在 benchmark 内核上，生产级 ML 框架的复杂内核可能暴露更多问题

## 未来工作方向

1. 扩展到分布式 GPU 工作负载
2. 与供应商特定硬件计数器的更深度集成
3. HPC 和科学模拟领域的应用

## 个人评注

**优点**：
- 编译器中心化的设计思路非常巧妙——profiling 功能作为编译器 pass 提供，而不是事后外部工具，确实能解决传统方法无法提供程序语义信息的核心问题
- 对 Flash Attention 3 的深入分析案例展示了该工具在真实优化工作流中的价值
- 多层 IR 设计（KPerfIR → KPerfGPUIR → LLVM）具有良好的可扩展性
- 端到端开销控制良好（< 10%），不会显著影响被测程序的执行特性

**潜在争议**：
- 论文声称 KPerfIR 是"首个"编译器中心化 GPU 性能工具，但 MosaicGPU profiler 已经在 PTX 汇编级别进行分析，KPerfIR 与 MosaicGPU 的区别主要在于"集成到编译器 IR"和"支持 MLIR/Triton 生态"
- 对 NVBit 的比较略显不公平——NVBit 是机器码级别工具，设计目标不同，不应该在同一维度比较
- 2% 的优化影响评估假设编译器优化不会显著改变插桩指令附近的代码，但实际中 profiling 可能改变寄存器分配和指令调度，从而影响优化质量
- **AMD 平台的实际支持程度存疑**：论文对 AMD 的实现描述较为简略，考虑到 ROCm 生态的复杂性，完整支持可能需要更多工作

总体而言，KPerfIR 是一项扎实的系统工作，为 AI 编译器生态系统提供了一个有价值的性能分析基础设施。
