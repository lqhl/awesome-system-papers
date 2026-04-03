# Voltrix: Sparse Matrix-Matrix Multiplication on Tensor Cores with Asynchronous and Balanced Kernel Optimization

**作者**：Yaqi Xia, Weihu Wang (Wuhan University), Donglin Yang (NVIDIA Corporation), Xiaobo Zhou (University of Macau), Dazhao Cheng (Wuhan University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/xia
**源文件**：[[atc2025-xia.pdf]]

---

## 一、背景

稀疏矩阵-稠密矩阵乘法（SpMM）是科学计算和机器学习中的核心操作，尤其在图神经网络（GNN）训练中，SpMM 占总计算成本的 80% 以上。NVIDIA GPU 从 Volta 架构起引入了 Tensor Core，其计算吞吐量远超传统 CUDA Core（如 H100 上 TF32 可达 495 TFLOPS vs CUDA Core FP32 的 67 TFLOPS）。然而，Tensor Core 专为稠密矩阵乘设计，面对 SpMM 中稀疏矩阵的不规则内存访问和数据稀疏性，难以直接高效利用。

现有工作如 TC-GNN 首次将稀疏矩阵压缩为 TCU block 映射到 Tensor Core，但数据加载效率极低；DTC-SpMM 尝试用异步加载流水线优化，但受限于指令粒度和单层流水线设计，改善有限。

---

## 二、要解决的问题

1. **数据加载瓶颈（Tensor Core 饥饿）**：在 TC-GNN 中，数据加载占 kernel 执行时间的 80% 以上，其中加载 DenseB 矩阵占 60% 以上。DTC-SpMM 的 LDGSTS 异步加载指令每次仅处理 16 字节，面对高维稠密矩阵（如 GNN 中 D > 256）需大量指令，且单层 warp 内流水线重叠度极低，同步开销进一步削弱收益。

2. **工作负载不均衡**：稀疏矩阵每行非零元素数量差异巨大，导致不同 SM 之间负载不均。TC-GNN 按 RowWindow 分配 CTA 实现输出均衡，但输入严重不均；DTC-SpMM 按固定 TCU block 数分配实现输入均衡，但输出不均且需 atomic 操作保证正确性，引入额外开销。两者均未同时实现输入输出的 co-balance。

---

## 三、洞察与设计

**关键洞察**：SpMM 在 Tensor Core 上的核心瓶颈不在计算本身，而在数据搬运——数据加载速度与 Tensor Core 计算速度之间存在巨大鸿沟。只要能充分重叠数据加载与计算，并同时在输入和输出两个维度上实现负载均衡（而非只关注其中一个），就能真正释放 Tensor Core 的算力。

基于此洞察，Voltrix-SpMM 提出两大创新：

### 创新一：Warp 级异步流水线

**BMat 压缩格式**：将 16×8 的 SparseA 矩阵用 bit-wise 压缩为 128-bit（4 个 Uint32），通过单条向量化指令 LDGSTS.128 完成加载。采用 row+column 混合 tiling 策略，使每个线程通过 thread ID 移位操作完成解码，且避免 shared memory bank conflict。对于非二值 SparseA，额外存储一个 value vector，通过 bitwise-and + __popc() 计算偏移量。

**Warp-Specialized Producer-Consumer 模型**：CTA 内的 warp 分为 Producer 和 Consumer。Producer warp 负责从 global memory 加载数据到 shared memory：SparseA 通过 INT4 向量化指令加载 BMat，DenseB 通过 TMA 批量异步指令加载（仅需单个 warp 8 个线程发起指令）。Consumer warp 从 shared memory 取数据送入 Tensor Core 执行 MMA（m16n8k8）。两者通过 MBarrier 信号机制实现 ping-pong 调度。

**多层流水线**：Consumer 同时处理多个 MMA 操作（Multiple MMA），配合多个 shared memory buffer（Multiple Buffer），实现多层级精细流水线。Producer 可同时为多个 buffer 发起数据拷贝，Consumer 在一个 buffer 计算完成后立即切换到另一个已就绪的 buffer，大幅提升带宽利用率和重叠度。

### 创新二：Persistent & I/O Co-Balanced Kernel

**SM-Aligned 设计**：将 CTA 数量固定为 SM 数量（H100 上 114 个），每个 CTA 常驻一个 SM 持续执行直到所有任务完成，避免频繁启动/终止 CTA 的 prologue/epilogue 开销。

**Input-Output Co-Balance**：将结果矩阵展开为 1D 向量，总任务量 = RowWindow 行数 × 结果维度。在 M 个 SM 间选择 M-1 个分割点，输入侧以 RowWindow 粒度分割保持数据连续性（消除 atomic 操作需求），输出侧以稠密矩阵维度为细粒度分割实现输出均衡。Scheduler 运行时动态追踪每个 CTA 的进度和 RowWindow 边界。

**贪心+启发式分割算法**：基于线性代价模型 C_all = Σ Num_SPA(i)·cf1·D + R_W·cf2·D + cf3，用贪心逐步推进分割点，靠近 RowWindow 边界时自动对齐以减少跨边界开销，最后用遗传算法微调全局最优。

---

## 四、实现细节

- 纯 CUDA 实现，约 5000 行代码，无第三方依赖
- 大量使用 C++ 模板元编程适配多层流水线配置，最小化 kernel 运行时开销
- 使用 inline PTX 指令调用 Hopper GPU 硬件特性：MMA、TMA、MBarrier
- 集成到 PyTorch 2.5，支持 Python 和 C++ 调用，接受 CSR 和 COO 格式
- 基于 CUDA 12.6 实现
- 多层流水线的最优配置（MMA 数量、buffer 数量）仅依赖稠密矩阵维度，通过预测试确定
- 代价模型用线性回归拟合三个系数 α1, α2, α3，R² = 0.92
- 开源地址：github.com/YaqiXia/Voltrix-SpMM

---

## 五、实验结果

**平台**：NVIDIA H100 PCIe GPU（456 Tensor Core，14592 CUDA Core，80GB 显存）

**数据集**：12 个真实图数据集（分 Type I 平均行长 < 20 和 Type II 平均行长 ~500）+ SuiteSparse 稀疏矩阵集合。稠密矩阵维度设为 256、512、1024。

| 对比方法 | 平均加速比 | 说明 |
|---------|-----------|------|
| vs TC-GNN | 36.5× | Tensor Core 基线 |
| vs DTC-SpMM | 1.8× | Tensor Core 基线 |
| vs RoDe | 1.7× (图数据集 1.9×) | CUDA Core SOTA |
| vs cuSPARSE | 2.7× (图数据集) / 2.5× (SuiteSparse) | NVIDIA 官方库 |
| vs DGL (端到端 GNN) | 2.0× | GNN 训练框架 |

**关键发现**：

- Voltrix-SpMM 是首个在 SpMM 任务上全面超越 CUDA Core 方法的 Tensor Core 实现（DTC-SpMM 和 TC-GNN 分别落后 RoDe 11% 和 70%）
- 随稠密矩阵维度增大，加速效果更显著（256→512→1024 对 cuSPARSE 加速比 2.4×→2.8×→3.0×）
- 流水线重叠率在 256 维和 512 维分别达 85% 和 97%
- 在数据分布不均匀性增大时（方差 0→192），Voltrix-SpMM 性能仅下降 4%，而 TC-GNN 下降 47%

**组件贡献拆解**（以 TC-GNN 为基线，D=256）：

| 组件 | 增量效果 |
|------|---------|
| 单层流水线（TMA） | 平均下降 32.6%（TMA 延迟高，单层重叠不足） |
| +BMat 压缩格式 | 平均 77× 加速（消除 SparseA 加载瓶颈） |
| +多层流水线 | 平均 2.1× 加速 |
| +Balanced Kernel | 最高 1.3× 加速（对不均匀数据集如 Reddit 效果显著） |

---

## 六、批判性分析

1. **BMat 77× 加速数字的误导性**：组件拆解中 BMat 带来的 77× 平均加速（Reddit 上 384×）数字极端巨大，但这实际上反映的是基线 TC-GNN 在 SparseA 处理上的极度低效，而非 BMat 本身的独立贡献。在叠加前一步（单层 TMA 流水线）后性能甚至下降了 32.6%，说明此处的加速主要来自消除了前一步引入的退化。组件拆解的基线选择和叠加顺序使每个组件的独立贡献难以准确评估。

2. **实验平台单一**：所有实验仅在 H100 PCIe 上进行，而 Voltrix-SpMM 大量使用 Hopper 特有指令（TMA、WGMMA、MBarrier），在 Ampere/Ada 等其他架构上完全无法运行。论文标题和摘要中的 "Tensor Cores" 表述具有一定泛化暗示，但实际上是 Hopper-specific 的设计。

3. **GNN 端到端评测过于简单**：仅测试了 2 层 GCN（hidden dim=256），这是最简单的 GNN 模型之一。对于更深、更复杂的模型（GAT、GraphSAGE、GIN）以及更多层数的场景，SpMM 在总计算中的占比会变化，端到端收益可能显著不同。

4. **与 cuSPARSE 的比较不完全公平**：cuSPARSE 是通用库，未针对特定稀疏模式优化，且部分 CUDA Core 方法（Sputnik、RoDe）在某些数据集上会因 shared memory 限制出现 CUDA error，而 Voltrix-SpMM 不会——这使得比较中 Voltrix-SpMM 在某些场景下的优势被放大。

5. **代价模型验证不充分**：R² = 0.92 看起来不错，但训练集和测试集的划分方式（随机 80/20）未详细说明是否考虑了数据集间的分布差异。对于具有极端不均匀分布的真实数据集，线性代价模型的适用性存疑。

6. **Balanced partitioning 的启动开销未讨论**：贪心+遗传算法搜索最优分割点的计算在 CPU 端执行，对于动态变化的稀疏模式（如 dynamic GNN），每次 SpMM 调用前都需重新搜索，这部分开销未被评估。

---

## 七、AI Infra / MLSys 视角

**启发价值**：

1. **Warp Specialization 的稀疏计算应用**：Voltrix-SpMM 将 GEMM 领域成熟的 warp-specialized producer-consumer 模式（如 CUTLASS、FlashAttention-3）成功移植到 SpMM，证明了该范式在不规则计算中的可行性。这一思路可推广到其他 AI Infra 中的稀疏/不规则操作，如 MoE gating、sparse attention、embedding lookup 等。

2. **Bit-wise 压缩格式的设计方法论**：BMat 格式同时优化加载效率（向量化）和转换效率（无 bank conflict），这种"压缩即计算友好"的设计理念值得在 AI 系统中推广，如稀疏模型权重的存储格式设计。

**可迁移的技术点**：

- TMA 批量异步加载 + MBarrier 协调的流水线模式可用于优化 LLM 推理中的 KV cache 加载、MoE 的 expert 数据搬运
- I/O co-balance 的分割策略可启发分布式训练中的 workload partitioning（如 pipeline parallelism 的 stage 划分）

**值得跟进的方向**：

- **结构化稀疏 + Tensor Core 的协同优化**：Voltrix-SpMM 处理的是非结构化稀疏，若结合 NVIDIA 的 2:4 结构化稀疏，可能进一步提升效率
- **动态稀疏模式下的自适应流水线**：当前最优配置依赖预测试，如何在 runtime 自适应调整是实际部署中的关键问题
- **多 GPU 扩展**：论文仅涉及单 GPU，大规模 GNN 训练中 SpMM 与通信的重叠优化是自然的延伸方向

---

## 八、总结

Voltrix-SpMM 通过三项关键创新——BMat bit-wise 压缩格式、warp-specialized producer-consumer 多层流水线、SM-aligned persistent & I/O co-balanced kernel——首次在非结构化 SpMM 任务上全面释放了 Tensor Core 的计算潜力，超越了所有现有 CUDA Core 和 Tensor Core 方法。系统在 H100 上实现了对 DTC-SpMM 1.8×、RoDe 1.7×、端到端 GNN 训练 2.0× 的加速。主要局限在于强依赖 Hopper 架构特性、GNN 端到端评测场景单一，以及负载均衡搜索的动态开销未充分评估。
