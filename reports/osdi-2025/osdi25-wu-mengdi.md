# Mirage: A Multi-Level Superoptimizer for Tensor Programs

## 论文基本信息

- **标题**: Mirage: A Multi-Level Superoptimizer for Tensor Programs
- **作者**: Mengdi Wu, Xinhao Cheng (CMU); Shengyu Liu, Chunan Shi (PKU); Jianan Ji, Man Kit Ao (CMU); Praveen Velliengiri (Penn State); Xupeng Miao (Purdue); Oded Padon (Weizmann); Zhihao Jia (CMU)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/wu-mengdi

## 研究背景与动机

深度神经网络（DNN）在 GPU 上的高性能执行对现代 ML 应用至关重要。当今的 DNN 框架通过张量程序指定 DNN 计算——有向无环图，节点为张量代数算子（如矩阵乘法），边为算子间共享的张量。

现有框架的优化方式存在根本性局限：
1. **基于规则的映射**: PyTorch、TensorFlow 使用手工设计的规则将张量程序映射到专家编写的 GPU kernel，需要大量工程努力且可能错失优化机会
2. **基于调度优化的框架（Halide/TVM/Ansor）**: 固定算法，只搜索调度空间，无法发现新的替代算法（如将卷积转换为矩阵乘法）
3. **基于代数变换的优化器（TASO/Grappler/Tensat/PET）**: 考虑代数等价变换，但需要程序员手工指定 kernel 集合（每个由张量函数定义），受限于提供 kernel 的性能

**根本问题**: 现有所有自动化方法都需要程序员手工指定一组 kernel，然后搜索代数或调度变换的空间。但最高效的优化（如 FlashAttention）需要同时在 kernel、thread block 和 thread 层级进行协调的变换，并在某些情况下引入全新的自定义 kernel——这类优化完全超出了现有方法的搜索空间。

## 要解决的核心问题

1. **跨 kernel、thread block、thread 三个 GPU 计算层级的联合优化缺失**: 现有方法只能在一个层级优化（如 TASO 只做 kernel 层级），无法发现需要跨层级协调的优化
2. **代数变换与调度变换的分离**: 现有方法将代数优化（改变算法）和调度优化（改变实现）分开处理，无法发现两者联合优化的机会
3. **自定义 kernel 的自动发现**: FlashAttention 等高效 kernel 需要将多个算子融合为新的自定义 kernel，完全超出了现有搜索空间
4. **大搜索空间的最优性保证**: 多层级优化使搜索空间急剧扩大，需要剪枝技术同时保证一定程度的全局最优性

## 主要贡献

1. **μGraph 表示法**: 首个在 kernel、thread block 和 thread 三个 GPU 计算层级上统一表示张量程序的层级图结构
2. **多层级超优化框架**: 利用 μGraph 发现跨层级的优化机会，结合代数变换、调度变换和自定义 kernel 生成
3. **基于抽象表达式的剪枝技术**: 显著减少候选 μGraph 数量，同时提供一定程度的全局最优性保证
4. **概率等价验证程序**: 利用 LAX fragment 特性，将有限域随机测试和多项式恒等测试（PIT）结合，提供任意精度的等价性保证
5. **自动发现 FlashAttention 及其变体**: 在 LLM 中广泛使用的 group-norm attention 场景下，自动发现了比现有方法快 3.3× 的优化 kernel

## 研究方法与设计

### μGraph 层级结构

μGraph 包含三个层级的图，每层对应 GPU 计算层次中的一个层级：

**Kernel 图**:
- 每个节点是一个 kernel（在全 GPU 上执行）
- 边是 kernel 间共享的张量（存储在 GPU 设备内存）
- 节点可以是预定义 kernel（如 cuDNN 卷积、cuBLAS 矩阵乘法）或图定义 kernel（由 lower-level 图指定）

**Block 图**:
- 每个节点是 block 算子（在单个 thread block 上执行）
- 边是 block 间共享的张量（存储在 GPU 共享内存）
- 每个 block 图关联 imap（输入分片映射）和 omap（输出拼接映射）指定 GPU 分块方式

**Thread 图**:
- 每个节点是 thread 算子（在单个 thread 上执行）
- 边是 thread 间共享的张量（存储在寄存器文件）
- 仅包含预定义 thread 算子（寄存器级别的元素操作）

**关键图属性**:
- `imap`: 将 grid 维度映射到输入张量维度（数据分区）或复制维度 φ（数据复制）
- `omap`: 将 grid 维度映射到输出张量维度（保证不同 block 输出不重叠）
- `fmap`: 将 for-loop 迭代映射到输入张量维度或复制维度

### RMSNorm 案例研究

**问题**: RMSNorm 后接矩阵乘法（MatMul）是 LLM 中的常见 pattern。现有系统需要分别运行两个 kernel，存储中间结果 Y 于设备内存。

**μGraph 发现的最优方案**:
1. **代数变换**: 利用矩阵乘法和逐元素除法的交换性重排序计算
2. **调度变换**: 将 RMSNorm 的累加和矩阵乘法的累加并行执行，避免写中间结果
3. **自定义 kernel**: 新增图定义 kernel，将两个算子融合进单个 kernel，减少设备内存访问和 kernel launch 开销

**实测性能**: 在 NVIDIA A100 上快 1.5×，H100 上快 1.9×。

### μGraph 生成器

#### LAX fragment 约束
- LAX（Linear Algebra with eXponential）fragment 是 Mirage 搜索空间的子集
- 包括多线性算子（矩阵乘法、卷积）、除法、有限指数（激活函数中常用）
- 限制 LAX fragment 使概率等价验证具有强理论保证

#### 表达式引导的生成
1. 计算 LAX 程序的抽象表达式
2. 按抽象表达式剪枝：具有相同抽象表达式的 μGraph 被剪枝
3. 逐层生成：Kernel 图 → Block 图 → Thread 图

#### 抽象表达式剪枝
- 定义抽象表达式：忽略具体张量形状、tile 维度的语义等价性
- 具有相同抽象表达式的 μGraph 产生相同的中间结果形状和算子类型
- 剪枝保证：在抽象表达式空间内的最优 μGraph 即为全局最优

### 概率等价验证器

**核心思想**: LAX fragment 上的随机测试具有强正确性保证。

**PIT 泛化**: 多项式恒等测试（PIT）算法（如Schwartz-Zippel）可泛化到 LAX 程序。

**具体机制**: 对 LAX 程序 P 和候选 μGraph Q：
1. 在有限域 $\mathbb{F}_p$ 上随机选择张量值
2. 执行 P 和 Q，比较输出
3. 重复多次，错误概率界为 $O(1/p)$

**LAX fragment 的关键性质**: LAX 程序是线性/多项式函数，随机测试在此 fragment 上具有类似 Schwartz-Zippel 的概率界。

### μGraph 优化器

对于每个验证后的 μGraph，评估其运行时性能：
- **Layout 优化**: 张量 layout 选择（影响内存访问模式）
- **调度规划**: tile 大小、共享内存使用、寄存器分配
- **内存分配**: 中间张量的放置（寄存器 vs 共享内存 vs 设备内存）

## 关键实现细节

### 搜索空间管理
- Kernel 和 Block 层：穷举搜索（受抽象剪枝约束）
- Thread 层：基于规则的搜索（thread 层级对性能影响较小）
- 仅关注 kernel 和 block 层的大幅性能差异

### 与现有系统的比较

| 维度 | TASO/PET | Ansor/TVM | FlashAttention | Mirage |
|------|---------|-----------|---------------|--------|
| 代数变换 | ✓ | ✗ | ✓ | ✓ |
| 调度变换 | ✗ | ✓ | ✓ | ✓ |
| 自定义 kernel | ✗ | ✗ | ✗ | ✓ |
| 多层级联合 | ✗ | ✗ | 部分 | ✓ |

## 实验结果与分析

### 测试平台
- NVIDIA A100（80GB SXM）和 H100（SXM3）
- 常用 DNN 基准测试

### 关键结果
- **LLM 中的 group-norm attention**: 在广泛使用和优化的 group-norm attention 上，Mirage 仍比当前方法快最高 3.3×
- **RMSNorm+MatMul fusion**: A100 上快 1.5×，H100 上快 1.9×
- **其他 DNN 基准**: 在各 DNN 基准上均有明显性能改善
- **发现的 μGraph 超出现有搜索空间**: 大部分发现的优化（如 FlashAttention 变体）完全不在现有方法搜索空间内

## 潜在问题与局限性

1. **LAX fragment 的覆盖范围**: 仅支持 LAX fragment（多线性算子 + 除法 + 有限指数），无法处理包含非线性操作（如某些激活函数）的复杂 DNN
2. **搜索时间**: 穷举搜索在大型 DNN 上可能耗时较长，论文未充分讨论搜索时间与优化收益的权衡
3. **与其他优化器的集成**: Mirage 作为独立的超优化器，与现有框架（如 PyTorch JIT、TVM）的集成方式未充分说明
4. **概率验证的残余错误率**: 虽然理论上可做到任意精度，但实际中 $O(1/p)$ 的错误概率在安全关键应用中可能不可接受
5. **GPU 架构适应**: μGraph 优化器针对特定 GPU 架构（如 A100、H100）生成代码，不同架构可能需要不同的 μGraph

## 未来工作方向

1. 扩展 LAX fragment 以支持更多算子
2. 与主流 DNN 框架的更紧密集成
3. 跨不同 GPU 架构的自适应优化

## 个人评注

### 优点
1. **开创性的多层级超优化概念**: μGraph 首次在统一的表示框架下融合了代数变换、调度变换和自定义 kernel 发现这三个原本分离的优化空间
2. **PIT 泛化的理论贡献**: 将有限域随机测试从多项式推广到 LAX fragment，并提供形式化的概率界，是重要的理论贡献
3. **对 FlashAttention 的自动化再发现**: 自动发现 FlashAttention 及其变体是令人印象深刻的验证——这说明 Mirage 的搜索空间确实包含了人类专家未能在通用框架中表达的优化知识
4. **抽象剪枝的理论洞见**: "具有相同抽象表达式的 μGraph 在全局最优搜索中等价"这一命题为大规模搜索空间的剪枝提供了坚实的理论基础

### 潜在问题
1. **"3.3× 性能提升"的具体场景**: 论文声称 Mirage 在广泛使用和优化的 group-norm attention 上比当前方法快 3.3×，但"当前方法"具体指什么？是在 TVM/Triton 中的实现还是手工优化版本？这一区别对评估绝对收益至关重要
2. **LAX fragment 的表达力边界**: 除法算子和"有限指数"（用于激活函数）的具体定义不够清晰。某些激活函数（如 GELU）的精确实现可能超出 LAX fragment 的表达能力
3. **等价验证的概率保证**: 论文声称"arbitrarily precise"的概率保证，但这依赖于随机种子选取的真正随机性。在实际系统中，PRNG 的质量可能影响实际的错误率。此外，未讨论是否存在对特定输入分布的系统性偏差
4. **"超出现有搜索空间"的广泛性**: 论文声称大部分发现的优化完全不在现有方法搜索空间内，但缺乏对"现有方法搜索空间"的精确定义。TASO 和 PET 各自支持的代数变换集合有多大，Mirage 发现的哪些具体变换超出了这些集合？
5. **抽象剪枝的最优性保证**: 论文声称抽象剪枝"provides a certain optimality guarantee"，但这个保证的精确形式（是否存在最优性损失的上界）未明确说明
