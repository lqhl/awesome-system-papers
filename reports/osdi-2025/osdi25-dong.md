# QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach

**作者**：Shouyang Dong, Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo, Jianxing Xu, Ruibai Xu, Xinkai Song, Yifan Hao, Ling Li, Xuehai Zhou, Tianshi Chen, Qi Guo, Yunji Chen（中科大、寒武纪、中科院计算所、中科院软件所、中国科学院大学）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），Boston, MA, USA, July 7–9, 2025
**DOI**：https://www.usenix.org/conference/osdi25/presentation/dong
**源文件**：[osdi25-dong.pdf](../../papers/osdi-2025/osdi25-dong.pdf)

---

## 一、背景

深度学习对算力的需求持续飙升，推动了异构深度学习系统（DLS）的繁荣：NVIDIA GPU（CUDA C）、AMD MI（HIP）、Google TPU、Cambricon MLU（BANG C）、Intel DLBoost（VNNI 扩展）各自拥有截然不同的编程接口、并行模型、内存层次结构和专用指令集。

这种碎片化带来严重的软件工程负担：同一个矩阵乘法或注意力机制，需要为每个平台手写一份高度优化的 kernel，且优化策略之间几乎无法复用。理想目标是实现"Write Once, Run Anywhere"——能将某平台的 tensor 程序自动转译到其他平台，同时保证功能正确性和性能。

---

## 二、要解决的问题

现有转译方案均存在明显缺陷：

1. **规则化方法**（PPCG、HIPIFY、C2Rust）：依赖专家手工定义 AST 变换规则，移植代价高，遇到非规则控制流则束手无策。

2. **符号综合方法**（Tenspiler、MetaLift）：基于 SMT 求解器验证语义等价，但搜索空间爆炸，仅能处理小规模代码（DSL 子集），且无法处理不同 DLS 的并行语义（如 SIMT vs. SIMD）。

3. **数据驱动/LLM 方法**（GPT-4、OpenAI o1）：
   - Zero-shot：编译错误率接近 100%（内存层次和指令使用完全错误）
   - Few-shot：计算正确率仅约 7.7%（CUDA→BANG C），整体平均 92.3% 计算错误率
   - 根本原因：LLM 缺乏对 DLS 特有并行语义和专用指令参数约束的深层理解，单步生成无法保证正确性

---

## 三、核心设计

QiMeng-Xpiler 提出 **神经-符号程序综合**（Neural-Symbolic Program Synthesis）范式，将转译过程拆解为一系列 LLM 辅助的变换 pass，再用小规模 SMT 求解器修复错误代码片段。

### 3.1 核心洞察

- **LLM 擅长**：生成高层程序骨架（控制流、操作语义）
- **SMT 擅长**：验证和修复低层细节（循环边界、索引表达式）
- 两者互补：LLM 把问题规模压小，SMT 再精确修复

### 3.2 整体架构

系统分为两部分：

**（a）Neural-Symbolic Program Synthesis**

转译流程被分解为 11 个变换 pass，分属三类：

| 类别 | Pass |
|------|------|
| 顺序化/并行化 | LoopRecovery, LoopBind, LoopSplit, LoopFuse, LoopReorder, LoopExpansion, LoopContraction |
| 内存转换 | Cache, Pipeline |
| （去）Tensorization | Tensorize, Detensorize |

每个 pass 的工作流：
1. **程序标注（Program Annotation）**：LLM 识别计算操作语义，BM25 检索 DLS 编程手册获取目标操作和参数约束，注入后续 prompt
2. **Meta-Prompts 变换**：利用高层 prompt 模板（含平台无关描述、平台特定示例、调优旋钮）驱动 LLM 生成变换后代码
3. **Bug 定位**：单元测试验证正确性，失败时定位错误代码片段
4. **SMT 修复**：对错误片段生成 SMT 约束（图 5），由 Z3 求解器修复循环边界、索引等低层细节

**（b）Hierarchical Performance Auto-Tuning**

- **Intra-Pass 调优**：暴力搜索每个 pass 内的参数（如 tiling size、循环阶数），生成多个候选程序
- **Inter-Pass 调优（MCTS）**：用蒙特卡洛树搜索确定最优 pass 序列；奖励函数基于实际执行吞吐量；搜索深度 N=13，512 次模拟 + 早停

---

## 四、实现细节

- **代码规模**：约 35K 行 Python，覆盖 LLM 标注、变换 pass、编译验证框架、SMT 修复、MCTS 搜索、intra-pass 搜索等核心模块
- **测试集**：约 38K 行 kernel 代码（CUDA C / HIP / C with VNNI / BANG C），85.7% 来自 TVM 生成 kernel，其余来自开源 GitHub 仓库（如 Deformable Attention、Self Attention、RMSNorm）
- **平台移植成本**：平台无关 pass（LoopSplit/Fuse/Reorder 等）无需修改；平台特定 pass（LoopRecovery/Bind、Cache、Tensorize 等）需手动指定并行变量和内存 scope，通常只需新增一行 prompt；Tenspiler 后端扩展通常只需几行代码——属于一次性移植工作
- **LLM**：使用 GPT-4（gpt-4）；SMT 求解器：Z3；检索引擎：BM25

---

## 五、实验结果

**实验平台**：Intel Gold 6348（VNNI）、NVIDIA A100（CUDA C）、AMD MI200（HIP）、Cambricon MLU（BANG C）

**基准**：21 个常用深度学习算子（MatMul、Convolution、Activation、Pooling、Element-wise、LLM 操作），每个算子 8 种 shape，共 168 个测试用例

### 5.1 准确率

| 源语言 | 方法 | 编译准确率 | 计算准确率 |
|--------|------|-----------|-----------|
| CUDA C → BANG C | GPT-4 Few-Shot | 50.6% | 7.7% |
| CUDA C → BANG C | OpenAI o1 Few-Shot | 51.8% | 48.2% |
| CUDA C → BANG C | QiMeng-Xpiler w/o SMT | 82.7% | 54.2% |
| CUDA C → BANG C | **QiMeng-Xpiler** | **100%** | **91.7%** |
| CUDA C → HIP | **QiMeng-Xpiler** | **100%** | **100%** |
| C w/ VNNI → CUDA C | **QiMeng-Xpiler** | **100%** | **98.2%** |
| HIP → BANG C | **QiMeng-Xpiler** | **100%** | **86.9%** |
| C → CUDA C（vs PPCG） | PPCG | 47.6% | 47.6% |
| C → CUDA C（vs PPCG） | **QiMeng-Xpiler** | **100%** | **98.2%** |

四个方向平均计算准确率：**95%**

### 5.2 执行性能

QiMeng-Xpiler 生成的代码平均达到 vendor 手动优化库（cuDNN/cuBLAS、CNNL、rocBLAS、oneDNN）的 **0.78×** 性能，差距主要来自手工实现可以使用汇编级优化、多阶段 pipeline、积极 loop unroll 等 QiMeng-Xpiler 尚未覆盖的技巧。

### 5.3 编程效率提升

| 任务 | 开发者 | 手工时间 | QiMeng-Xpiler 时间 | 提升倍数 |
|------|--------|---------|-------------------|---------|
| Deformable Attention CUDA→BANG C | 高级工程师 | ~6 天 | 4.5h + 0.5h 调试 | ~28.8× |
| Deformable Attention CUDA→BANG C | 初级工程师 | ~30 天 | 4.5h + 3h 调试 | **~96.0×** |
| Deformable Attention C with VNNI→CUDA C | 初级工程师 | ~3 天 | 2.1h | **~34.3×** |

### 5.4 编译时间

单个算子（CUDA C→BANG C）编译时间 1.2–7.8 小时，平均 3.7 小时。复杂算子（如矩阵乘法）因搜索空间更大而偏长；SMT 仅在 LLM 失败时触发，对简单程序开销较小。

---

## 六、批判性分析

**1. 编译时间开销被低估**

每个算子平均 3.7 小时的编译时间在实际工程中难以接受。论文将其定位为"一次性移植工作"，但在大型深度学习框架中，算子数量通常是几百到上千个，总移植时间可能达到数千小时。论文未讨论这一扩展问题。

**2. 性能差距缺乏深入分析**

0.78× 的性能差距被简单归因于"手动优化使用了汇编/多阶段 pipeline"，但未提供具体的 profiling 数据说明差距来自哪个瓶颈（计算利用率、内存带宽、指令级并行等）。这让读者难以判断差距是否可以通过改进 auto-tuning 弥补。

**3. LLM 选择固化为 GPT-4 的隐患**

整个系统强依赖 GPT-4（商业 API），但 GPT-4 版本会随时间更新，行为可能改变，复现性存疑。论文也未讨论使用开源 LLM 的可行性。

**4. 失败案例分析过于简短**

论文承认 Deformable Attention（CUDA→BANG C）约 8.3% 计算错误来自复杂控制流，但仅给出一个示例（图 10）并表示"未来会用更先进的 LLM/SMT 解决"，缺乏量化分析：有多少 kernel 有类似复杂控制流？这是否代表实际大模型 kernel 的普遍情况？

**5. SMT 修复的可扩展性限制未充分讨论**

SMT 修复的"小规模"约束（保证 SMT 可求解）是整个系统正确性的核心保障，但论文未明确定义"小规模"的上界，也未说明当 LLM 生成的错误片段超出 SMT 能力时系统如何降级处理。

**6. 性能比较基线的公平性**

性能对比的基线是 PyTorch 调用 vendor 库（cuDNN 等），而非同等条件下由人工从零编写的优化 kernel。这是合理的工程对比，但意味着 0.78× 这个数字包含了 vendor 库本身多年积累的专家优化，其差距对普通用户来说其实并不显著。

---

## 七、AI Infra / MLSys 视角

**直接相关性**：本文针对 AI 系统中最核心的基础设施问题之一——跨平台 tensor kernel 移植，具有很强的 AI Infra 价值。

**可借鉴的技术思路**：

1. **分解-修复范式**：将大问题（跨平台代码生成）分解为多个语义明确的小任务（11 个变换 pass），每步 LLM 生成 + SMT 验证修复，这一范式对其他代码生成/优化场景（如 schedule 搜索、kernel fusion）均有参考价值。

2. **BM25 + 编程手册检索增强**：利用文档检索将平台专用 API 知识注入 prompt，而非依赖 LLM 预训练知识——这是一种务实且有效的领域知识注入方式，可用于其他面向小众硬件的代码生成任务。

3. **MCTS 用于 pass 序列搜索**：将编译优化 pass 的排列搜索建模为 MDP + MCTS，是 ML-for-systems 中一种值得关注的方向。相比 beam search 或随机搜索，MCTS 对稀疏奖励有更好的探索能力。

**值得跟进的研究方向**：

- **降低编译时间**：探索用 learned cost model 替代真实执行测量来加速 auto-tuning，类比 TVM/Ansor 中的 cost model 方法；或用 few-shot transfer 在新算子上复用已有 pass 序列。
- **开源 LLM 替代**：研究使用 Codestral、DeepSeek-Coder 等开源代码模型是否能达到相近准确率，同时减少对商业 API 的依赖。
- **与 ML 编译器集成**：将 QiMeng-Xpiler 集成进 TVM/Triton 生态，作为 backend code lowering 的自动化工具，覆盖 NVIDIA 以外平台。
- **复杂控制流的处理**：结合程序分析技术（如区间分析、值范围推断）辅助 LLM 和 SMT 处理带条件跳转的 kernel。

---

## 八、总结

QiMeng-Xpiler 是首个能自动将 tensor 程序跨异构深度学习系统（CUDA/HIP/BANG/VNNI）转译的系统，通过将 LLM 的高层生成能力与 SMT 求解器的精确修复能力相结合，在 4 个平台、21 个算子上达到平均 95% 计算正确率和 0.78× vendor 库性能，编程效率最高提升 96×。核心局限在于单算子数小时级别的编译时间、对 GPT-4 API 的强依赖，以及对复杂控制流 kernel 的支持不足；适用场景是企业级 DLS 平台移植（一次性批量迁移），而非频繁迭代的研发场景。
