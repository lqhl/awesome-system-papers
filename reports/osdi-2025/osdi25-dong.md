# QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach

## 论文基本信息

- **标题**: QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach
- **作者**: Shouyang Dong, Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo, Xinkai Song, Yifan Hao, Qi Guo, Yunji Chen（中科院计算所 + 中国科学技术大学 + 寒武纪）; Jianxing Xu, Ruibai Xu, Xuehai Zhou, Tianshi Chen, Ling Li（计算所 + 中科大 + 寒武纪）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/dong

---

## 研究背景与动机

### 异构深度学习系统的编程困境

现代数据中心部署了多种深度学习系统（DLS）：NVIDIA GPU（CUDA）、AMD MI（HIP）、Intel DLBoost（VNNI）、Cambricon MLU（BANG）等。充分利用这些系统需要为每个平台开发高性能张量程序（算子的底层实现），这极富挑战性，因为需要深入理解各平台的并行模型、内存层次和专用指令集。

### 现有跨平台编程方案的局限

**规则方案（Rule-based）**：
- 专家手动定义不同编程语言间的转换规则（如 CUDA-to-FPGA 翻译器 FCUDA）
- 问题：不同平台架构差异巨大，无法手动定义高效转换规则
- 可扩展性差

**符号合成方案（Symbolic Synthesis）**：
- 使用 SMT solver 从 DSL 或输入/输出示例生成语义保持的目标代码
- 问题：依赖大规模搜索的 SMT solver，难以扩展；且无法处理不同并行语义（如 CUDA SIMT vs BANG SIMD）

**LLM 方案（Data-driven）**：
- 使用 LLM（TransCoder、StarCoder、GPT-4）进行程序翻译
- 问题：张量程序语义无法完全保持，翻译准确率仅 29.6%，需要大量人工修正

### 核心洞察

LLM 和符号合成各有优势：
- **LLM**：擅长生成高层程序结构和代码框架
- **符号合成**：擅长验证和修复低层细节（如循环边界、索引计算）

两者结合——"神经-符号"（Neural-Symbolic）方法——可能是解决张量程序跨平台翻译的正确路径。

---

## 要解决的核心问题

如何自动将张量程序跨平台翻译（transcompile）到不同深度学习系统，同时保证语义正确性（通过 SMT solver 保证）和接近最优的性能（通过层次化自动调优）？

---

## 主要贡献

1. **神经-符号程序合成框架**：LLM 生成高层程序框架，SMT solver 修复低层细节，保证语义正确性
2. **11 个转换 pass**：覆盖三类转换——顺序化/并行化、内存转换、张量化/反张量化
3. **层次化性能自动调优**：intra-pass 自动调优（brute-force 搜索最优参数）和 inter-pass 自动调优（MCTS 搜索最优 pass 序列）
4. **4 个 DLS 平台验证**：Intel VNNI、NVIDIA CUDA、AMD HIP、Cambricon BANG，平均翻译准确率 95%
5. **编程效率提升**：NVIDIA GPU 和 MLU 分别提升 34.3 倍和 96.0 倍

---

## 研究方法与设计

### 总体架构

QiMeng-Xpiler 由两部分组成：

**1. 神经-符号程序合成**
- 将翻译过程分解为多个 LLM 辅助的转换 pass
- 每个 pass 内：LLM 生成代码 → 单元测试验证 → SMT solver 修复错误
- 11 个 pass 分为三类

**2. 层次化性能自动调优**
- Intra-pass 调优：brute-force 搜索每个 pass 的参数（如 tile sizes）
- Inter-pass 调优：MCTS 搜索最优 pass 序列

### 三类转换 Pass

#### (1) 顺序化/并行化 Pass

| Pass 名称 | 描述 |
|-----------|------|
| LoopRecovery | 将并行变量转换为顺序 for 循环 |
| LoopBind | 将顺序循环分配给并行变量 |
| LoopSplit | 将循环拆分为多个子循环 |
| LoopFuse | 将多个循环合并为超循环 |
| LoopReorder | 改变循环执行顺序 |
| LoopExpansion | 将循环体拆分为多个循环体 |
| LoopContraction | 将生产者合并到消费者的循环体中 |

#### (2) 内存转换 Pass

| Pass 名称 | 描述 |
|-----------|------|
| Cache | 适配内存层次结构，高效加载/存储输入输出 |
| Pipeline | 数据加载/存储与计算的流水线化 |

#### (3) 张量化/反张量化 Pass

| Pass 名称 | 描述 |
|-----------|------|
| Tensorize | 用专用张量指令替换特定循环体 |
| Detensorize | 从专用张量指令恢复原始循环体 |

### 神经-符号合成流程

每个 pass 的合成流程包含 4 个步骤：

#### 步骤 1：程序标注（Program Annotation）

利用 LLM 和 BM25 搜索识别程序中的计算操作和内存空间/intrinsics：
```
输入：源程序 P
输出：标注后的程序

1. Pd ← LLM(P)  // 语义标注（识别 matmul 等操作）
2. for each op in getIntraOps(Pd):
3.   D ← BM25_search(op, programming_manual)  // 检索对应 intrinsics
4. Pd ← LLM(Pd, D)  // 引用标注
5. return Pd
```

#### 步骤 2：Meta-Prompts 转换

使用 LLM 将标注后的程序转换为目标平台代码，分为三部分：
- **平台无关描述**：描述程序功能和必须遵守的约束
- **平台相关示例**：从目标平台编程手册检索相关实现示例
- **调优旋钮**：循环拆分对齐大小等参数（可选）

#### 步骤 3：Bug 定位（Bug Localization）

通过控制流图（CFG）分析定位错误代码块：
```
输入：源程序 S，翻译后程序 E
输出：错误代码块及错误类型

1. Sast ← BuildAST(S); East ← BuildAST(E)
2. BS ← ExtractBufferSequence(Sast); BE ← ExtractBufferSequence(East)
3. berr ← BinarySearch(BE)  // 找不匹配的 buffer
4. NE ← FindBufferAccessNodes(East, berr)  // 定位代码块
5. NS ← MatchControlFlowBlocks(Sast, NE)   // 对应源程序块
6. if CFG(NS) ≠ CFG(NE): error_type ← IndexError
7. elif HasTensorIntrinsic(NE): error_type ← TensorInstructionError
```

#### 步骤 4：SMT 修复（SMT-based Code Repairing）

对索引相关错误（如循环边界不正确），使用 SMT solver 求解正确值。

### 层次化性能自动调优

#### Intra-pass 自动调优

对每个 pass 的参数（如 tile sizes）使用 brute-force 搜索找最优配置。

#### Inter-pass 自动调优（MCTS）

使用蒙特卡洛树搜索（MCTS）自动发现最优的 pass 序列：
- **选择**：基于 UCB 分数选择候选节点
- **扩展**：应用可用 pass 之一生成新程序
- **模拟**：执行程序获取运行时间奖励
- **回传**：将奖励反向传播更新所有祖先节点的分数

---

## 关键实现细节

- **LLM**：使用 GPT-4 作为代码生成模型
- **SMT Solver**：Z3 solver 用于代码修复
- **编程手册**：各平台官方编程手册作为检索语料
- **单元测试**：每步转换使用单元测试验证正确性
- **性能基准**：与 cuDNN/cuBLAS（NVIDIA）、oneDNN（Intel）对比

---

## 实验结果与分析

### 翻译准确率

- **平均翻译准确率：95%**（跨 4 个 DLS：Intel VNNI、NVIDIA CUDA、AMD HIP、Cambricon BANG）
- Zero-shot GPT-4 编译错误率 100%（LLM 不理解 DLS 内存层次和专用 intrinsics）
- Few-shot GPT-4 计算错误率 92.3%（但编译成功）

### 错误分类

| 错误类型 | Zero-shot | Few-shot |
|----------|-----------|----------|
| 并行性相关 | 100% | 97.2% |
| 内存相关 | 100% | 76.5% |
| 指令相关 | 100% | 94.4% |

### 性能

- 翻译后程序的性能达到人工优化库的 **0.78 倍**（平均，vs. cuDNN/cuBLAS、oneDNN）
- 编程效率提升：**NVIDIA GPU 34.3 倍**、**Cambricon MLU 96.0 倍**

### 跨平台翻译示例

- CUDA C → BANG C（Cambricon MLU）：成功处理并行索引转换（blockIdx → clusterId）、内存空间映射（__global__ → __mlu_shared__）、intrinsics 转换（wmma → __bang_mlp）

---

## 潜在问题与局限性

1. **对 GPT-4 的依赖**：使用闭源 LLM（GPT-4）意味着系统行为依赖于 LLM 的能力和可用性，且可能涉及 API 成本和隐私问题
2. **性能差距（0.78× vs 人工优化库）**：仍有约 22% 的性能差距，表明自动翻译的性能尚无法完全匹配人工优化
3. **SMT solver 的可扩展性**：SMT-based 代码修复在有限规模下高效，但对极复杂的张量程序可能仍面临搜索空间爆炸问题
4. **单元测试的覆盖**：翻译正确性依赖单元测试的覆盖程度，覆盖不足可能导致 bug 未被发现
5. **平台支持的局限**：仅支持 4 个 DLS 平台，且需要针对每个平台准备编程手册作为检索语料

---

## 未来工作方向

- 替换为开源 LLM 以降低依赖
- 进一步提升翻译后程序性能（缩小与人工优化库的差距）
- 支持更多 DLS 平台（TPU、GraphCore IPU 等）
- 探索端到端神经网络编译（而非仅算子级翻译）

---

## 个人评注

### 优势

1. **神经-符号结合的方法论**：将 LLM 的代码生成能力和 SMT solver 的形式化验证能力结合，是解决张量程序翻译的正确路径——两者各司其职，避免了各自单独使用的局限
2. **错误分类的洞察**：将翻译错误分为并行性、内存、指令三类，为系统性解决翻译问题奠定了基础；揭示了 Zero-shot GPT-4 100% 编译失败的根本原因
3. **程序标注的价值**：利用 LLM 和 BM25 在编程手册中检索对应实现，是将领域知识注入 LLM 的有效手段——这比直接 prompting 更可靠
4. **MCTS 用于 pass 序列搜索**：将程序翻译的 pass 序列优化问题建模为 MCTS，是对该问题的优雅建模，比暴力搜索更高效

### 潜在问题

1. **GPT-4 的依赖性风险**：作为 OSDI 论文，使用闭源 GPT-4 API 意味着系统不可独立复现（需要 OpenAI API key），也意味着无法在本地 LLM（Llama 等）上验证方案的一般性
2. **"0.78× 性能"与"95% 准确率"的取舍**：平均 95% 翻译准确率意味着仍有约 5% 的程序需要人工介入，但性能达到人工优化库的 78% 说明大多数翻译结果是有用的——这是一个实用的权衡
3. **BM25 检索的质量**：程序标注依赖 BM25 在编程手册中检索相关内容。检索质量直接影响后续 LLM 转换的准确性，但论文未充分讨论检索失败的处理方式
4. **跨平台语义的完备性**：各平台的 SIMT/SIMD 并行模型差异巨大（如 CUDA 的 threadIdx vs MLU 的 clusterId/coreId），MCTS 能否在所有场景下找到正确且高效的转换路径仍有疑问
