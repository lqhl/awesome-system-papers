# Mirage: A Multi-Level Superoptimizer for Tensor Programs

**作者**：Mengdi Wu, Xinhao Cheng (Carnegie Mellon University); Shengyu Liu, Chunan Shi (Peking University); Jianan Ji, Man Kit Ao (Carnegie Mellon University); Praveen Velliengiri (Pennsylvania State University); Xupeng Miao (Purdue University); Oded Padon (Weizmann Institute of Science); Zhihao Jia (Carnegie Mellon University)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/wu-mengdi
**源文件**：[osdi25-wu-mengdi.pdf](../../papers/osdi-2025/osdi25-wu-mengdi.pdf)

---

## 一、背景

深度神经网络（DNN）在 GPU 上的高性能执行是现代 ML 应用的关键需求。当前的 DNN 框架使用 tensor program（有向无环图，节点为张量代数算子）来描述计算。现有的自动优化方法分为两类：(1) **schedule-based 优化**（如 Halide、TVM、Ansor、Triton），在固定算法下搜索最优的 GPU 执行策略；(2) **代数变换优化**（如 TASO、PET、Tensat），利用数学等价性在 kernel 级别替换算子。

然而，两类方法都要求程序员手动指定 kernel 集合，且只在单一层级（kernel 级或 schedule 级）进行优化。一些高级优化（如 FlashAttention）需要跨 kernel、thread block、thread 三个 GPU 计算层级协同进行代数变换、schedule 变换和新 kernel 生成，这些优化超出了现有自动化方法的搜索空间，只能靠专家手写实现。

---

## 二、要解决的问题

1. **现有方法搜索空间受限**：schedule-based 方法只搜 schedule 不改算法，代数变换方法只在 kernel 级做算子替换，两者互不兼容，无法发现需要跨层级联合优化的高性能实现。
2. **手写 kernel 工程量巨大**：像 FlashAttention 这样的优化需要 700+ 行 Triton 代码，且需要深度理解 GPU 内存层级，难以推广到新的 DNN 结构。
3. **搜索空间爆炸**：跨 kernel/block/thread 三个层级的超优化搜索空间远大于单层级方法，如何高效搜索是核心挑战。
4. **等价性验证困难**：优化后的程序可能涉及数百万个张量元素，如何高效验证其与原始程序的功能等价性是一个难题。

---

## 三、洞察与设计

**关键洞察**：GPU 计算层级（kernel、thread block、thread）的内存访问代价差异悬殊（device memory → shared memory → register file），真正有意义的性能优化往往需要在这三个层级之间协同进行代数变换和 schedule 变换，而这种协同优化可以用一种统一的层级图表示（µGraph）来捕获，使得自动搜索成为可能。

### µGraph 表示

Mirage 的核心抽象是 µGraph——一种层级化图表示，统一描述 kernel graph、block graph 和 thread graph 三个层级的计算：

- **Kernel graph**：节点为 kernel 算子，边为 device memory 中的张量。节点可以是预定义 kernel（如 cuBLAS MatMul）或 graph-defined kernel（由 block graph 定义语义）。
- **Block graph**：节点为 block 算子，边为 shared memory 中的张量。通过 grid dimensions（控制 thread block 数量）、imap/omap（控制输入输出张量的分区与拼接）、for-loop body（分块加载大张量到 shared memory）实现细粒度控制。
- **Thread graph**：节点为 thread 算子，边为 register file 中的张量。进一步减少 shared memory 访问。

### 搜索与剪枝

Mirage 采用混合策略：在 kernel 和 block 级别穷举搜索，在 thread 级别使用 rule-based 的算子融合。为应对搜索空间爆炸，引入 **abstract expression** 剪枝技术：

- 为每个张量定义抽象表达式（忽略元素间差异的一阶逻辑项）
- 使用 SMT solver（Z3）检查 µGraph 前缀的抽象表达式是否可能是目标程序抽象表达式的子表达式
- 不满足条件的前缀直接剪枝，Theorem 1 保证在一定条件下不会剪掉最优解

### 概率等价性验证

Mirage 限定优化目标为 LAX 程序（仅含多线性算子、除法、以及每条路径至多一次指数运算），利用有限域上的随机测试进行等价性验证：

- 在两个有限域 Z_p 和 Z_q 上对随机输入求值（Z_q 用于指数内部，Z_p 用于外部）
- 基于 Theorem 2（扩展了经典 PIT 算法到 LAX 程序），可将错误概率降到任意低
- 避免浮点误差问题，提供强理论保证

### µGraph 优化器

对验证通过的 µGraph，进一步优化：
- **Tensor layout**：用 ILP（Z3 求解）选择最优数据布局
- **Operator scheduling**：动态规划最小化 thread block 内同步次数
- **Memory planning**：穷举内存偏移分配策略

---

## 四、实现细节

- 总代码量约 30K 行（C++、CUDA、Python）
- Kernel 算子基于 cuDNN/cuBLAS，block/thread 算子基于 cuTLASS 和 CUDA PTX
- SMT/ILP 求解使用 Z3 4.12.6
- 支持 JIT 编译，生成的 CUDA kernel 可直接集成到 PyTorch 程序
- 概率等价性验证使用 p=227、q=113（乘积适配 16-bit 整数），在 GPU 上加速执行
- 搜索默认配置：kernel graph 最多 5 个算子，block graph 最多 11 个算子
- 支持 Table 1 中的算子集合（Matmul、Sum、EwAdd/Mul/Div、Exp、Sqrt、SiLU、Accum 等），可扩展新算子（需提供浮点实现、模运算实现、抽象表达式公理）

---

## 五、实验结果

**平台**：NVIDIA A100 (40GB) 和 H100 (40GB)

**Benchmark**：

| 名称 | 描述 | 基础架构 |
|------|------|----------|
| GQA | Group-query attention | LLaMA-3-70B |
| QKNorm | QK normalization + attention | Chameleon-7B |
| RMSNorm | RMS normalization + linear | LLaMA-2-7B |
| LoRA | Low-rank adaptation | GPT-3-7B-LoRA |
| GatedMLP | Gated multi-layer perceptron | Falcon-7B |
| nTrans | Normalized Transformer | nGPT-1B |

**基线**：PyTorch (torch.compile + FlashAttention)、TensorRT、TensorRT-LLM、FlashAttention、FlashDecoding、Triton、TASO/PET

**微基准结果（vs 最优基线）**：

| Benchmark | A100 加速比 | H100 加速比 |
|-----------|-----------|-----------|
| GQA | 1.2×–1.8× | 1.2×–2.2× |
| QKNorm | 0.9×–1.4× | 1.1×–1.4× |
| RMSNorm | 1.0×–1.4× | 1.2×–1.9× |
| LoRA | 1.1×–1.5× | 2.0×–2.4× |
| GatedMLP | 1.5× | 2.6×–3.3× |
| nTrans | 0.3× | 0.3×–0.4× |

**端到端推理结果**（PyTorch + Mirage kernels vs 原生 PyTorch）：
- Chameleon-7B: 1.4×–1.9× 加速
- LLaMA-3-8B: 1.0×–1.5× 加速
- GPT-3-7B-LoRA: 0.9×–1.2× 加速
- nGPT-1B: 1.4× 加速

**搜索时间**：
- RMSNorm（11 算子 block graph）：28 秒
- 去掉 abstract expression 剪枝：>10 小时（block graph 最多 6 个算子就超时）
- 最长优化时间：约 4 小时（一次性成本）

**消融实验**（GQA, BS=1, A100）：去掉 thread graph construction 降 5%，去掉 layout optimization 降 18%，去掉 operator scheduling 降 60%，去掉 memory planning 降 70%。

---

## 六、批判性分析

1. **nTrans 表现差**：Mirage 在 nTrans 上比 TensorRT 慢 2-3 倍。论文解释为 "shared memory 中转开销在轻量计算中占主导"，但这暴露了 µGraph 设计中强制所有中间张量经 shared memory 的架构决策的局限性。虽然论文提到 "计划支持 bypass shared memory"，但当前系统实际上无法处理这类场景。

2. **LAX 片段限制较严**：概率等价性验证仅支持 LAX 程序（多线性 + 除法 + 受限指数运算），不支持 ReLU 等常见非线性激活。论文提到了 solver-based verifier 作为替代方案，但将其细节置于 "scope 之外"，回避了这一重要局限。

3. **搜索时间与可扩展性**：虽然单次搜索最多 4 小时，但论文未讨论当 DNN 模块变得更复杂（更多算子、更深的 block graph）时搜索时间的增长趋势。Abstract expression 剪枝的效果高度依赖于公理集 A_eq 的选择，而论文承认当前的 A_eq 不包含消去律（如 div(mul(x,y),y)=x），可能遗漏一些最优解。

4. **评估粒度**：所有 benchmark 都是相对小规模的子模块（attention、normalization + linear 等），而非完整的 Transformer 层或更大的计算图。论文未探讨 Mirage 在处理更大子图时的效果和搜索空间增长。

5. **数值精度问题被轻描淡写**：论文提到用浮点测试过滤数值误差大的 µGraph，但未详细说明过滤标准、被过滤掉的比例，以及在 FP16 下累积误差的影响。

6. **概率验证的实践妥协**：理论上需要 Ω(k²·ln(1/δ)/ln(q)) 次重复测试来达到误差阈值 δ，但实际实现只做了单次测试（"a single random test without iterating it"），完全依赖 "实践中未观察到 false positive" 这一经验性声明，与论文强调的 "strong theoretical guarantees" 存在矛盾。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

1. **统一表示的力量**：µGraph 将代数变换和 schedule 变换统一在同一搜索空间中，这一思路可推广到其他 AI Infra 优化场景（如分布式并行策略搜索、通信-计算 overlap 优化）。目前分布式训练中的并行策略（TP/PP/DP/SP）也面临类似的多层级联合优化问题。

2. **抽象表达式剪枝**：基于 SMT solver 的搜索空间剪枝技术可迁移到其他编译优化场景，如自动算子融合、内存优化策略搜索等。

3. **有限域验证**：将 PIT 扩展到 LAX 程序的技术可用于其他需要程序等价性验证的场景，如编译器正确性验证、自动微分正确性检查。

### 可跟进的方向

1. **扩展到分布式场景**：当前 Mirage 只优化单 GPU 上的 tensor program。将 µGraph 扩展到多 GPU 场景，将 device 间通信（AllReduce、AllGather 等）纳入搜索空间，有望自动发现如 Tensor Parallelism + kernel fusion 的联合优化。

2. **突破 LAX 限制**：支持更多非线性算子（ReLU、GELU、Softmax 中的 max 等），需要发展新的等价性验证技术，这是扩大 Mirage 适用范围的关键。

3. **训练场景适配**：当前 benchmark 聚焦推理。将 Mirage 应用于训练（前向 + 反向 + 梯度更新），尤其是与混合精度训练、activation checkpointing 的结合，是一个有价值的方向。

4. **与 LLM 推理系统集成**：将 Mirage 自动生成的 kernel 集成到 vLLM、TensorRT-LLM 等推理框架中，针对不同 batch size、sequence length 动态选择最优 µGraph。

### 最有价值的切入点

将 Mirage 的多层级超优化思路与**长序列 attention 变体**（如 sparse attention、linear attention、sliding window attention）结合。这些变体目前缺乏像 FlashAttention 那样的高度优化 kernel，而 Mirage 已经证明可以自动发现 FlashAttention 级别的优化，因此很可能为新型 attention 机制自动生成高性能实现。

---

## 八、总结

Mirage 是首个多层级 tensor program 超优化器，通过 µGraph 统一表示 GPU kernel/block/thread 三个层级的计算，结合 abstract expression 剪枝和有限域概率等价性验证，能够自动发现需要跨层级协同优化的高性能实现。在 A100/H100 上，Mirage 对多个常用 DNN 模块实现了最高 3.3× 的加速，甚至超越了 FlashAttention 等手写优化 kernel。主要局限在于仅支持 LAX 程序片段、轻量计算场景下的 shared memory 开销、以及搜索空间在更复杂计算图上的可扩展性。
