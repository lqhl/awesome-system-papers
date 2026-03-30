# NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing |
| 作者 | Songlin Huang, Chenshu Wu（香港大学） |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/huang-songlin |

## 研究背景与动机

GPU 在 AI 系统中扮演核心角色，支撑大规模并行计算工作负载。然而，GPU 程序的运行时行为分析存在根本性挑战：

**三大挑战**：
1. **专有异构硬件**：GPU 架构快速演进（如 tensor core、async copy），硬件计数器专有，限制了细粒度信息获取
2. **Kernel 的原子性**：GPU kernel 对 host OS 原子化，无法通过成熟 OS 技术（ptrace、eBPF）进行分析
3. **并发机制缺失**：GPU 不支持 timer interrupt 等 sampling profiler 的基础机制

**现有方案的问题**：
- **Kernel-exclusive profilers**（PyTorch Profiler）：仅捕获粗粒度指标（FLOP/s）
- **Hardware-dependent profilers**（CUPTI、NCU）：采样间隔大，无法捕获程序语义，硬件依赖性强
- **Binary instrumentation**（NvBit）：操作机器码，缺乏高层语义，缺乏可编程性

## 核心问题

如何构建一个**细粒度、可编程、硬件无关**的 GPU kernel profiling 系统：
1. **Fine-granularity**：在指令级提供性能数据
2. **Versatility**：同时支持值域（内存地址）和时间域（时间戳/intra-kernel micro-benchmarking）
3. **Programmability**：支持用户自定义探针逻辑，实现 cooperative probes

## 主要贡献

1. **NEUTRINO**：首个 GPU 汇编层 probing 系统，提供细粒度、可编程的 profiling
2. **汇编层 probing 设计**：在并行汇编层（PTX/GCNAsm）而非机器码层进行插桩
3. **DMAT（Densified Memory Access Timeline）**：新型可视化，展示 GPU 内存访问密度和时间模式
4. **eBPF 风格的 structured map**：解决 GPU 并行写入的竞态条件和存储压力问题
5. **同步/共享 block 的 Tailing Effect 发现**：首次揭示 GPU 上 warp specialization 的新行为
6. 开源：https://github.com/open-neutrino/neutrino

## 研究方法与设计

### 核心洞察

**为何选择汇编层**：
- 硬件导向：捕获硬件事件（如 tensor core 操作）
- 特殊寄存器：PTX %clock、GCNAsm hwreg 等
- 兼容性：AOT（JIT）两条编译路径在汇编层汇合
- 覆盖率：运行时方法覆盖所有用户代码，无需源代码

### 探针设计三要素

**1. Snippet（代码片段）**：
- 与探针目标相同的汇编代码
- helpers：`SAVE` 保存结果到 NEUTRINO Map，`OUT`/`IN1`/`IN2` 读取寄存器（值 profiling）
- `S_MEMTIME` 用于时间 profiling

**2. Tracepoint（追踪点）**：
- 粒度： finest 指令级
- 支持扩展到设备函数调用、thread start/end
- 每个 tracepoint 可标记多个 snippet

**3. Structured Map**：
- **Thread-level**（值 profiling）：每个线程独立保存（#Grid × #Block × cap）
- **Warp-level**（时间 profiling）：仅 warp 首领保存（#Grid × #Warp × cap）
- Race-free 保存（每线程独立段），减少元数据

### 虚拟化执行模型

**时间隔离**：SIMT 模型保证线程内指令线性执行，探针天然时间隔离

**资源隔离**：为探针声明独立寄存器组，不影响原程序资源
- 逻辑声明 → 物理寄存器分配（依赖跟踪算法）
- **可能不引入额外物理寄存器**（实际平均仅 4.11 个额外寄存器）

### 安全性验证

NEUTRINO 验证器防止三类不安全操作：
1. **覆盖原寄存器**：禁止修改原程序寄存器
2. **程序乱序**：禁止来自改变执行流的指令（分支等）
3. **共享内存使用**：禁止探针使用 SMEM

### 实现架构

**Hook Driver**（约 2500 行 C）：
- 模拟符号链接到驱动
- 捕获 GPU kernel 加载和 launch
- 提供代码追踪、缓存

**Probe Engine**（约 2000 行 Python）：
- `objdump` → 解析二进制
- 探针规划、匹配
- 重编译

**DSL Compiler**（约 1000 行 Python）：
- Python Tracing DSL → PTX/GCNAsm
- TOML 配置封装

### DMAT 可视化

**Densified Memory Access Timeline**：将内存访问密度信息映射到物理时间轴

- 比传统 page reference map 多了时间维度和并行密度
- 比采样 profiler 多了程序语义

## 关键实现细节

- 支持 NVIDIA（CUDA 驱动）和 AMD（ROCm 驱动）
- CLI 接口类似 bpftrace：`neutrino -p <probe> <program>`
- 探针用 Python DSL 编写，编译为 TOML 配置

## 实验结果与分析

### 正确性验证

- **执行正确性**：probing 不改变原始执行流
- **Profiling 准确性**：结果可信

### 开销评估

**延迟开销**：
- 大多数探针 **1.04×** slowdown
- 额外寄存器：平均 **4.11 个**

**共享内存开销**：
- 有效控制在 SMEM 限制内
- SWP GEMM 3 阶段：16 iterations 的 profiling 仅用 10.9 KB SMEM 缓冲后仍有余量

### 案例研究：Flash Attention v1 vs v2

**Tailing Effect 发现**：
- Shared block 中 warp 在 slow stage 和 fast stage 之间的切换
- 新的 scheduling 策略：优先选择无依赖 warp
- **v2 改善内存效率和更好的 overlap**

**GEMM 分析**：
- 50.93% 的 shared block 存在 tailing effect
- 吞吐量从 ~5 TFLOP/s 跳到 ~7.5 TFLOP/s

### 性能降解分析

**SASS ISA 级别**：
- 每条 record 降低为 3 条指令
- 平均额外周期开销 **33 cycles**

**优化影响**：
- 模型预测 vs 实际执行：偏差 <2%
- IR 级别 profiling 对编译器优化的干扰很小

## 潜在问题与局限性

1. **程序化硬件计数器访问受限**：汇编层探针无法访问未程序化硬件（如某些性能计数器）
2. **难以追踪 stall cycles**：profiling 基于执行，无法直接追踪无指令调度的时间
3. **缓存行为不可见**：NEUTRINO 无法直接观察缓存命中/未命中
4. **eBPF 类比的有效性**：论文大量使用 eBPF 作为设计类比，但 eBPF 在 Linux kernel 生态中有安全验证器和沙箱保护，NEUTRINO 的安全模型是否同样完善存疑
5. **验证器的不完整性**：论文承认 verifier 未处理不可达同步点、jmp 指令支持等，验证器本身是未完成的工作
6. **跨平台一致性**：NVIDIA 和 AMD 的汇编 ISA 差异显著，同一 DSL 是否能无缝映射到两个平台存疑

## 未来工作方向

1. 与硬件/软件 profiler 的集成，构建统一框架
2. 扩展到分布式 GPU 工作负载
3. 缓存模拟

## 个人评注

**优点**：
- 对 GPU profiling 三大挑战（专有硬件、kernel 原子性、并发机制缺失）的分析非常准确
- eBPF 风格的 map 设计巧妙地解决了 GPU 并行写入的竞态问题
- **Tailing Effect 的发现**是 paper 的亮点，展示了 NEUTRINO 在发现新性能现象方面的能力
- 对 Flash Attention v1 vs v2 的比较分析有实际价值

**潜在争议**：
- 论文声称 NEUTRINO 是"首个"GPU 汇编层 probing 系统，但 MosaicGPU 已在 PTX 级别进行分析。主要区别在于 NEUTRINO 强调**可编程性**和 **MLIR/Triton 集成**
- **4.11 个额外寄存器**的开销在寄存器受限的内核上可能带来显著性能影响（论文称"可能不引入"，但寄存器压力始终存在）
- 验证器作为"future work"承认未完成，意味着当前的探针编写存在安全隐患
- **DMAT 可视化**看起来有价值，但未提供量化比较，其实际分析价值有待社区验证

总体而言，NEUTRINO 为 GPU profiling 提供了一个有价值的可编程框架，Tailing Effect 的发现展示了其分析潜力。
