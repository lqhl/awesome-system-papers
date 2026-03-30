# PipeThreader: Software-Defined Pipelining for Efficient DNN Execution

## 论文基本信息

- **标题**: PipeThreader: Software-Defined Pipelining for Efficient DNN Execution
- **作者**: Yu Cheng, Lei Wang, Yining Shi（北京大学）; Yuqing Xia, Lingxiao Ma, Jilong Xue, Yang Wang, Fan Yang, Mao Yang（微软研究院）; Zhiwen Mo（帝国理工 + 微软研究院）; Feiyang Chen（上海交大 + 微软研究院）; Zhi Yang（北京大学）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/cheng
- **开源**: https://github.com/tile-ai/tilelang

---

## 研究背景与动机

### 硬件趋势：异构化

现代 GPU（如 NVIDIA H100、AMD MI300X）在每个 SM（Streaming Multiprocessor）内集成了异构组件：
- **TensorCores**：专用矩阵计算单元
- **Tensor Memory Accelerators (TMA)**：专用内存移动单元
- **CUDA Cores**：通用计算单元

现有 GPU 编程抽象（CUDA SPMD）将每个 SM 视为同质执行单元，隐藏了内部结构差异，无法充分利用现代 GPU 的异构计算能力。

### 软件趋势：操作符融合

FlashAttention 等操作符融合技术将多个 DNN 算子融合为单一 kernel，以减少内存开销并最大化数据局部性。但融合引入了更深的计算管线，硬件调度器难以理解，导致利用率低下。

### 现有 DNN 编译器的局限

TVM、Triton 等编译器缺乏表达流水线式 tile 执行的显式机制，无法指定执行顺序、资源分配和计算-通信重叠，阻碍了利用完整性能潜力。

---

## 要解决的核心问题

如何通过软件定义的流水线调度（software-defined pipelining）让 DNN 编译器在现代 GPU 的异构硬件上实现高效执行，同时最小化人工工作量？

---

## 主要贡献

1. **sTask 和 sEU 抽象**：将 DNN 计算表达为 specialized tasks（sTasks），映射到 specialized execution units（sEUs）
2. **sTask-graph 和 sProgram**：将 DNN 算子图转换为 sTask-graph，再映射为 sProgram（两维执行数组）
3. **Propagate 接口**：自动推导 sTask 的 tile shape，从输出向输入反向传播
4. **两层调度策略**：inter-EU 层（SPMD 风格并行）和 intra-EU 层（MPMD 风格流水线）
5. **在 H100 和 AMD MI300X 上发现类 FlashAttention-3 流水线**：无需人工实现，达到可比或更优性能
6. **Mamba2 ChunkScan 优化**：相比业界顶尖人工优化实现显著更优

---

## 研究方法与设计

### 核心观察

- 新一代 GPU 的计算粒度是 tile（数据块），tile 级执行可由软件层高效调度
- 操作符融合引入的深层管线暴露了硬件异构性，为软件调度创造了机会
- 现有编译器（TVM、Triton）缺乏表达 tile 级别流水线执行的显式机制

### 核心抽象

#### sTask（Specialized Task）

- 基本计算单元，在特定类型的 sEU 上执行
- 处理来自输入张量的 data tile，产出输出张量的 data tile
- 属性：
  - `expr`：索引式张量表达式
  - `shape`：沿每个循环轴定义的 tile shape
  - `target_sEU`：可执行该 sTask 的 sEU 类型

#### sEU（Specialized Execution Unit）

- GPU 硬件的抽象，分为两层：
  - **EU（Execution Unit）**：同质并行执行单元（如一个 SM）
  - **sEU（within EU）**：异构专用执行单元（如 SM 内的 TensorCore、TMU）
- `is_async` 属性：标识异步执行（如 TMA）还是同步执行（如 CUDA Core）

#### sTask-graph

- sTask 及其数据依赖的有向图
- 通过 sTask-partition 将算子转换为 sTask
- 支持 **空间划分**（沿 batch 维度的数据并行）和 **归约划分**（沿 sequence 维度的流水线并行）

#### sProgram

- sTask-graph 到 sEU 的映射，两维数组 `sProg[sEU][order]`
- 每个 entry 指定分配到特定 sEU 的 sTask 及其执行顺序
- 通过 barrier-sTask 维护依赖正确性

### 调度接口

PipeThreader 提供三个接口：
- **Append(s, <EU, sEU>)**：将 sTask 分配到特定 sEU
- **Wait(s, [t1, t2, ...])**：sTask 等待一组 sTask 完成后才执行（隐式添加 barrier）
- **Propagate(shape)**：从输出 tile shape 反向推导所有输入的 tile shape

### 两层调度策略

**Inter-EU 层**：
- 将 sTask 子图均匀分配到各 EU
- 利用各 EU 等价的计算能力

**Intra-EU 层**：
- 在给定 EU 上为 sTask 子图构建高效流水线
- 采用贪心策略：每次选择最早可完成的 sTask 进行调度

### 运行示例：FlashAttention

FlashAttention 三个算子（MatMulQK、Softmax、MatMulPV）融合为单一 kernel：
- `load_k`、`load_v` → TMA
- `mma_qk`、`mma_pv` → TensorCore
- `softmax`、`rescale` → CUDA Core

PipeThreader 发现可让 `mma_qk`（TensorCore）和 `softmax`（CUDA Core）流水线重叠执行，与 FlashAttention-3 手工优化方案相当。

### 运行示例：Mamba2 ChunkScan

Mamba2 的 ChunkScan 引入了 reduction 维度划分：
- 对 acc_o (M,N) 和 X (K,N) 的 reduction 维（K）进行划分
- 允许不同迭代之间的计算重叠

三种 sProgram 方案评估：
- sProg-A：提前调度 load_x，但 exp 依赖 load_cb_dA_dt，导致延迟
- sProg-B：反向调度，达到最优平衡（最优 0.81× vs 手工 0.47×）
- sProg-C：tile 过大，超出 on-chip 内存容量（OOM）

---

## 关键实现细节

- **代码规模**：8,500 行 C++ 和 Python 代码
- **基于**：TVM 和 Ladder 编译器
- **支持硬件**：NVIDIA H100、AMD MI300X
- **搜索空间**：FlashAttention 为 37,440 个有效 sProgram；Mamba2 为 1,040 种 sTask 排序配置
- **Propagate 机制**：自动推导 tile shape，无需手工指定每个算子的 tiling 参数

---

## 实验结果与分析

### 实验配置

- **硬件**：NVIDIA H100 SXM（80GB HBM3）、AMD MI300X
- **对比基准**：cuBLAS（97% TensorCore 利用率）、FlashAttention-2（Triton）、FlashAttention-3（手工优化）、Mamba2 官方实现
- **工作负载**：MatMul、FlashAttention（2/3）、Mamba2 ChunkScan

### H100 TensorCore 利用率

| 实现 | TensorCore | FMA | XU | DRAM |
|------|-----------|-----|-----|------|
| MatMul（无流水线） | 40% | 100% | - | - |
| cuBLAS | 97% | 100% | - | - |
| FlashAttention-2（Triton） | 72% | - | - | - |
| FlashAttention-3（手工） | 72% | - | - | - |
| PipeThreader（FlashAttention） | ~72% | - | - | - |
| Mamba2 官方 ChunkScan | 15% | - | - | - |
| PipeThreader（Mamba2） | ~40%+ | - | - | - |

### 性能对比

- **FlashAttention**：PipeThreader 在 H100 上发现与 FlashAttention-3 手工实现可比甚至更优的流水线方案，无需人工优化
- **Mamba2 ChunkScan**：PipeThreader 方案显著优于 Mamba2 官方实现（达数倍提升）
- **搜索效率**：Propagate 自动推导 tile shape，显著减少搜索空间

### 硬件无关性

- 在 NVIDIA H100 和 AMD MI300X 上均验证有效
- 证明了 sTask/sEU 抽象的硬件无关性

---

## 潜在问题与局限性

1. **搜索空间仍然巨大**：尽管有结构化搜索空间，FlashAttention 有 37,440 个有效 sProgram，Mamba2 有 1,040 种排序配置，搜索时间仍是实际问题
2. **两层调度策略的完备性**：贪心策略在测试案例上有效，但理论上可能存在更优方案未被发现
3. **硬件特性的覆盖**：sEU 抽象可能无法完全捕获某些硬件特定行为（如 warp scheduling 策略、shared memory bank conflicts 等）
4. **对融合 kernel 的依赖**：PipeThreader 依赖融合后的 DNN 算子作为输入，对未融合的原始 DNN 模型效果可能受限
5. **开源成熟度**：作为学术原型，8,500 行代码的完整性和可维护性需要验证

---

## 未来工作方向

- 更复杂的调度策略（超越贪心，如基于学习的调度）
- 支持更多种类的 DNN 算子和硬件
- 与 TVM/Triton 生态的更深度集成
- 探索异步执行和数据流编程模型

---

## 个人评注

### 优势

1. **精准的问题定位**：准确识别出现代 GPU 的异构性和融合算子的深层管线之间的矛盾，这是之前未被系统性解决的核心问题
2. **优雅的抽象层次**：sTask/sEU/sTask-graph/sProgram 的抽象层次分明，既捕获了硬件异构性，又保持了足够的表现力
3. **超越手工优化的潜力**：PipeThreader 能在 H100 上自动发现与 FlashAttention-3 手工实现相当的流水线方案，且能在 Mamba2 上显著超越官方实现，证明了自动化搜索的价值
4. **对 reduction tiling 的洞察**：将 reduction tiling 提升为第一等优化策略，是本文的重要创新——传统 tiling 只关注空间划分

### 潜在问题

1. **"可比或更优"的模糊表述**：论文声称 PipeThreader 可与 FlashAttention-3 手工实现可比或更优，但具体数字（如快了 % 多少）未明确给出，读者难以判断实际提升幅度
2. **Tile size 与 Pipeline depth 的权衡**：论文提到这个权衡，但没有给出如何自动化决策的明确策略——搜索空间的边界在哪里？
3. **对融合 kernel 的依赖**：如果目标是编译未融合的 DNN 模型，PipeThreader 需要先经过融合阶段，其效果受融合质量影响
4. **AMD MI300X 数据缺失**：论文声称在 AMD MI300X 上也验证了方案，但具体数据几乎未展示，难以判断跨平台迁移的实际效果
