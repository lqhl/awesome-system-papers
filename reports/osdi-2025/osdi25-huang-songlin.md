# NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing

**作者**：Songlin Huang, Chenshu Wu（The University of Hong Kong）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/huang-songlin
**源文件**：[osdi25-huang-songlin.pdf](../../papers/osdi-2025/osdi25-huang-songlin.pdf)

---

## 一、背景

在 scaling laws 驱动下，GPU 已成为 AI 和高性能计算的核心硬件。理解 GPU kernel 的细粒度运行时行为对于性能优化至关重要。然而，GPU profiling 面临三大独特挑战：

1. **硬件异构且封闭**：GPU 拥有 10,000+ 核心的大规模并行架构，硬件细节对外不透明，限制了细粒度信息的获取能力。
2. **Kernel 对 Host OS 不透明**：GPU kernel 对 host OS 来说是原子操作，kernel 内部执行由 GPU 硬件/固件管理，无法使用 ptrace、eBPF 等成熟的 OS profiling 技术。
3. **缺乏并发机制**：GPU 不支持 timer interrupt、lock 等 CPU profiler 依赖的并发机制，采样式 profiling 难以实现。

现有 GPU profiler 要么是 **kernel-exclusive**（如 torch.profiler，只能获取 FLOP/s 等粗粒度指标），要么是 **hardware-dependent**（如 Nsight Compute、CUPTI，依赖 PM counters 等硬件特性），无法提供细粒度、通用、可编程的 GPU kernel profiling。

---

## 二、要解决的问题

1. **粒度不足**：现有 profiler 最细只能到 PC sampling 级别，无法做到 instruction-level 的 profiling，无法精确映射到 tensor core、memory I/O 等硬件单元。
2. **缺乏可编程性**：用户无法自定义 profiling 逻辑，只能使用 profiler 预设的固定指标（如 memory throughput、FLOP/s）。
3. **平台依赖**：NVIDIA 的 Nsight Compute 只能用于 NVIDIA GPU，AMD 的 RGP 只能用于 AMD GPU，没有跨平台的 profiling 工具。
4. **缺乏时空全景**：现有工具无法同时捕获 memory access 的时间模式和空间模式，也无法反映并行线程的密度信息。
5. **协作性不足**：现有 GPU instrumentation 工具（如 NvBit）的 probe 之间无法共享状态、协作完成复杂 profiling 任务。

---

## 三、洞察与设计

**关键洞察**：GPU 生态中，无论是 AOT 编译路径（CUDA C++ → nvcc）还是 JIT 编译路径（Triton → LLVM），都在 parallel assembly 层（PTX / GCNAsm）汇合。Parallel assembly 是 AOT 和 JIT 两条编译路径的最高公共层，同时又足够底层以捕获硬件级事件。因此，在 assembly 层进行 runtime probing 可以同时实现细粒度、跨平台兼容性和运行时可编程性。

基于这一洞察，NEUTRINO 设计了一个类 eBPF 的 GPU kernel profiling 框架，包含三个核心组件：

### Probe 设计（三要素）

- **Snippet**：probe 的功能代码，使用 assembly 编写，支持 SAVE（存储值到 map）、OUT/IN1/IN2（读取寄存器）、S_MEMTIME（时间测量）等 helper。
- **Tracepoint**：probe 的注入点，主要在 instruction level（最细粒度），也可扩展到 device function call 和 thread start/end 级别。
- **Structured Map**：eBPF-like 的结构化输出格式，解决 GPU 并行环境下的 persistence 难题。

### 虚拟化执行模型

NEUTRINO probe 通过**时间分离**和**资源分离**实现对原始程序的"虚拟化"：
- **时间分离**：基于 SIMT 模型，线程内执行是顺序的，probe 插入 assembly 后自然保持时间隔离。
- **资源分离**：probe 使用独立的逻辑寄存器组，由 assembler 在 register allocation 阶段整合，不影响原始程序的寄存器和执行流。

### Structured Map

- **Thread-level map**：形状为 `[#Grid, #Block, cap]`，每个线程独立保存，用于 value profiling。
- **Warp-level map**：形状为 `[#Grid, #Warp, cap]`，仅 warp leader 保存，用于 time profiling，显著减少内存开销。
- 基于 ndarray layout 实现 race-free saving，无需 atomic 操作，metadata 可从 launch config 推断而非显式存储。

### 验证机制

防止三类不安全操作：覆写原始寄存器、改变执行流（禁止 branch 指令）、使用 shared memory。

---

## 四、实现细节

NEUTRINO 在 Linux 上实现，支持 NVIDIA GPU（CUDA driver）和 AMD GPU（ROCm driver），包含三个模块：

1. **Hook Driver**（~2,500 行 C 代码）：通过创建与 GPU driver shared library（libcuda.so / libamdhip.so）同签名的函数，利用 `LD_PRELOAD` 注入，捕获 GPU API 调用（cuModuleLoad、cuLaunchKernel 等）。维护 image storage 和 kernel storage 两个 hash 表，实现代码跟踪和缓存。

2. **Probe Engine**（~2,000 行 Python 代码）：对 GPU binary 执行 objdump → 提取 parallel assembly → 匹配 kernel → 规划 probe map → 解析 tracepoint → 注入 snippet → reassemble。

3. **DSL Compiler**（~1,000 行 Python 代码）：将平台无关的 Python Tracing DSL 编译为平台特定的 assembly probe。两步编译：Python AST → eBPF-like IR → PTX/GCNAsm。

使用方式类似 bpftrace：`neutrino -p <probe> <user/program>`

### 内置工具

- `block_sched`：分析 block 调度开销
- `gmem_bytes`：统计 GMEM 使用量
- `tensorop_count`：统计 tensor operation 次数
- `dmat`：绘制 DMAT 图

### DMAT（Densified Memory Access Timeline）

一种新的可视化表示，在传统 page reference map 基础上扩展：
- **物理时间轴**：使用 device-side physical clock 替代 virtual time，解决并行线程间的时间错位问题。
- **访问密度**（Color Depth）：用颜色深度表示同一时间同一页面的并行访问强度，区分于传统 page reference map 的 2D 点表示。

---

## 五、实验结果

**平台**：NVIDIA A100 80GB、NVIDIA RTX 4090 24GB（DMAT 使用 RTX 3080）

### 正确性验证

- 执行正确性：probed kernel 与 original kernel 输出无显著差异。
- Profiling 准确性：与 Nsight Compute 的重叠指标一致；微基准测试中地址一致（Hamming distance = 0），时钟误差 < 7%。

### 性能开销

| Probe 类型 | 平均 Kernel Slowdown | 平均额外寄存器 |
|---|---|---|
| 轻量级（block_sched, gmem_bytes, tensorop_count） | 1.04x | 3.78 |
| 重量级（dmat / mem_trace） | 7.12x | 5.09 |

- 轻量级 probe 在部分 kernel 上甚至出现**加速**（如 GEMM 上 gmem_bytes 仅 0.9868x），原因是 probe 的额外指令改变了 register dependency，使 assembler 生成了更优的 instruction flow（IPC 提升 5.88%）。

### GMEM 使用效率

- 轻量级 probe 的 GMEM 使用比原始模型内存小至少一个数量级。
- 随模型规模增长（Llama-1B → 3B → 8B），NEUTRINO 的 GMEM 占比反而下降，表明对大模型更友好。

### Profiler 暴露延迟

与 Nsight Compute 对比，NEUTRINO 在多项 benchmark 上的 exposed latency 显著更低。

### Case Study：同步对 Flash-Attn-v2 的影响

| 配置 | 特征 | 性能问题 |
|---|---|---|
| Exclusive blocks（128×128, 1 block/SM） | 结构化 memory access pattern | 高度同步导致 memory I/O 竞争（4.47x stall due to memory bus busy） |
| Shared blocks（128×64, 2 blocks/SM） | 非结构化、混乱的 memory access | tailing effect 达 24.69%，存在 slow stage (~1.8 TFLOP/s) → fast stage (~2.2 TFLOP/s) 的两阶段现象 |

NEUTRINO 发现 shared blocks 存在隐式 FIFO-like 优先级调度策略：后到达的 block 在先到达 block 完成前处于 slow stage，完成后跳至 fast stage。

---

## 六、批判性分析

1. **DMAT 的实际准确性存疑**：Table 2 显示 linear access pattern 的 DMAT RMSE 高达 59.62%，作者归因于"静态模拟未考虑 cache 等内存系统动态"，但这恰恰说明 DMAT 在 uncoalesced access 场景下的可信度有限。论文在展示 DMAT 的直觉优势时，回避了这一定量缺陷。

2. **Case Study 的因果推断不够严谨**：§7 中观察到 shared blocks 的两阶段现象并推测 FIFO-like 调度策略，但这一结论基于 observed correlation 而非 controlled experiment。GPU 的 warp scheduler 是硬件实现，作者无法排除其他因素（如 cache contention、memory bank conflict）对两阶段现象的贡献。

3. **重量级 probe 的 7.12x 平均开销被轻描淡写**：论文重点强调轻量级 probe 的 1.04x 低开销，但 dmat 这一最有价值的 probe 带来的高开销限制了其在 time-sensitive profiling 场景下的实用性。mem_trace 在 GEMM 上高达 10.37x 的 slowdown 意味着该 probe 可能显著改变 kernel 的运行时行为。

4. **"Abnormal Speedup" 的处理方式值得商榷**：部分 probe 导致 kernel 加速（最快 0.94x），作者将其归因于 assembler 优化。这虽然有趣，但也暗示 NEUTRINO 的 probe 会不可预测地改变 assembler 的优化决策，对 profiling 结果的代表性构成隐忧。

5. **验证机制承认不完备**：作者在 §8 中明确表示验证机制可能"过强"（如禁止所有 branch 指令），也存在未覆盖的安全因素（如 unreachable synchronization points）。对于一个声称类比 eBPF 的系统，验证的不完备性是一个实质性的安全隐患。

6. **跨平台声明与实际测试的差距**：虽然论文声称支持 NVIDIA 和 AMD GPU，但所有定量实验均在 NVIDIA 平台上进行，AMD 平台的性能开销和正确性未被系统性评估。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴价值

1. **填补 GPU profiling 的 observability gap**：NEUTRINO 提供了 instruction-level 的 GPU kernel 内部可见性，这对于 AI Infra 中的 kernel 性能调优（如 FlashAttention 变体对比、GEMM tiling 策略选择）具有直接价值。DMAT 可视化让 memory access pattern 的差异变得直观，有助于快速定位瓶颈。

2. **Assembly-layer probing 思路可迁移**：NEUTRINO 在 PTX assembly 层做 runtime instrumentation 的思路，可以启发 AI compiler（如 Triton、TVM）在 code generation 阶段集成类似的 profiling 能力，实现 auto-tuning 的闭环反馈。

3. **Block scheduling insight 对 kernel 设计的指导意义**：§7 发现的 shared blocks tailing effect 和隐式 FIFO 调度策略，对设计高性能 GPU kernel（特别是 FlashAttention、GEMM 等核心算子）的 tile size 和 block 配置策略有直接参考价值。

### 值得跟进的方向

1. **DMAT-guided auto-tuning**：将 DMAT 提供的 memory access pattern 信息反馈给 Triton auto-tuner，自动选择最优的 tile size、pipeline stage 数、warp 数等配置，替代目前基于 end-to-end latency 的盲搜策略。

2. **LLM inference 场景的细粒度 profiling**：在 vLLM、TensorRT-LLM 等推理框架中集成 NEUTRINO，profiling prefill 和 decode 阶段不同 kernel 的 memory access pattern 和 block scheduling 行为，指导 KV cache 管理和 batch scheduling 优化。

3. **Assembler-level 优化探索**：论文发现 probe 指令可能导致 assembler 生成更优的 instruction flow（5.88% IPC improvement），这与 DeepSeek 的 DeepGEMM 通过 flip machine code control bit 获得 10% speedup 的发现一致，暗示 assembly/machine code 层面存在未被充分探索的优化空间。

### 最有价值的切入点

将 NEUTRINO 集成到 ML compiler 的 auto-tuning pipeline 中：用 NEUTRINO 的轻量级 probe（block_sched + gmem_bytes）替代或补充目前基于 wall-clock time 的 kernel benchmarking，提供更丰富的性能 signal 来指导 search space pruning，有望显著加速 auto-tuning 收敛。

---

## 八、总结

NEUTRINO 是首个跨平台、可编程的 GPU kernel 细粒度 profiling 工具，通过在 parallel assembly 层进行 runtime probing，实现了 instruction-level 粒度、时间/值域双维度覆盖和 eBPF-like 可编程性。其提出的 DMAT 可视化为理解 GPU 运行时行为提供了新视角。轻量级 probe 仅引入 1.04x 平均开销，支持全模型 profiling。主要局限在于无法观测不可编程的硬件事件（如 cache miss）、重量级 probe 开销较高、以及验证机制尚不完备。NEUTRINO 已开源（https://github.com/open-neutrino/neutrino），作为 GPU 性能工程的基础设施，对 AI 系统研究者和工程师具有较高的实用价值。
