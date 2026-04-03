# GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs

**作者**：Yaoyu Wang, Xiao Guo, Junmin Xiao, De Chen, Guangming Tan（中国科学院计算技术研究所 SKLP / 中国科学院大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-yaoyu
**源文件**：[[atc2025-wang-yaoyu.pdf]]

---

## 一、背景

LLM 的参数规模快速增长，部署面临显存和推理延迟的双重压力。权重剪枝（weight pruning）是一种有效的压缩手段，能在保持精度的同时减少计算和存储开销，但剪枝后的矩阵乘法变为 Sparse Matrix Multiplication（SpMM），其在 GPU 上的高效实现成为推理加速的关键瓶颈。

LLM 推理中，QKV Projection、Output Projection、MLP1、MLP2 四个矩阵乘法占端到端执行时间约 80%。使用 magnitude 剪枝后，SpMM 仍占约 70% 的时间，存在较大的优化空间。

不同剪枝方法（structured / unstructured、magnitude / random）产生截然不同的稀疏模式（sparsity pattern），且 LLM 不同深度层的稀疏率也不同（底层和顶层约 70%，中间层约 90%），这使得单一优化策略无法适配所有场景。

---

## 二、要解决的问题

现有 GPU SpMM 方案在三个维度上存在不足：

1. **稀疏模式适配性差**：人工设计方法（ASpT、Sputnik、SparTA）各自针对特定稀疏模式优化，缺乏对多种剪枝方法产生的不同稀疏模式的通用适配能力。
2. **稀疏率适配性差**：不同深度层有不同稀疏率，需要不同的归约（reduction）算法才能高效执行。现有 auto-tuner（DgSPARSE、EC-SpMM）大多使用线程顺序归约，忽视了归约算法与稀疏率之间的交互关系。
3. **缺乏自动化代码生成**：现有方法依赖人工编写的预定义程序模板，编译器技术（TVM、AlphaSparse、TACO）要么不支持 SpMM、要么未针对 GPU 优化，缺少自动生成高性能 SpMM kernel 的能力。

---

## 三、洞察与设计

**关键洞察**：GPU 上 SpMM 的并行内存访问策略可以被抽象为「分盒子」（dividing box）的过程——将稀疏矩阵和稠密矩阵按 block/warp/thread 层级连续划分并集成；同时，不同稀疏率需要不同层级的归约算法组合（thread/warp/block），两者可以分别建模为 memory access space 和 reduction space，通过 cost model 在这两个空间中搜索最优组合。

基于此洞察，GeneralSparse 的设计分为四个部分：

### Memory Access Space

- **稀疏矩阵划分**：设计 row-based（single/multiple-row）和 split-based（row-nonsplit/split）两个正交维度，用 offset 抽象统一表示 thread/warp/block 级别的划分策略。
- **稠密矩阵划分**：按列均匀划分，列粒度可调，通过 thread-group 实现稀疏矩阵数据复用和稠密矩阵的 coalesced access。
- **格式调整**：包括 Sort（重排元素使访问更规则）、Pad（硬件对齐）、Interleaved storage（单次 coalesced 访问加载多个元素）、Vector instruction（向量化加载）。

### Reduction Space

- 设计 TOTAL 和 BITMAP 两类归约算法，分别对应 single-row 和 multiple-row 维度：
  - **TOTAL**：线程顺序归约，适合高稀疏率（每行非零元少），开销小。
  - **BITMAP**：用 bitmap 数据结构判断非零元素是否跨行，支持多行并行归约，适合低稀疏率（每行非零元多），实现更好的负载均衡。
- 提出 **SEGMENT** 算法处理 low-level BITMAP 产生的跨行中间结果。
- 三种算法可在 thread/warp/block 三个层级自由组合，通过 rule-based 策略根据 offset range 自动选择。

### Cost Model

- 线性回归模型，以稀疏矩阵特征（行数、列数、每行平均非零元等）为输入，拟合不同策略组合的执行时间，准确率约 90%。
- 离线遍历搜索（30-50 次迭代，10-30 秒），找到最优 memory access + reduction 组合。

### Code Generator

- 递归构造算法：从 block → warp → thread 递归分解 SpMM kernel 的多层并行结构。
- 代码优化器：识别 offset 的计算模式（Linear / Branch / Cyclicity / Quasilinear），用计算代替内存访问，减少 offset 读取开销。

---

## 四、实现细节

- 稀疏矩阵使用 CSR 格式存储。
- 支持 FP16/FP32 混合精度计算。
- 生成的 kernel 集成到 FasterTransformer 框架中，通过 C++ API 提供高效分布式推理。也可通过库调用方式集成到其他深度学习框架。
- 代码生成和编译时间：小矩阵几秒，大矩阵一两分钟；整个模型编译 Llama-7B 几分钟，Llama-65B 约十分钟。
- 离线搜索的最优策略可在 LLM 网络中复用，搜索开销相对于长时间运行的推理服务可忽略不计。
- 开源代码：https://github.com/Wangyaoyuu/GeneralSparse

---

## 五、实验结果

**平台**：NVIDIA Tesla A100（Ampere 架构），CUDA 12.1；额外在 V100 上验证。

### Kernel 级别性能（剪枝权重矩阵，OPT-30B/66B）

| 对比方法 | Batch=8 平均加速比 | Batch=32 平均加速比 | Batch=64 平均加速比 |
|---------|-----------------|------------------|------------------|
| cuSPARSE | 17.15× | 19.14× | 20.82× |
| Sputnik | 1.84× | 2.24× | 3.37× |
| SparTA | 1.57× | 1.37× | 1.27× |
| Flash-LLM | 1.30× | 1.31× | 1.38× |
| SparseTIR | 1.21× | 1.34× | 1.33× |

### SuiteSparse 矩阵集（1168 矩阵，FP32）

| 对比方法 | Col=8 平均加速比 | Col=32 平均加速比 | Col=64 平均加速比 |
|---------|---------------|----------------|----------------|
| cuSPARSE | 6.39× | 4.38× | 7.46× |
| Sputnik | 2.32× | 1.22× | 1.37× |
| DgSPARSE | 1.37× | 1.20× | 1.23× |
| TACO | 10.60× | 4.97× | 2.73× |

### 端到端模型推理（Magnitude 剪枝，70%/90% 混合稀疏率）

| 模型 | GPU 数 | Batch=8 vs Dense(cuBLAS) | Batch=32 vs Dense(cuBLAS) |
|------|--------|-------------------------|-------------------------|
| OPT-6.7B | 1 | 加速 | 加速 |
| OPT-13B | 1 | 加速 | 加速 |
| OPT-30B | 1 | 2.33× | OOM（Dense） |
| Llama-7B | 1 | 加速 | 加速 |
| Llama-13B | 1 | 加速 | 加速 |
| OPT-66B | 2 | 加速 | OOM（Dense） |
| Llama-65B | 2 | 加速 | OOM（Dense） |

- 端到端推理最高加速比达 2.33×（vs Dense cuBLAS）和 1.58×（vs Dense，batch=32）。
- 在 V100 上同样验证了性能优势：vs cuSPARSE 平均 16.08×，vs SparseTIR 平均 15.98×。
- 精度影响：OPT-30B 在 BoolIQ 上从 69.69% 降至 67.20%，OPT-60B 从 70.46% 降至 68.01%。

---

## 六、批判性分析

1. **Cost model 准确率仅约 90%，且存在系统性盲区**：论文承认在 SuiteSparse 上部分矩阵出现了性能下降（slowdown），归因于 cost model 的优化方向选择不当。线性回归模型可能无法捕捉复杂的非线性性能特征，但论文未深入分析失败案例的规律和改进方向。

2. **离线搜索成本被轻描淡写**：虽然单矩阵搜索 10-30 秒看似轻量，但 Llama-65B 的整体编译需要十余分钟。对于需要频繁更换剪枝策略或稀疏率的场景（如剪枝超参搜索），这个成本会快速累积。论文未讨论搜索结果在模型/硬件变化时的可迁移性。

3. **端到端评估的局限**：
   - 推理设置固定（input=64, output=512），未测试长序列或变长序列场景。
   - 仅使用 magnitude 剪枝做端到端评估，但 magnitude 是较旧的剪枝方法；未测试更先进的剪枝方法（如 SparseGPT、Wanda）。
   - 未报告 prefill 和 decode 阶段的分别加速比（仅在 OPT-66B 分析中提到 prefill 1.21×/1.45× 和 decode 1.52×/1.63×），缺乏系统性的阶段性分析。

4. **结构化剪枝场景的竞争力存疑**：Table 5 显示在 (8,8) 结构化剪枝粒度 + 70% 稀疏率下，GeneralSparse 不如 SparTA、Flash-LLM、TC-GNN、DTC-SpMM 等基于 Tensor Core 的方法。论文将此归因于「结构化剪枝较大且相对稠密时更适合 Tensor Core」，但这恰恰说明 GeneralSparse 的「通用性」在重要场景下并不成立。

5. **缺乏与 2:4 稀疏格式的对比**：NVIDIA Ampere/Hopper 架构原生支持 2:4 结构化稀疏，通过硬件加速可获得近 2× 吞吐提升。论文完全未讨论这一主流硬件稀疏加速方案，也未说明 GeneralSparse 在哪些场景下比 2:4 稀疏更有优势。

6. **精度评估过于简略**：仅在 BoolIQ 单个任务上报告了精度下降，缺乏在多个下游任务和更新模型上的精度验证。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

- **空间抽象 + 自动搜索**的方法论值得借鉴：将 SpMM 的优化策略分解为 memory access space 和 reduction space 两个正交空间，通过 cost model 驱动搜索，这种范式可推广到其他稀疏/不规则计算场景（如 MoE routing、sparse attention）。
- **Offset 计算模式识别**（Linear / Branch / Cyclicity / Quasilinear）是一个实用的代码生成优化技巧，可迁移到其他 GPU kernel 生成器中。

### 值得跟进的方向

1. **与现代剪枝方法结合**：SparseGPT、Wanda 等方法产生的稀疏模式与 magnitude/random 有显著差异，GeneralSparse 的 memory access space 是否能有效覆盖这些模式值得验证。
2. **动态稀疏场景**：当前方案是离线搜索 + 编译的静态方案。如果模型权重在线更新（如 LoRA 微调后重剪枝），能否降低重搜索/重编译成本？
3. **与硬件稀疏加速的协同**：如何在 2:4 稀疏硬件加速覆盖不到的场景（如非 50% 稀疏率、非规则结构）中定位 GeneralSparse 的价值？
4. **扩展到 Hopper/Blackwell 架构**：TMA（Tensor Memory Accelerator）和新的 warp group 抽象会改变 memory access space 的设计，需要重新适配。

### 最佳切入点

基于 GeneralSparse 的空间抽象思路，针对 MoE 模型中的稀疏 expert 计算（不同 expert 激活不同 token 数导致负载不均衡）设计类似的自适应 kernel 生成方案，是一个具有实际价值的延伸方向。

---

## 八、总结

GeneralSparse 提出了一种面向 GPU 的通用 SpMM 优化方案，通过将并行内存访问策略抽象为 memory access space、将归约策略抽象为 reduction space，结合 cost model 驱动的离线搜索和自动代码生成，实现了对多种剪枝模式和稀疏率的自适应处理。在剪枝 LLM 权重矩阵上相比 cuSPARSE 最高加速 20.82×，端到端推理最高加速 2.33×。主要局限在于结构化稀疏场景下竞争力不足、cost model 的鲁棒性有待提升、以及缺乏与硬件原生稀疏加速方案的系统比较。
