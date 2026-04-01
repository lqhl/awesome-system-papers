# PipeThreader: Software-Defined Pipelining for Efficient DNN Execution

**作者**：Yu Cheng, Lei Wang, Yining Shi (Peking University); Yuqing Xia, Lingxiao Ma, Jilong Xue, Yang Wang, Fan Yang, Mao Yang (Microsoft Research); Zhiwen Mo (Imperial College London & MSR); Feiyang Chen (Shanghai Jiao Tong University & MSR); Zhi Yang (Peking University, corresponding author)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/cheng
**源文件**：[osdi25-cheng.pdf](../../papers/osdi-2025/osdi25-cheng.pdf)

---

## 一、背景

现代 GPU（如 NVIDIA H100、AMD MI300X）内部集成了多种异构专用硬件单元：TensorCore 用于矩阵运算、CUDA Core 用于通用浮点计算、TMA (Tensor Memory Accelerator) 用于内存搬运。与此同时，DNN 模型规模持续增长，算子融合（operator fusion）技术被广泛采用以减少内存开销——典型如 FlashAttention 将多个算子融合进单个 GPU kernel。

这两个趋势——硬件异构化和计算流水线深度增加——使得高效调度变得极具挑战。传统 GPU 编程模型（CUDA）将 SM 视为同质执行单元，依赖硬件调度器通过大量并发线程来隐藏流水线停顿。但专用硬件单元要求更大粒度的 tensor tile 操作，可用并发线程数显著减少，硬件调度器已无法有效应对。当前最优的 DNN kernel（如 FlashAttention-3）依赖专家手工精心编排流水线，每次适配新硬件或新模型都需要重新实现，开发周期长达数月甚至一年。

---

## 二、要解决的问题

1. **硬件利用率低下**：在 H100 上，没有流水线优化的 MatMul TensorCore 利用率仅 40%；手工优化的 Mamba2-ChunkScan TensorCore 利用率也仅 15%。异构单元间缺乏协同调度导致大量硬件资源闲置。

2. **手工流水线优化不可泛化**：FlashAttention-3 从 FlashAttention-2 演进花了近一年，且仅适用于特定 GPU 架构和特定模型。新模型（如 Mamba2）、新硬件（如 AMD GPU）、新 tensor shape 都需要从头编写优化 kernel。

3. **现有编译器缺乏流水线抽象**：TVM、Triton 等编译器将硬件抽象为同质执行单元（EU），缺乏对异构专用单元的建模能力，无法表达和优化 tile 级别的流水线执行，开发者无法指定执行顺序、资源分配和计算-通信重叠。

---

## 三、洞察与设计

**关键洞察**：新硬件专用单元以 tensor tile 粒度处理数据，tile 级执行具有确定性的性能特征，因此可以将流水线调度从隐式的硬件行为转移到显式的软件控制——即 software-defined pipelining。通过在软件层面精确建模异构硬件单元的能力并编排 tile 级任务的执行顺序，可以系统性地发现高效的流水线调度方案。

基于此洞察，PipeThreader 引入两个核心抽象：

### sTask（Specialized Task）
将 DNN 算子分解为面向特定硬件单元的细粒度任务。每个 sTask 处理一个 data tile，包含 tensor 表达式、tile shape 和目标 sEU 类型。例如，FlashAttention 的 MatMul-Sum 操作被分解为 mma sTask（在 TensorCore 上执行）和 Sum sTask（在 CUDA Core 上执行），使两者可以流水线并行。

### sEU（Specialized Execution Unit）
将 GPU 抽象为层次化执行单元：上层是同质的 EU（如 SM），下层是每个 EU 内的异构 sEU（TensorCore、CUDA Core、TMA）。sEU 区分同步/异步属性，异步 sEU 可与其他 sEU 并发执行。

### sTask-graph 与 sProgram
sTask 之间的数据依赖形成 sTask-graph。PipeThreader 将 sTask-graph 映射到 sEU 上，生成 sProgram——一个二维数组 `sProg[sEU][order]`，定义每个 sTask 在哪个 sEU 上以什么顺序执行。sProgram 通过 barrier-sTask 保证依赖关系。

### 关键创新：Reduction Tiling
传统编译器主要做 spatial tiling 实现数据并行。PipeThreader 同时支持 reduction dimension 的分区，在 EU 内部创建更细粒度的 sTask，暴露更多流水线并行机会。这引入 tiling 大小与 pipeline 深度之间的 trade-off（更大 tile 提高数据复用但消耗更多 on-chip memory，限制 pipeline 并行度）。

---

## 四、实现细节

PipeThreader 基于 TVM 和 Ladder 实现，共 8.5k 行 C++ 和 Python 代码。开源于 https://github.com/tile-ai/tilelang。

### 调度接口
三个核心原语：
- **Append(sTask, \<EU, sEU\>)**：将 sTask 分配到指定 sEU
- **Wait(sTask_id, list\<sTask_id\>)**：同步依赖，插入 barrier-sTask
- **Propagate(sTask-graph, TileShape)**：从输出 tile shape 反向推导所有 sTask 的 tile shape

### 两层调度策略
- **Inter-EU 层**：枚举 output sTask 的不同 tile partition，用 Propagate 推导其他 sTask partition，将 sTask-subgraph 均匀分配到各 EU（SPMD 风格）
- **Intra-EU 层**：贪心算法调度 sTask 到 sEU。优先调度异步 sTask、依赖少且能解锁更多下游 sTask 的任务。通过 `check_valid` 检查 on-chip memory 约束，跳过超出内存限制的方案

### Profiler
为每个 sTask 在特定 sEU 上测量执行时间和资源占用（shared memory、register），指导调度决策。调度完成后还测量整个 sProgram 的 ground-truth latency。

### NVIDIA GPU 映射
- SM → EU，TensorCore/CUDA Core/TMA → sEU
- 利用 `cp.async.bulk` 和 `wgmma.mma_async` 指令实现异步执行
- Warp Specialization：producer warp 执行 load sTask，consumer warp 执行 mma/Softmax sTask
- 双缓冲 register 避免 TensorCore/CUDA Core 寄存器干扰
- Layout inference 自动推导 sTask 数据布局和线程绑定

### AMD GPU 映射
- CU → EU，MatrixCore/ALU/async copy → sEU
- 利用 `lgkmcnt` 和 `s_waitcnt` 指令管理异步 barrier

### 代码量对比
FlashAttention kernel：PipeThreader 68 行 Python vs FlashAttention-3 840 行 CUDA；MLA：PipeThreader 80 行 Python vs DeepSeek 500+ 行 CUDA。

---

## 五、实验结果

**硬件平台**：NVIDIA H100 (80GB) + AMD Instinct MI300X (192GB)

**模型覆盖**：LLAMA3-8B, LLAMA3-70B, Mamba2-1.3B, RetNet-65B, ResNet-50, UNet

### 算子级性能（H100）

| 算子类型 | 对比基线 | PipeThreader 平均加速 | 最大加速 |
|---------|---------|---------------------|---------|
| MatMul | cuBLAS | 1.06× | — |
| MatMul | PyTorch / Triton / Ladder | 1.24× / 1.13× / 2.07× | 1.40× / 1.26× / 2.25× |
| Conv2D | PyTorch / Triton / Ladder | 1.94× / 1.85× / 2.56× | 3.52× / 2.47× / 8.66× |
| Low-bit MatMul (W_FP4 A_FP16) | PyTorch / Ladder | 3.92× / 2.48× | 4.76× / 3.81× |
| FlashAttention | Triton / FlashAttention-3 | 1.36× / 1.07× | 1.50× / 2.18× |
| FlashDecoding | FA-3 / Triton | 1.12× / 2.27× | 1.23× / 3.06× |
| ChunkScan (Mamba2) | Triton | 1.71× | 1.99× |
| ChunkState (Mamba2) | Triton | 1.98× | 2.59× |

### 端到端性能（H100）

| 模型 | 对比基线 | 平均加速 |
|------|---------|---------|
| LLAMA3 FP16 | PyTorch-Inductor / TensorRT / vLLM | 1.79× / 1.28× / 1.10× |
| LLAMA3 W_FP4 A_FP16 | PyTorch-Inductor / vLLM / Ladder | 3.03× / 2.16× / 2.01× |
| Mamba2-1.3B | PyTorch-Inductor / Ladder | 1.92× / 45.93× |
| ResNet-50 + UNet | Ladder / PyTorch / ONNXRuntime | 2.01× / 2.54× / 3.99× |

### AMD MI300X 性能
- 算子级：比 Triton 加速 1.16×–5.42×，比 PyTorch 最高 6.21×
- 端到端 Mamba2：比 Ladder 加速 32.93×（最高 61.33×）
- 端到端 LLAMA3 FP16：比 ONNXRuntime 加速 6.33×（最高 15.51×）

### 编译时间
- MatMul：0.13 分钟（Triton 0.17 分钟，CUTLASS 3.36 分钟）
- FlashAttention (BS=64, SEQ=8k)：5.26 分钟

---

## 六、批判性分析

1. **搜索空间规模与编译时间的可扩展性存疑**：FlashAttention 的搜索空间有 37,440 个有效 sProgram，编译时间 5.26 分钟尚可接受。但论文未讨论更复杂的融合算子（如 MoE FFN + Attention 的联合优化）的搜索空间规模。随着 sTask 类型和数量增加，搜索空间可能组合爆炸，贪心策略能否持续有效未经验证。

2. **Profiler 准确性假设过于理想**：调度策略依赖 profiler 提供的单个 sTask 执行时间来估算整体 sProgram 性能。但实际执行中存在 cache 竞争、memory bank conflict、warp 调度干扰等因素，孤立测量的 sTask 执行时间可能与流水线执行时差异显著。论文虽然最后用 ground-truth latency 验证，但搜索过程中的决策可能因不准确的估计而错过更优解。

3. **端到端评估使用单层代理**：LLM 端到端实验仅测一个 decoder layer 并假设"延迟随层数线性增长"。这忽略了多层执行时的 GPU 内存压力变化、KV cache 的影响、以及 layer 间可能存在的调度干扰。

4. **RetNet-65B 上加速有限却被轻描淡写**：RetNet-65B 因 head dimension 大导致 shared memory 占用高，PipeThreader 优势显著下降（仅 1.03×–1.16×）。这暴露了 pipeline parallelism 与 on-chip memory 之间的根本矛盾——当模型本身需要大量 shared memory 时，留给流水线缓冲的空间不足。论文仅一句话带过，未深入讨论这一限制的普遍性。

5. **与 FlashAttention-3 的对比需要更仔细解读**：平均加速 1.07× 但最大 2.18×，说明在很多配置上 PipeThreader 与手工优化持平甚至略差，只在特定配置（小 sequence length）上优势明显。这其实表明 PipeThreader 更多是一个"自动化达到专家级"的工具，而非在性能上全面超越手工优化。

6. **AMD GPU 支持的完整性未充分验证**：MI300X 实验使用了 H100 benchmark 的子集，部分算子配置被跳过。FlashAttention 在 AMD 上仅与 FlashAttention-2（而非最新优化版本）对比。

---

## 七、AI Infra / MLSys 视角

### 核心启发

PipeThreader 提出的 sTask/sEU 抽象是对现有 DNN 编译器体系的重要补充。现有编译器（TVM、Triton）基本都在"同质 EU + spatial tiling"的范式下优化，PipeThreader 首次系统性地将异构硬件单元间的 pipeline parallelism 纳入编译优化框架。

### 可迁移的技术与 insight

1. **Reduction tiling 作为一等公民**：传统编译器将 reduction tiling 视为二等优化，PipeThreader 证明在深流水线场景下，reduction tiling 是暴露 pipeline parallelism 的关键。这个 insight 可以迁移到 KV cache 压缩、MoE gating 等场景。

2. **Software-defined pipelining 的范式**：随着 NVIDIA Blackwell 引入更多专用单元（如 FP4 TensorCore、第二代 TMA），硬件异构程度持续加深，software-defined pipelining 的价值只会增加。

3. **跨架构可移植性**：sTask/sEU 抽象可以自然映射到 TPU（TPU Core + DMA Engine）和 Trainium 等 AI 加速器，提供了一个统一的跨平台编译框架思路。

### 值得跟进的 future work

1. **分布式场景**：论文在 Discussion 中提到将 RDMA/NVLink 建模为 sEU、collective communication 建模为 sTask，实现 kernel 内 computation-communication overlap。这是一个高价值方向，当前 TileLink 等工作已初步探索，但缺乏系统性的编译器支持。

2. **MoE 模型优化**：论文提到 PipeThreader 可以为 MoE FFN 的 grouped MatMul 中每个 group 独立生成 sTask-subgraph。结合当前 DeepSeek-V3 等模型的 MoE 架构，自动优化不同 expert 的 kernel 调度是一个实际需求。

3. **与 Quantization-aware compilation 结合**：Low-bit MatMul 实验显示 PipeThreader 在引入 dequant 阶段后获得更大加速（3.92× vs 1.24×），说明流水线深度越深，PipeThreader 优势越大。W4A4、FP8 等新量化方案引入的额外计算阶段都是 PipeThreader 的发力点。

### 最有价值的切入点

基于 PipeThreader 做 **LLM serving 中 prefill/decode 的 kernel-level pipeline 优化**：当前 vLLM 等系统主要在 batch scheduling 层面优化，kernel 内部仍依赖 FlashAttention/FlashDecoding 的固定实现。结合 PipeThreader 的自动调度能力，可以根据不同的 batch size、sequence length 动态选择最优的 pipeline 方案，尤其在 continuous batching 下 prefill 和 decode 混合执行时。

---

## 八、总结

PipeThreader 是一个 DNN 编译器，通过 sTask-graph 抽象和层次化硬件建模（EU/sEU），将流水线调度从硬件行为转变为软件可控的优化空间。其核心贡献在于：(1) 首次系统性地将异构硬件单元间的 pipeline parallelism 纳入编译器自动优化框架；(2) 在 FlashAttention 等成熟架构上达到与手工优化持平或更优的性能；(3) 在 Mamba2 等新兴模型上显著超越现有方案。系统适用于需要深度算子融合和异构硬件协同的 DNN workload，主要局限在于搜索空间随模型复杂度增长的可扩展性，以及在 on-chip memory 受限场景下 pipeline parallelism 收益有限。代码开源于 TileLang 项目。
