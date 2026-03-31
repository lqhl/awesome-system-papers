# PipeThreader: Software-Defined Pipelining for Efficient DNN Execution

**作者**：Yu Cheng, Lei Wang, Yining Shi（北京大学计算机学院）；Yuqing Xia, Lingxiao Ma, Jilong Xue, Yang Wang, Zhiwen Mo, Feiyang Chen, Fan Yang, Mao Yang（Microsoft Research）；Zhi Yang（北京大学计算机学院）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会，2025 年 7 月）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/cheng
**源文件**：[osdi25-cheng.pdf](../../papers/osdi-2025/osdi25-cheng.pdf)

---

## 一、背景

深度神经网络（DNN）的快速增长，尤其是大语言模型（LLM）的兴起，促使硬件厂商在 GPU 内集成了异构专用执行单元，如 NVIDIA H100 中的 TensorCore（矩阵加速）、CUDA Core（通用浮点）和 Tensor Memory Accelerator（TMA，异步内存传输）。与此同时，软件侧广泛采用算子融合（operator fusion）技术——将 MatMul、Softmax 等多个算子合并为单一 GPU kernel（如 FlashAttention）——以减少内存带宽压力、提升计算密度。

然而这两个趋势共同引发了新的调度挑战：硬件侧，传统 GPU 调度器以 SM 为均质执行单元，无法感知 SM 内部 TensorCore / CUDA Core / TMA 的异构性；软件侧，深层融合算子形成了复杂的计算流水线，硬件调度器难以高效编排。结果是：开发者必须手工编写针对特定 GPU 的高性能 kernel（如 FlashAttention-3），不仅耗时（FlashAttention-2 升级到 FlashAttention-3 用了近一年），而且难以推广到新硬件或新模型。

---

## 二、要解决的问题

1. **硬件异构性被忽视**：现有 DNN 编译器（TVM、Triton、Welder 等）将 GPU 抽象为同构执行单元（SPMD），无法感知 SM 内部 TensorCore / CUDA Core / TMA 的并行潜力，导致 TensorCore 利用率低下（未优化 MatMul 仅约 40%，Mamba2 ChunkScan 仅约 15%）。

2. **流水线调度能力缺失**：现有编译器缺乏显式表达 tile 级流水线执行的机制，无法在同一 SM 内重叠 TMA 内存传输与 TensorCore 计算，也无法跨迭代流水线。

3. **手工优化不可泛化**：FlashAttention-3 等专家级实现与特定 GPU 架构紧耦合，每换一代 GPU 或出现新模型（Mamba2、RetNet 等），都需要重新手工实现，成本极高。

---

## 三、核心设计

PipeThreader 的核心思路是**将流水线调度职责从硬件转移到软件**，通过三层抽象实现「软件定义的流水线」：

### sTask（专用任务）

sTask 是 DNN 计算的基本调度单元，对应在某类专用执行单元（sEU）上执行的 tile 级操作。每个 sTask 包含：
- `expr`：tile 级张量表达式（如矩阵乘、Softmax）
- `shape`：沿各 loop 轴的 tile 尺寸
- `target_sEU`：目标执行单元类型（TMA / TensorCore / CUDA Core）

相比传统 tile 任务，sTask 明确携带目标 sEU 信息，使编译器可为不同 sEU 分配不同任务、实现异构并行（MPMD）。

### sEU（专用执行单元）

GPU 被建模为分层硬件：多个同构 EU（如 SM）构成 vDevice，每个 EU 内含多个异构 sEU（如 TMA、TensorCore、CUDA Core）。sEU 接口仅需实现 `Execute(sTask)` 及 `is_async` 属性，支持同步（CUDA Core）和异步（TMA）两种模式。异步 sEU 可与同步或异步 sEU 并发执行，是流水线的基础。

### sTask-graph 与 sProgram

- **sTask-graph**：以 sTask 为节点、依赖关系为有向边的计算图。通过 sTask-partition，将 DFG 中的算子拆分为 sTasks，支持空间维度（batch）和规约维度（sequence length）两个方向的 tiling。规约维度 tiling 是 PipeThreader 的关键创新，传统编译器将其视为次要优化，PipeThreader 将其作为一等公民，以实现跨迭代的流水线并行。
- **sProgram**：二维数组 `sProg[sEU][order]`，定义每个 sTask 分配到哪个 sEU 以及执行顺序。搜索空间为所有满足数据依赖的合法 sProgram（FlashAttention 有 37,440 个合法 sProgram）。

### 调度原语

三个调度接口构成策略与机制的分离：
- `Append(sTask, <EU, sEU>)`：将 sTask 分配到指定 sEU
- `Wait(sTask, list<sTask>)`：插入 barrier，等待依赖 sTasks 完成
- `Propagate(sTask-graph, TileShape)`：从输出 tile 形状反向推导整个 sTask-graph 的 tile shapes

### 两层调度策略

- **Inter-EU 层（SPMD）**：枚举输出 sTask 的 partition，通过 Propagate 推导全图 tile shapes，均匀分配 sTask-subgraph 到各 EU，利用各 EU 等价计算能力并行。
- **Intra-EU 层（MPMD 贪心）**：在单 EU 内，贪心地选择最早完成的 sTask，调度到合适 sEU，在满足依赖的前提下最大化流水线并行。两层联合优化 tile size 与 pipeline depth 的 trade-off。

---

## 四、实现细节

- 代码规模：8,500 行 C++ + Python，基于 TVM 和 Ladder 开源编译器构建。
- 前端支持：sTask IR（如图 7 所示的 FlashAttention 伪代码）和 ONNX graph，通过 Ladder 进行算子融合生成 tile-graph，再标注 `target_sEU` 转换为 sTask-graph。FlashAttention 仅需 68 行 Python IR，而手工实现 FlashAttention-3 的 CUDA kernel 为 840 行。
- **Layout 推导**：自动推导 sTask 的 Layout（数据布局与线程绑定映射函数），从高优先级 sTask（如 mma）的约束向外传播，避免手工指定。冲突通过优先级算法解决。
- **NVIDIA H100 特化**：利用 Warp Specialization，将线程分为 producer warp（TMA 加载）和 consumer warp（mma / Softmax），通过 mbarrier 实现精确同步，并使用 double buffering 降低寄存器干扰。
- **AMD MI300X 支持**：sEU 映射到 Matrix Core / ALU / 异步复制单元，使用 `lgkmcnt`/`s_waitcnt` 管理异步 barrier。换目标架构只需更新 sEU layouts、intrinsics 和资源限制，核心调度逻辑复用。
- 代码开源：https://github.com/tile-ai/tilelang

---

## 五、实验结果

### 测试平台

| GPU | CUDA/ROCm | OS |
|---|---|---|
| NVIDIA H100 80GB | CUDA 12.4 | Ubuntu 20.04 |
| AMD Instinct MI300X 192GB | ROCm 6.1.0 | Ubuntu 20.04 |

### Operator 微基准（NVIDIA H100）

| 算子类型 | 对比 PyTorch | 对比 cuBLAS/FlashAttention-3 | 对比 Ladder |
|---|---|---|---|
| MatMul | 1.24× (max 1.40×) | 1.06× vs cuBLAS | 2.07× |
| Conv2D | 1.94× (max 3.52×) | — | 2.56× |
| WFP4AFP16 MatMul | 3.92× (max 4.76×) | — | 2.48× |
| FlashAttention | 1.82× (max 2.29×) | 1.07× vs FA-3 (max 2.18×) | — |
| Mamba2 ChunkScan | — | 1.71× vs Triton | — |
| Mamba2 ChunkState | — | 1.98× vs Triton | — |

### 端到端性能（NVIDIA H100，LLAMA3-8B WFP16AFP16）

| 方案 | BS=1, SEQ=4k (ms) | BS=1, SEQ=1 (ms) | BS=32, SEQ=1 (ms) |
|---|---|---|---|
| PipeThreader | 3.29 | 0.29 | 1.29 |
| PyTorch-Inductor | 6.06 | 0.56 | 2.78 |
| TensorRT | 3.99 | 0.40 | 1.84 |
| vLLM | 3.05 | 0.59 | 1.11 |
| Ladder | 5.96 | 0.43 | 6.62 |

- Mamba2-1.3B：相较 Ladder 平均加速 45.93×（最高 84.41×）；相较 PyTorch-Inductor 加速 1.92×
- WFP4AFP16 LLAMA3-8B：相较 PyTorch-Inductor 加速 3.03×（最高 11.98×）
- AMD MI300X：相较 Triton 加速 1.16×–5.42×；Mamba2 相较 Ladder 加速 32.93×（最高 61.33×）

### 消融实验（联合优化 vs 解耦优化）

| 算子 | Triton (ms) | PT-Decouple (ms) | PT-Joint (ms) |
|---|---|---|---|
| ChunkScan BS=64, SEQ=8k | 13.332 | 12.150 | 6.981 |
| FlashAttention BS=64, SEQ=4k | 41.681 | 48.762 | 30.416 |

联合优化在 ChunkScan 上比解耦优化快约 1.74×，说明 tile size 与 pipeline scheduling 须协同优化。

---

## 六、批判性分析

**优势被选择性呈现**：端到端 LLM 评测仅测 single decoder layer，以此代表整模型性能，并称"延迟随层数线性扩展"——但这一假设仅在内存充足时成立；多层执行时 KV cache、batch size 动态变化等实际场景未被覆盖。

**基线对比不完全公平**：与 FlashAttention-3 的对比中，PipeThreader 仅以平均 1.07× 领先，部分配置反而被 FA-3 击败（论文承认 FA-3 在小 sequence length 下因固定 tile size 表现欠佳），而 PipeThreader 是自动搜索最优 tile size 的——这不是同等条件下的对比，更像是"自动调优 vs 固定配置"。

**Ladder 基线过弱**：多处大幅领先 Ladder（Mamba2 达 45×），但 Ladder 本身不支持 linear attention 融合，实际上是在和一个完全不具备该功能的编译器对比；这些数字反映的是功能差距，而非同等优化能力下的性能差距。

**编译时间问题被轻描淡写**：FlashAttention（BS=64, SEQ=8k）需要 5.26 分钟编译，ChunkScan 需要 3.92 分钟——对于生产推理系统来说，这是相当严重的冷启动开销。论文仅在消融实验中顺带提及，未正面讨论这是否实用。

**调度策略的泛化性存疑**：论文声称两层贪心策略"已经能大幅超越 SOTA"，但未给出为什么贪心策略近似最优的理论分析，也未分析在什么情况下搜索空间过大会导致次优解。37,440 个合法 sProgram 中只评估了极少数，最优 sProgram 是否被找到没有验证。

**能耗与资源开销未评估**：论文完全没有讨论 PipeThreader 生成 kernel 的能耗特性，对 AI 推理系统的 TCO 影响未知。

---

## 七、AI Infra / MLSys 视角

**核心 insight 的迁移价值**：将"流水线调度从硬件隐式行为提升为软件显式控制"这一思路，与 AI Infra 领域的核心诉求高度契合——随着 Blackwell（NVLink Switch、FP4 TensorCore）、AMD MI350X 等新架构的出现，手工优化 kernel 的成本越来越高。PipeThreader 的 sTask/sEU 抽象为跨架构自动调优提供了一个可行路径。

**对 LLM 推理系统的直接价值**：
- FlashDecoding、MLA（Multi-head Latent Attention，DeepSeek-V2/V3 核心算子）等新算子的自动高效实现，可以直接集成到 vLLM、SGLang 等推理框架的 kernel 后端。
- WFP4AFP16 量化场景的 3–12× 加速，对 Blackwell 架构下的量化推理极具吸引力。

**值得跟进的研究方向**：
1. **在线编译 + kernel cache**：当前编译时间过长（5+ 分钟），如何结合离线 AOT 编译与运行时 JIT 补充，使 PipeThreader 适配推理服务的冷启动约束？
2. **Multi-GPU 流水线**：论文提及可将 RDMA/NVLink 建模为 sEU，但未有实验验证。Tensor Parallelism + PipeThreader kernel 级流水线的协同调度是直接的延伸工作。
3. **新架构适配**：Blackwell 引入了 FP4 TensorCore 和 NVLink Switch，sEU 抽象如何对应？是否能自动发现 FP4 → FP8 dequant → GEMM 的最优融合流水线？
4. **强化学习 / 进化算法驱动的调度策略**：现有贪心策略是"够用但非最优"的，结合 cost model + 搜索算法（如 AutoTVM、Ansor 的思路）替换贪心策略，有望进一步压榨性能空间。

---

## 八、总结

PipeThreader 是一个 DNN 编译器，通过引入 sTask / sEU 抽象和 sTask-graph，将 GPU 内的流水线调度从硬件隐式行为提升为软件显式控制，从而自动为 TensorCore、CUDA Core、TMA 等异构单元生成高效的流水线调度方案。在 NVIDIA H100 和 AMD MI300X 上，PipeThreader 对 FlashAttention、Mamba2 等工作负载实现了与或超越专家手工实现的性能，尤其在新兴 linear attention 模型上相较 Ladder 有数十倍的提升。主要局限在于编译时间较长（数分钟级），端到端评测仅覆盖单层推理场景，以及部分基线对比存在不公平性。整体而言，本文为 AI 系统领域提供了一个务实可用的跨架构 kernel 自动生成框架，具有较高的工程和研究价值。
