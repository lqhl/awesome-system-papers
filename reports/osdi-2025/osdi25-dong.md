# QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach

**作者**：Shouyang Dong (中国科学技术大学/寒武纪/中科院计算所), Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo (中科院计算所), Jianxing Xu, Ruibai Xu (中国科学技术大学/寒武纪/中科院计算所), Xinkai Song, Yifan Hao (中科院计算所), Ling Li (中科院软件所/中国科学院大学), Xuehai Zhou (中国科学技术大学), Tianshi Chen (寒武纪), Qi Guo (中科院计算所), Yunji Chen* (中科院计算所/中国科学院大学)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/dong
**源文件**：[osdi25-dong.pdf](../../papers/osdi-2025/osdi25-dong.pdf)

---

## 一、背景

异构深度学习系统（DLS）如 NVIDIA GPU、AMD MI、Intel DL Boost CPU、寒武纪 MLU 等已广泛部署于数据中心。这些平台各自采用不同的编程语言和模型（CUDA C、HIP、VNNI intrinsics、BANG C），具有独特的并行模型（SIMT vs SIMD）、复杂的内存层次结构（shared memory、NRAM/WRAM 等）和专用指令集。为充分利用各平台性能，开发者需要为每个平台分别编写高性能 tensor 程序，工作量巨大。理想状态是实现 tensor 程序的"Write Once, Run Anywhere"。

现有的跨平台代码转译技术分为三类：基于规则（人工定义转换规则，劳动密集）、符号合成（基于 SMT solver 搜索，可扩展性差）、数据驱动（基于 LLM 生成，功能正确性无法保证）。这三类方法在面对 DLS 复杂的架构和编程模型时均存在显著局限。

---

## 二、要解决的问题

1. **规则方法不可扩展**：不同 DLS 之间架构差异巨大，人工定义转换规则成本极高，且难以覆盖所有情况。
2. **符号合成搜索空间爆炸**：SMT solver 无法处理大规模通用程序，也难以处理不同的并行语义（如 SIMT vs SIMD），且需要人工精确定义输入约束。
3. **LLM 转译正确性不足**：即使使用 GPT-4，zero-shot 编译错误率达 100%；few-shot 下计算错误率仍高达 92.3%。LLM 在生成高层程序骨架方面能力强，但在循环边界、索引计算等底层细节上容易出错。
4. **性能优化困难**：单纯依赖 LLM prompts 或符号合成规范都难以指导性能优化，生成代码性能远落后于人工优化版本。

---

## 三、洞察与设计

**关键洞察**：LLM 擅长生成高层程序骨架（控制流、内存布局、intrinsics 选择），而符号合成擅长修复底层细节（循环边界、索引计算）——两者的优势恰好互补。将整个转译过程分解为一系列小步转换 pass，可以让 LLM 的错误被限制在小范围内，从而使 SMT solver 在有限规模上高效修复。

基于这一洞察，QiMeng-Xpiler 的设计包含两大部分：

### 1. Neural-Symbolic Program Synthesis

将转译分解为 11 个 transformation pass，分为三类：
- **Sequentialization/Parallelization**（6 个 pass）：LoopRecovery、LoopBind、LoopSplit、LoopFuse、LoopReorder、LoopExpansion/Contraction——处理并行变量与循环的相互转换
- **Memory Conversion**（2 个 pass）：Cache、Pipeline——桥接不同 DLS 的内存层次语义
- **(De)Tensorization**（2 个 pass）：Tensorize、Detensorize——在标量代码与 tensor intrinsics 之间转换

每个 pass 的工作流程：
1. **Program Annotation**：LLM 标注计算语义 + BM25 从编程手册检索参考信息
2. **Meta-Prompts based Transformation**：使用包含平台无关描述、平台特定示例、调优旋钮的 meta-prompt 驱动 LLM 生成转换代码
3. **Bug Localization**：通过二分搜索定位错误 buffer，再通过 CFG 分析区分索引错误和 tensor 指令错误
4. **SMT-based Code Repairing**：对索引错误用 Z3 求解约束，对 tensor 指令错误用 Tenspiler 合成

### 2. Hierarchical Performance Auto-Tuning

- **Intra-Pass Auto-Tuning**：暴力搜索每个 pass 的参数（如 tiling size、loop order）
- **Inter-Pass Auto-Tuning (MCTS)**：将转译建模为 Markov 决策过程，用 Monte Carlo Tree Search 探索最优 pass 序列。搜索深度 N=13，512 次模拟，带 early stopping。

---

## 四、实现细节

- 实现规模：约 35k 行 Python 代码
- 测试套件：约 38k 行 CUDA C、HIP、C with VNNI、BANG C kernel 代码，85.7% 来自 TVM 生成的 kernel，其余来自开源 GitHub 仓库
- LLM 后端：GPT-4
- 符号合成：Z3 SMT solver + Tenspiler
- 信息检索：BM25 搜索引擎，从目标平台编程手册中检索相关示例
- 扩展到新 DLS 的人工成本很低：指定并行变量和内存 scope 通常只需一行 prompt，扩展 Tenspiler 后端只需几行代码

评估的 21 个算子涵盖 MatMul、Convolution、Activation、Pooling、Element-wise、LLM operation（含 Deformable Attention、Self Attention、RMSNorm 等），每个算子 8 种 shape，共 168 个测试用例，代码规模 7-214 行。

---

## 五、实验结果

**实验平台**：Intel Gold 6348 CPU (VNNI)、NVIDIA A100 GPU (CUDA C)、AMD MI200 (HIP)、Cambricon MLU (BANG C)

### 准确率（12 个转译方向）

| 指标 | QiMeng-Xpiler | GPT-4 Few-Shot | OpenAI o1 Few-Shot |
|------|--------------|----------------|---------------------|
| 编译准确率 | 99.4%–100% | 35.1%–97.0% | 42.3%–98.8% |
| 计算准确率 | 86.9%–100% | 5.4%–97.0% | 7.7%–98.2% |

与规则方法对比：CUDA C → HIP 方向 QiMeng-Xpiler 100% vs HIPIFY 85.7%；C → CUDA C 方向 QiMeng-Xpiler 98.2% vs PPCG 47.6%。

### 执行性能

转译代码平均达到 vendor 手工优化库（cuDNN/cuBLAS、CNNL、oneDNN、rocBLAS）性能的 **0.78×**。

### FlashAttention 案例

FA1/FA2 在不同方向的转译性能为原生实现的 0.61×–0.81×。

### 编译时间

CUDA C → BANG C 方向，6 个典型算子编译时间 1.2–7.8 小时，平均 3.7 小时。

### 生产力提升

以 Deformable Attention（~200 LoC）为例：

| 角色 | CUDA C → BANG C | C with VNNI → CUDA C |
|------|----------------|---------------------|
| 高级工程师手写 | ~6 天 | ~1 天 |
| QiMeng-Xpiler | 4.5+0.5 小时（提升 **28.8×**） | 2.1 小时（提升 **11.4×**） |
| 初级工程师手写 | ~30 天 | ~3 天 |
| QiMeng-Xpiler | 4.5+3 小时（提升 **96.0×**） | 2.1 小时（提升 **34.3×**） |

---

## 六、批判性分析

1. **性能差距掩盖在平均值中**：0.78× 的平均性能看似不错，但论文未详细报告各算子各方向的具体性能数据分布。从 Figure 7 可以看出部分算子性能远低于平均值（如某些方向的 Deformable Attention），而 element-wise 等简单算子容易拉高整体均值。这个平均数可能给人过于乐观的印象。

2. **计算准确率的 86.9% 下限值得关注**：虽然论文强调"close to 100%"，但 HIP → BANG C 方向仅 86.9%，BANG C → C with VNNI 方向 95.2%。对于转译器这种需要 100% 正确性的工具，13% 的失败率在生产环境中仍然不可接受，用户仍需人工验证每个输出。

3. **编译时间成本较高**：平均 3.7 小时的转译时间（最高 7.8 小时）使得快速迭代变得困难。论文对此轻描淡写，但在实际开发流程中这是一个显著的工程障碍。

4. **测试用例规模有限**：最大 214 行代码，且 85.7% 来自 TVM 生成的规整 kernel。真实世界的高性能 tensor 程序往往更长、更复杂，包含更多条件分支和手工优化技巧。论文自身也在 failure case 中承认复杂控制流会导致失败。

5. **对 GPT-4 的强依赖**：系统的核心依赖 GPT-4 的代码生成能力，但论文未讨论 LLM 更新对系统稳定性的影响（如 API 变更、模型行为漂移），也未评估使用其他 LLM 的效果。

6. **生产力评估方法论薄弱**：仅用 2 名学生 + 2 名工程师在 1 个算子上做对比，样本量极小，且未说明如何控制变量（如工程师对目标平台的熟悉程度）。96× 的生产力提升数字虽然醒目，但统计意义存疑。

7. **寒武纪背景的潜在偏见**：作者团队多来自寒武纪和中科院计算所，BANG C 作为寒武纪的编程语言在评估中占据核心地位。虽然跨平台评估增加了可信度，但论文对 BANG C 相关结果的讨论明显更详尽，且该方向的实验（如 case study、failure analysis）占比最大。

---

## 七、AI Infra / MLSys 视角

1. **跨平台 kernel 移植的实用价值**：随着 AI 加速器生态碎片化加剧（NVIDIA、AMD、Intel、国产芯片），跨平台 tensor 程序移植是一个真实且紧迫的工程问题。QiMeng-Xpiler 的 neural-symbolic 范式为自动化移植提供了一个可行的框架方向。

2. **LLM + 形式化验证的协作模式**：论文提出的"LLM 生成骨架 + SMT solver 修复细节"的协作范式，不仅适用于代码转译，还可以迁移到以下 AI Infra 场景：
   - **自动 kernel 优化**：LLM 生成 schedule/tiling 方案，形式化方法验证正确性
   - **编译器 pass 生成**：LLM 生成优化 pass 的初始版本，符号方法修复 edge case
   - **硬件描述语言转译**：类似思路可用于不同加速器 RTL 之间的转换

3. **值得跟进的研究方向**：
   - **扩展到更大规模 kernel**：当前系统限于 ~200 行代码，如何处理 FlashAttention 级别的复杂 kernel（数千行、深度流水线）是关键挑战
   - **端到端框架集成**：将转译器集成到 PyTorch/TVM 等框架的编译管线中，实现从高层 IR 到多平台 kernel 的自动化
   - **降低编译时间**：探索轻量级 LLM 或本地模型替代 GPT-4，减少 API 调用开销
   - **支持更多硬件原语**：如 NVIDIA Hopper 的 TMA、AMD CDNA3 的新 matrix core 等

4. **最有价值的切入点**：将 neural-symbolic 范式应用于 TVM/Triton 等编译器的 auto-scheduling 环节——用 LLM 生成候选 schedule，用形式化方法验证等价性，用 auto-tuning 优化性能。这比完整的源到源转译更具实用性，因为输入输出更规整。

---

## 八、总结

QiMeng-Xpiler 提出了一种 neural-symbolic 方法来自动转译异构 DLS 上的 tensor 程序，核心思路是将转译分解为一系列 LLM 驱动的 transformation pass，辅以 SMT-based 符号合成修复和 MCTS-based 层次化 auto-tuning。在 4 个 DLS（Intel VNNI、NVIDIA GPU、AMD MI、Cambricon MLU）上的实验表明，系统平均转译准确率达 95%，性能达 vendor 优化库的 0.78×，编程效率提升可达 96×。主要局限在于对复杂控制流的处理能力不足、编译时间较长（平均 3.7 小时）、以及在部分转译方向上准确率仍未达到生产级要求（86.9%）。该工作为跨平台 tensor 程序自动移植开辟了一条可行路径，其 LLM 与形式化方法协作的范式对 AI 编译器和系统优化领域具有借鉴意义。
