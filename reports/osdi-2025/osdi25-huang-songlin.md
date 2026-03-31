# NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing

**作者**：Songlin Huang, Chenshu Wu（The University of Hong Kong）
**会议**：USENIX OSDI 2025
**DOI**：https://www.usenix.org/conference/osdi25/presentation/huang-songlin
**源文件**：[osdi25-huang-songlin.pdf](../../papers/osdi-2025/osdi25-huang-songlin.pdf)

---

## 一、背景

随着 AI 系统在 scaling laws 时代的快速发展，GPU 已成为现代计算系统的核心。训练/推理系统、调度、通信优化等研究方向都迫切需要对 GPU 程序运行时行为有细粒度的观测能力。理解 GPU kernel 的内部执行细节——内存访问模式、warp 调度、张量核心利用率——是优化 ML 系统性能的基础。

然而，GPU 与 CPU 的架构差异使传统 OS profiling 技术失效：GPU kernel 对宿主 OS 是原子性的（atomic），其内部执行由 GPU 硬件/固件管理，无法通过 ptrace 或 eBPF 等成熟技术观测；GPU 线程也不支持 timer interrupt，无法使用采样式 profiler。

---

## 二、要解决的问题

现有 GPU kernel profiler 存在两大根本缺陷：

1. **kernel-exclusive（仅内核级）**：以 torch.profiler 为代表的框架只能捕获粗粒度指标（FLOP/s、整体 kernel 耗时），无法深入 kernel 内部观测指令级行为。

2. **hardware-dependent（硬件依赖）**：以 Nsight Compute / CUPTI / AMD RGP 为代表的硬件 profiler 依赖 Performance Monitor (PM) 计数器，采样式、不可编程，且无法适应新硬件特性（如 async tensor core、TMA unit）。此外无法实现 tracepoint 级别的精确事件追踪。

两类工具的共同盲区：
- 无法实现 **时间域 + 值域** 同时覆盖的细粒度 profiling；
- 无法灵活定义探针（probe），不支持跨 tracepoint 的协作式测量；
- 无法对真实模型（多 kernel）做整体 profiling。

---

## 三、核心设计

NEUTRINO 的核心思想：在 **并行汇编层（parallel assembly layer，即 PTX / GCNAsm）** 进行运行时 probing，类比 eBPF 对 Linux kernel 的作用。

### 选择汇编层的理由
- **最细粒度**：汇编指令可直接映射到 tensor core、memory I/O 等硬件单元；
- **硬件无关**：PTX/GCNAsm 是 AOT（ATen、CUTLASS）和 JIT（Triton、MLIR）两条编译路径的最高公共层；
- **运行时注入**：无需重新编译，支持 probe 的动态启用/禁用；
- **特殊寄存器**：可直接读取 `%clock`、`%globaltimer`、`hwreg` 等运行时信息。

### Probe 三要素设计
1. **Snippet**：探针的功能代码，写在汇编（或 Python DSL）中，提供 `SAVE`、`OUT`/`IN1`/`IN2`、`nl.clock()` 等 helper；
2. **Tracepoint**：注入位置，默认为指令级，也可扩展到 device function call、thread start/end；
3. **Structured Map**：eBPF-like 结构化输出缓冲，分两级：
   - **Thread-level**：每线程独立写入，用于值域 profiling（内存地址等）；
   - **Warp-level**：每 warp 只由 leader 写入，用于时间域 profiling，显著减少内存压力。

### 虚拟化执行模型
NEUTRINO 通过**时间分离**（SIMT 保证线程内顺序执行）和**资源分离**（探针使用独立的逻辑寄存器组）实现探针对原程序的虚拟化，探针不影响原程序的执行流和寄存器状态。Probe 之间可通过寄存器（thread-local）和 Map（global）协作，支持跨 tracepoint 的复杂测量任务（如测量两个指令之间的耗时差）。

### 可视化：DMAT（Densified Memory Access Timeline）
在传统 page reference map（虚拟时间 × 页地址）基础上增加两个维度：
- **物理时间**：使用 GPU device-side clock 替代虚拟自增索引，支持多线程聚合；
- **密度（color depth）**：记录同一时刻并发访问同一页的线程数，直观反映并行化程度和访问聚合性。

---

## 四、实现细节

实现规模约 5,500 行代码，分三个模块：

| 模块 | 规模 | 语言 | 功能 |
|------|------|------|------|
| Hook Driver | ~2,500 行 | C | 通过 `LD_PRELOAD` 模拟 driver 共享库（libcuda.so / libamdhip.so），拦截 `cuModuleLoad`、`cuLaunchKernel` 等 API，实现 code tracking 和 runtime probing |
| Probe Engine | ~2,000 行 | Python | objdump GPU binary → 解析汇编 → 匹配 tracepoint → 注入 snippet → 重汇编（ptxas） |
| DSL Compiler | ~1,000 行 | Python | 将 Python Tracing DSL（@probe 装饰器）编译为 eBPF-like IR，再翻译到 PTX/GCNAsm |

Hook Driver 使用 `dlfcn` 调用真实驱动函数，所有代码运行在 user mode，支持 fork/wait，比 eBPF uprobe 更安全灵活。

Probe Engine 对汇编的处理流程：
1. 规划 Map 地址（依据 blockDim / gridDim 和 map 定义）；
2. 粗粒度解析汇编（参数声明、寄存器声明、指令列表）；
3. 精细解析每条匹配指令（opcode + operands）并填充 helper token；
4. 在匹配指令前/后插入 snippet，在 kernel 头部插入 map 规划代码。

用户接口类似 bpftrace：`neutrino -p block_sched python script.py`。

---

## 五、实验结果

**实验平台**：NVIDIA A100 80GB、NVIDIA RTX 4090 24GB；CUDA 12.6、PyTorch 2.5.0、Triton 3.1.0、CUTLASS 3.5.0。

### 正确性验证

- **执行正确性**：探针前后输出无差异；
- **指标准确性**：与 Nsight Compute 对比 block_sched / gmem_bytes / tensorop_count，结果一致；
- **DMAT 精度**：地址序列 Hamming distance = 0（完全准确），时间分辨率 < 200 cycles（< 7% 误差）。

### 性能与资源开销

| 探针类型 | 平均 kernel slowdown | 额外物理寄存器 |
|---------|---------------------|-------------|
| 轻量探针（block_sched / gmem_bytes / tensorop_count） | ~1.04x | 平均 +3.78 个 |
| 重探针（dmat / mem_trace） | ~7.12x | 平均 +5.09 个 |

异常发现：部分轻量探针出现性能提升（如 gmem_bytes 在 GEMM 上达 0.9868x 加速），原因是探针引入的额外指令改变了汇编器的寄存器依赖追踪，触发更优的指令重排（IPC 提升 5.88%）。

### 全模型 Profiling（GMEM 用量）

对 ResNet、Stable Diffusion、Mamba-1.7B、Llama3-1/3/8B 进行全模型推理 profiling：
- 轻量探针内存占用比原模型小至少一个数量级；
- dmat 探针内存占用在 batch_size=256 时仍在原模型内存范围内；
- 随模型规模增大，NEUTRINO 内存占用比例下降（可扩展性好）。

### 与 Nsight Compute 的 Exposed Latency 对比

NEUTRINO 的整体 profiling 延迟（prologue + kernel + epilogue）显著低于 Nsight Compute，且 prologue 占比 < 1%。

### Case Study：同步对 GPU 运行时行为的影响

对比 FlashAttn-v2 的两种配置（exclusive blocks vs. shared blocks）：
- exclusive blocks：内存访问模式规整，但存在 4.47x 的内存总线竞争 stall；
- shared blocks：意外出现非结构化访问模式，存在 **tailing effect**（达 24.69% 的尾延迟），原因是隐式 FIFO 调度策略导致后来的 block 等待前面的 block 释放 CU；
- 同类 tailing effect 在 GEMM 上也存在（50.93%），从 ~5 TFLOP/s 跳升至 ~7.5 TFLOP/s。

---

## 六、批判性分析

**正确性验证方法存在局限**：DMAT 精度验证依赖于"精心设计的 micro-benchmarking kernel"，这些 kernel 关闭了 L1 cache、用 spin sleep 模拟计算。真实 workload 中 cache 行为复杂多变，论文坦承未建模 cache 动态，导致 uncoalesced access 下 DMAT RMSE 高达 60%——但在实际应用中 uncoalesced access 恰恰是需要重点分析的场景，这里的精度保证最弱。

**性能提升异象处理不充分**：探针导致 kernel 变快（0.9868x）这一现象被论文归因于汇编器指令重排，并被包装成"promising opportunity"。但这实际上意味着 NEUTRINO 会改变原程序的汇编机器码结构，**探针版本和原版程序的行为可能存在系统性偏差**，影响 profiling 可信度。这是一个根本性的观测者效应问题，论文仅列为 discussion 而非核心局限。

**验证系统不完备**：论文第 3.4 节承认当前 verifier 仍不完整，存在未覆盖的不安全场景（如不可达同步点），且 GPU kernel 级别的形式化验证本身仍是开放问题。这意味着 NEUTRINO 的安全性保证是尽力而为，而非形式验证。

**Case Study 的因果性有待商榷**：论文从 DMAT 的可视化图像推断 shared blocks 的 tailing effect 源于 FIFO 调度，但 GPU warp scheduler 的实现是硬件黑箱，该推断属于相关性观察，缺乏控制实验支撑。

**对比基线不够公平**：与 Nsight Compute 的 exposed latency 对比中，两者的功能集合不同——Nsight Compute 提供更丰富的硬件计数器信息，NEUTRINO 仅比较重叠指标，未讨论在等价功能条件下的真实开销对比。

---

## 七、AI Infra / MLSys 视角

NEUTRINO 对 AI Infra / MLSys 研究有直接价值：

**调试与优化工具链**：现有 ML 框架（PyTorch、Triton）的 profiler 停留在 kernel 粒度，无法定位 kernel 内部的性能瓶颈。NEUTRINO 填补了"kernel 粒度 profiler"与"硬件 PM counter"之间的空白，可用于：
- 分析 FlashAttention、GEMM 等核心算子的内存访问模式；
- 诊断 Triton kernel 的 warp 调度效率；
- 量化 pipeline 中的 bubble（DMAT 中的 empty holes）。

**可迁移的设计思路**：
1. **eBPF-like probe 设计范式**可迁移到其他异构加速器（如 TPU、NPU）的 profiling 框架设计；
2. **结构化 Map + 逻辑寄存器虚拟化**的组合是解决大规模并行系统 race-free 持久化的通用方案；
3. **DMAT 可视化**可扩展用于分析 Attention 算子的 KV cache reuse 效率、MoE 路由的访存局部性等。

**值得跟进的研究方向**：
- **GPU 共享 profiling**：NEUTRINO 目前仅支持进程级 profiling，无法分析 MPS / MIG 场景下的多租户干扰，这对 GPU cluster scheduling 研究极为重要；
- **硬件-软件融合 profiler**：将 NEUTRINO 的指令级追踪与 Nsight 的 PM counter 数据融合，实现"stall cycle 归因"——当前 NEUTRINO 无法追踪 stall cycle（无指令调度的 cycle），但 DMAT 可辅助 cache 模拟；
- **probe-guided 自动调优**：将 NEUTRINO 的 profiling 结果（如 DMAT 显示的 empty holes）作为反馈信号，驱动 Triton autotuner 的超参数搜索；
- **LLM 推理系统诊断**：利用 NEUTRINO 分析 vLLM、SGLang 等推理引擎的 PagedAttention、continuous batching 的实际内存访问行为，验证其设计假设。

---

## 八、总结

NEUTRINO 是一个基于 GPU 汇编层运行时 probing 的细粒度、可编程 GPU kernel profiler，通过 Hook Driver + Probe Engine + DSL Compiler 的三层架构，在 Linux 上支持 NVIDIA 和 AMD GPU。其核心贡献在于将 eBPF 的 probe 设计范式移植到 GPU 汇编层，实现了指令级粒度、时间/值域双覆盖、跨 tracepoint 协作的 profiling 能力，并提出 DMAT 可视化揭示 GPU 并行运行时的内存访问密度与时序。主要局限是 uncoalesced access 场景下 DMAT 精度较低（~60% RMSE）、安全验证不完备、以及探针对原程序汇编产生的不可控副作用（观测者效应）。该工具对 AI Infra 研究者调试和优化 ML kernel 具有直接实用价值。
